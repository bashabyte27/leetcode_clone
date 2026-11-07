"""
Student-facing course pages (Phase 2): catalog, course landing, enrollment,
public lesson previews and "My learning". The interactive lesson player
arrives in Phase 3; until then "Continue" opens the syllabus at the student's
lesson.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import access, catalog
from .models import Enrollment, Lesson
from .rendering import STEP_PREFETCH, prepare_steps


def _course_or_404(request, slug):
    course = access.course_for_slug(request.user, slug)
    if course is None:
        raise Http404("Course not found")
    return course


def catalog_view(request):
    staff = access.is_staff(request.user)
    data = catalog.catalog(staff=staff)
    enrolled = set()
    if request.user.is_authenticated:
        enrolled = set(Enrollment.objects.filter(user=request.user).exclude(status=Enrollment.Status.DROPPED)
                       .values_list("course__slug", flat=True))
    selected = request.GET.get("path", "")
    path = next((p for p in data["paths"] if p["slug"] == selected), None)
    in_path = {c["slug"]: n for n, c in enumerate(path["courses"], start=1)} if path else {}
    return render(request, "courses/catalog.html", {
        "data": data, "enrolled": enrolled, "path": path, "in_path": in_path, "staff": staff,
    })


def course_detail(request, slug):
    course = _course_or_404(request, slug)
    staff = access.is_staff(request.user)
    data = catalog.outline(course, staff=staff)
    enrollment = access.enrollment_for(request.user, course)
    active = enrollment is not None and enrollment.status != Enrollment.Status.DROPPED

    continue_pk = None
    if active:
        continue_pk = enrollment.last_lesson_id or next(
            (l["pk"] for m in data["modules"] for l in m["lessons"]), None)
    open_module = next((m["pk"] for m in data["modules"] for l in m["lessons"] if l["pk"] == continue_pk),
                       data["modules"][0]["pk"] if data["modules"] else None)

    description = (course.subtitle or course.description or "").strip()
    return render(request, "courses/course_detail.html", {
        "course": course, "data": data, "stats": data["stats"], "enrollment": enrollment if active else None,
        "continue_pk": continue_pk, "open_module": open_module, "staff": staff,
        "premium_locked": access.premium_locked(request.user, course),
        "meta_description": description[:300],
        "canonical": request.build_absolute_uri(reverse("courses:course", args=[course.slug])),
    })


@login_required
@require_POST
def enroll(request, slug):
    course = _course_or_404(request, slug)
    enrollment, created = Enrollment.objects.get_or_create(user=request.user, course=course)
    if not created and enrollment.status == Enrollment.Status.DROPPED:
        enrollment.status = Enrollment.Status.ACTIVE
        enrollment.started_at = timezone.now()
        enrollment.save(update_fields=["status", "started_at", "updated_at"])
        created = True
    if created:
        messages.success(request, f"You're enrolled in {course.title}. Start with the first lesson below.")
    return redirect(reverse("courses:course", args=[course.slug]) + "#syllabus")


def preview_lesson(request, slug, module_slug, lesson_slug):
    course = _course_or_404(request, slug)
    lesson = catalog.lesson_by_slugs(course, module_slug, lesson_slug)
    if lesson is None:
        raise Http404("Lesson not found")
    module = lesson.module
    staff = access.is_staff(request.user)
    if not (access.is_public_preview(lesson, module) or staff):
        messages.info(request, f"“{lesson.title}” opens in the lesson player once you enroll.")
        return redirect(reverse("courses:course", args=[course.slug]) + f"#lesson-{lesson.pk}")

    steps = prepare_steps(list(lesson.steps.select_related("coding_question").prefetch_related(
        "outcomes", *STEP_PREFETCH).order_by("position")), reveal_answers=False)
    previous, following = catalog.neighbours(course, lesson)

    def link(row):
        if row is None:
            return None
        mod, les = row
        return {"title": les.title, "number": f"{mod.position}.{les.position}",
                "url": (reverse("courses:preview", args=[course.slug, mod.slug, les.slug])
                        if access.is_public_preview(les, mod) else ""),
                "pk": les.pk}

    enrollment = access.enrollment_for(request.user, course)
    return render(request, "courses/lesson_preview.html", {
        "course": course, "module": module, "lesson": lesson, "steps": steps,
        "previous": link(previous), "next": link(following), "staff": staff,
        "is_preview_only": not access.is_public_preview(lesson, module),
        "enrolled": enrollment is not None and enrollment.status != Enrollment.Status.DROPPED,
        "course_url": reverse("courses:course", args=[course.slug]),
        "outcomes": lesson.outcomes.order_by("position", "code"),
        "step_minutes": lesson.est_minutes,
    })


@login_required
def my_learning(request):
    enrollments = list(
        Enrollment.objects.filter(user=request.user).exclude(status=Enrollment.Status.DROPPED)
        .select_related("course__category", "last_lesson__module")
        .annotate(lesson_count=Count("course__modules__lessons", distinct=True),
                  module_count=Count("course__modules", filter=Q(course__modules__is_introduction=False),
                                     distinct=True))
        .order_by("-updated_at"))
    visible = [e for e in enrollments if access.can_view_course(request.user, e.course)]
    firsts = {}
    if visible:
        for lesson in (Lesson.objects.filter(module__course__in=[e.course for e in visible])
                       .select_related("module").order_by("module__course_id", "module__position", "position")):
            firsts.setdefault(lesson.module.course_id, lesson)
    rows = []
    for e in visible:
        lesson = e.last_lesson or firsts.get(e.course_id)
        rows.append({"enrollment": e, "course": e.course, "lesson": lesson,
                     "continue_url": reverse("courses:course", args=[e.course.slug])
                     + (f"#lesson-{lesson.pk}" if lesson else "#syllabus")})
    return render(request, "courses/my_learning.html", {"rows": rows, "nav_active": "my_learning"})
