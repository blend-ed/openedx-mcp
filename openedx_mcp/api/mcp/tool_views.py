"""LMS write tool endpoints — enrollment, users, roles, access. All rails via
audited_write: scope check, rate limit, dry-run/confirm-token, audit."""
from rest_framework.response import Response

from ...models import Scope
from ...native import enrollment as ne
from ...native import roles as nr
from ...native import users as nu
from .auth import require_scopes
from .base import MCPView
from .guards import audited_write

# Levels that toggle platform-wide admin — gated by grant:admin, not write:roles.
_ADMIN_LEVELS = {"global_staff", "superuser"}


class EnrollUserView(MCPView):
    @audited_write("enroll_user", scope=Scope.WRITE_ENROLLMENT, require_confirm=False)
    def post(self, request, confirmed=True):
        d = request.data
        result = ne.enroll(d["username"], d["course_id"], mode=d.get("mode", "audit"))
        return Response(result), 1


class UnenrollUserView(MCPView):
    """Confirm-gated: unenrolling can drop a learner's access mid-course."""
    @audited_write("unenroll_user", scope=Scope.WRITE_ENROLLMENT, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        username, course_id = d["username"], d["course_id"]
        if not confirmed:
            current = ne.get_enrollment(username, course_id)
            if not current or not current.get("is_active"):
                return Response({"error": f"{username} is not actively enrolled in {course_id}."},
                                status=404)
            return Response({"would_unenroll": username, "course_id": course_id,
                             "current_mode": current.get("mode")})
        return Response(ne.unenroll(username, course_id)), 1


class BulkEnrollView(MCPView):
    """Enroll or unenroll many by email. action=unenroll also withdraws pending
    invites (emails with no account yet)."""
    @audited_write("bulk_enroll", scope=Scope.WRITE_ENROLLMENT, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        entries = d.get("entries", [])
        action = d.get("action", "enroll")
        if action not in ("enroll", "unenroll"):
            return Response({"error": "action must be 'enroll' or 'unenroll'."}, status=400)
        if not confirmed:
            # Real audience preview: what happens to each address, with samples.
            preview = ne.preview_bulk_enroll(d["course_id"], entries, action=action)
            if action == "enroll":
                preview["mode"] = d.get("mode", "audit")
            return Response(preview)
        if action == "unenroll":
            return Response(ne.bulk_unenroll(d["course_id"], entries)), len(entries)
        result = ne.bulk_enroll(d["course_id"], entries, mode=d.get("mode", "audit"),
                                auto_enroll=d.get("auto_enroll", True))
        return Response(result), len(entries)


class CreateUserView(MCPView):
    @audited_write("create_user", scope=Scope.WRITE_USERS, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        if not confirmed:
            conflicts = nu.account_conflicts(d["email"], d["username"])
            if conflicts:
                return Response({"error": "Already taken: " + ", ".join(conflicts) + ".",
                                 "conflicts": conflicts}, status=409)
            return Response({"would_create": {
                "email": d["email"], "username": d["username"],
                "name": d.get("name") or d["username"], "is_active": False,
                "send_activation_email": bool(d.get("send_activation_email", False))}})
        result = nu.create_user(d["email"], d["username"], name=d.get("name", ""),
                                send_activation_email=d.get("send_activation_email", False))
        return Response(result), 1


class SetRoleView(MCPView):
    """Grant/revoke a course or global role. action ∈ grant|revoke; also handles
    global staff / superuser flags. Course roles need write:roles; global_staff/
    superuser additionally need grant:admin."""
    @audited_write("set_role", scope=Scope.WRITE_ROLES, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        action, level = d["action"], d["level"]
        user = d["username"]
        if level in _ADMIN_LEVELS:
            require_scopes(request, Scope.GRANT_ADMIN)  # escalation gate
        if not confirmed:
            return Response({"would": action, "level": level, "user": user,
                             "course_id": d.get("course_id")})
        if level == "global_staff":
            return Response(nu.set_global_staff(user, action == "grant")), 1
        if level == "superuser":
            return Response(nu.set_superuser(user, action == "grant")), 1
        # course-scoped role
        fn = nr.grant_course_role if action == "grant" else nr.revoke_course_role
        return Response(fn(user, level, d["course_id"])), 1


class InstructorAccessView(MCPView):
    """allow/revoke instructor-dashboard access on a course."""
    @audited_write("instructor_access", scope=Scope.WRITE_ROLES, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        action, level, course_id, user = d["action"], d.get("level", "staff"), \
            d["course_id"], d["username"]
        if not confirmed:
            return Response({"would": action, "level": level, "user": user,
                             "course_id": course_id})
        fn = nr.instructor_allow if action == "grant" else nr.instructor_revoke
        return Response(fn(course_id, user, level)), 1


class ResetAttemptsView(MCPView):
    """Reset (or delete) a learner's state for one problem block."""
    @audited_write("reset_attempts", scope=Scope.WRITE_USERS, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        if not confirmed:
            return Response({"would_reset": d["username"], "block": d["block_locator"],
                             "delete": d.get("delete_module", False)})
        return Response(ne.reset_student_attempts(
            d["course_id"], d["username"], d["block_locator"], request.user,
            delete_module=d.get("delete_module", False))), 1


class DeactivateUserView(MCPView):
    """Destructive: disable an account (is_active=False). Needs write:users + destructive."""
    @audited_write("deactivate_user", scope=Scope.WRITE_USERS, destructive=True, require_confirm=True)
    def post(self, request, confirmed=True):
        user = nu.get_user(request.data["username"])
        if user is None:
            return Response({"error": "No such user."}, status=404)
        if not confirmed:
            return Response({"would_deactivate": user.username})
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response({"deactivated": user.username}), 1
