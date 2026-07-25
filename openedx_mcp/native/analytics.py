"""
Read-only analytics — course listings, enrollment counts, grades.
Cheap reads only: CourseOverview (cached) + enrollment_counts + persisted grades.
Importable in LMS (grades) and both processes (overviews).
"""
from opaque_keys.edx.keys import CourseKey


def list_courses(org=None, limit=100, offset=0):
    """List courses from the cached CourseOverview table (no modulestore hit)."""
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
    qs = CourseOverview.get_all_courses(orgs=[org] if org else None)
    qs = qs.order_by("id")
    total = qs.count()
    rows = [_overview_dict(c) for c in qs[offset:offset + limit]]
    return {"total": total, "limit": limit, "offset": offset, "courses": rows}


def _overview_dict(c):
    return {
        "course_id": str(c.id), "display_name": c.display_name,
        "org": c.org, "number": c.display_number_with_default,
        "start": c.start.isoformat() if c.start else None,
        "end": c.end.isoformat() if c.end else None,
        "self_paced": c.self_paced,
    }


def course_detail(course_id):
    from openedx.core.djangoapps.content.course_overviews.api import get_course_overview_or_none
    c = get_course_overview_or_none(CourseKey.from_string(course_id))
    if c is None:
        return None
    from .enrollment import enrollment_counts
    d = _overview_dict(c)
    d["enrollment"] = enrollment_counts(course_id)
    return d


def analytics_overview(org=None):
    """Consolidated stat cards across the platform (or one org): course count,
    total enrollments, per-course enrollment counts."""
    from common.djangoapps.student.models import CourseEnrollment
    from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
    qs = CourseOverview.get_all_courses(orgs=[org] if org else None)
    per_course, total_enroll = [], 0
    for c in qs:
        counts = CourseEnrollment.objects.enrollment_counts(c.id)
        total_enroll += counts.get("total", 0)
        per_course.append({"course_id": str(c.id), "display_name": c.display_name,
                           "enrollment": counts.get("total", 0)})
    per_course.sort(key=lambda r: r["enrollment"], reverse=True)
    return {"total_courses": len(per_course), "total_enrollments": total_enroll,
            "courses": per_course}


def user_course_grade(username, course_id):
    """Single learner's course grade. Native: grades.api.CourseGradeFactory().read.
    May compute if not persisted — do not call in a tight loop over many users."""
    from django.contrib.auth import get_user_model
    from lms.djangoapps.grades.api import CourseGradeFactory
    user = get_user_model().objects.get(username=username)
    grade = CourseGradeFactory().read(user, course_key=CourseKey.from_string(course_id))
    return {"user": username, "course_id": course_id,
            "percent": grade.percent, "passed": grade.passed,
            "letter_grade": grade.letter_grade}
