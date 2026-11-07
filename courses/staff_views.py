"""
Staff course builder (/staff/courses/).

Thin views: forms own field rules, `courses.services` owns ordering and
publishing. Every view is staff-only.
"""

import base64
import hashlib
import io
import json

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from assessment.models import CodingQuestion, McqQuestion
from staff.views import staff_required

from . import services, sheet_importer
from .forms import STEP_FORMS, CourseForm, LessonForm, ModuleForm, OutcomeForm
from .models import Course, LearningOutcome, Lesson, LessonStep, Module, StepQuestion
from .rendering import STEP_PREFETCH, prepare_steps
from .steps import STEP_TYPES


def builder_url(obj):
    """Where to fix something — used for publish-report links."""
    if isinstance(obj, Course):
        return reverse("course_builder:course", args=[obj.pk])
    if isinstance(obj, Module):
        return reverse("course_builder:module", args=[obj.pk])
    if isinstance(obj, Lesson):
        return reverse("course_builder:lesson", args=[obj.pk])
    if isinstance(obj, LessonStep):
        return reverse("course_builder:step", args=[obj.pk])
    return ""


def _crumbs(*objs):
    """Breadcrumb trail: Courses › Course › Module › Lesson."""
    trail = [("Courses", reverse("course_builder:course_list"))]
    for obj in objs:
        label = obj.title if not isinstance(obj, (Module, Lesson)) else str(obj)
        trail.append((label, builder_url(obj)))
    return trail


# ─────────────────────────── Courses ───────────────────────────


@staff_required
def course_list(request):
    courses = (Course.objects.select_related("category")
               .annotate(module_count=Count("modules", distinct=True),
                         lesson_count=Count("modules__lessons", distinct=True))
               .order_by("category__position", "title"))
    return render(request, "courses/builder/course_list.html", {"courses": courses})


@staff_required
def course_create(request):
    form = CourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.created_by = request.user
        course.save()
        form.save_m2m()
        messages.success(request, f"Created “{course.title}”. Add its first module below.")
        return redirect("course_builder:course", course.pk)
    return render(request, "courses/builder/course_form.html", {"form": form, "crumbs": _crumbs()})


@staff_required
def course_detail(request, course_id):
    course = get_object_or_404(Course.objects.select_related("category"), pk=course_id)
    form = CourseForm(request.POST or None, instance=course)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Course details saved.")
        return redirect("course_builder:course", course.pk)
    return render(request, "courses/builder/course_detail.html", {
        "course": course, "form": form, "modules": services.course_outline(course),
        "crumbs": _crumbs(course), "open_settings": request.method == "POST",
    })


