"""LMS ops endpoints — certificates, async reports (grade export), retirement.
Reads require staff/superuser; writes add scope + rails via audited_write."""
from rest_framework.response import Response

from ...models import Scope
from ...native import certificates as nc
from ...native import reports as nrep
from ...native import retirement as nret
from .base import MCPView
from .guards import audited_write

# --- certificates ---

class UserCertificateView(MCPView):
    def get(self, request, username, course_id):
        return Response(nc.get_user_certificate(username, course_id))


class UserCertificatesView(MCPView):
    def get(self, request, username):
        return Response(nc.list_user_certificates(username))


class CourseCertificatesView(MCPView):
    def get(self, request, course_id):
        return Response(nc.list_course_certificates(
            course_id, limit=int(request.query_params.get("limit", 200)),
            offset=int(request.query_params.get("offset", 0))))


class GenerateCertificateView(MCPView):
    @audited_write("generate_certificate", scope=Scope.WRITE_CERTIFICATES, require_confirm=False)
    def post(self, request, confirmed=True):
        d = request.data
        # Batch when no username given (whole course / a student_set).
        if not d.get("username"):
            return Response(nc.generate_course_certificates(
                request, d["course_id"], student_set=d.get("student_set"))), 1
        return Response(nc.generate_user_certificate(d["username"], d["course_id"])), 1


class RegenerateCertificatesView(MCPView):
    @audited_write("regenerate_certificates", scope=Scope.WRITE_CERTIFICATES, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        if not confirmed:
            return Response({"would_regenerate": d["course_id"], "statuses": d["statuses"]})
        return Response(nc.regenerate_course_certificates(
            request, d["course_id"], d["statuses"])), 1


class InvalidateCertificateView(MCPView):
    @audited_write("invalidate_certificate", scope=Scope.WRITE_CERTIFICATES, destructive=True, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        if not confirmed:
            return Response({"would_invalidate": d["username"], "course_id": d["course_id"]})
        return Response(nc.invalidate_certificate(
            request, d["username"], d["course_id"], notes=d.get("notes", ""))), 1


# --- async reports (grade export) ---

class SubmitReportView(MCPView):
    @audited_write("submit_report", scope=Scope.WRITE_REPORTS, require_confirm=False)
    def post(self, request, confirmed=True):
        d = request.data
        return Response(nrep.submit_report(
            request, d["course_id"], kind=d.get("kind", "grades"),
            features=d.get("features"))), 1


class ReportTasksView(MCPView):
    def get(self, request, course_id):
        return Response(nrep.list_tasks(course_id))


class ReportDownloadsView(MCPView):
    def get(self, request, course_id):
        return Response(nrep.list_report_downloads(
            course_id, config_name=request.query_params.get("config", "GRADES_DOWNLOAD")))


# --- account retirement ---

class RetirementStatusView(MCPView):
    def get(self, request, username):
        return Response(nret.retirement_status(username))


class RequestRetirementView(MCPView):
    @audited_write("request_retirement", scope=Scope.WRITE_USERS, destructive=True, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        full = d.get("full", True)
        if not confirmed:
            return Response({"would_retire": d["username"],
                             "mode": "full (irreversible, clears PII)" if full else "queue-only"})
        return Response(nret.request_retirement(d["username"], full=full)), 1
