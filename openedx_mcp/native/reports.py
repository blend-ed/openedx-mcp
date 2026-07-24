"""
Async instructor reports — grade export & friends (LMS).
Native: lms.djangoapps.instructor_task.api.submit_* (enqueue) + InstructorTask
(poll) + ReportStore (download links). All submit_* need a Django request.
"""
from opaque_keys.edx.keys import CourseKey

# report kind -> (instructor_task.api function name, needs default feature list)
_KINDS = {
    "grades": "submit_calculate_grades_csv",
    "problem_grade": "submit_problem_grade_report",
    "students_features": "submit_calculate_students_features_csv",
    "may_enroll": "submit_calculate_may_enroll_csv",
    "inactive_enrolled": "submit_calculate_inactive_enrolled_students_csv",
    "proctored_exam": "submit_proctored_exam_results_report",
    "course_survey": "submit_course_survey_report",
}
# kinds whose submit_* take a `features` positional
_NEEDS_FEATURES = {"students_features", "may_enroll", "inactive_enrolled"}
_DEFAULT_FEATURES = ["id", "username", "name", "email", "enrollment_mode"]


def _key(course_id):
    return course_id if isinstance(course_id, CourseKey) else CourseKey.from_string(course_id)


def _django_request(request):
    return getattr(request, "_request", request)


def submit_report(request, course_id, kind="grades", features=None):
    """Enqueue an async report. Returns the InstructorTask id/state. Raises
    AlreadyRunningError if an identical report is already active."""
    from lms.djangoapps.instructor_task import api as task_api
    if kind not in _KINDS:
        raise ValueError(f"Unknown report kind: {kind}. One of {sorted(_KINDS)}.")
    fn = getattr(task_api, _KINDS[kind])
    key = _key(course_id)
    req = _django_request(request)
    if kind in _NEEDS_FEATURES:
        task = fn(req, key, features or _DEFAULT_FEATURES)
    else:
        task = fn(req, key)
    return {"task_id": str(task.task_id), "task_type": task.task_type,
            "task_state": task.task_state, "kind": kind}


def list_tasks(course_id):
    """Recent instructor tasks for a course, with poll status."""
    from lms.djangoapps.instructor_task.models import InstructorTask
    from lms.djangoapps.instructor_task.api_helper import get_status_from_instructor_task
    rows = InstructorTask.objects.filter(course_id=_key(course_id)).order_by("-created")[:50]
    return {"course_id": str(_key(course_id)),
            "tasks": [get_status_from_instructor_task(t) for t in rows]}


def list_report_downloads(course_id, config_name="GRADES_DOWNLOAD"):
    """Download links (filename, url) for generated reports, newest first."""
    from lms.djangoapps.instructor_task.models import ReportStore
    store = ReportStore.from_config(config_name)
    links = store.links_for(_key(course_id))
    return {"course_id": str(_key(course_id)),
            "downloads": [{"name": name, "url": url} for name, url in links]}
