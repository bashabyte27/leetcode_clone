"""
Rebuild solved-problem and user stats tables from real submissions, and close
out submissions stuck in pending/running (e.g. the worker died mid-judge).

    python manage.py rebuild_progress
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from submissions.models import Submission, SubmissionStatusChoices
from submissions.stats import rebuild_all


class Command(BaseCommand):
    help = "Backfill UserSolvedProblem / UserStats and fail stale pending/running submissions."

    def handle(self, *args, **options):
        stale = Submission.objects.filter(
            status__in=[SubmissionStatusChoices.PENDING, SubmissionStatusChoices.RUNNING],
            submitted_at__lt=timezone.now() - timedelta(minutes=10),
        ).update(status=SubmissionStatusChoices.INTERNAL_ERROR)
        rebuild_all()
        self.stdout.write(self.style.SUCCESS(f"Progress rebuilt; {stale} stuck submission(s) closed."))
