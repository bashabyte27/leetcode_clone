"""
problems/models.py
------------------
Handles problems, tags, companies, test cases, code templates,
editorials, daily challenges, bookmarks, reports, notes, and
user-created problem lists.

Key improvements vs original:
  - Language model replaces bare CharField (consistent across apps)
  - DailyChallenge model added
  - UserNote model added
  - ProblemList / ProblemListItem with correct unique constraints
  - ProblemReport uses TextChoices for both reason and status
  - Problem has is_active flag and order_num (problem number)
  - ProblemCompany tracks frequency (how often company asks it)
  - Editorial has time/space complexity and is_published flag
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


# ─────────────────────────── Choices ────────────────────────────


class DifficultyChoices(models.TextChoices):
    EASY = 'easy', 'Easy'
    MEDIUM = 'medium', 'Medium'
    HARD = 'hard', 'Hard'


class ProblemReportReasonChoices(models.TextChoices):
    INCORRECT = 'incorrect', 'Incorrect Problem'
    DUPLICATE = 'duplicate', 'Duplicate Problem'
    OUTDATED = 'outdated', 'Outdated Content'
    INAPPROPRIATE = 'inappropriate', 'Inappropriate Content'
    OTHER = 'other', 'Other'


class ProblemReportStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    REVIEWED = 'reviewed', 'Reviewed'
    RESOLVED = 'resolved', 'Resolved'
    REJECTED = 'rejected', 'Rejected'


# ─────────────────────── Shared / Reference ──────────────────────


class Language(models.Model):
    """
    Central language registry.
    All apps that reference a language (Submissions, CodeTemplates,
    DraftCode, Discussions) use a FK to this model instead of a
    bare CharField — one place to add/deprecate a language.
    """
    name = models.CharField(max_length=50, unique=True)   # Python 3, C++17, Java 17
    slug = models.SlugField(unique=True, db_index=True)
    version = models.CharField(max_length=20, blank=True, null=True)
    # judge_id maps to Judge0 or similar online judge system IDs
    judge_id = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = 'Language'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name}" + (f" {self.version}" if self.version else "")


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, db_index=True)

    class Meta:
        verbose_name = 'Tag'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    logo_url = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


# ──────────────────────── Problem Core ───────────────────────────


class Problem(models.Model):
    """
    Core problem entity.
    M2M to Tag and Company are through explicit join tables so we
    can store extra attributes (frequency on ProblemCompany).
    """
    # LeetCode-style numeric ID (e.g. 1 = Two Sum)
    order_num = models.PositiveIntegerField(unique=True, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField()
    difficulty = models.CharField(
        max_length=10,
        choices=DifficultyChoices.choices,
        db_index=True,
    )
    # Stored acceptance rate — recomputed periodically by a background task
    acceptance_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    likes = models.PositiveIntegerField(default=0)
    dislikes = models.PositiveIntegerField(default=0)
    is_premium = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    tags = models.ManyToManyField(Tag, through='ProblemTag', related_name='problems')
    companies = models.ManyToManyField(Company, through='ProblemCompany', related_name='problems')

    created_by = models.ForeignKey(
        'users.Users',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_problems',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Problem'
        ordering = ['order_num']
        indexes = [
            models.Index(fields=['difficulty', 'is_active']),
            models.Index(fields=['is_premium', 'is_active']),
            models.Index(fields=['slug']),
            models.Index(fields=['order_num']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        num = f"#{self.order_num} " if self.order_num else ""
        return f"{num}{self.title} [{self.difficulty}]"


# ──────────────────────── Join Tables ────────────────────────────


class ProblemTag(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='problem_tags')
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name='tag_problems')

    class Meta:
        unique_together = ('problem', 'tag')
        verbose_name = 'Problem Tag'

    def __str__(self) -> str:
        return f"{self.problem.title} | {self.tag.name}"


class ProblemCompany(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='problem_companies')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='company_problems')
    # 0.0–1.0 normalised frequency score; higher = asked more often
    frequency = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('problem', 'company')
        verbose_name = 'Problem Company'
        ordering = ['-frequency']

    def __str__(self) -> str:
        return f"{self.problem.title} | {self.company.name} ({self.frequency:.0%})"


# ──────────────────── Problem Sub-Models ─────────────────────────


class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField()
    expected_output = models.TextField()
    is_sample = models.BooleanField(default=False)
    # explanation is only relevant for sample test cases shown on the problem page
    explanation = models.TextField(blank=True, null=True)
    order_num = models.PositiveIntegerField()

    class Meta:
        unique_together = ('problem', 'order_num')
        ordering = ['order_num']
        verbose_name = 'Test Case'

    def __str__(self) -> str:
        return f"TC #{self.order_num} — {self.problem.title}"


class ProblemHint(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='hints')
    hint_text = models.TextField()
    order_num = models.PositiveIntegerField()

    class Meta:
        unique_together = ('problem', 'order_num')
        ordering = ['order_num']
        verbose_name = 'Problem Hint'

    def __str__(self) -> str:
        return f"Hint #{self.order_num} — {self.problem.title}"


class CodeTemplate(models.Model):
    """
    Per-language starter code shown to the user.
    solution_code is staff-only; never exposed via public API.
    Language FK replaces the original bare CharField.
    """
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='code_templates')
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='templates')
    template_code = models.TextField()
    solution_code = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('problem', 'language')
        verbose_name = 'Code Template'

    def __str__(self) -> str:
        return f"Template: {self.problem.title} | {self.language.name}"


class Editorial(models.Model):
    """
    Official editorial / solution explanation for a problem.
    is_published controls visibility; allows staff to draft before making public.
    """
    problem = models.OneToOneField(Problem, on_delete=models.CASCADE, related_name='editorial')
    content = models.TextField()                        # Markdown or HTML
    video_url = models.URLField(blank=True, null=True)
    time_complexity = models.CharField(max_length=100, blank=True, null=True)   # e.g. O(n log n)
    space_complexity = models.CharField(max_length=100, blank=True, null=True)  # e.g. O(1)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Editorial'

    def __str__(self) -> str:
        return f"Editorial: {self.problem.title}"


# ──────────────────────── Daily Challenge ────────────────────────


class DailyChallenge(models.Model):
    """
    One problem featured per calendar date.
    Drives streak tracking in UserStats.
    The unique constraint on `date` enforces exactly one challenge per day.
    """
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='daily_challenges')
    date = models.DateField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Daily Challenge'
        ordering = ['-date']

    def __str__(self) -> str:
        return f"Daily {self.date}: {self.problem.title}"


# ──────────────────── User-Problem Interactions ───────────────────


class Bookmark(models.Model):
    user = models.ForeignKey('users.Users', on_delete=models.CASCADE, related_name='bookmarks')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'problem')
        verbose_name = 'Bookmark'
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self) -> str:
        return f"{self.user.user_name} → {self.problem.title}"


class ProblemReport(models.Model):
    """
    Bug fix: both `reason` and `status` now use TextChoices.
    `resolved_by` lets us track which moderator handled it.
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='problem_reports',
    )
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=30, choices=ProblemReportReasonChoices.choices)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=ProblemReportStatusChoices.choices,
        default=ProblemReportStatusChoices.PENDING,
        db_index=True,
    )
    resolved_by = models.ForeignKey(
        'users.Users',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Problem Report'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['problem', 'status']),
        ]

    def __str__(self) -> str:
        return f"Report: {self.problem.title} by {self.user.user_name}"


