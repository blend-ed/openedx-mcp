"""
Enrollment operations — thin wrappers over native Open edX enrollment APIs (LMS).

All imports are lazy so this module is importable outside a running platform.
"""
from opaque_keys.edx.keys import CourseKey


def _course_key(course_id):
    return course_id if isinstance(course_id, CourseKey) else CourseKey.from_string(course_id)


def enroll(username, course_id, mode="audit"):
    """Enroll one user. Native: openedx.core.djangoapps.enrollments.api.add_enrollment
    (fires enrollment signals + tracking events)."""
    from openedx.core.djangoapps.enrollments import api as enrollment_api
    return enrollment_api.add_enrollment(username, str(_course_key(course_id)), mode=mode)


def unenroll(username, course_id):
    """Deactivate one enrollment. Native: update_enrollment(is_active=False)."""
    from openedx.core.djangoapps.enrollments import api as enrollment_api
    return enrollment_api.update_enrollment(username, str(_course_key(course_id)), is_active=False)


def get_enrollment(username, course_id):
    from openedx.core.djangoapps.enrollments import api as enrollment_api
    return enrollment_api.get_enrollment(username, str(_course_key(course_id)))


def bulk_enroll(course_id, entries, mode="audit", auto_enroll=True):
    """Enroll many. entries = [{"email"|"username": ..., "mode"?: ...}].
    Uses instructor.enrollment.enroll_email so invited-but-unregistered addresses
    get a CourseEnrollmentAllowed (auto-enroll on signup)."""
    from lms.djangoapps.instructor.enrollment import enroll_email
    key = _course_key(course_id)
    results = []
    for e in entries:
        email = e.get("email")
        entry_mode = e.get("mode", mode)
        try:
            # Ulmo's enroll_email returns (previous_state, after_state,
            # enrollment_obj) — index instead of a fixed-arity unpack so a future
            # signature change can't re-break this.
            states = enroll_email(key, email, auto_enroll=auto_enroll)
            after = states[1]
            results.append({"email": email, "mode": entry_mode,
                            "enrolled": after.enrollment, "allowed": after.allowed})
        except Exception as exc:  # noqa: BLE001 — report per-row, don't abort the batch
            results.append({"email": email, "error": str(exc)})
    return {"course_id": str(key), "count": len(entries), "results": results}


def preview_bulk_enroll(course_id, entries):
    """Classify a bulk-enroll batch before applying: which addresses are already
    actively enrolled vs new. Cheap read; used to build the dry-run audience."""
    from common.djangoapps.student.models import CourseEnrollment
    key = _course_key(course_id)
    emails = [e.get("email", "").strip().lower() for e in entries if e.get("email")]
    active = set(
        CourseEnrollment.objects.filter(course_id=key, is_active=True,
                                        user__email__in=emails)
        .values_list("user__email", flat=True)
    )
    active = {e.lower() for e in active}
    already = [e for e in emails if e in active]
    new = [e for e in emails if e not in active]
    return {"course_id": str(key), "total": len(emails),
            "already_enrolled": len(already), "to_enroll": len(new),
            "sample_new": new[:20]}


def reset_student_attempts(course_id, username, block_locator, requesting_user,
                           delete_module=False):
    """Reset (or delete) a learner's state for one problem block. Native:
    instructor.enrollment.reset_student_attempts. Fires score-changed signals."""
    from django.contrib.auth import get_user_model
    from lms.djangoapps.instructor.enrollment import reset_student_attempts as _reset
    from opaque_keys.edx.keys import UsageKey
    student = get_user_model().objects.get(username=username)
    _reset(_course_key(course_id), student, UsageKey.from_string(block_locator),
           requesting_user, delete_module=delete_module)
    return {"reset": username, "block": block_locator, "deleted": delete_module}


def enrollment_counts(course_id):
    """Per-mode + total counts. Cheap; uses read replica.
    Native: CourseEnrollment.objects.enrollment_counts."""
    from common.djangoapps.student.models import CourseEnrollment
    return CourseEnrollment.objects.enrollment_counts(_course_key(course_id))
