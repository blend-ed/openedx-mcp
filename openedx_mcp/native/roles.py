"""
Roles & access — course-team roles, org roles, and instructor-level access.
Native: common.djangoapps.student.roles + lms.djangoapps.instructor.access.
Role helpers are importable in both processes; instructor.access is LMS.
"""
from opaque_keys.edx.keys import CourseKey

# level -> AccessRole class name in student.roles for course-scoped roles
_COURSE_ROLES = {
    "instructor": "CourseInstructorRole",
    "staff": "CourseStaffRole",
    "limited_staff": "CourseLimitedStaffRole",
    "beta": "CourseBetaTesterRole",
    "data_researcher": "CourseDataResearcherRole",
}
_ORG_ROLES = {
    "org_staff": "OrgStaffRole",
    "org_instructor": "OrgInstructorRole",
    "org_content_creator": "OrgContentCreatorRole",
    "org_data_researcher": "OrgDataResearcherRole",
}


def _course_role(level, course_id):
    from common.djangoapps.student import roles
    cls = getattr(roles, _COURSE_ROLES[level])
    return cls(CourseKey.from_string(course_id))


def list_user_roles(username_or_email):
    """All CourseAccessRole rows for a user. Native: UserBasedRole.courses_with_role
    is per-role; we read the model directly for a full picture."""
    from common.djangoapps.student.models import CourseAccessRole
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(username=username_or_email)
    rows = CourseAccessRole.objects.filter(user=user).values("role", "org", "course_id")
    return {"user": user.username,
            "is_staff": user.is_staff, "is_superuser": user.is_superuser,
            "roles": list(rows)}


def grant_course_role(username_or_email, level, course_id):
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(username=username_or_email)
    _course_role(level, course_id).add_users(user)
    return {"granted": level, "user": user.username, "course_id": course_id}


def revoke_course_role(username_or_email, level, course_id):
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(username=username_or_email)
    _course_role(level, course_id).remove_users(user)
    return {"revoked": level, "user": user.username, "course_id": course_id}


def list_course_team(course_id):
    """Users holding instructor/staff on a course."""
    key = CourseKey.from_string(course_id)
    from common.djangoapps.student.roles import CourseInstructorRole, CourseStaffRole
    def _names(role):
        return sorted(u.username for u in role.users_with_role())
    return {"course_id": str(key),
            "instructors": _names(CourseInstructorRole(key)),
            "staff": _names(CourseStaffRole(key))}


# --- instructor-level access (LMS: allow/revoke against the course object) ---

def instructor_allow(course_id, username_or_email, level="staff"):
    """Native: instructor.access.allow_access(course, user, level)."""
    from django.contrib.auth import get_user_model
    from lms.djangoapps.instructor.access import allow_access
    from openedx.core.lib.courses import get_course_by_id
    course = get_course_by_id(CourseKey.from_string(course_id))
    user = get_user_model().objects.get(username=username_or_email)
    allow_access(course, user, level)
    return {"allowed": level, "user": user.username, "course_id": course_id}


def instructor_revoke(course_id, username_or_email, level="staff"):
    from django.contrib.auth import get_user_model
    from lms.djangoapps.instructor.access import revoke_access
    from openedx.core.lib.courses import get_course_by_id
    course = get_course_by_id(CourseKey.from_string(course_id))
    user = get_user_model().objects.get(username=username_or_email)
    revoke_access(course, user, level)
    return {"revoked": level, "user": user.username, "course_id": course_id}
