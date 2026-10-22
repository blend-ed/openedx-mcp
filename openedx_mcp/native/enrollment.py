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


def bulk_unenroll(course_id, entries):
    """Unenroll many by email. Native: instructor.enrollment.unenroll_email (what
    the Instructor Dashboard's batch unenroll runs). Deactivates an enrollment and
    also deletes a pending CourseEnrollmentAllowed, so invites to emails with no
    account can be withdrawn."""
    from lms.djangoapps.instructor.enrollment import unenroll_email
    key = _course_key(course_id)
    results = []
    for e in entries:
        email = e.get("email")
        try:
            before, after = unenroll_email(key, email)[:2]
            results.append({"email": email,
                            "was_enrolled": before.enrollment, "was_pending": before.allowed,
                            "enrolled": after.enrollment, "allowed": after.allowed})
        except Exception as exc:  # noqa: BLE001 — report per-row, don't abort the batch
            results.append({"email": email, "error": str(exc)})
    return {"course_id": str(key), "count": len(entries), "results": results}


def _classify(key, entries):
    """Split a batch of emails by current state in one course: enrolled, pending
    (CourseEnrollmentAllowed without an active enrollment), has an account but
    not enrolled, or no account at all."""
    from common.djangoapps.student.models import CourseEnrollment, CourseEnrollmentAllowed
    from django.contrib.auth import get_user_model
    emails = [e.get("email", "").strip().lower() for e in entries if e.get("email")]
    enrolled = {x.lower() for x in CourseEnrollment.objects.filter(
        course_id=key, is_active=True, user__email__in=emails).values_list("user__email", flat=True)}
    allowed = {x.lower() for x in CourseEnrollmentAllowed.objects.filter(
        course_id=key, email__in=emails).values_list("email", flat=True)}
    accounts = {x.lower() for x in get_user_model().objects.filter(
        email__in=emails).values_list("email", flat=True)}
    groups = {"enrolled": [], "pending": [], "account_not_enrolled": [], "no_account": []}
    for email in emails:
        if email in enrolled:
            groups["enrolled"].append(email)
        elif email in allowed:
            groups["pending"].append(email)
        elif email in accounts:
            groups["account_not_enrolled"].append(email)
        else:
            groups["no_account"].append(email)
    return emails, groups


def preview_bulk_enroll(course_id, entries, action="enroll"):
    """What a bulk enroll/unenroll batch would do, before applying. Cheap reads;
    used to build the dry-run audience.

    enroll: will_enroll (has an account), will_be_pending (no account yet: gets a
    CourseEnrollmentAllowed and is enrolled on signup), already_enrolled.
    unenroll: will_unenroll, will_revoke_pending, not_enrolled (no-op)."""
    key = _course_key(course_id)
    emails, g = _classify(key, entries)
    out = {"course_id": str(key), "action": action, "total": len(emails)}
    if action == "unenroll":
        out.update({"will_unenroll": len(g["enrolled"]), "will_revoke_pending": len(g["pending"]),
                    "not_enrolled": len(g["account_not_enrolled"]) + len(g["no_account"]),
                    "sample_unenroll": g["enrolled"][:20], "sample_revoke": g["pending"][:20]})
    else:
        out.update({"already_enrolled": len(g["enrolled"]),
                    "will_enroll": len(g["account_not_enrolled"]),
                    "will_be_pending": len(g["no_account"]) + len(g["pending"]),
                    "sample_enroll": g["account_not_enrolled"][:20],
                    "sample_pending": (g["no_account"] + g["pending"])[:20]})
    return out


def pending_count(course_id):
    """Invites to this course not yet turned into an active enrollment:
    CourseEnrollmentAllowed rows whose email has no active enrollment."""
    from common.djangoapps.student.models import CourseEnrollment, CourseEnrollmentAllowed
    key = _course_key(course_id)
    enrolled_emails = CourseEnrollment.objects.filter(
        course_id=key, is_active=True).values("user__email")
    return CourseEnrollmentAllowed.objects.filter(course_id=key).exclude(
        email__in=enrolled_emails).count()


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