@staff_required
def course_publish(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if request.method == "POST":
        if request.POST.get("action") == "unpublish":
            services.unpublish(course)
            messages.success(request, "Course moved back to draft.")
            return redirect("course_builder:course", course.pk)
        report = services.publish(course, builder_url)
        if report.can_publish:
            messages.success(request, f"“{course.title}” is published.")
            return redirect("course_builder:course", course.pk)
        messages.error(request, "Fix the blocking issues below before publishing.")
    else:
        report = services.publish_report(course, builder_url)
    return render(request, "courses/builder/publish.html",
                  {"course": course, "report": report, "crumbs": _crumbs(course)})


# ─────────────────────────── Modules ───────────────────────────


@staff_required
@require_POST
def module_create(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, "Give the module a title.")
        return redirect("course_builder:course", course.pk)
    module = Module.objects.create(course=course, title=title[:200],
                                   position=services.next_position(course.modules.all()))
    messages.success(request, f"Added module {module.position}.")
    return redirect("course_builder:module", module.pk)


@staff_required
def module_detail(request, module_id):
    module = get_object_or_404(Module.objects.select_related("course"), pk=module_id)
    form = ModuleForm(request.POST or None, instance=module)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Module saved.")
        return redirect("course_builder:module", module.pk)
    lessons = services.module_outline(module)
    return render(request, "courses/builder/module_detail.html", {
        "module": module, "course": module.course, "form": form, "lessons": lessons,
        "lesson_target": services.LESSONS_PER_MODULE,
        "outcomes": module.outcomes.select_related("lesson").order_by("code"),
        "outcome_form": OutcomeForm(module=module),
        "crumbs": _crumbs(module.course, module),
    })


@staff_required
@require_POST
def module_delete(request, module_id):
    module = get_object_or_404(Module, pk=module_id)
    course = module.course
    services.delete_and_renumber(module, course.modules.all())
    messages.success(request, "Module deleted.")
    return redirect("course_builder:course", course.pk)


# ─────────────────────────── Content-sheet import ───────────────────────────

IMPORT_MAX_BYTES = 5 * 1024 * 1024
_IMPORT_SESSION_KEY = "course_sheet_import"


def _named(raw, name):
    buffer = io.BytesIO(raw)
    buffer.name = name
    return buffer


def _digest(pending):
    return hashlib.sha256(f"{pending['tab']}|{pending['data']}".encode()).hexdigest()


@staff_required
def sheet_import(request):
    """
    Upload the course workbook → pick a tab → dry-run report → Apply.
    The file waits in the session between steps (nothing touches the ephemeral disk),
    and Apply only runs on the exact file + tab that passed the dry run.
    """
    pending = request.session.get(_IMPORT_SESSION_KEY)
    report = None
    action = request.POST.get("action") if request.method == "POST" else None

    if action == "upload":
        request.session.pop(_IMPORT_SESSION_KEY, None)
        pending = None
        upload = request.FILES.get("file")
        if not upload or not upload.name.lower().endswith((".xlsx", ".csv")):
            messages.error(request, "Choose the course workbook (.xlsx) or one tab saved as .csv.")
        elif upload.size > IMPORT_MAX_BYTES:
            messages.error(request, "That file is over 5 MB. Download just the tabs you need.")
        else:
            raw = upload.read()
            try:
                tabs = sheet_importer.list_tabs(_named(raw, upload.name))
            except Exception:
                tabs = []
                messages.error(request, "That file could not be read as a spreadsheet.")
            if tabs:
                pending = {"name": upload.name, "data": base64.b64encode(raw).decode(), "tabs": tabs,
                           "tab": tabs[0], "checked": False}
                request.session[_IMPORT_SESSION_KEY] = pending

    elif action == "check" and pending:
        tab = request.POST.get("tab", "")
        if tab not in pending["tabs"]:
            messages.error(request, "Pick one of the tabs in the file.")
        else:
            pending.update(tab=tab, checked=False)
            report = sheet_importer.import_sheet(_named(base64.b64decode(pending["data"]), pending["name"]),
                                                 tab=None if tab == "(CSV file)" else tab,
                                                 owner=request.user, dry_run=True)
            pending["checked"] = report.ok
            request.session[_IMPORT_SESSION_KEY] = pending

    elif action == "apply" and pending:
        if not pending.get("checked") or request.POST.get("digest") != _digest(pending):
            messages.error(request, "Check the file again before applying it.")
            return redirect("course_builder:sheet_import")
        tab = pending["tab"]
        report = sheet_importer.import_sheet(_named(base64.b64decode(pending["data"]), pending["name"]),
                                             tab=None if tab == "(CSV file)" else tab,
                                             owner=request.user, dry_run=False)
        if report.applied:
            request.session.pop(_IMPORT_SESSION_KEY, None)
            messages.success(request, f"Imported {report.course.title} from {pending['name']} ({tab}).")
            return redirect("course_builder:course", report.course.pk)
        pending["checked"] = False
        request.session[_IMPORT_SESSION_KEY] = pending

    elif action == "reset":
        request.session.pop(_IMPORT_SESSION_KEY, None)
        return redirect("course_builder:sheet_import")

    return render(request, "courses/builder/sheet_import.html", {
        "pending": pending, "report": report,
        "digest": _digest(pending) if pending and pending.get("checked") else "",
        "crumbs": [("Courses", reverse("course_builder:course_list")), ("Import from sheet", "")],
    })


# ─────────────────────────── Outcomes ───────────────────────────


@staff_required
@require_POST
def outcome_create(request, module_id):
    module = get_object_or_404(Module, pk=module_id)
    form = OutcomeForm(request.POST, module=module)
    if form.is_valid():
        form.save()
        messages.success(request, "Outcome added.")
    else:
        messages.error(request, "Outcome not added: " + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect(reverse("course_builder:module", args=[module.pk]) + "#outcomes")


@staff_required
@require_POST
def outcome_delete(request, outcome_id):
    outcome = get_object_or_404(LearningOutcome, pk=outcome_id)
    module_id = outcome.module_id
    outcome.delete()
    messages.success(request, "Outcome removed; steps and questions tagged with it are now untagged.")
    return redirect(reverse("course_builder:module", args=[module_id]) + "#outcomes")


# ─────────────────────────── Lessons ───────────────────────────


@staff_required
@require_POST
def lesson_create(request, module_id):
    module = get_object_or_404(Module, pk=module_id)
    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, "Give the lesson a title.")
        return redirect("course_builder:module", module.pk)
    lesson = Lesson.objects.create(module=module, title=title[:200],
                                   position=services.next_position(module.lessons.all()))
    return redirect("course_builder:lesson", lesson.pk)


@staff_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related("module__course"), pk=lesson_id)
    form = LessonForm(request.POST or None, instance=lesson)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lesson saved.")
        return redirect("course_builder:lesson", lesson.pk)
    steps = list(services.lesson_steps(lesson))
    for step in steps:
        step.problems = step.publish_problems()
    present = {s.step_type for s in steps}
    return render(request, "courses/builder/lesson_detail.html", {
        "lesson": lesson, "module": lesson.module, "course": lesson.module.course, "form": form,
        "steps": steps, "step_types": STEP_TYPES.values(), "present_types": present,
        "crumbs": _crumbs(lesson.module.course, lesson.module, lesson),
    })