class UserNote(models.Model):
    """
    Personal markdown notes a user keeps per problem.
    OneToOne through unique_together — one note doc per (user, problem) pair.
    """
    user = models.ForeignKey('users.Users', on_delete=models.CASCADE, related_name='notes')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='user_notes')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'problem')
        verbose_name = 'User Note'
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self) -> str:
        return f"Note: {self.user.user_name} on {self.problem.title}"


# ──────────────────────── Problem Lists ──────────────────────────


class ProblemList(models.Model):
    """User-curated problem lists (public or private)."""
    user = models.ForeignKey('users.Users', on_delete=models.CASCADE, related_name='problem_lists')
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    is_public = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Problem List'
        indexes = [
            models.Index(fields=['user', 'is_public']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.user_id}-{self.title}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"List: {self.title} by {self.user.user_name}"


class ProblemListItem(models.Model):
    """
    Bug fix (original): unique_together only had (problem_list, order_num),
    which allowed the same problem to appear multiple times in a list.
    Added (problem_list, problem) constraint to prevent duplicates.
    """
    problem_list = models.ForeignKey(ProblemList, on_delete=models.CASCADE, related_name='items')
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='list_appearances')
    notes = models.TextField(blank=True, null=True)
    order_num = models.PositiveIntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ('problem_list', 'order_num'),   # ordering unique per list
            ('problem_list', 'problem'),     # no duplicate problems in a list
        ]
        ordering = ['order_num']
        verbose_name = 'Problem List Item'

    def __str__(self) -> str:
        return f"{self.problem_list.title} | #{self.order_num} {self.problem.title}"