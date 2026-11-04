import hmac
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from submissions.judge import (
    _code_reads_input,
    comparable_case_text,
    is_code_safe,
    normalize_case_text,
    run_code as execute_code,
)

from .forms import (
    AssessmentDetailsForm,
    AssessmentForm,
    AssessmentQuestionAddForm,
    AssessmentSectionForm,
    CodingQuestionForm,
    CodingQuestionLanguageFormSet,
    CodingTestCaseFormSet,
    McqOptionFormSet,
    McqQuestionForm,
)
from .imports import (
    ImportFileError,
    build_import_template,
    import_question_candidates,
    parse_question_file,
)
from .models import (
    Assessment,
    AssessmentModerator,
    AssessmentQuestion,
    AssessmentQuestionSnapshot,
    AssessmentSectionResult,
    AssessmentResult,
    AssessmentSection,
    AssessmentSectionSnapshot,
    AssessmentSubmission,
    AssessmentSubmissionResult,
    Attempt,
    AttemptAuthorization,
    AttemptAnswer,
    AttemptAnswerOption,
    AttemptEvent,
    AttemptQuestionState,
    AttemptSectionState,
    AssessmentVersion,
    CodeDraft,
    CodingQuestionLanguageSnapshot,
    CodingQuestionSnapshot,
    CodingTestCaseSnapshot,
    CodingQuestion,
    McqOptionSnapshot,
    McqQuestion,
    McqQuestionSnapshot,
    Participant,
    ProgrammingLanguage,
    ViolationLog,
)
def _require_management_access(user):
    if not (user.is_staff or user.is_faculty):
        raise PermissionDenied


def _require_assessment_management_access(user):
    if (
        user.is_staff
        or user.is_faculty
        or Assessment.objects.filter(created_by=user).exists()
        or AssessmentModerator.objects.filter(user=user).exists()
    ):
        return
    raise PermissionDenied


def _managed_assessments(user):
    assessments = Assessment.objects.all()
    if user.is_staff:
        return assessments
    return assessments.filter(
        Q(created_by=user) | Q(moderators__user=user)
    ).distinct()


def _managed_questions(model, user):
    questions = model.objects.all()
    if not user.is_staff:
        questions = questions.filter(owner=user)
    return questions


QUESTION_BANK_GROUPS = (
    ("coding", "Coding questions"),
    ("programming_mcq", "Programming MCQ"),
    ("aptitude", "Aptitude"),
    ("quant", "Quant"),
    ("reasoning", "Reasoning"),
    ("other", "Other"),
)


def _question_bank_queryset(user, group):
    if group == "coding":
        return "coding", _managed_questions(CodingQuestion, user)
    if group == "programming_mcq":
        return "mcq", _managed_questions(McqQuestion, user).filter(
            Q(question_type=McqQuestion.QuestionType.PROGRAMMING)
            | Q(category=McqQuestion.Category.PROGRAMMING)
        )
    if group in {
        McqQuestion.Category.APTITUDE,
        McqQuestion.Category.QUANT,
        McqQuestion.Category.REASONING,
        McqQuestion.Category.PROGRAMMING,
    }:
        return "mcq", _managed_questions(McqQuestion, user).filter(category=group)
    if group == "other":
        return "mcq", _managed_questions(McqQuestion, user).exclude(
            category__in=[
                McqQuestion.Category.APTITUDE,
                McqQuestion.Category.QUANT,
                McqQuestion.Category.REASONING,
                McqQuestion.Category.PROGRAMMING,
            ]
        ).exclude(question_type=McqQuestion.QuestionType.PROGRAMMING)
    return "coding", _managed_questions(CodingQuestion, user)


def _filter_question_bank(queryset, model_type, query, topic, subtopic):
    if query:
        search_fields = (
            Q(title__icontains=query)
            | Q(topic__icontains=query)
            | Q(statement__icontains=query)
        )
        search_fields |= (
            Q(subtopic__icontains=query)
            if model_type == "coding"
            else Q(sub_topic__icontains=query)
        )
        queryset = queryset.filter(search_fields)
    if topic:
        queryset = queryset.filter(topic__iexact=topic)
    if subtopic:
        queryset = (
            queryset.filter(subtopic__iexact=subtopic)
            if model_type == "coding"
            else queryset.filter(sub_topic__iexact=subtopic)
        )
    return queryset


def _question_bank_payload(queryset, model_type):
    rows = []
    for question in queryset.order_by("title"):
        if model_type == "coding":
            subtopic = question.subtopic
            question_type = "Coding"
            edit_url = reverse(
                "assessment:coding_question_edit",
                args=[question.pk],
            )
        else:
            subtopic = question.sub_topic
            question_type = (
                "Programming MCQ"
                if (
                    question.question_type == McqQuestion.QuestionType.PROGRAMMING
                    or question.category == McqQuestion.Category.PROGRAMMING
                )
                else question.get_category_display()
            )
            edit_url = reverse(
                "assessment:mcq_question_edit",
                args=[question.pk],
            )
        rows.append(
            {
                "id": f"{model_type}-{question.pk}",
                "title": question.title,
                "topic": question.topic,
                "subtopic": subtopic,
                "question_type": question_type,
                "edit_url": edit_url,
            }
        )
    return rows


def _post_data(request):
    return request.POST if request.method == "POST" else None


def _assessment_or_404(request, assessment_id):
    return get_object_or_404(_managed_assessments(request.user), pk=assessment_id)


def _section_or_404(request, assessment_id, section_id):
    assessment = _assessment_or_404(request, assessment_id)
    section = get_object_or_404(
        AssessmentSection.objects.select_related("assessment"),
        pk=section_id,
        assessment=assessment,
    )
    return assessment, section


def _assessment_context(assessment):
    return {
        "assessment": assessment,
        "question_count": assessment.assessment_questions.count(),
        "sections": assessment.sections.prefetch_related(
            "questions__mcq_question__options",
            "questions__coding_question__supported_languages",
        ),
        "assignments": assessment.assessment_questions.select_related(
            "section",
            "mcq_question",
            "coding_question",
        ).order_by("section__position", "position"),
        "moderators": assessment.moderators.select_related("user").order_by(
            "user__user_name"
        ),
    }


def _attempt_duration_seconds(attempt):
    if attempt.submitted_at is None:
        return 0
    return max(0, int((attempt.submitted_at - attempt.started_at).total_seconds()))