@staff_required
@require_POST
def lesson_delete(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    module = lesson.module
    services.delete_and_renumber(lesson, module.lessons.all())
    messages.success(request, "Lesson deleted.")
    return redirect("course_builder:module", module.pk)


@staff_required
def lesson_preview(request, lesson_id):
    lesson = get_object_or_404(Lesson.objects.select_related("module__course"), pk=lesson_id)
    steps = prepare_steps(list(services.lesson_steps(lesson).prefetch_related(*STEP_PREFETCH)), reveal_answers=True)
    return render(request, "courses/builder/lesson_preview.html", {
        "lesson": lesson, "module": lesson.module, "course": lesson.module.course, "steps": steps,
        "crumbs": _crumbs(lesson.module.course, lesson.module, lesson),
    })


# ─────────────────────────── Steps ───────────────────────────


@staff_required
@require_POST
def step_create(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    step_type = request.POST.get("step_type")
    if step_type not in STEP_TYPES:
        raise Http404("Unknown step type")
    step = LessonStep.objects.create(lesson=lesson, step_type=step_type, title=STEP_TYPES[step_type].label,
                                     position=services.next_position(lesson.steps.all()))
    return redirect("course_builder:step", step.pk)


@staff_required
def step_edit(request, step_id):
    step = get_object_or_404(LessonStep.objects.select_related("lesson__module__course", "coding_question"), pk=step_id)
    form_class = STEP_FORMS[step.step_type]
    form = form_class(request.POST or None, step=step)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Step saved.")
        return redirect("course_builder:step", step.pk)
    lesson = step.lesson
    questions = step.questions.select_related("mcq", "outcome").order_by("position") if step.spec.uses_mcqs else []
    special = {"title", "required", "outcomes", "coding_question", "hint_1", "hint_2", "hint_3"}
    return render(request, "courses/builder/step_edit.html", {
        "step": step, "spec": step.spec, "form": form, "lesson": lesson, "module": lesson.module,
        "typed_fields": [form[name] for name in form.fields if name not in special],
        "hint_fields": [form[name] for name in ("hint_1", "hint_2", "hint_3") if name in form.fields],
        "course": lesson.module.course, "questions": questions,
        "module_outcomes": LearningOutcome.objects.filter(module=lesson.module).order_by("code"),
        "problems": step.publish_problems(),
        "crumbs": _crumbs(lesson.module.course, lesson.module, lesson) + [(f"Step {step.position}", "")],
    })


@staff_required
@require_POST
def step_delete(request, step_id):
    step = get_object_or_404(LessonStep, pk=step_id)
    lesson = step.lesson
    services.delete_and_renumber(step, lesson.steps.all())
    messages.success(request, "Step deleted.")
    return redirect("course_builder:lesson", lesson.pk)


# ─────────────────────────── Step questions (QUIZ / PREDICT) ───────────────────────────


@staff_required
@require_POST
def step_question_add(request, step_id):
    step = get_object_or_404(LessonStep, pk=step_id)
    mcq = get_object_or_404(McqQuestion, pk=request.POST.get("mcq_id"), is_active=True)
    if not step.spec.uses_mcqs:
        return JsonResponse({"error": "This step type doesn't take MCQs."}, status=400)
    duplicate = JsonResponse({"error": "That question is already on this step."}, status=400)
    if step.questions.filter(mcq=mcq).exists():
        return duplicate
    try:
        with transaction.atomic():  # savepoint: a race still can't poison the request transaction
            sq = StepQuestion.objects.create(step=step, mcq=mcq, position=services.next_position(step.questions.all()))
    except IntegrityError:
        return duplicate
    return JsonResponse({"ok": True, "id": sq.pk})


@staff_required
@require_POST
def step_question_update(request, question_id):
    sq = get_object_or_404(StepQuestion.objects.select_related("step__lesson"), pk=question_id)
    outcome_id = request.POST.get("outcome_id") or None
    if outcome_id and not LearningOutcome.objects.filter(pk=outcome_id, module_id=sq.step.lesson.module_id).exists():
        return JsonResponse({"error": "Pick an outcome from this module."}, status=400)
    sq.outcome_id = outcome_id
    sq.save(update_fields=["outcome"])
    return JsonResponse({"ok": True})


@staff_required
@require_POST
def step_question_remove(request, question_id):
    sq = get_object_or_404(StepQuestion, pk=question_id)
    step = sq.step
    services.delete_and_renumber(sq, step.questions.all())
    return JsonResponse({"ok": True})


# ─────────────────────────── Reorder + search APIs ───────────────────────────

_REORDERABLE = {
    "modules": (Course, lambda parent: parent.modules.all()),
    "lessons": (Module, lambda parent: parent.lessons.all()),
    "steps": (Lesson, lambda parent: parent.steps.all()),
    "questions": (LessonStep, lambda parent: parent.questions.all()),
}


@staff_required
@require_POST
def reorder(request, kind, parent_id):
    if kind not in _REORDERABLE:
        raise Http404
    parent_model, children = _REORDERABLE[kind]
    parent = get_object_or_404(parent_model, pk=parent_id)
    try:
        ids = json.loads(request.body or "{}").get("ids", [])
        services.reorder(children(parent), ids)
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "Invalid order."}, status=400)
    return JsonResponse({"ok": True})


@staff_required
@require_GET
def search_questions(request):
    kind = request.GET.get("type", "mcq")
    q = request.GET.get("q", "").strip()
    if kind == "coding":
        qs = CodingQuestion.objects.filter(is_active=True)
        if request.GET.get("mode"):
            qs = qs.filter(coding_mode=request.GET["mode"])
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(topic__icontains=q))
        rows = [{"id": c.pk, "title": c.title, "meta": f"{c.get_coding_mode_display()} · {c.topic} · {c.get_difficulty_display()}"}
                for c in qs.order_by("title")[:20]]
    else:
        qs = McqQuestion.objects.filter(is_active=True)
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(topic__icontains=q) | Q(statement__icontains=q))
        rows = [{"id": m.pk, "title": m.title, "meta": f"{m.topic} · {m.get_difficulty_display()}"}
                for m in qs.order_by("-created_at")[:20]]
    return JsonResponse({"results": rows})
