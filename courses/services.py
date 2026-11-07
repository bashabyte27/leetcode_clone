"""
Course-building services: ordering, structure edits and publish validation.

Views stay thin: they call these functions, which own every rule about
positions and publishing so the staff UI, admin and importer behave the same.
"""

from dataclasses import dataclass, field
from typing import List

from django.db import transaction
from django.db.models import Count, Max, Prefetch

from .models import Course, Lesson, LessonStep, Module, StepQuestion

LESSONS_PER_MODULE = 6
_PARKING_OFFSET = 10000  # temporary positions while renumbering (keeps unique constraints happy)


# ─────────────────────────── Ordering ───────────────────────────


def next_position(queryset):
    return (queryset.aggregate(m=Max("position"))["m"] or 0) + 1


@transaction.atomic
def reorder(queryset, ordered_ids):
    """
    Apply a new order to the rows of `queryset` (all siblings under one parent).
    `ordered_ids` must contain exactly the ids in the queryset.
    """
    rows = {row.pk: row for row in queryset.select_for_update()}
    ids = [int(i) for i in ordered_ids]
    if sorted(ids) != sorted(rows):
        raise ValueError("The new order must list every item exactly once.")
    model = queryset.model
    for row in rows.values():  # park first so no two rows ever share a position
        row.position += _PARKING_OFFSET
    model.objects.bulk_update(rows.values(), ["position"])
    for pos, pk in enumerate(ids, start=1):
        rows[pk].position = pos
    model.objects.bulk_update(rows.values(), ["position"])


def renumber(queryset):
    """Close gaps after a delete (1, 2, 4 → 1, 2, 3)."""
    reorder(queryset, list(queryset.order_by("position").values_list("pk", flat=True)))


@transaction.atomic
def delete_and_renumber(obj, siblings):
    obj.delete()
    renumber(siblings)


# ─────────────────────────── Builder queries ───────────────────────────


def course_outline(course):
    """Modules with lesson counts, in order, for the course workspace."""
    return course.modules.annotate(lesson_count=Count("lessons", distinct=True),
                                   outcome_count=Count("outcomes", distinct=True)).order_by("position")


def module_outline(module):
    return module.lessons.annotate(step_count=Count("steps")).order_by("position")


def lesson_steps(lesson):
    """Steps with everything the editor and publish checks touch, in a fixed number of queries."""
    return (lesson.steps.select_related("coding_question")
            .prefetch_related("outcomes", "hints",
                              Prefetch("questions", queryset=StepQuestion.objects.select_related("mcq", "outcome")))
            .order_by("position"))


# ─────────────────────────── Publish validation ───────────────────────────


@dataclass
class Issue:
    message: str
    url: str = ""
    where: str = ""


@dataclass
class PublishReport:
    blocking: List[Issue] = field(default_factory=list)
    warnings: List[Issue] = field(default_factory=list)

    @property
    def can_publish(self):
        return not self.blocking


def publish_report(course, url_for=None):
    """
    Everything that stands between this course and publishing.

    Blocking: missing structure or incomplete steps (untagged questions/tasks,
    empty content, no coding question...). Warnings: drafting-time shape rules
    such as a module that doesn't have exactly six lessons.
    `url_for(obj)` lets the caller attach "fix it" links.
    """
    link = url_for or (lambda obj: "")
    report = PublishReport()
    if not course.description.strip():
        report.warnings.append(Issue("Add a course description for the landing page.", link(course), "Course"))

    modules = list(course.modules.order_by("position").prefetch_related(
        Prefetch("lessons", queryset=Lesson.objects.order_by("position").prefetch_related(
            Prefetch("steps", queryset=LessonStep.objects.select_related("coding_question").prefetch_related(
                "outcomes", Prefetch("questions", queryset=StepQuestion.objects.order_by("position")),
            ).order_by("position")),
        )),
    ))
    if not modules:
        report.blocking.append(Issue("Add at least one module.", link(course), "Course"))

    for module in modules:
        lessons = list(module.lessons.all())
        where_m = f"Module {module.position} · {module.title}"
        if not lessons:
            report.blocking.append(Issue("Add lessons to this module.", link(module), where_m))
        elif len(lessons) != LESSONS_PER_MODULE and not module.is_introduction:
            report.warnings.append(Issue(
                f"Has {len(lessons)} lesson{'s' if len(lessons) != 1 else ''}; modules are designed for {LESSONS_PER_MODULE}.",
                link(module), where_m))
        for lesson in lessons:
            where_l = f"M{module.position} · L{lesson.position} {lesson.title}"
            steps = list(lesson.steps.all())
            if not steps:
                report.blocking.append(Issue("Add the lesson steps.", link(lesson), where_l))
            for step in steps:
                for problem in step.publish_problems():
                    report.blocking.append(Issue(problem, link(step), f"{where_l} · step {step.position} ({step.spec.label})"))
    return report


@transaction.atomic
def publish(course, url_for=None):
    report = publish_report(course, url_for)
    if report.can_publish:
        course.mark_published()
    return report


def unpublish(course):
    course.is_published = False
    course.save(update_fields=["is_published", "updated_at"])