def _format_duration(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _assessment_leaderboard(assessment):
    results = (
        AssessmentResult.objects.filter(
            assessment=assessment,
            evaluation_status=AssessmentResult.EvaluationStatus.FINALIZED,
            attempt__participant__assessment=assessment,
            attempt__status=Attempt.Status.SUBMITTED,
            attempt__submitted_at__isnull=False,
        )
        .select_related("attempt", "attempt__participant__user")
        .order_by("attempt__submitted_at", "attempt__attempt_number")
    )
    best_results = {}
    for result in results:
        attempt = result.attempt
        participant_id = attempt.participant_id
        duration = _attempt_duration_seconds(attempt)
        previous = best_results.get(participant_id)
        result_key = (-result.total_score, duration, attempt.submitted_at, attempt.attempt_number)
        if previous is None or result_key < previous["sort_key"]:
            best_results[participant_id] = {
                "result": result,
                "attempt": attempt,
                "user": attempt.participant.user,
                "duration_seconds": duration,
                "sort_key": result_key,
            }

    leaderboard = sorted(
        best_results.values(),
        key=lambda row: (
            row["sort_key"],
            row["user"].user_name.casefold(),
        ),
    )
    previous_rank_key = None
    current_rank = 0
    for index, row in enumerate(leaderboard, start=1):
        rank_key = (row["result"].total_score, row["duration_seconds"])
        if rank_key != previous_rank_key:
            current_rank = index
            previous_rank_key = rank_key
        row["rank"] = current_rank
        row["time_taken"] = _format_duration(row["duration_seconds"])
        row["profile_url"] = reverse(
            "users:profile",
            args=[row["user"].user_name],
        )
        row["details_url"] = (
            f"{reverse('assessment:assessment_detail', args=[assessment.pk])}"
            f"?tab=leaderboard&user={row['user'].pk}#participant-details"
        )
    return leaderboard


def _assessment_submission_row(kind, item):
    attempt = item.attempt
    snapshot = item.assessment_question_snapshot
    if kind == "coding":
        question_title = snapshot.coding_snapshot.title
        status = item.get_status_display()
        submitted_at = item.submitted_at
        key = f"coding-{item.pk}"
    else:
        question_title = snapshot.mcq_snapshot.title
        status = (
            "Accepted"
            if item.is_correct is True
            else "Wrong Answer"
            if item.is_correct is False
            else "Submitted"
        )
        submitted_at = item.answered_at
        key = f"answer-{item.pk}"

    return {
        "key": key,
        "kind": kind,
        "item": item,
        "username": attempt.participant.user.user_name,
        "question_title": question_title,
        "submission_type": "Coding" if kind == "coding" else "MCQ",
        "status": status,
        "submitted_at": submitted_at,
    }


def _assessment_submission_rows(assessment):
    coding_submissions = (
        AssessmentSubmission.objects.filter(
            attempt__participant__assessment=assessment,
        )
        .select_related(
            "attempt__participant__user",
            "assessment_question_snapshot__coding_snapshot",
        )
    )
    mcq_answers = (
        AttemptAnswer.objects.filter(
            attempt__participant__assessment=assessment,
            assessment_question_snapshot__mcq_snapshot__isnull=False,
        )
        .filter(
            Q(text_answer__gt="")
            | Q(code_answer__gt="")
            | Q(selected_options__isnull=False)
        )
        .select_related(
            "attempt__participant__user",
            "assessment_question_snapshot__mcq_snapshot",
        )
        .distinct()
    )
    rows = [
        _assessment_submission_row("coding", submission)
        for submission in coding_submissions
    ]
    rows.extend(_assessment_submission_row("answer", answer) for answer in mcq_answers)
    return sorted(rows, key=lambda row: row["submitted_at"], reverse=True)


def _assessment_submission_history(assessment, selected_row):
    item = selected_row["item"]
    user_id = item.attempt.participant.user_id
    snapshot_id = item.assessment_question_snapshot_id
    if selected_row["kind"] == "coding":
        history_items = (
            AssessmentSubmission.objects.filter(
                attempt__participant__assessment=assessment,
                attempt__participant__user_id=user_id,
                assessment_question_snapshot_id=snapshot_id,
            )
            .select_related(
                "attempt__participant__user",
                "assessment_question_snapshot__coding_snapshot",
            )
        )
        kind = "coding"
    else:
        history_items = (
            AttemptAnswer.objects.filter(
                attempt__participant__assessment=assessment,
                attempt__participant__user_id=user_id,
                assessment_question_snapshot_id=snapshot_id,
            )
            .filter(
                Q(text_answer__gt="")
                | Q(code_answer__gt="")
                | Q(selected_options__isnull=False)
            )
            .select_related(
                "attempt__participant__user",
                "assessment_question_snapshot__mcq_snapshot",
            )
            .distinct()
        )
        kind = "answer"
    rows = [_assessment_submission_row(kind, history_item) for history_item in history_items]
    return sorted(rows, key=lambda row: row["submitted_at"], reverse=True)


@login_required
def dashboard(request):
    _require_assessment_management_access(request.user)
    active_tab = request.GET.get("tab", "assessments")
    if active_tab not in {"assessments", "questions"}:
        active_tab = "assessments"
    query = request.GET.get("q", "").strip()
    context = {"active_tab": active_tab, "query": query}
    if active_tab == "assessments":
        assessments = _managed_assessments(request.user).select_related(
            "created_by"
        ).prefetch_related("sections")
        if query:
            assessments = assessments.filter(
                Q(name__icontains=query) | Q(slug__icontains=query)
            )
        context["page_obj"] = Paginator(assessments, 25).get_page(
            request.GET.get("page", 1)
        )
    else:
        question_group = request.GET.get("question_group", "coding")
        if question_group not in {value for value, _ in QUESTION_BANK_GROUPS}:
            question_group = "coding"
        topic = request.GET.get("topic", "").strip()
        subtopic = request.GET.get("subtopic", "").strip()
        model_type, base_questions = _question_bank_queryset(
            request.user,
            question_group,
        )
        questions = _filter_question_bank(
            base_questions,
            model_type,
            query,
            topic,
            subtopic,
        )
        topic_field = "topic"
        subtopic_field = "subtopic" if model_type == "coding" else "sub_topic"
        topic_options = list(
            base_questions.order_by(topic_field)
            .values_list(topic_field, flat=True)
            .distinct()
        )
        subtopic_questions = (
            base_questions.filter(topic__iexact=topic)
            if topic
            else base_questions
        )
        subtopic_options = list(
            subtopic_questions.order_by(subtopic_field)
            .values_list(subtopic_field, flat=True)
            .distinct()
        )
        question_rows = _question_bank_payload(questions, model_type)
        context.update(
            {
                "question_group": question_group,
                "question_groups": QUESTION_BANK_GROUPS,
                "topic": topic,
                "subtopic": subtopic,
                "topic_options": [value for value in topic_options if value],
                "subtopic_options": [value for value in subtopic_options if value],
                "question_rows": question_rows,
                "question_count": len(question_rows),
                "can_create_questions": request.user.is_staff
                or request.user.is_faculty,
            }
        )
    return render(
        request,
        "assessment/dashboard.html",
        context,
    )


@login_required
def question_bank_search(request):
    _require_assessment_management_access(request.user)
    group = request.GET.get("group", "coding")
    if group not in {value for value, _ in QUESTION_BANK_GROUPS}:
        return JsonResponse({"error": "Choose a valid question category."}, status=400)

    query = request.GET.get("q", "").strip()
    topic = request.GET.get("topic", "").strip()
    subtopic = request.GET.get("subtopic", "").strip()
    model_type, base_questions = _question_bank_queryset(request.user, group)
    filtered_questions = _filter_question_bank(
        base_questions,
        model_type,
        query,
        topic,
        subtopic,
    )
    topic_field = "topic"
    subtopic_field = "subtopic" if model_type == "coding" else "sub_topic"
    subtopic_questions = (
        base_questions.filter(topic__iexact=topic) if topic else base_questions
    )
    topics = list(
        base_questions.order_by(topic_field)
        .values_list(topic_field, flat=True)
        .distinct()
    )
    subtopics = list(
        subtopic_questions.order_by(subtopic_field)
        .values_list(subtopic_field, flat=True)
        .distinct()
    )
    rows = _question_bank_payload(filtered_questions, model_type)
    return JsonResponse(
        {
            "results": rows,
            "topics": [value for value in topics if value],
            "subtopics": [value for value in subtopics if value],
            "count": len(rows),
        }
    )


@login_required
def assessment_create(request):
    _require_management_access(request.user)
    form = AssessmentForm(_post_data(request))
    form.fields["status"].initial = Assessment.Status.DRAFT
    form.fields["status"].disabled = True
    if request.method == "POST" and form.is_valid():
        assessment = form.save(commit=False)
        assessment.created_by = request.user
        assessment.status = Assessment.Status.DRAFT
        assessment.save()
        messages.success(request, "Assessment created.")
        return redirect("assessment:assessment_detail", assessment_id=assessment.pk)
    return render(
        request,
        "assessment/assessment_form.html",
        {"form": form, "mode": "create"},
    )


@login_required
def assessment_detail(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    return _assessment_detail_page(request, assessment)


@login_required
def assessment_detail_by_slug(request, assessment_slug):
    assessment = get_object_or_404(
        _managed_assessments(request.user),
        slug=assessment_slug,
    )
    return _assessment_detail_page(request, assessment)


def _published_assessment_version(assessment):
    return (
        AssessmentVersion.objects.filter(
            assessment=assessment,
            status=AssessmentVersion.Status.PUBLISHED,
        )
        .order_by("-is_current", "-version_number")
        .first()
    )


def _assessment_participant(assessment, user):
    participant = Participant.objects.filter(
        assessment=assessment,
        user=user,
    ).select_related("user").first()
    if participant is None:
        if (
            assessment.status != Assessment.Status.PUBLISHED
            or _published_assessment_version(assessment) is None
        ):
            raise Http404("Assessment registration is unavailable.")
        participant, _ = Participant.objects.get_or_create(
            assessment=assessment,
            user=user,
        )
    if participant.status in {
        Participant.Status.DISQUALIFIED,
        Participant.Status.REMOVED,
    }:
        raise PermissionDenied
    return participant


def _expire_attempt_if_needed(attempt):
    expired = False
    with transaction.atomic():
        locked_attempt = (
            Attempt.objects.select_for_update()
            .get(pk=attempt.pk)
        )
        if locked_attempt.status != Attempt.Status.IN_PROGRESS:
            return False
        now = timezone.now()
        deadline = locked_attempt.expires_at
        version_end = (
            locked_attempt.assessment_version.end_time
            if locked_attempt.assessment_version_id
            else None
        )
        if version_end and (deadline is None or version_end < deadline):
            deadline = version_end
        if deadline is None or now <= deadline + timedelta(seconds=3):
            return False
        expired = True
    if expired:
        _finalize_exam_attempt(attempt, timed_out=True)
        attempt.refresh_from_db()
    return expired


def _assessment_attempt_state(participant):
    attempt = (
        participant.attempts.select_related("assessment_version")
        .order_by("-attempt_number")
        .first()
    )
    if attempt:
        _expire_attempt_if_needed(attempt)
        attempt.refresh_from_db()
    return attempt


def _attempt_payload(attempt):
    now = timezone.now()
    remaining_seconds = 0
    if attempt.status == Attempt.Status.IN_PROGRESS and attempt.expires_at:
        remaining_seconds = max(
            0,
            int((attempt.expires_at - now).total_seconds()),
        )
    return {
        "id": str(attempt.pk),
        "status": attempt.status,
        "attempt_number": attempt.attempt_number,
        "expires_at": attempt.expires_at.isoformat() if attempt.expires_at else None,
        "server_time": now.isoformat(),
        "remaining_seconds": remaining_seconds,
        "session_id": str(attempt.active_session_id),
    }


def _assessment_section_summary(version):
    rows = []
    total_marks = 0
    total_negative_marks = 0
    for section in version.section_snapshots.prefetch_related(
        "questions__mcq_snapshot",
        "questions__coding_snapshot",
    ):
        questions = list(section.questions.all())
        has_mcq = any(question.mcq_snapshot_id for question in questions)
        has_coding = any(question.coding_snapshot_id for question in questions)
        if has_mcq and has_coding:
            question_type = "MCQ and Coding"
        elif has_coding:
            question_type = "Coding"
        else:
            question_type = "MCQ"
        marks = sum(question.max_score for question in questions)
        negative_marks = sum(question.negative_marks for question in questions)
        total_marks += marks
        total_negative_marks += negative_marks
        rows.append(
            {
                "title": section.title,
                "question_type": question_type,
                "question_count": len(questions),
                "marks": marks,
                "time_limit_minutes": section.time_limit_minutes,
            }
        )
    return rows, total_marks, total_negative_marks


def _publish_assessment(assessment, user):
    with transaction.atomic():
        assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
        if assessment.status == Assessment.Status.ARCHIVED:
            return None, ["Archived assessments cannot be published."]
        if assessment.end_time and assessment.end_time <= timezone.now():
            return None, ["The assessment end time must be in the future."]
        if (
            assessment.start_time
            and assessment.end_time
            and assessment.start_time >= assessment.end_time
        ):
            return None, ["The assessment start time must be earlier than its end time."]

        sections = list(
            assessment.sections.prefetch_related(
                "questions__mcq_question__options",
                "questions__mcq_question__programming_language",
                "questions__coding_question__supported_languages__language",
                "questions__coding_question__test_cases",
            ).order_by("position")
        )
        if not sections:
            return None, ["Add at least one section before publishing."]
        if any(not section.questions.all() for section in sections):
            return None, ["Add at least one question to every section before publishing."]

        total_marks = sum(
            assignment.max_score
            for section in sections
            for assignment in section.questions.all()
        )
        if assessment.passing_marks > total_marks:
            return None, ["Passing marks cannot exceed the assessment's total marks."]

        for section in sections:
            for assignment in section.questions.all():
                if assignment.mcq_question_id:
                    options = list(assignment.mcq_question.options.all())
                    correct_count = sum(option.is_correct for option in options)
                    if len(options) < 2:
                        return None, [
                            f"MCQ “{assignment.mcq_question.title}” needs at least two options."
                        ]
                    if assignment.mcq_question.allow_multiple:
                        if correct_count < 1:
                            return None, [
                                f"MCQ “{assignment.mcq_question.title}” needs a correct option."
                            ]
                    elif correct_count != 1:
                        return None, [
                            f"MCQ “{assignment.mcq_question.title}” must have exactly one correct option."
                        ]
                else:
                    coding_question = assignment.coding_question
                    if not coding_question.supported_languages.all():
                        return None, [
                            f"Coding question “{coding_question.title}” needs a supported language."
                        ]
                    if not coding_question.test_cases.all():
                        return None, [
                            f"Coding question “{coding_question.title}” needs at least one test case."
                        ]

        now = timezone.now()
        version_number = (
            assessment.versions.aggregate(max_number=Max("version_number"))[
                "max_number"
            ]
            or 0
        ) + 1
        AssessmentVersion.objects.filter(
            assessment=assessment,
            is_current=True,
        ).update(is_current=False)
        version = AssessmentVersion.objects.create(
            assessment=assessment,
            version_number=version_number,
            status=AssessmentVersion.Status.PUBLISHED,
            is_current=True,
            name=assessment.name,
            description=assessment.description,
            start_time=assessment.start_time,
            end_time=assessment.end_time,
            duration_minutes=assessment.duration_minutes,
            passing_marks=assessment.passing_marks,
            max_attempts=assessment.max_attempts,
            allow_paste_in_editor=assessment.allow_paste_in_editor,
            result_release_policy=assessment.result_release_policy,
            results_release_at=assessment.results_release_at,
            published_at=now,
            published_by=user,
        )

        for section in sections:
            section_snapshot = AssessmentSectionSnapshot.objects.create(
                version=version,
                source_section=section,
                title=section.title,
                instructions=section.instructions,
                position=section.position,
                time_limit_minutes=section.time_limit_minutes,
            )
            for assignment in section.questions.all():
                snapshot_fields = {
                    "section": section_snapshot,
                    "source_assessment_question": assignment,
                    "position": assignment.position,
                    "max_score": assignment.max_score,
                    "negative_marks": assignment.negative_marks,
                }
                if assignment.mcq_question_id:
                    question = assignment.mcq_question
                    mcq_snapshot = McqQuestionSnapshot.objects.create(
                        version=version,
                        source_question=question,
                        title=question.title,
                        question_type=question.question_type,
                        category=question.category,
                        topic=question.topic,
                        sub_topic=question.sub_topic,
                        difficulty=question.difficulty,
                        statement=question.statement,
                        code_snippet=question.code_snippet,
                        explanation=question.explanation,
                        allow_multiple=question.allow_multiple,
                        programming_language_name=(
                            question.programming_language.name
                            if question.programming_language_id
                            else ""
                        ),
                    )
                    McqOptionSnapshot.objects.bulk_create(
                        [
                            McqOptionSnapshot(
                                question=mcq_snapshot,
                                text=option.text,
                                is_correct=option.is_correct,
                                position=option.position,
                            )
                            for option in question.options.all()
                        ]
                    )
                    snapshot_fields["mcq_snapshot"] = mcq_snapshot
                else:
                    question = assignment.coding_question
                    coding_snapshot = CodingQuestionSnapshot.objects.create(
                        version=version,
                        source_question=question,
                        title=question.title,
                        coding_mode=question.coding_mode,
                        topic=question.topic,
                        subtopic=question.subtopic,
                        difficulty=question.difficulty,
                        statement=question.statement,
                        input_format=question.input_format,
                        output_format=question.output_format,
                        constraints_text=question.constraints_text,
                        explanation=question.explanation,
                        time_limit_seconds=question.time_limit_seconds,
                        memory_limit_kb=question.memory_limit_kb,
                    )
                    CodingQuestionLanguageSnapshot.objects.bulk_create(
                        [
                            CodingQuestionLanguageSnapshot(
                                question=coding_snapshot,
                                language=question_language.language,
                                language_name=question_language.language.name,
                                language_slug=question_language.language.slug,
                                judge0_language_id=(
                                    question_language.language.judge0_language_id
                                ),
                                starter_code=question_language.starter_code,
                                buggy_code=question_language.buggy_code,
                            )
                            for question_language in question.supported_languages.all()
                        ]
                    )
                    CodingTestCaseSnapshot.objects.bulk_create(
                        [
                            CodingTestCaseSnapshot(
                                question=coding_snapshot,
                                source_test_case=test_case,
                                input_data=test_case.input_data,
                                expected_output=test_case.expected_output,
                                is_sample=test_case.is_sample,
                                weight=test_case.weight,
                                position=test_case.position,
                                explanation=test_case.explanation,
                            )
                            for test_case in question.test_cases.all()
                        ]
                    )
                    snapshot_fields["coding_snapshot"] = coding_snapshot
                AssessmentQuestionSnapshot.objects.create(**snapshot_fields)

        assessment.status = Assessment.Status.PUBLISHED
        assessment.save(update_fields=["status", "updated_at"])
    return version, []


@login_required
def assessment_view(request, assessment_slug):
    assessment = get_object_or_404(Assessment, slug=assessment_slug)
    participant = (
        Participant.objects.filter(assessment=assessment, user=request.user)
        .select_related("user")
        .first()
    )
    if participant is None:
        if assessment.status != Assessment.Status.PUBLISHED:
            message = (
                "This assessment has not been published by its organizer yet."
            )
            return render(
                request,
                "assessment/assessment_unavailable.html",
                {"assessment": assessment, "message": message},
                status=403,
            )
        if _published_assessment_version(assessment) is None:
            message = (
                "This assessment does not have a published version yet. "
                "Please contact its organizer."
            )
            return render(
                request,
                "assessment/assessment_unavailable.html",
                {"assessment": assessment, "message": message},
                status=403,
            )
        participant, _ = Participant.objects.get_or_create(
            assessment=assessment,
            user=request.user,
            defaults={"status": Participant.Status.REGISTERED},
        )
    if participant.status in {
        Participant.Status.DISQUALIFIED,
        Participant.Status.REMOVED,
    }:
        return render(
            request,
            "assessment/assessment_unavailable.html",
            {
                "assessment": assessment,
                "message": (
                    "Your access to this assessment has been blocked or removed. "
                    "Please contact its organizer if you think this is a mistake."
                ),
            },
            status=403,
        )
    attempt = _assessment_attempt_state(participant)
    version = (
        attempt.assessment_version
        if attempt and attempt.assessment_version_id
        else _published_assessment_version(assessment)
    )
    sections, total_marks, total_negative_marks = (
        _assessment_section_summary(version)
        if version
        else ([], 0, 0)
    )
    now = timezone.now()
    start_time = version.start_time if version else assessment.start_time
    end_time = version.end_time if version else assessment.end_time
    is_published = (
        assessment.status == Assessment.Status.PUBLISHED
        and version is not None
    )
    extra_attempts = (
        participant.attempt_authorizations.aggregate(extra=Sum("extra_attempts"))[
            "extra"
        ]
        or 0
    )
    allowed_attempts = (
        version.max_attempts + extra_attempts
        if version
        else assessment.max_attempts + extra_attempts
    )
    attempts_used = participant.attempts.count()
    attempts_remaining = max(0, allowed_attempts - attempts_used)
    warning_limit = max(
        0,
        int(getattr(settings, "ASSESSMENT_PROCTOR_WARNING_LIMIT", 3)),
    )
    violation_count = (
        ViolationLog.objects.filter(attempt=attempt).count()
        if attempt
        else 0
    )
    state = "ready"
    if attempt and attempt.status == Attempt.Status.IN_PROGRESS:
        state = "in_progress"
    elif not is_published:
        state = "not_live"
    elif end_time and now >= end_time:
        state = "expired"
    elif start_time and now < start_time:
        state = "upcoming"
    elif attempt and attempt.status in {
        Attempt.Status.SUBMITTED,
        Attempt.Status.TIMED_OUT,
    }:
        if attempts_remaining == 0:
            state = (
                "submitted"
                if attempt.status == Attempt.Status.SUBMITTED
                else "expired"
            )
    elif attempts_remaining == 0:
        state = "attempt_limit"

    return render(
        request,
        "assessment/assessment_view.html",
        {
            "assessment": assessment,
            "version": version,
            "participant": participant,
            "attempt": attempt,
            "attempt_payload": _attempt_payload(attempt) if attempt else None,
            "assessment_state": state,
            "attempts_used": attempts_used,
            "attempts_allowed": allowed_attempts,
            "attempts_remaining": attempts_remaining,
            "new_attempt_available": (
                state == "ready"
                and attempt is not None
                and attempt.status
                in {
                    Attempt.Status.SUBMITTED,
                    Attempt.Status.TIMED_OUT,
                    Attempt.Status.CANCELLED,
                }
            ),
            "sections": sections,
            "total_marks": total_marks,
            "total_negative_marks": total_negative_marks,
            "passing_marks": version.passing_marks if version else 0,
            "instruction_text": version.description if version else assessment.description,
            "roll_number": getattr(request.user, "roll_number", "") or "Not provided",
            "start_time": start_time,
            "start_countdown_visible": bool(start_time and now < start_time),
            "end_time": end_time,
            "server_time": now.isoformat(),
            "proctor_config": {
                "warningLimit": warning_limit,
                "autoSubmit": bool(
                    getattr(settings, "ASSESSMENT_PROCTOR_AUTO_SUBMIT", True)
                ),
                "logUrl": reverse(
                    "assessment:log_violation",
                    args=[assessment.slug],
                ),
                "attemptId": str(attempt.pk) if attempt else None,
                "warningsRemaining": max(0, warning_limit - violation_count),
                "invigilatorPinEnabled": bool(
                    getattr(settings, "ASSESSMENT_INVIGILATOR_PIN", "")
                ),
            },
        },
    )


def _api_error(message, status):
    return JsonResponse({"error": message}, status=status)


@login_required
@require_POST
def start_attempt(request, assessment_slug):
    assessment = get_object_or_404(Assessment, slug=assessment_slug)
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _api_error("Request body must be valid JSON.", 400)
    if not isinstance(payload, dict):
        return _api_error("Request body must be a JSON object.", 400)
    try:
        client_session_id = uuid.UUID(str(payload["session_id"])) if payload.get("session_id") else uuid.uuid4()
    except (ValueError, TypeError, AttributeError):
        return _api_error("A valid session_id is required.", 400)
    try:
        participant = _assessment_participant(assessment, request.user)
    except Http404:
        return _api_error("You are not registered for this assessment.", 403)
    except PermissionDenied:
        return _api_error("This assessment registration is not active.", 403)

    with transaction.atomic():
        participant = Participant.objects.select_for_update().get(pk=participant.pk)
        attempt = _assessment_attempt_state(participant)
        if attempt and attempt.status == Attempt.Status.IN_PROGRESS:
            attempt.active_session_id = client_session_id
            attempt.save(update_fields=["active_session_id"])
            return JsonResponse({"attempt": _attempt_payload(attempt), "resumed": True})
        if attempt and attempt.active_session_id == client_session_id:
            return _api_error("This assessment attempt has already ended.", 409)
        version = _published_assessment_version(assessment)
        now = timezone.now()
        if (
            assessment.status != Assessment.Status.PUBLISHED
            or version is None
        ):
            return _api_error("This assessment is not live yet.", 409)
        if version.start_time and now < version.start_time:
            return _api_error("This assessment has not started yet.", 409)
        if version.end_time and now >= version.end_time:
            return _api_error("This assessment has expired.", 409)

        extra_attempts = participant.attempt_authorizations.aggregate(
            extra=Sum("extra_attempts")
        )["extra"] or 0
        attempts_used = participant.attempts.count()
        if attempts_used >= version.max_attempts + extra_attempts:
            return _api_error("You have used all allowed attempts.", 409)

        deadline = now + timedelta(minutes=version.duration_minutes)
        if version.end_time:
            deadline = min(deadline, version.end_time)
        attempt, created = Attempt.objects.get_or_create(
            participant=participant,
            attempt_number=attempts_used + 1,
            defaults={
                "assessment_version": version,
                "status": Attempt.Status.IN_PROGRESS,
                "expires_at": deadline,
                "active_session_id": client_session_id,
            },
        )
        if created:
            Participant.objects.filter(pk=participant.pk).update(
                status=Participant.Status.STARTED
            )
            AttemptEvent.objects.create(
                attempt=attempt,
                event_type=AttemptEvent.EventType.STARTED,
                details={"source": "assessment_landing"},
            )
        elif attempt.active_session_id != client_session_id:
            attempt.active_session_id = client_session_id
            attempt.save(update_fields=["active_session_id"])
    return JsonResponse(
        {"attempt": _attempt_payload(attempt), "resumed": not created}
    )


@login_required
@require_GET
def get_attempt_status(request, assessment_slug):
    assessment = get_object_or_404(Assessment, slug=assessment_slug)
    try:
        participant = _assessment_participant(assessment, request.user)
    except Http404:
        return _api_error("You are not registered for this assessment.", 403)
    except PermissionDenied:
        return _api_error("This assessment registration is not active.", 403)
    attempt = _assessment_attempt_state(participant)
    if attempt is None:
        return JsonResponse(
            {
                "attempt": None,
                "violation_count": 0,
                "warnings_remaining": max(
                    0,
                    int(getattr(settings, "ASSESSMENT_PROCTOR_WARNING_LIMIT", 3)),
                ),
            }
        )
    session_id = request.GET.get("session_id")
    try:
        if uuid.UUID(str(session_id)) != attempt.active_session_id:
            return _api_error(
                "This attempt is active in another tab or device.",
                409,
            )
    except (ValueError, TypeError, AttributeError):
        return _api_error("A valid session_id is required.", 400)
    violation_count = ViolationLog.objects.filter(attempt=attempt).count()
    warning_limit = max(
        0,
        int(getattr(settings, "ASSESSMENT_PROCTOR_WARNING_LIMIT", 3)),
    )
    return JsonResponse(
        {
            "attempt": _attempt_payload(attempt),
            "violation_count": violation_count,
            "warnings_remaining": max(0, warning_limit - violation_count),
        }
    )


def _exam_json_body(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _api_error("Request body must be valid JSON.", 400)
    if not isinstance(payload, dict):
        return None, _api_error("Request body must be a JSON object.", 400)
    return payload, None


def _exam_attempt(
    request,
    assessment_slug,
    payload=None,
    claim_session=False,
    allow_finished=False,
):
    assessment = get_object_or_404(Assessment, slug=assessment_slug)
    try:
        participant = _assessment_participant(assessment, request.user)
    except Http404:
        return None, None, _api_error("Assessment access is unavailable.", 403)
    except PermissionDenied:
        return None, None, _api_error("Your assessment access is blocked.", 403)

    payload = payload or {}
    attempt_id = payload.get("attempt_id") or request.GET.get("attempt_id")
    attempt = get_object_or_404(
        Attempt.objects.select_related("assessment_version", "participant"),
        pk=attempt_id,
        participant=participant,
        assessment_version__assessment=assessment,
    )
    finished_statuses = {Attempt.Status.SUBMITTED, Attempt.Status.TIMED_OUT}
    if attempt.status != Attempt.Status.IN_PROGRESS and not (
        allow_finished and attempt.status in finished_statuses
    ):
        return None, None, _api_error("This assessment attempt has ended.", 409)

    session_value = (
        payload.get("session_id")
        or request.headers.get("X-Assessment-Session")
        or request.GET.get("session_id")
    )
    try:
        session_id = uuid.UUID(str(session_value))
    except (ValueError, TypeError, AttributeError):
        return None, None, _api_error("A valid session_id is required.", 400)
    if claim_session:
        Attempt.objects.filter(pk=attempt.pk).update(active_session_id=session_id)
        attempt.active_session_id = session_id
    elif attempt.active_session_id != session_id:
        return None, None, _api_error(
            "This attempt is active in another tab or device.",
            409,
        )

    if attempt.status == Attempt.Status.IN_PROGRESS:
        deadline = attempt.expires_at
        version_end = attempt.assessment_version.end_time
        if version_end and (deadline is None or version_end < deadline):
            deadline = version_end
        now = timezone.now()
        if deadline and now > deadline + timedelta(seconds=3):
            _expire_attempt_if_needed(attempt)
            attempt.refresh_from_db()
            return None, None, _api_error("This assessment attempt has expired.", 409)
    return attempt, assessment, None


def _ensure_section_timer(attempt, section):
    if not section.time_limit_minutes:
        return None
    section_deadline = timezone.now() + timedelta(
        minutes=section.time_limit_minutes
    )
    attempt_deadline = attempt.expires_at or attempt.assessment_version.end_time
    if attempt_deadline:
        section_deadline = min(section_deadline, attempt_deadline)
    state, _ = AttemptSectionState.objects.get_or_create(
        attempt=attempt,
        section=section,
        defaults={"expires_at": section_deadline},
    )
    return state


def _section_time_error(attempt, question):
    section_state = _ensure_section_timer(attempt, question.section)
    if section_state and timezone.now() >= section_state.expires_at:
        return _api_error("This section's time has expired.", 409)
    return None


def _question_answered(attempt_answer, code_drafts, code_submissions):
    if attempt_answer and (
        attempt_answer.text_answer
        or list(attempt_answer.selected_options.all())
        or attempt_answer.code_answer
    ):
        return True
    return any(draft.source_code for draft in code_drafts) or bool(code_submissions)


@login_required
@require_GET
def get_exam_state(request, assessment_slug):
    attempt, _assessment, error = _exam_attempt(
        request,
        assessment_slug,
        claim_session=True,
    )
    if error:
        return error

    version = attempt.assessment_version
    section_rows = list(
        version.section_snapshots.prefetch_related(
            Prefetch(
                "questions",
                queryset=AssessmentQuestionSnapshot.objects.select_related(
                    "mcq_snapshot",
                    "coding_snapshot",
                ),
            )
        ).order_by("position")
    )
    questions = [
        question
        for section in section_rows
        for question in section.questions.all()
    ]
    question_ids = [question.pk for question in questions]
    question_states = {
        state.question_id: state
        for state in AttemptQuestionState.objects.filter(
            attempt=attempt,
            question_id__in=question_ids,
        )
    }
    answers = {
        answer.assessment_question_snapshot_id: answer
        for answer in AttemptAnswer.objects.filter(
            attempt=attempt,
            assessment_question_snapshot_id__in=question_ids,
        ).prefetch_related("selected_options")
    }
    drafts = {}
    for draft in CodeDraft.objects.filter(
        attempt=attempt,
        question_id__in=question_ids,
    ).select_related("language"):
        drafts.setdefault(draft.question_id, []).append(draft)
    submissions = {}
    for question_id in AssessmentSubmission.objects.filter(
        attempt=attempt,
        assessment_question_snapshot_id__in=question_ids,
    ).values_list("assessment_question_snapshot_id", flat=True):
        submissions.setdefault(question_id, True)

    sections = []
    section_states = {
        section_state.section_id: section_state
        for section_state in AttemptSectionState.objects.filter(
            attempt=attempt,
            section__in=section_rows,
        )
    }
    for section in section_rows:
        section_state = section_states.get(section.pk)
        section_questions = []
        answered_count = 0
        marked_count = 0
        for question in section.questions.all():
            state = question_states.get(question.pk)
            answer = answers.get(question.pk)
            question_drafts = drafts.get(question.pk, [])
            is_answered = _question_answered(
                answer,
                question_drafts,
                submissions.get(question.pk),
            )
            answered_count += int(is_answered)
            marked_count += int(bool(state and state.marked_for_review))
            section_questions.append(
                {
                    "id": question.pk,
                    "title": (
                        question.mcq_snapshot.title
                        if question.mcq_snapshot_id
                        else question.coding_snapshot.title
                    ),
                    "type": "mcq" if question.mcq_snapshot_id else "coding",
                    "max_score": str(question.max_score),
                    "visited": bool(state and state.visited),
                    "answered": is_answered,
                    "marked_for_review": bool(state and state.marked_for_review),
                }
            )
        sections.append(
            {
                "id": section.pk,
                "title": section.title,
                "position": section.position,
                "time_limit_minutes": section.time_limit_minutes,
                "expires_at": (
                    section_state.expires_at.isoformat()
                    if section_state
                    else None
                ),
                "expired": bool(
                    section_state and timezone.now() >= section_state.expires_at
                ),
                "answered": answered_count,
                "total": len(section_questions),
                "marked": marked_count,
                "questions": section_questions,
            }
        )
    current_question_id = attempt.current_question_id
    if current_question_id not in question_ids:
        current_question_id = question_ids[0] if question_ids else None
    return JsonResponse(
        {
            "attempt": _attempt_payload(attempt),
            "assessment": version.name,
            "allow_paste_in_editor": version.allow_paste_in_editor,
            "sections": sections,
            "current_section_id": (
                attempt.current_section_id
                or (questions[0].section_id if questions else None)
            ),
            "current_question_id": current_question_id,
            "server_time": timezone.now().isoformat(),
        }
    )


@login_required
@require_GET
def get_exam_question(request, assessment_slug):
    attempt, _assessment, error = _exam_attempt(request, assessment_slug)
    if error:
        return error
    question_id = request.GET.get("question_id")
    question = get_object_or_404(
        AssessmentQuestionSnapshot.objects.select_related(
            "section",
            "mcq_snapshot",
            "coding_snapshot",
        ).prefetch_related(
            "mcq_snapshot__options",
            "coding_snapshot__languages",
            "coding_snapshot__languages__language",
            "coding_snapshot__test_cases",
        ),
        pk=question_id,
        section__version=attempt.assessment_version,
    )
    section_state = _ensure_section_timer(attempt, question.section)
    if section_state and timezone.now() >= section_state.expires_at:
        return _api_error("This section's time has expired.", 409)
    now = timezone.now()
    state, _ = AttemptQuestionState.objects.get_or_create(
        attempt=attempt,
        question=question,
    )
    state.visited = True
    state.last_visited = now
    state.save(update_fields=["visited", "last_visited"])
    attempt.current_section = question.section
    attempt.current_question = question
    attempt.save(update_fields=["current_section", "current_question"])

    answer = (
        AttemptAnswer.objects.filter(
            attempt=attempt,
            assessment_question_snapshot=question,
        )
        .prefetch_related("selected_options")
        .first()
    )
    if question.mcq_snapshot_id:
        question_data = {
                "id": question.pk,
                "section_id": question.section_id,
                "section_expires_at": (
                    section_state.expires_at.isoformat()
                    if section_state
                    else None
                ),
                "type": "mcq",
                "title": question.mcq_snapshot.title,
                "statement": question.mcq_snapshot.statement,
                "code_snippet": question.mcq_snapshot.code_snippet,
                "allow_multiple": question.mcq_snapshot.allow_multiple,
                "max_score": str(question.max_score),
                "negative_marks": str(question.negative_marks),
                "options": [
                    {"id": option.pk, "text": option.text}
                    for option in question.mcq_snapshot.options.all()
                ],
                "selected_option_ids": (
                    list(answer.selected_options.values_list("option_id", flat=True))
                    if answer
                    else []
                ),
            }
        question_data["html"] = render_to_string(
            "assessment/partials/mcq_question.html",
            {
                "question": question,
                "mcq": question.mcq_snapshot,
                "selected_option_ids": set(question_data["selected_option_ids"]),
            },
            request=request,
        )
        return JsonResponse(question_data)

    coding = question.coding_snapshot
    language_options = list(coding.languages.select_related("language").all())
    drafts = {
        draft.language_id: draft.source_code
        for draft in CodeDraft.objects.filter(
            attempt=attempt,
            question=question,
        )
    }
    question_data = {
            "id": question.pk,
            "section_id": question.section_id,
            "section_expires_at": (
                section_state.expires_at.isoformat()
                if section_state
                else None
            ),
            "type": "coding",
            "title": coding.title,
            "statement": coding.statement,
            "input_format": coding.input_format,
            "output_format": coding.output_format,
            "constraints_text": coding.constraints_text,
            "coding_mode": coding.coding_mode,
            "max_score": str(question.max_score),
            "negative_marks": str(question.negative_marks),
            "languages": [
                {
                    "id": item.language_id,
                    "name": item.language_name,
                    "slug": item.language_slug,
                    "starter_code": item.starter_code,
                    "draft": drafts.get(item.language_id, ""),
                }
                for item in language_options
            ],
            "samples": [
                {
                    "position": test_case.position,
                    "input": test_case.input_data,
                    "expected_output": test_case.expected_output,
                    "explanation": test_case.explanation,
                }
                for test_case in coding.test_cases.filter(is_sample=True)
            ],
            "submissions": list(
                AssessmentSubmission.objects.filter(
                    attempt=attempt,
                    assessment_question_snapshot=question,
                )
                .select_related("language")
                .order_by("-submitted_at")
            ),
        }
    question_data["html"] = render_to_string(
        "assessment/partials/coding_question.html",
        {
            "question": question,
            "coding": coding,
            "languages": language_options,
            "samples": coding.test_cases.filter(is_sample=True),
            "submissions": question_data["submissions"],
        },
        request=request,
    )
    question_data["submissions"] = [
        {
            "id": submission.pk,
            "status": submission.status,
            "score": str(submission.score),
            "language": submission.language.name,
            "submitted_at": submission.submitted_at.isoformat(),
            "source_code": submission.source_code,
        }
        for submission in question_data["submissions"]
    ]
    return JsonResponse(question_data)


@login_required
@require_POST
def save_mcq_answer(request, assessment_slug):
    payload, error = _exam_json_body(request)
    if error:
        return error
    attempt, _assessment, error = _exam_attempt(request, assessment_slug, payload)
    if error:
        return error
    question = get_object_or_404(
        AssessmentQuestionSnapshot.objects.select_related("mcq_snapshot"),
        pk=payload.get("question_id"),
        section__version=attempt.assessment_version,
        mcq_snapshot__isnull=False,
    )
    section_error = _section_time_error(attempt, question)
    if section_error:
        return section_error
    option_ids = payload.get("option_ids")
    if not isinstance(option_ids, list) or any(
        not isinstance(option_id, int) for option_id in option_ids
    ):
        return _api_error("option_ids must be a list of option IDs.", 400)
    if len(set(option_ids)) != len(option_ids):
        return _api_error("Duplicate option IDs are not allowed.", 400)
    options = list(
        McqOptionSnapshot.objects.filter(
            question=question.mcq_snapshot,
            pk__in=option_ids,
        )
    )
    if len(options) != len(option_ids):
        return _api_error("One or more selected options are invalid.", 400)
    if not question.mcq_snapshot.allow_multiple and len(options) > 1:
        return _api_error("This question accepts only one answer.", 400)

    answer, _ = AttemptAnswer.objects.get_or_create(
        attempt=attempt,
        assessment_question_snapshot=question,
    )
    AttemptAnswerOption.objects.filter(attempt_answer=answer).exclude(
        option_id__in=option_ids
    ).delete()
    existing_ids = set(
        AttemptAnswerOption.objects.filter(attempt_answer=answer).values_list(
            "option_id",
            flat=True,
        )
    )
    AttemptAnswerOption.objects.bulk_create(
        [
            AttemptAnswerOption(attempt_answer=answer, option=option)
            for option in options
            if option.pk not in existing_ids
        ]
    )
    AttemptEvent.objects.create(
        attempt=attempt,
        event_type=AttemptEvent.EventType.ANSWER_SAVED,
        details={"question_id": question.pk, "type": "mcq"},
    )
    return JsonResponse({"saved": True})


@login_required
@require_POST
def save_code_draft(request, assessment_slug):
    payload, error = _exam_json_body(request)
    if error:
        return error
    attempt, _assessment, error = _exam_attempt(request, assessment_slug, payload)
    if error:
        return error
    question = get_object_or_404(
        AssessmentQuestionSnapshot.objects.select_related("coding_snapshot"),
        pk=payload.get("question_id"),
        section__version=attempt.assessment_version,
        coding_snapshot__isnull=False,
    )
    section_error = _section_time_error(attempt, question)
    if section_error:
        return section_error
    source_code = payload.get("source_code")
    if not isinstance(source_code, str) or len(source_code) > 100_000:
        return _api_error("source_code must be text no longer than 100,000 characters.", 400)
    language = get_object_or_404(
        ProgrammingLanguage,
        pk=payload.get("language_id"),
        question_snapshots__question=question.coding_snapshot,
    )
    CodeDraft.objects.update_or_create(
        attempt=attempt,
        question=question,
        language=language,
        defaults={"source_code": source_code},
    )
    return JsonResponse({"saved": True, "updated_at": timezone.now().isoformat()})


@login_required
@require_POST
def run_assessment_code(request, assessment_slug):
    payload, error = _exam_json_body(request)
    if error:
        return error
    attempt, _assessment, error = _exam_attempt(request, assessment_slug, payload)
    if error:
        return error
    question = get_object_or_404(
        AssessmentQuestionSnapshot.objects.select_related("coding_snapshot"),
        pk=payload.get("question_id"),
        section__version=attempt.assessment_version,
        coding_snapshot__isnull=False,
    )
    section_error = _section_time_error(attempt, question)
    if section_error:
        return section_error
    source_code = payload.get("source_code")
    if not isinstance(source_code, str) or len(source_code) > 100_000:
        return _api_error("source_code must be text no longer than 100,000 characters.", 400)
    if not source_code.strip():
        return _api_error("Code cannot be empty.", 400)
    is_safe, reason = is_code_safe(source_code)
    if not is_safe:
        return _api_error(reason or "Code was rejected.", 400)
    if question.coding_snapshot.test_cases.filter(
        is_sample=True,
        input_data__gt="",
    ).exists() and not _code_reads_input(source_code):
        return _api_error("Your code must read the provided input.", 400)
    language = get_object_or_404(
        ProgrammingLanguage.objects.filter(is_active=True, is_judge0_executable=True),
        pk=payload.get("language_id"),
        question_snapshots__question=question.coding_snapshot,
    )
    samples = list(
        question.coding_snapshot.test_cases.filter(is_sample=True).order_by("position")
    )
    if not samples:
        return _api_error("This coding question has no sample test cases.", 409)
    results = []
    for test_case in samples:
        actual, runtime, run_error, run_status = execute_code(
            source_code,
            language,
            normalize_case_text(test_case.input_data),
        )
        status = (
            "accepted"
            if run_status == "accepted"
            and comparable_case_text(actual) == comparable_case_text(test_case.expected_output)
            else "wrong_answer"
            if run_status in {"accepted", "wrong_answer"}
            else run_status
        )
        results.append(
            {
                "position": test_case.position,
                "status": status,
                "input": test_case.input_data,
                "expected_output": test_case.expected_output,
                "actual_output": actual or "",
                "error": run_error or "",
                "runtime_ms": str(runtime),
            }
        )
    return JsonResponse({"results": results})


@login_required
@require_POST
def submit_assessment_code(request, assessment_slug):
    payload, error = _exam_json_body(request)
    if error:
        return error
    attempt, _assessment, error = _exam_attempt(request, assessment_slug, payload)
    if error:
        return error
    question = get_object_or_404(
        AssessmentQuestionSnapshot.objects.select_related("coding_snapshot"),
        pk=payload.get("question_id"),
        section__version=attempt.assessment_version,
        coding_snapshot__isnull=False,
    )
    section_error = _section_time_error(attempt, question)
    if section_error:
        return section_error
    source_code = payload.get("source_code")
    if not isinstance(source_code, str) or len(source_code) > 100_000:
        return _api_error("source_code must be text no longer than 100,000 characters.", 400)
    if not source_code.strip():
        return _api_error("Code cannot be empty.", 400)
    is_safe, reason = is_code_safe(source_code)
    if not is_safe:
        return _api_error(reason or "Code was rejected.", 400)
    language = get_object_or_404(
        ProgrammingLanguage.objects.filter(is_active=True, is_judge0_executable=True),
        pk=payload.get("language_id"),
        question_snapshots__question=question.coding_snapshot,
    )
    test_cases = list(
        question.coding_snapshot.test_cases.all().order_by("position")
    )
    if not test_cases:
        return _api_error("This coding question has no test cases.", 409)
    submission = AssessmentSubmission.objects.create(
        attempt=attempt,
        assessment_question_snapshot=question,
        language=language,
        source_code=source_code,
        status=AssessmentSubmission.Status.PROCESSING,
    )
    passed_weight = 0
    total_weight = sum(case.weight for case in test_cases)
    total_runtime = Decimal("0")
    passed_count = 0
    all_passed = True
    for test_case in test_cases:
        actual, runtime, run_error, run_status = execute_code(
            source_code,
            language,
            normalize_case_text(test_case.input_data),
        )
        passed = (
            run_status == "accepted"
            and comparable_case_text(actual) == comparable_case_text(test_case.expected_output)
        )
        passed_count += int(passed)
        passed_weight += test_case.weight if passed else 0
        all_passed = all_passed and passed
        total_runtime = max(total_runtime, runtime or Decimal("0"))
        AssessmentSubmissionResult.objects.create(
            submission=submission,
            test_case_snapshot=test_case,
            is_passed=passed,
            actual_output=actual or "",
            expected_output=test_case.expected_output,
            execution_time_ms=max(0, int(runtime or 0)),
            error_message=run_error or "",
        )
    score = (
        question.max_score * Decimal(passed_weight) / Decimal(total_weight)
        if total_weight
        else Decimal("0")
    )
    submission.status = (
        AssessmentSubmission.Status.ACCEPTED
        if all_passed
        else AssessmentSubmission.Status.WRONG_ANSWER
    )
    submission.score = score
    submission.execution_time_ms=max(0, int(total_runtime))
    submission.evaluated_at = timezone.now()
    submission.save(
        update_fields=["status", "score", "execution_time_ms", "evaluated_at"]
    )
    return JsonResponse(
        {
            "submission_id": submission.pk,
            "status": submission.status,
            "passed": passed_count,
            "total": len(test_cases),
            "score": str(score),
            "max_score": str(question.max_score),
        }
    )


@login_required
@require_POST
def update_exam_question_state(request, assessment_slug):
    payload, error = _exam_json_body(request)
    if error:
        return error
    attempt, _assessment, error = _exam_attempt(request, assessment_slug, payload)
    if error:
        return error
    question = get_object_or_404(
        AssessmentQuestionSnapshot,
        pk=payload.get("question_id"),
        section__version=attempt.assessment_version,
    )
    section_error = _section_time_error(attempt, question)
    if section_error:
        return section_error
    action = payload.get("action")
    if action not in {"mark_for_review", "clear_response", "navigate"}:
        return _api_error("Unknown question action.", 400)
    state, _ = AttemptQuestionState.objects.get_or_create(
        attempt=attempt,
        question=question,
    )
    if action == "mark_for_review":
        state.marked_for_review = bool(payload.get("marked", True))
        state.save(update_fields=["marked_for_review"])
    elif action == "clear_response":
        AttemptAnswer.objects.filter(
            attempt=attempt,
            assessment_question_snapshot=question,
        ).delete()
        CodeDraft.objects.filter(attempt=attempt, question=question).delete()
        state.marked_for_review = False
        state.save(update_fields=["marked_for_review"])
    else:
        state.visited = True
        state.last_visited = timezone.now()
        state.save(update_fields=["visited", "last_visited"])
        attempt.current_section = question.section
        attempt.current_question = question
        attempt.save(update_fields=["current_section", "current_question"])
    return JsonResponse({"updated": True})


def _finalize_exam_attempt(attempt, timed_out=False):
    with transaction.atomic():
        locked = Attempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.status not in {Attempt.Status.IN_PROGRESS, Attempt.Status.TIMED_OUT}:
            result = getattr(locked, "result", None)
            return result
        questions = list(
            AssessmentQuestionSnapshot.objects.filter(
                section__version=locked.assessment_version
            )
            .select_related("section", "mcq_snapshot", "coding_snapshot")
            .prefetch_related("mcq_snapshot__options")
        )
        answers = {
            answer.assessment_question_snapshot_id: answer
            for answer in AttemptAnswer.objects.filter(
                attempt=locked
            ).prefetch_related("selected_options")
        }
        best_submissions = {}
        for submission in AssessmentSubmission.objects.filter(
            attempt=locked
        ).order_by("assessment_question_snapshot_id", "-score", "-submitted_at"):
            best_submissions.setdefault(
                submission.assessment_question_snapshot_id,
                submission,
            )
        section_scores = {}
        correct_count = incorrect_count = unanswered_count = 0
        raw_total = Decimal("0")
        max_score = Decimal("0")
        for question in questions:
            max_score += question.max_score
            score = Decimal("0")
            answer = answers.get(question.pk)
            if question.mcq_snapshot_id:
                selected = (
                    set(answer.selected_options.values_list("option_id", flat=True))
                    if answer
                    else set()
                )
                correct = {
                    option.pk
                    for option in question.mcq_snapshot.options.all()
                    if option.is_correct
                }
                if selected and selected == correct:
                    score = question.max_score
                    correct_count += 1
                elif selected:
                    score = -question.negative_marks
                    incorrect_count += 1
                else:
                    unanswered_count += 1
            else:
                submission = best_submissions.get(question.pk)
                if submission:
                    score = submission.score
                    if submission.status == AssessmentSubmission.Status.ACCEPTED:
                        correct_count += 1
                    else:
                        incorrect_count += 1
                else:
                    unanswered_count += 1
            raw_total += score
            section_scores[question.section_id] = (
                section_scores.get(question.section_id, Decimal("0")) + score
            )
            if answer:
                answer.score = score
                answer.is_correct = score == question.max_score
                answer.save(update_fields=["score", "is_correct"])

        final_score = max(Decimal("0"), raw_total)
        result, created = AssessmentResult.objects.get_or_create(
            attempt=locked,
            defaults={
                "assessment": locked.participant.assessment,
                "total_score": final_score,
                "max_score": max_score,
                "correct_count": correct_count,
                "incorrect_count": incorrect_count,
                "unanswered_count": unanswered_count,
                "evaluation_status": AssessmentResult.EvaluationStatus.FINALIZED,
            },
        )
        if not created:
            result.total_score = final_score
            result.max_score = max_score
            result.correct_count = correct_count
            result.incorrect_count = incorrect_count
            result.unanswered_count = unanswered_count
            result.evaluation_status = AssessmentResult.EvaluationStatus.FINALIZED
            result.save()
        section_max_scores = {}
        for question in questions:
            section_max_scores[question.section_id] = (
                section_max_scores.get(question.section_id, Decimal("0"))
                + question.max_score
            )
        for section in locked.assessment_version.section_snapshots.all():
            section_max = section_max_scores.get(section.pk, Decimal("0"))
            section_score = max(
                Decimal("0"),
                section_scores.get(section.pk, Decimal("0")),
            )
            AssessmentSectionResult.objects.update_or_create(
                result=result,
                section_snapshot=section,
                defaults={"score": section_score, "max_score": section_max},
            )
        if locked.status == Attempt.Status.IN_PROGRESS:
            locked.status = (
                Attempt.Status.TIMED_OUT if timed_out else Attempt.Status.SUBMITTED
            )
            locked.submitted_at = timezone.now()
            locked.score = final_score
            locked.save(update_fields=["status", "submitted_at", "score"])
            Participant.objects.filter(pk=locked.participant_id).update(
                status=Participant.Status.COMPLETED
            )
            AttemptEvent.objects.create(
                attempt=locked,
                event_type=(
                    AttemptEvent.EventType.TIMED_OUT
                    if timed_out
                    else AttemptEvent.EventType.SUBMITTED
                ),
                details={"source": "exam_shell"},
            )
        return result


@login_required
@require_POST
def submit_exam(request, assessment_slug):
    payload, error = _exam_json_body(request)
    if error:
        return error
    action = payload.get("action", "manual")
    if action not in {"manual", "time_expired"}:
        return _api_error("Unknown exam submission action.", 400)
    attempt, _assessment, error = _exam_attempt(
        request,
        assessment_slug,
        payload,
        allow_finished=True,
    )
    if error:
        return error
    timed_out = action == "time_expired"
    if timed_out and attempt.status == Attempt.Status.IN_PROGRESS:
        deadline = attempt.expires_at
        version_end = attempt.assessment_version.end_time
        if version_end and (deadline is None or version_end < deadline):
            deadline = version_end
        if deadline and timezone.now() < deadline:
            return _api_error("The assessment time has not expired.", 409)
    result = _finalize_exam_attempt(attempt, timed_out=timed_out)
    attempt.refresh_from_db()
    return JsonResponse(
        {
            "submitted": True,
            "status": attempt.status,
            "score": f"{result.total_score:.2f}",
            "max_score": f"{result.max_score:.2f}",
            "correct": result.correct_count,
            "incorrect": result.incorrect_count,
            "unanswered": result.unanswered_count,
        }
    )


def _finish_attempt(attempt, event_type, details=None):
    if attempt.status != Attempt.Status.IN_PROGRESS:
        return False
    _finalize_exam_attempt(attempt)
    attempt.refresh_from_db()
    return attempt.status == Attempt.Status.SUBMITTED


@login_required
@require_POST
@transaction.atomic
def log_violation(request, assessment_slug):
    assessment = get_object_or_404(Assessment, slug=assessment_slug)
    try:
        participant = _assessment_participant(assessment, request.user)
    except Http404:
        return _api_error("You are not registered for this assessment.", 403)
    except PermissionDenied:
        return _api_error("This assessment registration is not active.", 403)
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _api_error("Request body must be valid JSON.", 400)
    if not isinstance(payload, dict):
        return _api_error("Request body must be a JSON object.", 400)
    attempt_id = payload.get("attempt_id")
    attempt = get_object_or_404(
        Attempt.objects.select_for_update(),
        pk=attempt_id,
        participant=participant,
        status=Attempt.Status.IN_PROGRESS,
    )
    try:
        session_id = uuid.UUID(str(payload.get("session_id")))
    except (ValueError, TypeError, AttributeError):
        return _api_error("A valid session_id is required.", 400)
    if session_id != attempt.active_session_id:
        return _api_error(
            "This attempt is active in another tab or device.",
            409,
        )
    _expire_attempt_if_needed(attempt)
    attempt.refresh_from_db()
    if attempt.status != Attempt.Status.IN_PROGRESS:
        return _api_error("This assessment attempt has ended.", 409)

    event_type = payload.get("event_type")
    if event_type == "submit_and_exit":
        _finish_attempt(attempt, event_type)
        return JsonResponse({"submitted": True, "status": attempt.status})
    if event_type == "invigilator_exit":
        expected_pin = str(getattr(settings, "ASSESSMENT_INVIGILATOR_PIN", ""))
        provided_pin = str(payload.get("pin", ""))
        if not expected_pin or not hmac.compare_digest(provided_pin, expected_pin):
            return _api_error("The invigilator PIN is invalid or unavailable.", 403)
        _finish_attempt(attempt, event_type)
        return JsonResponse({"submitted": True, "status": attempt.status})

    allowed_events = {
        "fullscreen_exit",
        "tab_hidden",
        "window_blur",
        "devtools_open",
        "copy_blocked",
        "cut_blocked",
        "paste_blocked",
        "drag_blocked",
        "context_menu_blocked",
        "shortcut_blocked",
        "extension_warning",
        "navigation_blocked",
    }
    if not isinstance(event_type, str) or event_type not in allowed_events:
        return _api_error("Unknown proctoring event.", 400)
    try:
        event_id = uuid.UUID(str(payload.get("event_id")))
    except (ValueError, TypeError, AttributeError):
        return _api_error("A valid event_id is required.", 400)

    timestamp = payload.get("timestamp")
    occurred_at = parse_datetime(timestamp) if isinstance(timestamp, str) else None
    if occurred_at is None:
        return _api_error("A valid event timestamp is required.", 400)
    if timezone.is_naive(occurred_at):
        occurred_at = timezone.make_aware(occurred_at)
    details = payload.get("details", {})
    if not isinstance(details, dict):
        return _api_error("Event details must be an object.", 400)
    violation, created = ViolationLog.objects.get_or_create(
        client_event_id=event_id,
        defaults={
            "attempt": attempt,
            "user": request.user,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "details": details,
        },
    )
    if violation.attempt_id != attempt.pk or violation.user_id != request.user.pk:
        return _api_error("This event ID has already been used.", 409)
    warning_limit = max(
        0,
        int(getattr(settings, "ASSESSMENT_PROCTOR_WARNING_LIMIT", 3)),
    )
    violation_count = ViolationLog.objects.filter(attempt=attempt).count()
    auto_submit = (
        created
        and bool(getattr(settings, "ASSESSMENT_PROCTOR_AUTO_SUBMIT", True))
        and violation_count > warning_limit
    )
    if auto_submit:
        _finish_attempt(
            attempt,
            "proctor_warning_limit",
            {"violation_count": violation_count},
        )
    return JsonResponse(
        {
            "violation_count": violation_count,
            "warning_limit": warning_limit,
            "warnings_remaining": max(0, warning_limit - violation_count),
            "auto_submitted": auto_submit,
            "attempt_status": (
                Attempt.Status.SUBMITTED if auto_submit else attempt.status
            ),
        }
    )


def _assessment_detail_page(request, assessment):
    active_tab = request.GET.get("tab", "details")
    valid_tabs = {
        "details",
        "questions",
        "moderators",
        "participants",
        "leaderboard",
        "submissions",
        "reports",
    }
    if active_tab not in valid_tabs:
        active_tab = "details"
    if active_tab == "questions" and request.GET.get("action") == "add":
        section = assessment.sections.order_by("position").first()
        if section:
            return redirect(
                "assessment:section_question_add",
                assessment_id=assessment.pk,
                section_id=section.pk,
            )
        return redirect("assessment:section_create", assessment_id=assessment.pk)

    details_form = AssessmentDetailsForm(instance=assessment)
    if request.method == "POST" and request.POST.get("action") == "save_details":
        details_form = AssessmentDetailsForm(request.POST, instance=assessment)
        if details_form.is_valid():
            details_form.save()
            messages.success(request, "Assessment details saved.")
            return redirect(
                f"{reverse('assessment:assessment_detail', args=[assessment.pk])}?tab=details"
            )
        active_tab = "details"

    context = _assessment_context(assessment)
    if active_tab == "leaderboard":
        leaderboard = _assessment_leaderboard(assessment)
        selected_user_id = request.GET.get("user", "")
        selected_participant = next(
            (
                row
                for row in leaderboard
                if str(row["user"].pk) == selected_user_id
            ),
            None,
        )
        participant_tab = request.GET.get("participant_tab", "summary")
        if participant_tab not in {"summary", "submissions"}:
            participant_tab = "summary"
        participant_submissions = []
        if selected_participant is not None and participant_tab == "submissions":
            participant_submissions = (
                AssessmentSubmission.objects.filter(
                    attempt=selected_participant["attempt"],
                )
                .select_related(
                    "language",
                    "assessment_question_snapshot__coding_snapshot",
                )
                .order_by("-submitted_at")
            )
        context.update(
            {
                "leaderboard": leaderboard,
                "selected_participant": selected_participant,
                "participant_tab": participant_tab,
                "participant_submissions": participant_submissions,
            }
        )
    elif active_tab == "submissions":
        submission_rows = _assessment_submission_rows(assessment)
        selected_key = request.GET.get("submission", "")
        selected_submission = next(
            (row for row in submission_rows if row["key"] == selected_key),
            None,
        )
        if selected_key and selected_submission is None:
            raise Http404("Submission not found for this assessment.")
        context.update(
            {
                "submission_rows": submission_rows,
                "selected_submission": selected_submission,
                "submission_history": (
                    _assessment_submission_history(assessment, selected_submission)
                    if selected_submission
                    else []
                ),
            }
        )
    elif active_tab == "participants":
        participants = (
            assessment.participants.select_related("user")
            .annotate(attempt_count=Count("attempts", distinct=True))
            .prefetch_related(
                Prefetch(
                    "attempts",
                    queryset=Attempt.objects.order_by("-attempt_number"),
                    to_attr="signup_attempts",
                ),
                Prefetch(
                    "attempt_authorizations",
                    queryset=AttemptAuthorization.objects.order_by("-created_at"),
                    to_attr="signup_authorizations",
                ),
            )
            .order_by("user__user_name")
        )
        context["signup_search"] = request.GET.get("q", "").strip()
        if context["signup_search"]:
            participants = participants.filter(
                Q(user__user_name__icontains=context["signup_search"])
                | Q(user__email__icontains=context["signup_search"])
            )
        published_version = _published_assessment_version(assessment)
        base_attempt_limit = (
            published_version.max_attempts
            if published_version
            else assessment.max_attempts
        )
        participant_rows = list(participants)
        for participant in participant_rows:
            participant.allowed_attempts = base_attempt_limit + sum(
                authorization.extra_attempts
                for authorization in participant.signup_authorizations
            )
        context["participants"] = participant_rows
    context.update(
        {
            "active_tab": active_tab,
            "details_form": details_form,
            "can_manage_moderators": (
                request.user.is_staff
                or request.user.is_faculty
                or assessment.created_by_id == request.user.pk
            ),
            "can_manage_participants": (
                request.user.is_staff
                or request.user.is_faculty
                or assessment.created_by_id == request.user.pk
            ),
            "can_publish": (
                request.user.is_staff
                or request.user.is_faculty
                or assessment.created_by_id == request.user.pk
            ),
        }
    )
    return render(
        request,
        "assessment/assessment_detail.html",
        context,
    )


@login_required
def assessment_edit(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    original_status = assessment.status
    form = AssessmentForm(_post_data(request), instance=assessment)
    if request.method == "POST" and form.is_valid():
        if (
            original_status != Assessment.Status.PUBLISHED
            and form.cleaned_data["status"] == Assessment.Status.PUBLISHED
        ):
            assessment.status = original_status
            form.add_error(
                "status",
                "Use the Publish assessment action on the assessment details page.",
            )
        else:
            form.save()
            messages.success(request, "Assessment changes saved.")
            return redirect("assessment:assessment_detail", assessment_id=assessment.pk)
    return render(
        request,
        "assessment/assessment_form.html",
        {"form": form, "assessment": assessment, "mode": "edit"},
    )


@login_required
@require_POST
def assessment_publish(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    _require_moderator_management_access(request.user, assessment)
    if assessment.status == Assessment.Status.ARCHIVED:
        messages.error(request, "Archived assessments cannot be published.")
    else:
        version, errors = _publish_assessment(assessment, request.user)
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            messages.success(
                request,
                f"Assessment published as version {version.version_number}.",
            )
    return redirect("assessment:assessment_detail", assessment_id=assessment.pk)


@login_required
@require_POST
@transaction.atomic
def assessment_participant_action(request, assessment_id, participant_id, action):
    assessment = _assessment_or_404(request, assessment_id)
    _require_moderator_management_access(request.user, assessment)
    participant = get_object_or_404(
        Participant.objects.select_for_update(),
        pk=participant_id,
        assessment=assessment,
    )
    tab_url = (
        f"{reverse('assessment:assessment_detail', args=[assessment.pk])}"
        "?tab=participants"
    )
    status_by_action = {
        "block": Participant.Status.DISQUALIFIED,
        "remove": Participant.Status.REMOVED,
    }
    if action == "restore":
        latest_attempt = participant.attempts.order_by("-attempt_number").first()
        if latest_attempt and latest_attempt.status == Attempt.Status.IN_PROGRESS:
            participant.status = Participant.Status.STARTED
        elif latest_attempt and latest_attempt.status != Attempt.Status.CANCELLED:
            participant.status = Participant.Status.COMPLETED
        else:
            participant.status = Participant.Status.REGISTERED
        message = f"Access restored for {participant.user.user_name}."
    elif action in status_by_action:
        participant.status = status_by_action[action]
        action_label = "blocked" if action == "block" else "removed"
        message = f"{participant.user.user_name} was {action_label} from the assessment."
    elif action == "grant_attempts":
        try:
            extra_attempts = int(request.POST.get("extra_attempts", ""))
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid number of additional attempts.")
            return redirect(tab_url)
        reason = request.POST.get("reason", "").strip()
        if not 1 <= extra_attempts <= 10 or not reason:
            messages.error(
                request,
                "Grant 1–10 attempts and provide a reason.",
            )
            return redirect(tab_url)
        AttemptAuthorization.objects.create(
            participant=participant,
            authorized_by=request.user,
            extra_attempts=extra_attempts,
            reason=reason,
        )
        messages.success(
            request,
            f"Granted {extra_attempts} additional attempt"
            f"{'' if extra_attempts == 1 else 's'} to {participant.user.user_name}.",
        )
        return redirect(tab_url)
    elif action == "restart":
        latest_attempt = (
            participant.attempts.select_for_update()
            .order_by("-attempt_number")
            .first()
        )
        if latest_attempt:
            if latest_attempt.status == Attempt.Status.IN_PROGRESS:
                latest_attempt.status = Attempt.Status.CANCELLED
            latest_attempt.active_session_id = uuid.uuid4()
            latest_attempt.save(
                update_fields=["status", "active_session_id"]
            )
            AttemptEvent.objects.create(
                attempt=latest_attempt,
                event_type=AttemptEvent.EventType.RESTARTED,
                details={
                    "restarted_by": str(request.user.pk),
                    "reason": request.POST.get("reason", "").strip(),
                },
            )
        extra_attempts = participant.attempt_authorizations.aggregate(
            total=Sum("extra_attempts")
        )["total"] or 0
        attempts_used = participant.attempts.count()
        version = _published_assessment_version(assessment)
        allowed_attempts = (
            version.max_attempts
            if version
            else assessment.max_attempts
        ) + extra_attempts
        if attempts_used >= allowed_attempts:
            AttemptAuthorization.objects.create(
                participant=participant,
                authorized_by=request.user,
                extra_attempts=1,
                reason=request.POST.get("reason", "").strip()
                or "Faculty-authorized assessment restart",
            )
        participant.status = Participant.Status.REGISTERED
        participant.save(update_fields=["status"])
        messages.success(
            request,
            f"{participant.user.user_name} can start a fresh assessment attempt. "
            "Previous attempt data is retained for audit.",
        )
        return redirect(tab_url)
    else:
        raise Http404("Unknown participant action.")

    participant.save(update_fields=["status"])
    messages.success(request, message)
    return redirect(tab_url)


def _require_moderator_management_access(user, assessment):
    if (
        user.is_staff
        or user.is_faculty
        or assessment.created_by_id == user.pk
    ):
        return
    raise PermissionDenied


@login_required
def moderator_search(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    _require_moderator_management_access(request.user, assessment)
    query = request.GET.get("q", "").strip()
    results = []
    if len(query) >= 2:
        user_model = get_user_model()
        users = user_model.objects.filter(
            is_active=True,
            user_name__icontains=query,
        ).exclude(pk=request.user.pk)
        users = users.exclude(moderated_assessments__assessment=assessment)
        results = list(users.order_by("user_name").values("id", "user_name")[:10])
    return JsonResponse({"results": results})


@login_required
@require_POST
def moderator_add(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    _require_moderator_management_access(request.user, assessment)
    user_model = get_user_model()
    moderator = get_object_or_404(
        user_model,
        pk=request.POST.get("user_id"),
        is_active=True,
    )
    AssessmentModerator.objects.get_or_create(assessment=assessment, user=moderator)
    messages.success(request, f"{moderator.user_name} can now manage this assessment.")
    return redirect(
        f"{reverse('assessment:assessment_detail', args=[assessment.pk])}?tab=moderators"
    )


@login_required
@require_POST
def moderator_remove(request, assessment_id, moderator_id):
    assessment = _assessment_or_404(request, assessment_id)
    _require_moderator_management_access(request.user, assessment)
    moderator = get_object_or_404(
        AssessmentModerator,
        assessment=assessment,
        user_id=moderator_id,
    )
    name = moderator.user.user_name
    moderator.delete()
    messages.success(request, f"{name} was removed as an assessment moderator.")
    return redirect(
        f"{reverse('assessment:assessment_detail', args=[assessment.pk])}?tab=moderators"
    )


@login_required
@require_POST
def assessment_delete(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    name = assessment.name
    assessment.delete()
    messages.success(request, f"Assessment “{name}” deleted.")
    return redirect("assessment:dashboard")


@login_required
def section_create(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    form = AssessmentSectionForm(
        _post_data(request),
        assessment=assessment,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Section created.")
        return redirect("assessment:assessment_detail", assessment_id=assessment.pk)
    return render(
        request,
        "assessment/section_form.html",
        {"form": form, "assessment": assessment, "mode": "create"},
    )


@login_required
def section_edit(request, assessment_id, section_id):
    assessment, section = _section_or_404(request, assessment_id, section_id)
    form = AssessmentSectionForm(
        _post_data(request),
        instance=section,
        assessment=assessment,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Section changes saved.")
        return redirect("assessment:assessment_detail", assessment_id=assessment.pk)
    return render(
        request,
        "assessment/section_form.html",
        {
            "form": form,
            "assessment": assessment,
            "section": section,
            "mode": "edit",
        },
    )


@login_required
@require_POST
def section_delete(request, assessment_id, section_id):
    assessment, section = _section_or_404(request, assessment_id, section_id)
    title = section.title
    section.delete()
    messages.success(request, f"Section “{title}” deleted.")
    return redirect("assessment:assessment_detail", assessment_id=assessment.pk)


@login_required
def question_bank(request):
    _require_management_access(request.user)
    query = request.GET.get("q", "").strip()
    mcq_questions = _managed_questions(McqQuestion, request.user)
    coding_questions = _managed_questions(CodingQuestion, request.user)
    if query:
        mcq_questions = mcq_questions.filter(
            Q(title__icontains=query) | Q(topic__icontains=query)
        )
        coding_questions = coding_questions.filter(
            Q(title__icontains=query) | Q(topic__icontains=query)
        )
    return render(
        request,
        "assessment/question_bank.html",
        {
            "mcq_questions": mcq_questions.order_by("title"),
            "coding_questions": coding_questions.order_by("title"),
            "query": query,
        },
    )


@login_required
def question_add(request):
    _require_assessment_management_access(request.user)
    if request.method == "POST":
        assessment_id = request.POST.get("assessment_id", "")
        if not assessment_id.isdecimal():
            messages.error(request, "Select an assessment to add a question to.")
        else:
            assessment = get_object_or_404(
                _managed_assessments(request.user),
                pk=assessment_id,
            )
            section = assessment.sections.order_by("position").first()
            if section:
                return redirect(
                    "assessment:section_question_add",
                    assessment_id=assessment.pk,
                    section_id=section.pk,
                )
            return redirect(
                "assessment:section_create",
                assessment_id=assessment.pk,
            )
    assessments = _managed_assessments(request.user).order_by("name")
    return render(
        request,
        "assessment/question_add.html",
        {
            "assessments": assessments,
            "has_assessments": assessments.exists(),
        },
    )


@login_required
def question_create(request):
    _require_management_access(request.user)
    return render(
        request,
        "assessment/question_create.html",
        {
            "question_return_url": (
                f"{reverse('assessment:dashboard')}?tab=questions"
            ),
        },
    )


@login_required
@require_POST
def assessment_question_add(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    form = AssessmentQuestionAddForm(
        request.POST,
        assessment=assessment,
        user=request.user,
    )
    if form.is_valid():
        question_field = (
            "mcq_question"
            if form.cleaned_data["question_type"] == "mcq"
            else "coding_question"
        )
        added = False
        with transaction.atomic():
            locked_assessment = Assessment.objects.select_for_update().get(
                pk=assessment.pk
            )
            if AssessmentQuestion.objects.filter(
                assessment=locked_assessment,
                **{question_field: form.selected_question},
            ).exists():
                messages.error(request, "This question is already in the assessment.")
            else:
                section = form.cleaned_data["section"]
                if section is not None:
                    section = AssessmentSection.objects.get(
                        pk=section.pk,
                        assessment=locked_assessment,
                    )
                else:
                    section = locked_assessment.sections.order_by("position").first()
                if section is None:
                    section, _ = AssessmentSection.objects.get_or_create(
                        assessment=locked_assessment,
                        position=1,
                        defaults={"title": "Questions"},
                    )
                last_position = section.questions.aggregate(
                    last_position=Max("position")
                )["last_position"]
                AssessmentQuestion.objects.create(
                    assessment=locked_assessment,
                    section=section,
                    position=(last_position or 0) + 1,
                    max_score=form.cleaned_data["max_score"],
                    negative_marks=form.cleaned_data["negative_marks"],
                    **{question_field: form.selected_question},
                )
                added = True
        if added:
            messages.success(request, "Question added to the assessment.")
            return redirect(
                f"{reverse('assessment:assessment_detail', args=[assessment.pk])}?tab=questions"
            )
    else:
        for error in form.errors.get("__all__", []):
            messages.error(request, error)
        for error in form.errors.get("question_id", []):
            messages.error(request, error)
        if not form.errors.get("__all__") and not form.errors.get("question_id"):
            messages.error(request, "Check the question assignment details and try again.")
    return redirect(
        f"{reverse('assessment:assessment_detail', args=[assessment.pk])}?tab=questions&action=add"
    )


def _question_form_context(kind, form, **extra):
    context = {"kind": kind, "form": form, **extra}
    if kind == "mcq":
        context["option_formset"] = extra["option_formset"]
    else:
        context["language_formset"] = extra["language_formset"]
        context["test_case_formset"] = extra["test_case_formset"]
    return context


def _question_return_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse("assessment:question_bank")


def _question_creation_assessment(request):
    assessment_id = request.POST.get("assessment") or request.GET.get("assessment")
    if not assessment_id:
        _require_management_access(request.user)
        return None
    if not assessment_id.isdecimal():
        raise PermissionDenied
    return _assessment_or_404(request, int(assessment_id))


@login_required
def question_create_options(request, assessment_id):
    assessment = _assessment_or_404(request, assessment_id)
    return render(
        request,
        "assessment/question_create_options.html",
        {
            "assessment": assessment,
            "question_return_url": (
                f"{reverse('assessment:assessment_detail', args=[assessment.pk])}"
                "?tab=questions&action=add"
            ),
        },
    )


@login_required
def question_import_options(request):
    assessment_id = request.GET.get("assessment", "")
    section_id = request.GET.get("section", "")
    assessment = None
    section = None
    if assessment_id:
        if not assessment_id.isdecimal():
            raise PermissionDenied
        assessment = _assessment_or_404(request, int(assessment_id))
    else:
        _require_management_access(request.user)
    if section_id:
        if assessment is None or not section_id.isdecimal():
            raise PermissionDenied
        assessment, section = _section_or_404(
            request,
            assessment.pk,
            int(section_id),
        )
    return render(
        request,
        "assessment/question_import_options.html",
        {
            "assessment": assessment,
            "section": section,
        },
    )


@login_required
def question_import_template(request, question_type):
    if question_type not in {"mcq", "coding"}:
        raise Http404
    _require_assessment_management_access(request.user)
    workbook = build_import_template(question_type)
    response = HttpResponse(
        workbook.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{question_type}-questions-template.xlsx"'
    )
    return response


@login_required
def question_import(request, question_type):
    if question_type not in {"mcq", "coding"}:
        raise Http404

    assessment_id = request.POST.get("assessment") or request.GET.get("assessment", "")
    section_id = request.POST.get("section") or request.GET.get("section", "")
    assessment = None
    section = None
    if assessment_id:
        if not assessment_id.isdecimal():
            raise PermissionDenied
        assessment = _assessment_or_404(request, int(assessment_id))
    else:
        _require_management_access(request.user)
    if section_id:
        if assessment is None or not section_id.isdecimal():
            raise PermissionDenied
        assessment, section = _section_or_404(
            request,
            assessment.pk,
            int(section_id),
        )

    errors = []
    imported_count = 0
    skipped = []
    if request.method == "POST":
        if assessment is not None and section is None:
            selected_section_id = request.POST.get("section_id", "")
            if selected_section_id:
                section = get_object_or_404(
                    assessment.sections,
                    pk=selected_section_id,
                )
        upload = request.FILES.get("file")
        if upload is None:
            errors.append("Choose an .xlsx or .pdf file to import.")
        else:
            try:
                candidates = parse_question_file(upload, question_type)
                with transaction.atomic():
                    imported, skipped = import_question_candidates(
                        candidates,
                        question_type,
                        request.user,
                        assessment=assessment,
                        section=section,
                    )
                imported_count = len(imported)
            except ImportFileError as exc:
                errors.append(str(exc))

    return render(
        request,
        "assessment/question_import.html",
        {
            "question_type": question_type,
            "assessment": assessment,
            "section": section,
            "sections": assessment.sections.order_by("position") if assessment else [],
            "errors": errors,
            "imported_count": imported_count,
            "skipped": skipped,
            "template_url": reverse(
                "assessment:question_import_template",
                args=[question_type],
            ),
        },
    )


@login_required
def mcq_question_create(request):
    assessment = _question_creation_assessment(request)
    form = McqQuestionForm(_post_data(request))
    question = form.instance
    option_formset = McqOptionFormSet(
        _post_data(request),
        instance=question,
    )
    if request.method == "POST":
        form_valid = form.is_valid()
        formset_valid = option_formset.is_valid()
        if form_valid and formset_valid:
            with transaction.atomic():
                question = form.save(commit=False)
                question.owner = request.user
                question.save()
                option_formset.instance = question
                option_formset.save()
            messages.success(request, "MCQ question created.")
            return redirect(_question_return_url(request))
    return render(
        request,
        "assessment/question_form.html",
        _question_form_context(
            "mcq",
            form,
            option_formset=option_formset,
            mode="create",
            next_url=request.POST.get("next") or request.GET.get("next", ""),
            assessment=assessment,
        ),
    )


@login_required
def mcq_question_edit(request, question_id):
    question = get_object_or_404(
        _managed_questions(McqQuestion, request.user),
        pk=question_id,
    )
    _require_management_access(request.user)
    form = McqQuestionForm(_post_data(request), instance=question)
    option_formset = McqOptionFormSet(
        _post_data(request),
        instance=question,
    )
    if request.method == "POST":
        form_valid = form.is_valid()
        formset_valid = option_formset.is_valid()
        if form_valid and formset_valid:
            with transaction.atomic():
                form.save()
                option_formset.save()
            messages.success(request, "MCQ question changes saved.")
            return redirect("assessment:question_bank")
    return render(
        request,
        "assessment/question_form.html",
        _question_form_context(
            "mcq",
            form,
            option_formset=option_formset,
            question=question,
            mode="edit",
        ),
    )


@login_required
def coding_question_create(request):
    assessment = _question_creation_assessment(request)
    form = CodingQuestionForm(_post_data(request))
    question = form.instance
    language_formset_kwargs = {}
    if request.method != "POST":
        default_languages = list(
            ProgrammingLanguage.objects.filter(
                is_active=True,
                is_judge0_executable=True,
            ).order_by("name")
        )
        language_formset_kwargs = {
            "initial": [{"language": language.pk} for language in default_languages],
            "extra": max(len(default_languages), 1),
        }
    language_formset = CodingQuestionLanguageFormSet(
        _post_data(request),
        instance=question,
        prefix="languages",
        **language_formset_kwargs,
    )
    test_case_formset = CodingTestCaseFormSet(
        _post_data(request),
        instance=question,
        prefix="test-cases",
    )
    if request.method == "POST":
        form_valid = form.is_valid()
        languages_valid = language_formset.is_valid()
        cases_valid = test_case_formset.is_valid()
        if form_valid and languages_valid and cases_valid:
            with transaction.atomic():
                question = form.save(commit=False)
                question.owner = request.user
                question.save()
                language_formset.instance = question
                test_case_formset.instance = question
                language_formset.save()
                test_case_formset.save()
            messages.success(request, "Coding question created.")
            return redirect(_question_return_url(request))
    return render(
        request,
        "assessment/question_form.html",
        _question_form_context(
            "coding",
            form,
            language_formset=language_formset,
            test_case_formset=test_case_formset,
            mode="create",
            next_url=request.POST.get("next") or request.GET.get("next", ""),
            assessment=assessment,
        ),
    )


@login_required
def coding_question_edit(request, question_id):
    question = get_object_or_404(
        _managed_questions(CodingQuestion, request.user),
        pk=question_id,
    )
    _require_management_access(request.user)
    form = CodingQuestionForm(_post_data(request), instance=question)
    language_formset = CodingQuestionLanguageFormSet(
        _post_data(request),
        instance=question,
        prefix="languages",
    )
    test_case_formset = CodingTestCaseFormSet(
        _post_data(request),
        instance=question,
        prefix="test-cases",
    )
    if request.method == "POST":
        form_valid = form.is_valid()
        languages_valid = language_formset.is_valid()
        cases_valid = test_case_formset.is_valid()
        if form_valid and languages_valid and cases_valid:
            with transaction.atomic():
                form.save()
                language_formset.save()
                test_case_formset.save()
            messages.success(request, "Coding question changes saved.")
            return redirect("assessment:question_bank")
    return render(
        request,
        "assessment/question_form.html",
        _question_form_context(
            "coding",
            form,
            language_formset=language_formset,
            test_case_formset=test_case_formset,
            question=question,
            mode="edit",
        ),
    )


@login_required
def section_question_add(request, assessment_id, section_id):
    assessment, section = _section_or_404(request, assessment_id, section_id)
    if request.method == "POST" and "bulk_add" in request.POST:
        question_type = request.POST.get("question_type", "mcq")
        selected_ids = request.POST.getlist("selected_questions")
        if question_type not in {"mcq", "coding"}:
            messages.error(request, "Choose a valid question type.")
        elif not selected_ids:
            messages.error(request, "Select at least one question to add.")
        elif any(not question_id.isdecimal() for question_id in selected_ids):
            messages.error(request, "The selected question list is invalid.")
        else:
            question_model = McqQuestion if question_type == "mcq" else CodingQuestion
            category_filter = request.POST.get("category", "").strip()
            query_filter = request.POST.get("q", "").strip()
            topic_filter = request.POST.get("topic", "").strip()
            subtopic_filter = request.POST.get("subtopic", "").strip()
            available_questions = _managed_questions(
                question_model,
                request.user,
            ).filter(
                is_active=True,
                pk__in=selected_ids,
            ).exclude(
                assessment_assignments__assessment=assessment,
            )
            if question_type == "mcq" and category_filter:
                available_questions = available_questions.filter(
                    category=category_filter
                )
            if query_filter:
                available_questions = available_questions.filter(
                    Q(title__icontains=query_filter)
                    | Q(topic__icontains=query_filter)
                    | Q(statement__icontains=query_filter)
                )
            if topic_filter:
                available_questions = available_questions.filter(
                    topic__iexact=topic_filter
                )
            if subtopic_filter:
                subtopic_field = "sub_topic" if question_type == "mcq" else "subtopic"
                available_questions = available_questions.filter(
                    **{f"{subtopic_field}__iexact": subtopic_filter}
                )
            available_questions = available_questions.distinct()
            questions_by_id = {
                str(question.pk): question for question in available_questions
            }
            unique_ids = list(dict.fromkeys(selected_ids))
            if len(questions_by_id) != len(unique_ids):
                messages.error(
                    request,
                    "One or more selected questions are unavailable or already assigned.",
                )
            else:
                question_field = (
                    "mcq_question" if question_type == "mcq" else "coding_question"
                )
                with transaction.atomic():
                    locked_assessment = Assessment.objects.select_for_update().get(
                        pk=assessment.pk
                    )
                    locked_section = AssessmentSection.objects.get(
                        pk=section.pk,
                        assessment=locked_assessment,
                    )
                    still_available = _managed_questions(
                        question_model,
                        request.user,
                    ).filter(
                        is_active=True,
                        pk__in=unique_ids,
                    ).exclude(
                        assessment_assignments__assessment=locked_assessment,
                    ).count()
                    if still_available != len(unique_ids):
                        messages.error(
                            request,
                            "One or more selected questions are already assigned.",
                        )
                        return redirect(
                            f"{reverse('assessment:section_question_add', args=[assessment.pk, section.pk])}"
                            f"?question_type={question_type}"
                        )
                    last_position = locked_section.questions.aggregate(
                        last_position=Max("position")
                    )["last_position"] or 0
                    assignments = [
                        AssessmentQuestion(
                            assessment=locked_assessment,
                            section=locked_section,
                            position=last_position + index,
                            max_score=1,
                            negative_marks=0,
                            **{question_field: questions_by_id[question_id]},
                        )
                        for index, question_id in enumerate(unique_ids, start=1)
                    ]
                    AssessmentQuestion.objects.bulk_create(assignments)
                messages.success(
                    request,
                    f"{len(assignments)} question(s) added to {section.title}.",
                )
                return redirect(
                    f"{reverse('assessment:assessment_detail', args=[assessment.pk])}"
                    f"?tab=questions#section-{section.pk}"
                )

    form = AssessmentQuestionAddForm(
        _post_data(request),
        assessment=assessment,
        user=request.user,
        section=section,
    )
    question_type = (
        request.POST.get("question_type")
        if request.method == "POST"
        else request.GET.get("question_type", "mcq")
    )
    if question_type not in {"coding", "mcq"}:
        question_type = "mcq"
    category = (
        request.POST.get("category", "")
        if request.method == "POST"
        else request.GET.get("category", "")
    )
    valid_categories = {value for value, _ in McqQuestion.Category.choices}
    if category not in valid_categories:
        category = ""
    query = (
        request.POST.get("q", "")
        if request.method == "POST"
        else request.GET.get("q", "")
    ).strip()
    topic = (
        request.POST.get("topic", "")
        if request.method == "POST"
        else request.GET.get("topic", "")
    ).strip()
    subtopic = (
        request.POST.get("subtopic", "")
        if request.method == "POST"
        else request.GET.get("subtopic", "")
    ).strip()
    question_model = McqQuestion if question_type == "mcq" else CodingQuestion
    available_questions = _managed_questions(
        question_model,
        request.user,
    ).filter(
        is_active=True,
    ).exclude(
        assessment_assignments__assessment=assessment,
    )
    if question_type == "mcq" and category:
        available_questions = available_questions.filter(category=category)
    if query:
        available_questions = available_questions.filter(
            Q(title__icontains=query)
            | Q(topic__icontains=query)
            | Q(statement__icontains=query)
        )
    if topic:
        available_questions = available_questions.filter(topic__iexact=topic)
    subtopic_field = "sub_topic" if question_type == "mcq" else "subtopic"
    if subtopic:
        available_questions = available_questions.filter(
            **{f"{subtopic_field}__iexact": subtopic}
        )
    available_questions = available_questions.distinct().order_by("title")
    if question_type == "mcq":
        available_questions = available_questions.prefetch_related("options")
        question_rows = [
            {
                "id": question.pk,
                "title": question.title,
                "topic": question.topic,
                "subtopic": question.sub_topic,
                "category": question.get_category_display(),
                "statement": question.statement,
                "options": list(question.options.all()),
            }
            for question in available_questions
        ]
    else:
        question_rows = [
            {
                "id": question.pk,
                "title": question.title,
                "topic": question.topic,
                "subtopic": question.subtopic,
                "category": question.get_coding_mode_display(),
                "statement": question.statement,
                "options": [],
            }
            for question in available_questions
        ]
    filter_options = _managed_questions(question_model, request.user).filter(
        is_active=True,
    )
    if question_type == "mcq" and category:
        filter_options = filter_options.filter(category=category)
    topic_options = list(
        filter_options.order_by("topic")
        .values_list("topic", flat=True)
        .distinct()
    )
    if topic:
        filter_options = filter_options.filter(topic__iexact=topic)
    subtopic_options = list(
        filter_options.order_by(subtopic_field)
        .values_list(subtopic_field, flat=True)
        .distinct()
    )
    if request.method == "POST" and form.is_valid():
        question_field = (
            "mcq_question"
            if form.cleaned_data["question_type"] == "mcq"
            else "coding_question"
        )
        with transaction.atomic():
            locked_assessment = Assessment.objects.select_for_update().get(
                pk=assessment.pk
            )
            if AssessmentQuestion.objects.filter(
                assessment=locked_assessment,
                **{question_field: form.selected_question},
            ).exists():
                form.add_error(
                    "question_id",
                    "This question is already in the assessment.",
                )
            else:
                locked_section = AssessmentSection.objects.get(
                    pk=section.pk,
                    assessment=locked_assessment,
                )
                last_position = locked_section.questions.aggregate(
                    last_position=Max("position")
                )["last_position"]
                AssessmentQuestion.objects.create(
                    assessment=locked_assessment,
                    section=locked_section,
                    position=(last_position or 0) + 1,
                    max_score=form.cleaned_data["max_score"],
                    negative_marks=form.cleaned_data["negative_marks"],
                    **{question_field: form.selected_question},
                )
        if not form.errors:
            messages.success(request, "Question added to the section.")
            return redirect(
                f"{reverse('assessment:assessment_detail', args=[assessment.pk])}"
                f"?tab=questions#section-{section.pk}"
            )
    return render(
        request,
        "assessment/assignment_form.html",
        {
            "form": form,
            "assessment": assessment,
            "section": section,
            "question_type": question_type,
            "question_types": AssessmentQuestionAddForm.QUESTION_TYPES,
            "question_categories": McqQuestion.Category.choices,
            "category": category,
            "query": query,
            "topic": topic,
            "subtopic": subtopic,
            "topic_options": [value for value in topic_options if value],
            "subtopic_options": [value for value in subtopic_options if value],
            "question_rows": question_rows,
        },
    )


@login_required
def section_question_search(request, assessment_id, section_id):
    assessment, section = _section_or_404(request, assessment_id, section_id)
    del section
    query = request.GET.get("q", "").strip()
    question_type = request.GET.get("type", "coding")
    if question_type not in {"coding", "mcq"}:
        return JsonResponse({"results": []}, status=400)
    if not query:
        return JsonResponse({"results": []})

    question_model = CodingQuestion if question_type == "coding" else McqQuestion
    questions = _managed_questions(question_model, request.user).filter(
        is_active=True,
        title__icontains=query,
    ).exclude(
        assessment_assignments__assessment=assessment
    ).distinct().order_by("title")[:10]

    if question_type == "coding":
        results = [
            {
                "id": question.pk,
                "title": question.title,
                "topic": question.topic,
                "subtopic": question.subtopic,
                "mode": question.get_coding_mode_display(),
            }
            for question in questions
        ]
    else:
        results = [
            {
                "id": question.pk,
                "title": question.title,
                "topic": question.topic,
                "subtopic": question.sub_topic,
                "mode": "",
            }
            for question in questions
        ]
    return JsonResponse({"results": results})


@login_required
@require_POST
def section_question_remove(request, assessment_id, section_id, assignment_id):
    assessment, section = _section_or_404(request, assessment_id, section_id)
    assignment = get_object_or_404(
        AssessmentQuestion,
        pk=assignment_id,
        assessment=assessment,
        section=section,
    )
    assignment.delete()
    messages.success(request, "Question removed from the section.")
    return redirect(
        f"{reverse('assessment:assessment_detail', args=[assessment.pk])}"
        f"?tab=questions#section-{section.pk}"
    )
