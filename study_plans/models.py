"""
study_plans/models.py
---------------------
Handles curated study plans, their daily problem schedules, user enrolment,
per-day progress tracking, and user-created custom problem lists.

Key design decisions:
  - StudyPlan / StudyPlanItem: admin-curated plans are read-only to users.
    Users enrol into a plan — they do not modify it. This is modelled by
    keeping StudyPlan and StudyPlanItem as pure content tables and
    UserStudyPlan / UserStudyPlanProgress as the user-state tables.

  - StudyPlanItem: unique_together covers (study_plan, day_num, order_num)
    rather than just (study_plan, day_num) — a single day can and should
    have multiple problems. The original had this wrong.

  - UserStudyPlanProgress: one row per (user, study_plan_item) — tracks
    completion of each individual problem within a day, not just the day.
    This allows partial-day completion and is required for the progress bar.

  - UserStudyPlan: tracks enrolment metadata and the user's current day.
    `completed_at` is set automatically by a signal when all items are done.

  - ProblemList / ProblemListItem: user-created bookmarked lists
    (equivalent to LeetCode's "Favourite" lists). Completely separate from
    admin study plans — different purpose, different ownership model.

  - ProblemListItem: `order_num` is unique_together with `problem_list` —
    not globally unique. The original made it globally unique which meant
    only one list could have an item at position 1. Fixed here.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# ─────────────────────────── Choices ────────────────────────────


class PlanDifficultyChoices(models.TextChoices):
    BEGINNER = 'beginner', 'Beginner'
    EASY = 'easy', 'Easy'
    MEDIUM = 'medium', 'Medium'
    HARD = 'hard', 'Hard'
    MIXED = 'mixed', 'Mixed'


# ─────────────────────────── Study Plan ──────────────────────────


class StudyPlan(models.Model):
    """
    Admin-curated study plan (e.g. "SQL 50", "Top Interview 150").
    Users enrol into these — they cannot edit the plan itself.

    `total_days` is a denormalised count of distinct day_num values in
    StudyPlanItem. It is set manually by admins and used for display
    (progress bar denominator) without a GROUP BY query on every page load.

    `is_premium`: if True, only users with an active subscription can enrol.
    Check this before creating a UserStudyPlan row.
    """
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField()
    difficulty = models.CharField(
        max_length=20,
        choices=PlanDifficultyChoices.choices,
        default=PlanDifficultyChoices.MIXED,
        db_index=True,
    )
    total_days = models.PositiveSmallIntegerField(
        default=30,
        help_text='Total number of days in the plan. Must match the max day_num in StudyPlanItem.',
    )
    total_problems = models.PositiveSmallIntegerField(
        default=0,
        help_text='Denormalised count of all problems across all days. Updated on item save/delete.',
    )
    cover_image_url = models.URLField(blank=True)
    is_premium = models.BooleanField(
        default=False,
        db_index=True,
        help_text='If True, only premium users can enrol.',
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Inactive plans are hidden from the catalogue but existing enrolments are unaffected.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Study Plan'
        ordering = ['title']
        indexes = [
            models.Index(fields=['is_active', 'is_premium']),
            models.Index(fields=['difficulty', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def completion_label(self) -> str:
        """Returns a short label for display: '30 Days', '75 Problems'."""
        return f"{self.total_days} Days · {self.total_problems} Problems"

    def __str__(self) -> str:
        return f"StudyPlan: {self.title} | {self.difficulty} | {self.total_days} days"


# ─────────────────────── Study Plan Item ─────────────────────────


class StudyPlanItem(models.Model):
    """
    One problem within a study plan, assigned to a specific day and position.

    unique_together covers (study_plan, day_num, order_num) — not just
    (study_plan, day_num). A single day has multiple problems ordered by
    order_num. The original model's constraint prevented this entirely.

    unique_together also covers (study_plan, problem) — the same problem
    cannot appear twice in the same plan on different days.
    """
    study_plan = models.ForeignKey(
        StudyPlan,
        on_delete=models.CASCADE,
        related_name='items',
    )
    problem = models.ForeignKey(
        'problems.Problem',
        on_delete=models.CASCADE,
        related_name='study_plan_items',
    )
    day_num = models.PositiveSmallIntegerField(
        help_text='Which day of the plan this problem belongs to (1-indexed).',
    )
    order_num = models.PositiveSmallIntegerField(
        help_text='Display order within the day (1 = first problem of the day).',
    )
    note = models.TextField(
        blank=True,
        help_text='Optional editorial note shown alongside the problem on this day.',
    )

    class Meta:
        unique_together = [
            ('study_plan', 'day_num', 'order_num'),   # no duplicate positions within a day
            ('study_plan', 'problem'),                 # no duplicate problems within a plan
        ]
        ordering = ['day_num', 'order_num']
        verbose_name = 'Study Plan Item'
        indexes = [
            models.Index(fields=['study_plan', 'day_num']),
        ]

    def clean(self):
        if self.day_num and self.study_plan_id:
            if self.day_num > self.study_plan.total_days:
                raise ValidationError(
                    f"day_num ({self.day_num}) cannot exceed the plan's "
                    f"total_days ({self.study_plan.total_days})."
                )

    def __str__(self) -> str:
        return (
            f"{self.study_plan.title} | "
            f"Day {self.day_num} · #{self.order_num} | "
            f"{self.problem.title}"
        )


# ─────────────────── User Study Plan (Enrolment) ─────────────────


class UserStudyPlan(models.Model):
    """
    Tracks a user's enrolment into a study plan.
    One row per (user, study_plan) — a user can only be enrolled once.

    `current_day` is updated each time the user completes all problems
    for a given day. It drives the "Continue" button on the dashboard.

    `completed_at` is set by a post_save signal on UserStudyPlanProgress
    when every StudyPlanItem in the plan has a corresponding completed
    UserStudyPlanProgress row for this user.

    Do not expose `is_completed` as a field — derive it from `completed_at`
    to keep a single source of truth.
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='study_plan_enrolments',
    )
    study_plan = models.ForeignKey(
        StudyPlan,
        on_delete=models.CASCADE,
        related_name='enrolments',
    )
    current_day = models.PositiveSmallIntegerField(
        default=1,
        help_text='The day the user is currently working on.',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set by signal when all items across all days are marked complete.',
    )

    class Meta:
        unique_together = ('user', 'study_plan')
        verbose_name = 'User Study Plan Enrolment'
        indexes = [
            models.Index(fields=['user', 'completed_at']),
        ]

    @property
    def is_completed(self) -> bool:
        """Single source of truth — derived from completed_at, not a stored flag."""
        return self.completed_at is not None

    @property
    def progress_percent(self) -> int:
        """
        Approximate progress based on current_day vs total_days.
        For precise progress (accounting for partial days), query
        UserStudyPlanProgress directly.
        """
        if self.study_plan.total_days == 0:
            return 0
        return min(100, int((self.current_day - 1) / self.study_plan.total_days * 100))

    def mark_completed(self):
        """Called by signal — sets completed_at if not already set."""
        if not self.completed_at:
            self.completed_at = timezone.now()
            self.save(update_fields=['completed_at'])

    def __str__(self) -> str:
        status = 'Completed' if self.is_completed else f'Day {self.current_day}'
        return f"{self.user.user_name} | {self.study_plan.title} | {status}"


