"""
leaderboard/services.py
-----------------------
Every leaderboard query lives here, so the view (and later the profile
page) share ONE definition of "points" and "rank".

Source of truth: accepted rows in submissions.Submission.

* A problem counts once per user, however many accepted submissions it has
  (COUNT(DISTINCT problem_id)).
* Only active problems and active users count.
* Points are computed inside the database in a single grouped query;
  nothing is looped over in Python.

Tie-breaks (all from existing data):
    points DESC -> problems solved DESC -> older account first -> user id
"""

from datetime import timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

from problems.models import DifficultyChoices
from submissions.models import Submission, SubmissionStatusChoices

POINTS = {
    DifficultyChoices.EASY: 10,
    DifficultyChoices.MEDIUM: 25,
    DifficultyChoices.HARD: 50,
}

RANK_ORDERING = ('-points', '-solved', 'user__created_at', 'user_id')


def _unique_solved(difficulty):
    return Count('problem_id', filter=Q(problem__difficulty=difficulty), distinct=True)


def _period_cutoff(period='all'):
    period = (period or 'all').lower()
    if period == 'week':
        return timezone.now() - timedelta(days=7)
    if period == 'month':
        return timezone.now() - timedelta(days=30)
    return None


def solver_stats(period='all'):
    """
    One row per active user with at least one accepted submission on an
    active problem, carrying easy_solved / medium_solved / hard_solved,
    solved and points.  Unordered; callers add ordering or filters.
    """
    easy, medium, hard = (
        DifficultyChoices.EASY, DifficultyChoices.MEDIUM, DifficultyChoices.HARD,
    )
    queryset = Submission.objects.filter(
        status=SubmissionStatusChoices.ACCEPTED,
        problem__is_active=True,
        user__is_active=True,
    )
    cutoff = _period_cutoff(period)
    if cutoff is not None:
        queryset = queryset.filter(submitted_at__gte=cutoff)
    return (
        queryset
        .order_by()  # drop Submission.Meta.ordering so it can't leak into GROUP BY
        .values('user_id', 'user__user_name', 'user__avatar_url', 'user__created_at')
        .annotate(
            easy_solved=_unique_solved(easy),
            medium_solved=_unique_solved(medium),
            hard_solved=_unique_solved(hard),
        )
        .annotate(
            solved=F('easy_solved') + F('medium_solved') + F('hard_solved'),
            points=(
                F('easy_solved') * POINTS[easy]
                + F('medium_solved') * POINTS[medium]
                + F('hard_solved') * POINTS[hard]
            ),
        )
    )


def leaderboard_queryset(query='', period='all'):
    """Ranked users only (points > 0), best first."""
    queryset = solver_stats(period=period).filter(points__gt=0)
    if query:
        queryset = queryset.filter(user__user_name__istartswith=query)
    return queryset.order_by(*RANK_ORDERING)


def get_user_standing(user_id, period='all'):
    """
    Rank and stats for one user, using two small queries and no full scan
    in Python.  rank is None when the user has no points yet.
    """
    empty = {
        'rank': None, 'points': 0, 'solved': 0,
        'easy_solved': 0, 'medium_solved': 0, 'hard_solved': 0,
    }
    found = list(solver_stats(period=period).filter(user_id=user_id)[:1])
    if not found or found[0]['points'] <= 0:
        return empty

    me = found[0]
    # Users strictly ahead of me under RANK_ORDERING.
    ahead = solver_stats(period=period).filter(
        Q(points__gt=me['points'])
        | Q(points=me['points'], solved__gt=me['solved'])
        | Q(points=me['points'], solved=me['solved'],
            user__created_at__lt=me['user__created_at'])
        | Q(points=me['points'], solved=me['solved'],
            user__created_at=me['user__created_at'], user_id__lt=me['user_id'])
    ).count()

    return {
        'rank': ahead + 1,
        'points': me['points'],
        'solved': me['solved'],
        'easy_solved': me['easy_solved'],
        'medium_solved': me['medium_solved'],
        'hard_solved': me['hard_solved'],
    }