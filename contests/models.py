"""
contests/models.py
------------------
Handles contests, per-contest problems, participants,
contest submissions, and ELO-style rating history.

Key improvements vs original:
  - ContestSubmission: removed redundant `problem` FK
    (accessible via contest_submission.contest_problem.problem)
  - ContestProblem: unique_together now covers (contest, problem) too —
    the same problem cannot appear twice in one contest
  - ContestRating: new model tracking per-contest ELO delta
  - Contest: is_published flag + created_by for admin workflow
  - ContestParticipant: finish_time stored for tie-breaking
  - SubmissionStatusChoices imported from submissions app (single source)
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from submissions.models import SubmissionStatusChoices


# ─────────────────────────── Choices ────────────────────────────


class ContestTypeChoices(models.TextChoices):
    WEEKLY = 'weekly', 'Weekly Contest'
    BIWEEKLY = 'biweekly', 'Biweekly Contest'
    VIRTUAL = 'virtual', 'Virtual Contest'
    SPECIAL = 'special', 'Special Contest'


# ──────────────────────── Contest ────────────────────────────────


class Contest(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField()
    contest_type = models.CharField(
        max_length=20,
        choices=ContestTypeChoices.choices,
        db_index=True,
    )
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    is_virtual = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False, db_index=True)
    created_by = models.ForeignKey(
        'users.Users',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_contests',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contest'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['start_time', 'is_published']),
            models.Index(fields=['contest_type', 'start_time']),
        ]

    def clean(self):
        if self.end_time and self.start_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def duration_minutes(self) -> int:
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() / 60)
        return 0

    def __str__(self) -> str:
        return f"Contest: {self.title} [{self.contest_type}]"


# ─────────────────────── Contest Problems ────────────────────────


class ContestProblem(models.Model):
    """
    Bug fix (original): unique_together only covered (contest, order_num).
    Added (contest, problem) constraint — same problem cannot appear
    twice in the same contest.
    """
    contest = models.ForeignKey(
        Contest,
        on_delete=models.CASCADE,
        related_name='contest_problems',
    )
    problem = models.ForeignKey(
        'problems.Problem',
        on_delete=models.CASCADE,
        related_name='contest_appearances',
    )
    order_num = models.PositiveSmallIntegerField()   # A=1, B=2, C=3 ...
    points = models.PositiveIntegerField(default=100)

    class Meta:
        unique_together = [
            ('contest', 'order_num'),    # no duplicate positions
            ('contest', 'problem'),      # no duplicate problems
        ]
        ordering = ['order_num']
        verbose_name = 'Contest Problem'

    def __str__(self) -> str:
        label = chr(64 + self.order_num) if self.order_num <= 26 else str(self.order_num)
        return f"{self.contest.title} | {label}. {self.problem.title}"


# ──────────────────── Contest Participant ────────────────────────


class ContestParticipant(models.Model):
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='contest_participations',
    )
    contest = models.ForeignKey(
        Contest,
        on_delete=models.CASCADE,
        related_name='participants',
    )
    rank = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    score = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    penalty_minutes = models.PositiveIntegerField(default=0)
    # Timestamp of last accepted submission — used for tie-breaking
    finish_time = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'contest')
        ordering = ['rank']
        verbose_name = 'Contest Participant'
        indexes = [
            models.Index(fields=['contest', 'rank']),
            models.Index(fields=['user', 'contest']),
        ]

    def __str__(self) -> str:
        return f"{self.user.user_name} | {self.contest.title} | Rank: {self.rank}"


# ─────────────────── Contest Submissions ─────────────────────────


class ContestSubmission(models.Model):
    """
    Bug fix (original): had both a `problem` FK and a `contest_problem` FK.
    `contest_problem` already links to the problem — the direct `problem` FK
    was redundant and could go out of sync.
    Access the problem via: instance.contest_problem.problem

    OneToOne with Submission ensures one contest record per judge submission.
    """
    participant = models.ForeignKey(
        ContestParticipant,
        on_delete=models.CASCADE,
        related_name='contest_submissions',
    )
    contest_problem = models.ForeignKey(
        ContestProblem,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    submission = models.OneToOneField(
        'submissions.Submission',
        on_delete=models.CASCADE,
        related_name='contest_submission',
    )
    score_gained = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    is_accepted = models.BooleanField(default=False, db_index=True)
    # Penalty (wrong attempts × penalty_per_attempt) for ICPC-style scoring
    penalty_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Contest Submission'
        indexes = [
            models.Index(fields=['participant', 'contest_problem']),
            models.Index(fields=['participant', 'is_accepted']),
        ]

    @property
    def problem(self):
        """Convenience accessor — avoids the redundant FK anti-pattern."""
        return self.contest_problem.problem

    def __str__(self) -> str:
        return (
            f"{self.participant.user.user_name} | "
            f"{self.contest_problem.problem.title} | "
            f"Accepted: {self.is_accepted}"
        )


# ──────────────────── Contest Rating ─────────────────────────────


class ContestRating(models.Model):
    """
    ELO-style rating history — one row per (user, contest) after the
    contest ends and rankings are finalised.

    `delta` can be negative (rank poorly → lose rating).
    The current rating lives in UserStats.contest_rating and is updated
    alongside writing a new ContestRating row.
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='contest_ratings',
    )
    contest = models.ForeignKey(
        Contest,
        on_delete=models.CASCADE,
        related_name='ratings',
    )
    rating_before = models.PositiveIntegerField()
    rating_after = models.PositiveIntegerField()
    delta = models.IntegerField()          # rating_after - rating_before (may be negative)
    rank = models.PositiveIntegerField()   # final rank in this contest
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'contest')
        ordering = ['-created_at']
        verbose_name = 'Contest Rating'
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def clean(self):
        if self.delta != (self.rating_after - self.rating_before):
            raise ValidationError(
                "delta must equal rating_after - rating_before."
            )

    def __str__(self) -> str:
        sign = '+' if self.delta >= 0 else ''
        return (
            f"{self.user.user_name} | {self.contest.title} | "
            f"{self.rating_before} → {self.rating_after} ({sign}{self.delta})"
        )