"""
submissions/models.py
---------------------
Handles code submissions, per-test-case results, ad-hoc code runs,
and the denormalized UserSolvedProblem table for O(1) solved lookups.

SubmissionStatusChoices is defined here and imported by the
contests app — the single source of truth for submission statuses.
"""

from django.db import models


# ─────────────────────────── Choices ────────────────────────────


class SubmissionStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RUNNING = 'running', 'Running'
    ACCEPTED = 'accepted', 'Accepted'
    WRONG_ANSWER = 'wrong_answer', 'Wrong Answer'
    TIME_LIMIT_EXCEEDED = 'time_limit_exceeded', 'Time Limit Exceeded'
    MEMORY_LIMIT_EXCEEDED = 'memory_limit_exceeded', 'Memory Limit Exceeded'
    RUNTIME_ERROR = 'runtime_error', 'Runtime Error'
    COMPILE_ERROR = 'compile_error', 'Compile Error'
    INTERNAL_ERROR = 'internal_error', 'Internal Error'


# ──────────────────────── Submission ─────────────────────────────


class Submission(models.Model):
    """
    Records a full judge submission.
    runtime_percentile / memory_percentile are computed after judging
    by comparing against all accepted submissions for the same problem
    and language — updated via a background task.
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    problem = models.ForeignKey(
        'problems.Problem',
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    language = models.ForeignKey(
        'problems.Language',
        on_delete=models.SET_NULL,
        null=True,
        related_name='submissions',
    )
    code = models.TextField()
    status = models.CharField(
        max_length=30,
        choices=SubmissionStatusChoices.choices,
        default=SubmissionStatusChoices.PENDING,
        db_index=True,
    )
    runtime_ms = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    memory_kb = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    # Percentile vs other accepted submissions for the same (problem, language)
    runtime_percentile = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    memory_percentile = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Submission'
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['user', 'problem']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['problem', 'status']),
            models.Index(fields=['problem', 'language', 'status']),  # for percentile queries
            models.Index(fields=['submitted_at']),
        ]

    @property
    def is_accepted(self) -> bool:
        return self.status == SubmissionStatusChoices.ACCEPTED

    def __str__(self) -> str:
        return (
            f"Submission: {self.user.user_name} | "
            f"{self.problem.title} | {self.status}"
        )


# ─────────────────── Per-Test-Case Results ───────────────────────


class SubmissionResult(models.Model):
    """
    Individual test case outcome within a submission.
    Storing expected_output here (denormalized from TestCase) lets us
    show the diff even if the test case is later edited.
    """
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='results',
    )
    test_case = models.ForeignKey(
        'problems.TestCase',
        on_delete=models.CASCADE,
        related_name='results',
    )
    status = models.CharField(
        max_length=30,
        choices=SubmissionStatusChoices.choices,
    )
    actual_output = models.TextField(blank=True, null=True)
    # Snapshot of expected output at submission time
    expected_output = models.TextField(blank=True, null=True)
    runtime_ms = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    memory_kb = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        unique_together = ('submission', 'test_case')
        verbose_name = 'Submission Result'
        indexes = [
            models.Index(fields=['submission', 'status']),
        ]

    def __str__(self) -> str:
        return (
            f"Result: Sub#{self.submission_id} | "
            f"TC#{self.test_case.order_num} | {self.status}"
        )


# ──────────────────────── Code Run ───────────────────────────────


class CodeRun(models.Model):
    """
    Records a 'Run Code' event — user tests against custom input
    without making an official submission.
    These are cheaper to create (no test-case loop) and are used
    for UX (show output immediately) but don't affect stats.
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='code_runs',
    )
    problem = models.ForeignKey(
        'problems.Problem',
        on_delete=models.CASCADE,
        related_name='code_runs',
    )
    language = models.ForeignKey(
        'problems.Language',
        on_delete=models.SET_NULL,
        null=True,
        related_name='code_runs',
    )
    code = models.TextField()
    custom_input = models.TextField(blank=True, null=True)
    stdout = models.TextField(blank=True, null=True)
    stderr = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=30,
        choices=SubmissionStatusChoices.choices,
        default=SubmissionStatusChoices.PENDING,
    )
    runtime_ms = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    ran_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Code Run'
        ordering = ['-ran_at']
        indexes = [
            models.Index(fields=['user', 'problem']),
            models.Index(fields=['user', 'ran_at']),
        ]

    def __str__(self) -> str:
        return f"CodeRun: {self.user.user_name} | {self.problem.title}"


# ─────────────── Denormalized Solved Tracker ─────────────────────


class UserSolvedProblem(models.Model):
    """
    Denormalized O(1) lookup table: 'has user solved this problem?'

    Why not just query Submission?
        SELECT DISTINCT problem_id FROM submissions
        WHERE user_id = ? AND status = 'accepted'
    is fine at small scale but slow at millions of submissions.
    This table is written once (first AC) and updated cheaply on
    re-solves (update best_submission if faster/smaller).

    Maintained by a post_save signal on Submission.
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='solved_problems',
    )
    problem = models.ForeignKey(
        'problems.Problem',
        on_delete=models.CASCADE,
        related_name='solved_by',
    )
    # Best (fastest runtime) accepted submission
    best_submission = models.ForeignKey(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        related_name='best_for',
    )
    # Language of the best submission
    language = models.ForeignKey(
        'problems.Language',
        on_delete=models.SET_NULL,
        null=True,
    )
    attempt_count = models.PositiveIntegerField(default=1)
    first_solved_at = models.DateTimeField()
    last_solved_at = models.DateTimeField()

    class Meta:
        unique_together = ('user', 'problem')
        verbose_name = 'User Solved Problem'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['problem']),
            # Enables heatmap/calendar queries: solved problems in a date range
            models.Index(fields=['user', 'first_solved_at']),
            models.Index(fields=['user', 'last_solved_at']),
        ]

    def __str__(self) -> str:
        return f"{self.user.user_name} solved {self.problem.title}"