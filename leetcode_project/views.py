"""
Landing page view.

Everything the home page shows as a number or a list comes from the
database, so the marketing copy can never drift away from reality.
Each block is computed independently and fails soft: a broken query
hides one section instead of taking the whole landing page down.
"""

import logging

from django.db import DatabaseError
from django.db.models import Count, Q
from django.shortcuts import render

from assessment.models import CodingQuestion, McqQuestion
from leaderboard import services as leaderboard_services
from problems.models import DifficultyChoices, Language, Problem
from problems.stats import acceptance_percent, annotate_acceptance
from submissions.models import Submission, SubmissionStatusChoices

logger = logging.getLogger(__name__)


def _safe(fn, default):
    try:
        return fn()
    except DatabaseError:
        logger.exception("Landing page query failed: %s", fn.__name__)
        return default


def _problem_stats():
    return Problem.objects.filter(is_active=True).aggregate(
        total=Count("id"),
        easy=Count("id", filter=Q(difficulty=DifficultyChoices.EASY)),
        medium=Count("id", filter=Q(difficulty=DifficultyChoices.MEDIUM)),
        hard=Count("id", filter=Q(difficulty=DifficultyChoices.HARD)),
    )


def _featured_problems():
    problems = list(
        annotate_acceptance(Problem.objects.filter(is_active=True, is_premium=False))
        .order_by("order_num", "id")
        .only("title", "slug", "difficulty", "order_num")[:7]
    )
    for problem in problems:
        problem.acceptance = acceptance_percent(problem)
    return problems


def _languages():
    return list(
        Language.objects.filter(is_active=True)
        .order_by("name")
        .values_list("name", flat=True)
    )


def _question_bank_size():
    return CodingQuestion.objects.count() + McqQuestion.objects.count()


def _accepted_count():
    return Submission.objects.filter(status=SubmissionStatusChoices.ACCEPTED).count()


def _top_solvers():
    rows = leaderboard_services.leaderboard_queryset(period="all")[:3]
    return [
        {"username": row["user__user_name"], "points": row["points"], "solved": row["solved"]}
        for row in rows
    ]


def home(request):
    problem_stats = _safe(_problem_stats, {"total": 0, "easy": 0, "medium": 0, "hard": 0})
    languages = _safe(_languages, [])

    context = {
        "problem_stats": problem_stats,
        "featured_problems": _safe(_featured_problems, []),
        "languages": languages,
        "question_bank_size": _safe(_question_bank_size, 0),
        "accepted_count": _safe(_accepted_count, 0),
        "top_solvers": _safe(_top_solvers, []),
        "is_faculty": request.user.is_authenticated
        and (request.user.is_staff or getattr(request.user, "is_faculty", False)),
    }
    return render(request, "index.html", context)
