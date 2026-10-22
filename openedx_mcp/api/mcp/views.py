"""LMS read-only tool endpoints + whoami. All require staff/superuser (except
the unauthenticated health probe)."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ...models import MCPAuditLog
from ...native import analytics as na
from ...native import roles as nr
from ...native import users as nu
from .auth import get_key, granted_scopes
from .base import MCPView, int_param


class HealthView(APIView):
    """Unauthenticated liveness probe. No DB, no platform calls — just confirms
    the facade is up. Used by container/k8s probes."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok", "service": "openedx-mcp"})


class WhoAmIView(MCPView):
    def get(self, request):
        key = get_key(request)
        return Response({
            "user": request.user.username,
            "is_staff": request.user.is_staff,
            "is_superuser": request.user.is_superuser,
            "auth": "mcp_key" if key else "jwt_or_session",
            "key_name": key.name if key else None,
            "scopes": sorted(granted_scopes(request)),
        })


class AnalyticsOverviewView(MCPView):
    def get(self, request):
        return Response(na.analytics_overview(org=request.query_params.get("org")))


class CoursesView(MCPView):
    def get(self, request):
        return Response(na.list_courses(
            org=request.query_params.get("org"),
            limit=int_param(request, "limit", 100),
            offset=int_param(request, "offset", 0),
        ))


class CourseDetailView(MCPView):
    def get(self, request, course_id):
        detail = na.course_detail(course_id)
        if detail is None:
            return Response({"error": "No such course."}, status=404)
        return Response(detail)


class UsersView(MCPView):
    def get(self, request):
        is_staff = request.query_params.get("is_staff")
        return Response(nu.list_users(
            query=request.query_params.get("q", ""),
            is_staff=None if is_staff is None else is_staff.lower() == "true",
            limit=int_param(request, "limit", 50),
            offset=int_param(request, "offset", 0),
        ))


class UserRolesView(MCPView):
    def get(self, request, username):
        return Response(nr.list_user_roles(username))


class CourseTeamView(MCPView):
    def get(self, request, course_id):
        return Response(nr.list_course_team(course_id))


class UserGradeView(MCPView):
    def get(self, request, username, course_id):
        return Response(na.user_course_grade(username, course_id))


class AuditLogView(MCPView):
    """Recent MCP write-tool audit rows, newest first. Superusers see every key's
    rows; staff see only rows for their own account."""
    def get(self, request):
        qs = MCPAuditLog.objects.select_related("key", "user")
        if not request.user.is_superuser:
            qs = qs.filter(user=request.user)
        for field in ("tool", "outcome"):
            value = request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        limit = min(int_param(request, "limit", 50), 200)
        offset = int_param(request, "offset", 0)
        total = qs.count()
        rows = [{
            "at": r.created_at.isoformat(), "tool": r.tool, "outcome": r.outcome,
            "user": r.user.username if r.user else None,
            "key": r.key.name if r.key else None,
            "affected": r.affected_count, "request": r.request_summary,
            "error": r.error or None,
        } for r in qs[offset:offset + limit]]
        return Response({"total": total, "limit": limit, "offset": offset, "rows": rows})
