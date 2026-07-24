"""LMS URL config — mounted at ^api/mcp/ by MCPLmsConfig."""
from django.urls import path

from . import ops_views as ov
from . import tool_views as tv
from . import views as v

app_name = "openedx_mcp"

COURSE_ID = "<path:course_id>"

urlpatterns = [
    # context
    path("whoami/", v.WhoAmIView.as_view(), name="whoami"),

    # reads
    path("analytics/overview/", v.AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("courses/", v.CoursesView.as_view(), name="courses"),
    path(f"courses/{COURSE_ID}/", v.CourseDetailView.as_view(), name="course-detail"),
    path("users/", v.UsersView.as_view(), name="users"),
    path("users/<str:username>/roles/", v.UserRolesView.as_view(), name="user-roles"),
    path(f"courses/{COURSE_ID}/team/", v.CourseTeamView.as_view(), name="course-team"),
    path(f"grades/<str:username>/{COURSE_ID}/", v.UserGradeView.as_view(), name="user-grade"),

    # writes — enrollment
    path("enroll/", tv.EnrollUserView.as_view(), name="enroll"),
    path("unenroll/", tv.UnenrollUserView.as_view(), name="unenroll"),
    path("bulk-enroll/", tv.BulkEnrollView.as_view(), name="bulk-enroll"),

    # writes — users & roles
    path("users/create/", tv.CreateUserView.as_view(), name="create-user"),
    path("users/deactivate/", tv.DeactivateUserView.as_view(), name="deactivate-user"),
    path("roles/set/", tv.SetRoleView.as_view(), name="set-role"),
    path("access/instructor/", tv.InstructorAccessView.as_view(), name="instructor-access"),
    path("students/reset-attempts/", tv.ResetAttemptsView.as_view(), name="reset-attempts"),

    # certificates
    path(f"certificates/course/{COURSE_ID}/", ov.CourseCertificatesView.as_view(),
         name="course-certificates"),
    path("certificates/user/<str:username>/", ov.UserCertificatesView.as_view(),
         name="user-certificates"),
    path(f"certificates/user/<str:username>/{COURSE_ID}/", ov.UserCertificateView.as_view(),
         name="user-certificate"),
    path("certificates/generate/", ov.GenerateCertificateView.as_view(), name="generate-cert"),
    path("certificates/regenerate/", ov.RegenerateCertificatesView.as_view(), name="regenerate-cert"),
    path("certificates/invalidate/", ov.InvalidateCertificateView.as_view(), name="invalidate-cert"),

    # async reports (grade export)
    path("reports/submit/", ov.SubmitReportView.as_view(), name="submit-report"),
    path(f"reports/tasks/{COURSE_ID}/", ov.ReportTasksView.as_view(), name="report-tasks"),
    path(f"reports/downloads/{COURSE_ID}/", ov.ReportDownloadsView.as_view(), name="report-downloads"),

    # account retirement
    path("retirement/status/<str:username>/", ov.RetirementStatusView.as_view(),
         name="retirement-status"),
    path("retirement/request/", ov.RequestRetirementView.as_view(), name="retirement-request"),
]
