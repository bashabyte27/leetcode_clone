"""Clear cached catalog/syllabus reads whenever course content is saved or deleted."""

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from . import catalog
from .models import CareerPath, CareerPathCourse, Category, Course, LearningOutcome, Lesson, LessonStep, Module


def _course_id(instance):
    if isinstance(instance, Course):
        return instance.pk
    if isinstance(instance, (Module, LearningOutcome)):
        return instance.course_id
    if isinstance(instance, Lesson):
        return getattr(instance.module, "course_id", None) if instance.module_id else None
    if isinstance(instance, LessonStep):
        return instance.lesson.module.course_id if instance.lesson_id else None
    return None


_WATCHED = (Course, Module, Lesson, LessonStep, LearningOutcome, Category, CareerPath, CareerPathCourse)


@receiver(post_save)
@receiver(post_delete)
def _bust_on_change(sender, instance, **kwargs):
    if isinstance(instance, _WATCHED):
        try:
            catalog.bust(_course_id(instance))
        except Exception:  # a related row may already be gone during cascades; the TTL still applies
            catalog.bust()


@receiver(m2m_changed, sender=Course.prerequisites.through)
def _bust_on_prerequisites(sender, instance, **kwargs):
    catalog.bust(getattr(instance, "pk", None))
