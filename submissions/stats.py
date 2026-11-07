"""
Keeps the denormalised progress tables in step with real submissions:

* UserSolvedProblem: one row per (user, problem) the user has solved
* UserStats: solved counts per difficulty plus submission totals

Both used to be documented as "maintained by a signal", but no signal existed,
so they were always empty or zero (the staff user report reads them).
"""

from django.db import transaction
from django.db.models import Count, Q

from submissions.models import Submission, SubmissionStatusChoices, UserSolvedProblem
from users.models import UserStats

ACCEPTED = SubmissionStatusChoices.ACCEPTED


def record_judged_submission(submission):
    """Call after a submission reaches its final status."""
    with transaction.atomic():
        if submission.status == ACCEPTED:
            _sync_solved(submission.user_id, submission.problem_id)
        refresh_user_stats(submission.user_id)


def _sync_solved(user_id, problem_id):
    subs = Submission.objects.filter(user_id=user_id, problem_id=problem_id)
    accepted = subs.filter(status=ACCEPTED)
    first = accepted.order_by('submitted_at').first()
    if first is None:
        UserSolvedProblem.objects.filter(user_id=user_id, problem_id=problem_id).delete()
        return
    last = accepted.order_by('-submitted_at').first()
    best = accepted.order_by('runtime_ms', 'memory_kb', 'submitted_at').first()
    UserSolvedProblem.objects.update_or_create(
        user_id=user_id,
        problem_id=problem_id,
        defaults={
            'best_submission': best,
            'language_id': best.language_id,
            'attempt_count': subs.count(),
            'first_solved_at': first.submitted_at,
            'last_solved_at': last.submitted_at,
        },
    )


def refresh_user_stats(user_id):
    solved = UserSolvedProblem.objects.filter(user_id=user_id).aggregate(
        easy=Count('id', filter=Q(problem__difficulty='easy')),
        medium=Count('id', filter=Q(problem__difficulty='medium')),
        hard=Count('id', filter=Q(problem__difficulty='hard')),
    )
    totals = Submission.objects.filter(user_id=user_id).aggregate(
        total=Count('id'), accepted=Count('id', filter=Q(status=ACCEPTED)),
    )
    UserStats.objects.update_or_create(
        user_id=user_id,
        defaults={
            'easy_solved': solved['easy'],
            'medium_solved': solved['medium'],
            'hard_solved': solved['hard'],
            'total_submissions': totals['total'],
            'accepted_submissions': totals['accepted'],
        },
    )


def rebuild_all():
    """Backfill from existing submissions (used by the data migration / management command)."""
    pairs = (
        Submission.objects.filter(status=ACCEPTED)
        .values_list('user_id', 'problem_id').distinct()
    )
    for user_id, problem_id in pairs:
        _sync_solved(user_id, problem_id)
    for user_id in Submission.objects.values_list('user_id', flat=True).distinct():
        refresh_user_stats(user_id)
