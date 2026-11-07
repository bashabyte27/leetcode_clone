"""
Read models for the public course pages: the catalog and a course's syllabus.

Both are plain dicts/lists (cache-friendly, no lazy querysets in templates) and
are built in a fixed number of queries. Public reads are cached for
COURSES_CACHE_SECONDS; staff always read fresh so the builder and the public
page never disagree while editing. Saves and deletes clear the cache through
courses.signals; the TTL covers bulk edits (re-ordering, imports).
"""

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Prefetch, Q
from django.urls import reverse

from .access import is_public_preview
from .models import CareerPath, CareerPathCourse, Category, Course, LearningOutcome, Lesson, LessonStep, StepQuestion

CATALOG_KEY = "courses:catalog:v1"


def outline_key(course_id):
    return f"courses:outline:v1:{course_id}"


def _cached(key, build, fresh):
    seconds = settings.COURSES_CACHE_SECONDS
    if fresh or seconds <= 0:
        return build()
    value = cache.get(key)
    if value is None:
        value = build()
        cache.set(key, value, seconds)
    return value


def bust(course_id=None):
    cache.delete(CATALOG_KEY)
    if course_id:
        cache.delete(outline_key(course_id))


# ─────────────────────────── Catalog ───────────────────────────


def catalog(staff=False):
    """
    {"categories": [{title, slug, description, icon, courses: [...]}], "paths": [...], "course_count": n}
    Staff also get unpublished courses (flagged `is_draft`).
    """
    key = CATALOG_KEY + (":staff" if staff else "")
    return _cached(key, lambda: _build_catalog(staff), fresh=staff)


def _build_catalog(staff):
    courses = Course.objects.all() if staff else Course.objects.filter(is_published=True)
    courses = (courses.annotate(
        module_count=Count("modules", filter=Q(modules__is_introduction=False), distinct=True),
        lesson_count=Count("modules__lessons", distinct=True),
    ).order_by("title", "-version"))
    categories = (Category.objects.filter(is_active=True).order_by("position", "title")
                  .prefetch_related(Prefetch("courses", queryset=courses, to_attr="listed")))
    out, seen = [], set()
    for category in categories:
        rows = []
        for course in category.listed:
            if course.slug in seen:  # newest version only
                continue
            seen.add(course.slug)
            rows.append(_course_card(course))
        if rows:
            out.append({"title": category.title, "slug": category.slug, "description": category.description,
                        "icon": category.icon or "journal-code", "courses": rows})
    path_courses = CareerPathCourse.objects.filter(course__in=courses).select_related("course").order_by("position")
    paths = (CareerPath.objects.filter(is_active=True).order_by("position", "title")
             .prefetch_related(Prefetch("path_courses", queryset=path_courses, to_attr="ordered")))
    path_rows = [{"title": p.title, "slug": p.slug, "goal": p.goal, "goal_label": p.get_goal_display(),
                  "description": p.description,
                  "courses": [{"title": pc.course.title, "slug": pc.course.slug} for pc in p.ordered]}
                 for p in paths]
    return {"categories": out, "paths": [p for p in path_rows if p["courses"]],
            "course_count": sum(len(c["courses"]) for c in out)}


def _course_card(course):
    return {
        "pk": course.pk, "slug": course.slug, "title": course.title, "subtitle": course.subtitle,
        "level": course.get_level_display(), "est_weeks": course.est_weeks, "access": course.access,
        "module_count": course.module_count, "lesson_count": course.lesson_count,
        "is_draft": not course.is_published, "url": reverse("courses:course", args=[course.slug]),
    }


# ─────────────────────────── Course syllabus ───────────────────────────


def outline(course, staff=False):
    """Everything the course landing page shows about the content, in 5 queries."""
    return _cached(outline_key(course.pk), lambda: _build_outline(course), fresh=staff)


def _build_outline(course):
    lessons = Lesson.objects.order_by("position")
    modules = list(course.modules.order_by("position").prefetch_related(Prefetch("lessons", queryset=lessons)))
    steps = LessonStep.objects.filter(lesson__module__course=course)
    by_type = dict(steps.values_list("step_type").annotate(n=Count("pk")).values_list("step_type", "n"))
    mcq_count = StepQuestion.objects.filter(step__lesson__module__course=course).count()
    outcomes = list(LearningOutcome.objects.filter(course=course, module__isnull=True).order_by("position", "code")
                    .values("code", "title", "text"))
    prerequisites = [{"title": p.title, "url": reverse("courses:course", args=[p.slug])}
                     for p in course.prerequisites.filter(is_published=True).order_by("title")]

    module_rows, minutes, lesson_count, first_preview = [], 0, 0, None
    for module in modules:
        lesson_rows = []
        for lesson in module.lessons.all():
            preview = is_public_preview(lesson, module)
            url = reverse("courses:preview", args=[course.slug, module.slug, lesson.slug]) if preview else ""
            row = {"pk": lesson.pk, "position": lesson.position, "title": lesson.title, "summary": lesson.summary,
                   "est_minutes": lesson.est_minutes, "preview": preview, "preview_url": url,
                   "number": f"{module.position}.{lesson.position}"}
            if preview and first_preview is None:
                first_preview = row
            lesson_rows.append(row)
        module_minutes = sum(l["est_minutes"] for l in lesson_rows)
        minutes += module_minutes
        lesson_count += len(lesson_rows)
        module_rows.append({
            "pk": module.pk, "position": module.position, "title": module.title, "summary": module.summary,
            "is_introduction": module.is_introduction, "minutes": module_minutes, "lessons": lesson_rows,
            "has_project": bool(module.mini_project_brief.strip()),
            "label": "Introduction" if module.is_introduction else f"Module {module.position}",
        })
    return {
        "modules": module_rows,
        "outcomes": outcomes,
        "prerequisites": prerequisites,
        "first_preview": first_preview,
        "stats": {
            "modules": sum(1 for m in modules if not m.is_introduction),
            "lessons": lesson_count,
            "hours": round(minutes / 60),
            "minutes": minutes,
            "videos": by_type.get("VIDEO", 0),
            "coding": by_type.get("CODING", 0) + by_type.get("FIX_BUG", 0),
            "quizzes": by_type.get("QUIZ", 0) + by_type.get("PREDICT", 0),
            "mcqs": mcq_count,
            "parsons": by_type.get("PARSONS", 0),
        },
    }


def lesson_by_slugs(course, module_slug, lesson_slug):
    return (Lesson.objects.select_related("module__course")
            .filter(module__course=course, module__slug=module_slug, slug=lesson_slug).first())


def neighbours(course, lesson):
    """(previous, next) public-preview lessons around `lesson`, for the preview page footer."""
    rows = [(m, l) for m in course.modules.order_by("position").prefetch_related(
        Prefetch("lessons", queryset=Lesson.objects.order_by("position"))) for l in m.lessons.all()]
    index = next((i for i, (_, l) in enumerate(rows) if l.pk == lesson.pk), None)
    if index is None:
        return None, None
    prev_row = rows[index - 1] if index > 0 else None
    next_row = rows[index + 1] if index + 1 < len(rows) else None
    return prev_row, next_row

