"""
Certificates — native lms.djangoapps.certificates.api + instructor_task.api (LMS).
Batch generate/regenerate submit async instructor tasks (need a request).
"""
from opaque_keys.edx.keys import CourseKey


def _key(course_id):
    return course_id if isinstance(course_id, CourseKey) else CourseKey.from_string(course_id)


def get_user_certificate(username, course_id):
    from lms.djangoapps.certificates.api import get_certificate_for_user
    return get_certificate_for_user(username, _key(course_id)) or {"certificate": None}


def list_user_certificates(username):
    from lms.djangoapps.certificates.api import get_certificates_for_user
    return {"user": username, "certificates": get_certificates_for_user(username)}


def list_course_certificates(course_id, limit=200, offset=0):
    """Issued (downloadable) certs for a course, from GeneratedCertificate."""
    from lms.djangoapps.certificates.data import CertificateStatuses
    from lms.djangoapps.certificates.models import GeneratedCertificate
    qs = (GeneratedCertificate.objects
          .filter(course_id=_key(course_id), status=CertificateStatuses.downloadable)
          .select_related("user").order_by("-created_date"))
    total = qs.count()
    rows = [{"username": c.user.username, "mode": c.mode, "grade": c.grade,
             "status": c.status, "uuid": str(c.verify_uuid),
             "created": c.created_date.isoformat() if c.created_date else None}
            for c in qs[offset:offset + limit]]
    return {"course_id": str(_key(course_id)), "total": total, "certificates": rows}


def generate_user_certificate(username, course_id):
    """Enqueue cert generation for one user. Native: generate_certificate_task."""
    from django.contrib.auth import get_user_model
    from lms.djangoapps.certificates.api import generate_certificate_task
    user = get_user_model().objects.get(username=username)
    generate_certificate_task(user, _key(course_id))
    return {"queued": username, "course_id": str(_key(course_id))}


def generate_course_certificates(request, course_id, student_set=None):
    """Batch generate. Native: instructor_task.api.generate_certificates_for_students.
    student_set ∈ None(all) | all_allowlisted | allowlisted_not_generated | specific_student."""
    from lms.djangoapps.instructor_task.api import generate_certificates_for_students
    task = generate_certificates_for_students(
        _django_request(request), _key(course_id), student_set=student_set)
    return _task_dict(task)


def regenerate_course_certificates(request, course_id, statuses):
    """Batch regenerate for the given CertificateStatuses list."""
    from lms.djangoapps.instructor_task.api import regenerate_certificates
    task = regenerate_certificates(_django_request(request), _key(course_id), statuses)
    return _task_dict(task)


def invalidate_certificate(request, username, course_id, notes=""):
    """Invalidate a user's cert (and record who did it)."""
    from django.contrib.auth import get_user_model
    from lms.djangoapps.certificates.api import (
        get_certificate_for_user_id, create_certificate_invalidation_entry,
        invalidate_certificate as _invalidate,
    )
    user = get_user_model().objects.get(username=username)
    ok = _invalidate(user.id, _key(course_id), source="openedx-mcp")
    cert = get_certificate_for_user_id(user, _key(course_id))
    if cert is not None:
        create_certificate_invalidation_entry(cert, request.user, notes or "via openedx-mcp")
    return {"invalidated": ok, "user": username, "course_id": str(_key(course_id))}


def _django_request(request):
    """instructor_task.api.submit_* expect a Django HttpRequest with an
    authenticated user; DRF wraps one at request._request."""
    return getattr(request, "_request", request)


def _task_dict(task):
    return {"task_id": str(task.task_id), "task_type": task.task_type,
            "task_state": task.task_state}
