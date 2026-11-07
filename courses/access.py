"""
Who may see what in the courses product. Every student-facing view asks here;
nothing is decided in templates or on the client.

    Visitor          browse published courses, open public preview lessons
    Logged in        enroll in any published course
    Premium          the whole of a premium course
    Staff            everything, including unpublished drafts (shown with a banner)

Premium courses keep their introduction module, their first module and any
lesson marked "free preview" open to every enrolled student, so a course can be
tried properly before paying. COURSES_PREMIUM_GATING=False opens everything
(college pilots).
"""

from django.conf import settings
from django.utils import timezone

from .models import Course, Enrollment


def is_staff(user):
    return bool(getattr(user, "is_authenticated", False) and user.is_staff)


def has_premium(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_premium", False):
        return True
    from premium.models import Subscription, SubscriptionStatusChoices
    return Subscription.objects.filter(
        user=user, status__in=[SubscriptionStatusChoices.ACTIVE, SubscriptionStatusChoices.TRIALING],
        current_period_end__gt=timezone.now(),
    ).exists()


def visible_courses(user):
    qs = Course.objects.all()
    return qs if is_staff(user) else qs.filter(is_published=True)


def can_view_course(user, course):
    return course.is_published or is_staff(user)


def course_for_slug(user, slug):
    """The newest version of `slug` this user may see, or None."""
    return visible_courses(user).filter(slug=slug).select_related("category").order_by("-version").first()


def is_public_preview(lesson, module):
    """Lessons anyone (even logged out) can open from the course page."""
    return bool(lesson.is_free_preview or module.is_free_preview or module.is_introduction)


def is_free_to_enrolled(lesson, module, course):
    """Lessons an enrolled student can take without Premium."""
    if course.access == Course.Access.FREE or not settings.COURSES_PREMIUM_GATING:
        return True
    return is_public_preview(lesson, module) or module.position <= 1


def enrollment_for(user, course):
    if not getattr(user, "is_authenticated", False):
        return None
    return Enrollment.objects.filter(user=user, course=course).select_related("last_lesson__module").first()


def premium_locked(user, course):
    """True when this user will hit the premium wall somewhere in `course`."""
    return (course.access == Course.Access.PREMIUM and settings.COURSES_PREMIUM_GATING
            and not has_premium(user) and not is_staff(user))