# ──────────────── User Study Plan Progress ────────────────────────


class UserStudyPlanProgress(models.Model):
    """
    Tracks completion of each individual StudyPlanItem by a user.
    One row per (user_study_plan, study_plan_item) — written when the user
    submits an accepted solution for that problem within the plan context.

    This is the ground truth for progress. UserStudyPlan.current_day and
    UserStudyPlan.completed_at are derived from aggregating these rows
    (via signal or periodic task).

    `submission` links to the specific accepted Submission that earned the
    completion mark. This lets us show "Solved in Python in 42ms" on the
    plan detail page without a separate query.
    """
    user_study_plan = models.ForeignKey(
        UserStudyPlan,
        on_delete=models.CASCADE,
        related_name='progress_items',
    )
    study_plan_item = models.ForeignKey(
        StudyPlanItem,
        on_delete=models.CASCADE,
        related_name='user_progress',
    )
    submission = models.ForeignKey(
        'submissions.Submission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='study_plan_completions',
        help_text='The accepted submission that completed this item. Null if marked manually.',
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_study_plan', 'study_plan_item')
        verbose_name = 'User Study Plan Progress'
        indexes = [
            models.Index(fields=['user_study_plan', 'completed_at']),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user_study_plan.user.user_name} | "
            f"{self.study_plan_item.study_plan.title} | "
            f"Day {self.study_plan_item.day_num} | "
            f"{self.study_plan_item.problem.title}"
        )


# ─────────────────────── Problem List ────────────────────────────




