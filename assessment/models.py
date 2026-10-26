"""
BashaByte — assessments models (consolidated, final).

Authoritative sources of truth:
- Per-answer scores:        AttemptAnswer.score
- Per-coding-submission:    AssessmentSubmission.score
- Per-attempt final result: AssessmentResult (with AssessmentSectionResult per section)
- Attempt.score:            cached aggregate for in-progress UI (NOT authoritative)

Snapshots are created by a service at publication time (never inside save()).
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------

class ProgrammingLanguage(models.Model):
    """
    Authoritative registry of languages usable by the assessment engine.

    `problems.Language` is a display catalog.  We do not duplicate its data:
    the optional FK links the two records so an editor only maintains the
    language once.  Judge0 execution identity lives here, not on
    problems.Language.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    # Execution capability (separate from the catalog identity)
    is_judge0_executable = models.BooleanField(default=False)
    judge0_language_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Judge0 runtime language id. NULL if not executable.",
    )

    problems_language = models.ForeignKey(
        "problems.Language",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessment_languages",
        help_text="Optional link to the catalog row in the problems app.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "is_judge0_executable"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(is_judge0_executable=False)
                    | Q(judge0_language_id__isnull=False)
                ),
                name="prog_lang_judge0_id_required",
            ),
        ]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# MCQ authoring
# ---------------------------------------------------------------------------

class McqQuestion(models.Model):
    class QuestionType(models.TextChoices):
        REGULAR = "regular", "Regular MCQ"
        PROGRAMMING = "programming", "Programming MCQ"

    class Category(models.TextChoices):
        APTITUDE = "aptitude", "Aptitude"
        QUANT = "quant", "Quantitative"
        REASONING = "reasoning", "Reasoning"
        VERBAL = "verbal", "Verbal"
        PROGRAMMING = "programming", "Programming"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcq_questions",
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.PROGRAMMING,
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.PROGRAMMING,
    )
    topic = models.CharField(max_length=100)
    sub_topic = models.CharField(max_length=100, blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices)

    statement = models.TextField()
    code_snippet = models.TextField(blank=True)

    # Replaces the old inner TextChoices enum.  Optional even for programming
    # MCQs, because some snippet-based MCQs are language-agnostic.
    programming_language = models.ForeignKey(
        ProgrammingLanguage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mcq_questions",
    )

    explanation = models.TextField(blank=True)
    allow_multiple = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "difficulty"]),
            models.Index(fields=["question_type", "is_active"]),
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["programming_language", "is_active"]),
        ]

    def __str__(self):
        return self.title


class McqOption(models.Model):
    question = models.ForeignKey(
        McqQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="uniq_mcq_option_position",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="mcq_option_position_gte_1",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} - Option {self.position}"


# ---------------------------------------------------------------------------
# Coding authoring
# ---------------------------------------------------------------------------

class CodingQuestion(models.Model):
    class CodingMode(models.TextChoices):
        SCRATCH = "scratch", "Write From Scratch"
        FIX = "fix", "Fix the Error"
        COMPLETE = "complete", "Complete the Code"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="coding_questions",
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    coding_mode = models.CharField(
        max_length=20,
        choices=CodingMode.choices,
        default=CodingMode.SCRATCH,
    )

    topic = models.CharField(max_length=255)
    subtopic = models.CharField(max_length=255, blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices)

    statement = models.TextField()
    input_format = models.TextField(blank=True)
    output_format = models.TextField(blank=True)
    constraints_text = models.TextField(blank=True)

    explanation = models.TextField(blank=True)

    time_limit_seconds = models.PositiveSmallIntegerField(default=2)
    memory_limit_kb = models.PositiveIntegerField(default=262144)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["difficulty", "is_active"]),
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["coding_mode", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(time_limit_seconds__gte=1),
                name="coding_q_time_limit_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(memory_limit_kb__gte=1),
                name="coding_q_memory_limit_gte_1",
            ),
        ]

    def __str__(self):
        return self.title


class CodingTestCase(models.Model):
    question = models.ForeignKey(
        CodingQuestion,
        on_delete=models.CASCADE,
        related_name="test_cases",
    )
    input_data = models.TextField(blank=True, default="")
    expected_output = models.TextField()

    is_sample = models.BooleanField(default=False)
    weight = models.PositiveSmallIntegerField(default=1)
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    explanation = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="uniq_coding_test_position",
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=1),
                name="coding_test_weight_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="coding_test_position_gte_1",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} - Test Case {self.position}"


class CodingQuestionLanguage(models.Model):
    """
    Per-language configuration.  Starter/buggy code lives ONLY here.
    """

    question = models.ForeignKey(
        CodingQuestion,
        on_delete=models.CASCADE,
        related_name="supported_languages",
    )
    language = models.ForeignKey(
        ProgrammingLanguage,
        on_delete=models.PROTECT,
        related_name="coding_questions",
    )
    starter_code = models.TextField(blank=True, default="")
    buggy_code = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "language"],
                name="uniq_coding_question_language",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} - {self.language.name}"


# ---------------------------------------------------------------------------
# Assessment authoring
# ---------------------------------------------------------------------------

class Assessment(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class ResultReleasePolicy(models.TextChoices):
        IMMEDIATE = "immediate", "Immediately After Submission"
        AFTER_END = "after_end", "After Assessment Ends"
        SCHEDULED = "scheduled", "At Scheduled Time"
        MANUAL = "manual", "Manually Released"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_assessments",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    max_attempts = models.PositiveSmallIntegerField(default=1)

    result_release_policy = models.CharField(
        max_length=20,
        choices=ResultReleasePolicy.choices,
        default=ResultReleasePolicy.AFTER_END,
    )
    results_release_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Required only when policy is 'scheduled'.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "start_time"]),
            models.Index(fields=["status", "end_time"]),
            models.Index(fields=["created_by", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=1),
                name="assessment_duration_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__gte=1),
                name="assessment_max_attempts_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    Q(start_time__isnull=True)
                    | Q(end_time__isnull=True)
                    | Q(start_time__lt=F("end_time"))
                ),
                name="assessment_start_before_end",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(result_release_policy="scheduled")
                    | Q(results_release_at__isnull=False)
                ),
                name="assessment_scheduled_needs_release_at",
            ),
        ]

    def __str__(self):
        return self.name


class AssessmentSection(models.Model):
    """Authored section of an assessment (draft state)."""

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    time_limit_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optional section-only time limit. NULL = use assessment limit.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "position"],
                name="uniq_section_position_per_assessment",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="section_position_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(time_limit_minutes__isnull=True)
                | Q(time_limit_minutes__gte=1),
                name="section_time_limit_positive",
            ),
        ]

    def __str__(self):
        return f"{self.assessment.name} - {self.title}"


class AssessmentQuestion(models.Model):
    """
    Live assignment of a reusable question into an assessment section.

    `assessment` is denormalised from `section.assessment` so that duplicate
    detection can be enforced across the whole assessment.  The service layer
    must guarantee `assessment == section.assessment`.
    """

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="assessment_questions",
    )
    section = models.ForeignKey(
        AssessmentSection,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    mcq_question = models.ForeignKey(
        McqQuestion,
        on_delete=models.PROTECT,
        related_name="assessment_assignments",
        null=True,
        blank=True,
    )
    coding_question = models.ForeignKey(
        CodingQuestion,
        on_delete=models.PROTECT,
        related_name="assessment_assignments",
        null=True,
        blank=True,
    )

    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        ordering = ["position"]
        indexes = [
            models.Index(fields=["section", "position"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(mcq_question__isnull=False, coding_question__isnull=True)
                    | Q(mcq_question__isnull=True, coding_question__isnull=False)
                ),
                name="aq_exactly_one_question_type",
            ),
            models.CheckConstraint(
                condition=Q(max_score__gt=0),
                name="aq_max_score_positive",
            ),
            models.CheckConstraint(
                condition=Q(negative_marks__gte=0),
                name="aq_negative_marks_gte_0",
            ),
            models.UniqueConstraint(
                fields=["section", "position"],
                name="uniq_aq_position_per_section",
            ),
            models.UniqueConstraint(
                fields=["assessment", "mcq_question"],
                condition=Q(mcq_question__isnull=False),
                name="uniq_mcq_per_assessment",
            ),
            models.UniqueConstraint(
                fields=["assessment", "coding_question"],
                condition=Q(coding_question__isnull=False),
                name="uniq_coding_per_assessment",
            ),
        ]

    def __str__(self):
        if self.mcq_question_id:
            return f"{self.assessment.name} - {self.mcq_question.title}"
        return f"{self.assessment.name} - {self.coding_question.title}"


# ---------------------------------------------------------------------------
# Published versions and snapshots
# ---------------------------------------------------------------------------

class AssessmentVersion(models.Model):
    """
    Immutable published snapshot of an assessment's configuration.

    Snapshots (sections, question content, options, test cases) are created
    once at publish time by a service, transactionally.  Historical attempts
    reference the version, not the live authoring models.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class ResultReleasePolicy(models.TextChoices):
        IMMEDIATE = "immediate", "Immediately After Submission"
        AFTER_END = "after_end", "After Assessment Ends"
        SCHEDULED = "scheduled", "At Scheduled Time"
        MANUAL = "manual", "Manually Released"

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_current = models.BooleanField(
        default=False,
        help_text="True for the version used by new attempts.",
    )

    # Frozen configuration
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField()
    max_attempts = models.PositiveSmallIntegerField(default=1)
    result_release_policy = models.CharField(
        max_length=20,
        choices=ResultReleasePolicy.choices,
    )
    results_release_at = models.DateTimeField(null=True, blank=True)

    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="published_assessment_versions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["assessment", "version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "version_number"],
                name="uniq_version_number_per_assessment",
            ),
            models.UniqueConstraint(
                fields=["assessment"],
                condition=Q(is_current=True),
                name="one_current_version_per_assessment",
            ),
            models.CheckConstraint(
                condition=Q(version_number__gte=1),
                name="version_number_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(duration_minutes__gte=1),
                name="version_duration_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(max_attempts__gte=1),
                name="version_max_attempts_gte_1",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(result_release_policy="scheduled")
                    | Q(results_release_at__isnull=False)
                ),
                name="version_scheduled_needs_release_at",
            ),
        ]

    def __str__(self):
        return f"{self.assessment.name} v{self.version_number}"


class AssessmentSectionSnapshot(models.Model):
    version = models.ForeignKey(
        AssessmentVersion,
        on_delete=models.CASCADE,
        related_name="section_snapshots",
    )
    source_section = models.ForeignKey(
        AssessmentSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
    )

    title = models.CharField(max_length=255)
    instructions = models.TextField(blank=True)
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "position"],
                name="uniq_section_snapshot_position",
            ),
        ]

    def __str__(self):
        return f"{self.version} - {self.title}"


class McqQuestionSnapshot(models.Model):
    """Frozen content of an MCQ.  Options live in McqOptionSnapshot."""

    version = models.ForeignKey(
        AssessmentVersion,
        on_delete=models.CASCADE,
        related_name="mcq_snapshots",
    )
    source_question = models.ForeignKey(
        McqQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
    )

    title = models.CharField(max_length=255)
    question_type = models.CharField(max_length=20)
    category = models.CharField(max_length=20)
    topic = models.CharField(max_length=100)
    sub_topic = models.CharField(max_length=100, blank=True)
    difficulty = models.CharField(max_length=10)
    statement = models.TextField()
    code_snippet = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    allow_multiple = models.BooleanField(default=False)
    programming_language_name = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "source_question"],
                condition=Q(source_question__isnull=False),
                name="uniq_mcq_snapshot_per_version",
            ),
        ]

    def __str__(self):
        return self.title


class McqOptionSnapshot(models.Model):
    question = models.ForeignKey(
        McqQuestionSnapshot,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="uniq_mcq_option_snapshot_position",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} option {self.position}"


class CodingQuestionSnapshot(models.Model):
    version = models.ForeignKey(
        AssessmentVersion,
        on_delete=models.CASCADE,
        related_name="coding_snapshots",
    )
    source_question = models.ForeignKey(
        CodingQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
    )

    title = models.CharField(max_length=255)
    coding_mode = models.CharField(max_length=20)
    topic = models.CharField(max_length=255)
    subtopic = models.CharField(max_length=255, blank=True)
    difficulty = models.CharField(max_length=10)
    statement = models.TextField()
    input_format = models.TextField(blank=True)
    output_format = models.TextField(blank=True)
    constraints_text = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    time_limit_seconds = models.PositiveSmallIntegerField()
    memory_limit_kb = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "source_question"],
                condition=Q(source_question__isnull=False),
                name="uniq_coding_snapshot_per_version",
            ),
        ]

    def __str__(self):
        return self.title


class CodingQuestionLanguageSnapshot(models.Model):
    question = models.ForeignKey(
        CodingQuestionSnapshot,
        on_delete=models.CASCADE,
        related_name="languages",
    )
    language = models.ForeignKey(
        ProgrammingLanguage,
        on_delete=models.PROTECT,
        related_name="question_snapshots",
    )
    language_name = models.CharField(max_length=100)
    language_slug = models.SlugField(max_length=100)
    judge0_language_id = models.PositiveIntegerField(null=True, blank=True)

    starter_code = models.TextField(blank=True, default="")
    buggy_code = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "language"],
                name="uniq_coding_snapshot_language",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} - {self.language_name}"


class CodingTestCaseSnapshot(models.Model):
    question = models.ForeignKey(
        CodingQuestionSnapshot,
        on_delete=models.CASCADE,
        related_name="test_cases",
    )
    source_test_case = models.ForeignKey(
        CodingTestCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
    )

    input_data = models.TextField(blank=True, default="")
    expected_output = models.TextField()
    is_sample = models.BooleanField(default=False)
    weight = models.PositiveSmallIntegerField(default=1)
    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    explanation = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="uniq_coding_test_snapshot_position",
            ),
            models.CheckConstraint(
                condition=Q(weight__gte=1),
                name="coding_test_snapshot_weight_gte_1",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} test {self.position}"


class AssessmentQuestionSnapshot(models.Model):
    """
    A frozen assignment.  Links section snapshot + question content snapshot
    + scored configuration.  Attempts and submissions reference this.
    """

    section = models.ForeignKey(
        AssessmentSectionSnapshot,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    source_assessment_question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
    )

    mcq_snapshot = models.OneToOneField(
        McqQuestionSnapshot,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assignment_snapshot",
    )
    coding_snapshot = models.OneToOneField(
        CodingQuestionSnapshot,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assignment_snapshot",
    )

    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    max_score = models.DecimalField(max_digits=6, decimal_places=2)
    negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(mcq_snapshot__isnull=False, coding_snapshot__isnull=True)
                    | Q(mcq_snapshot__isnull=True, coding_snapshot__isnull=False)
                ),
                name="aq_snapshot_exactly_one_type",
            ),
            models.CheckConstraint(
                condition=Q(max_score__gt=0),
                name="aq_snapshot_max_score_positive",
            ),
            models.CheckConstraint(
                condition=Q(negative_marks__gte=0),
                name="aq_snapshot_negative_gte_0",
            ),
            models.UniqueConstraint(
                fields=["section", "position"],
                name="uniq_aq_snapshot_position",
            ),
        ]

    def __str__(self):
        target = self.mcq_snapshot or self.coding_snapshot
        return f"{self.section} - {target}"


# ---------------------------------------------------------------------------
# Moderators, participants, authorisations
# ---------------------------------------------------------------------------

class AssessmentModerator(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="moderators",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="moderated_assessments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "user"],
                name="uniq_assessment_moderator",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.assessment.name}"


class Participant(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"
        DISQUALIFIED = "disqualified", "Disqualified"

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessment_participations",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REGISTERED,
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "user"],
                name="uniq_assessment_participant",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.assessment.name}"


class AttemptAuthorization(models.Model):
    """Explicit entitlement to additional attempts."""

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="attempt_authorizations",
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="granted_attempt_authorizations",
    )
    extra_attempts = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)]
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["participant", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(extra_attempts__gte=1),
                name="attempt_auth_extra_gte_1",
            ),
        ]

    def __str__(self):
        return f"{self.participant} +{self.extra_attempts}"


# ---------------------------------------------------------------------------
# Attempts and answers
# ---------------------------------------------------------------------------

class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        TIMED_OUT = "timed_out", "Timed Out"
        CANCELLED = "cancelled", "Cancelled"

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    assessment_version = models.ForeignKey(
        AssessmentVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attempts",
        help_text="Frozen version the attempt was started against.",
    )
    attempt_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)]
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )

    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Server-authoritative deadline. Set by the start service.",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    time_extension_minutes = models.PositiveIntegerField(default=0)

    # Cached aggregate for the live UI.  Authoritative released score lives on
    # AssessmentResult.
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        ordering = ["attempt_number"]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["participant", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "attempt_number"],
                name="uniq_participant_attempt_number",
            ),
            models.CheckConstraint(
                condition=Q(attempt_number__gte=1),
                name="attempt_number_gte_1",
            ),
        ]

    def __str__(self):
        return (
            f"{self.participant.user} - "
            f"{self.participant.assessment.name} - "
            f"Attempt {self.attempt_number}"
        )


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(
        Attempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    assessment_question_snapshot = models.ForeignKey(
        AssessmentQuestionSnapshot,
        on_delete=models.PROTECT,
        related_name="attempt_answers",
    )

    text_answer = models.TextField(blank=True, default="")

    coding_language = models.ForeignKey(
        ProgrammingLanguage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attempt_answers",
    )
    code_answer = models.TextField(blank=True, default="")

    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "assessment_question_snapshot"],
                name="uniq_answer_per_attempt_question",
            ),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_id} - Q{self.assessment_question_snapshot_id}"


class AttemptAnswerOption(models.Model):
    attempt_answer = models.ForeignKey(
        AttemptAnswer,
        on_delete=models.CASCADE,
        related_name="selected_options",
    )
    option = models.ForeignKey(
        McqOptionSnapshot,
        on_delete=models.PROTECT,
        related_name="answer_selections",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt_answer", "option"],
                name="uniq_selected_option_per_answer",
            ),
        ]

    def __str__(self):
        return f"Answer {self.attempt_answer_id} - Option {self.option_id}"


class AttemptEvent(models.Model):
    class EventType(models.TextChoices):
        STARTED = "started", "Started"
        ANSWER_SAVED = "answer_saved", "Answer Saved"
        QUESTION_VISITED = "question_visited", "Question Visited"
        SUBMITTED = "submitted", "Submitted"
        TIMED_OUT = "timed_out", "Timed Out"
        FULLSCREEN_EXIT = "fullscreen_exit", "Fullscreen Exit"

    attempt = models.ForeignKey(
        Attempt,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["attempt", "event_type", "created_at"]),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_id} - {self.event_type}"


# ---------------------------------------------------------------------------
# Coding submissions
# ---------------------------------------------------------------------------

class AssessmentSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        ACCEPTED = "accepted", "Accepted"
        WRONG_ANSWER = "wrong_answer", "Wrong Answer"
        COMPILATION_ERROR = "compilation_error", "Compilation Error"
        RUNTIME_ERROR = "runtime_error", "Runtime Error"
        TIME_LIMIT_EXCEEDED = "time_limit_exceeded", "Time Limit Exceeded"
        MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded", "Memory Limit Exceeded"
        INTERNAL_ERROR = "internal_error", "Internal Error"

    attempt = models.ForeignKey(
        Attempt,
        on_delete=models.CASCADE,
        related_name="coding_submissions",
    )
    assessment_question_snapshot = models.ForeignKey(
        AssessmentQuestionSnapshot,
        on_delete=models.PROTECT,
        related_name="coding_submissions",
    )
    language = models.ForeignKey(
        ProgrammingLanguage,
        on_delete=models.PROTECT,
        related_name="assessment_submissions",
    )

    source_code = models.TextField()
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_used_kb = models.PositiveIntegerField(null=True, blank=True)
    judge0_token = models.CharField(max_length=255, blank=True, default="")

    submitted_at = models.DateTimeField(auto_now_add=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["attempt", "assessment_question_snapshot"]),
            models.Index(fields=["status", "submitted_at"]),
            models.Index(fields=["judge0_token"]),
        ]

    def __str__(self):
        return f"Attempt {self.attempt_id} - Submission {self.pk}"


class AssessmentSubmissionResult(models.Model):
    submission = models.ForeignKey(
        AssessmentSubmission,
        on_delete=models.CASCADE,
        related_name="test_results",
    )
    test_case_snapshot = models.ForeignKey(
        CodingTestCaseSnapshot,
        on_delete=models.PROTECT,
        related_name="submission_results",
    )

    is_passed = models.BooleanField(default=False)
    actual_output = models.TextField(blank=True, default="")
    expected_output = models.TextField(blank=True, default="")
    execution_time_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_used_kb = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "test_case_snapshot"],
                name="uniq_submission_test_snapshot_result",
            ),
        ]

    def __str__(self):
        return f"Submission {self.submission_id} - Test {self.test_case_snapshot_id}"


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

class AssessmentResult(models.Model):
    """
    Authoritative per-attempt result.  Attempt.score is only a cached
    in-progress aggregate.
    """

    class EvaluationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        EVALUATING = "evaluating", "Evaluating"
        FINALIZED = "finalized", "Finalized"

    attempt = models.OneToOneField(
        Attempt,
        on_delete=models.CASCADE,
        related_name="result",
    )
    # Denormalised for leaderboard queries without joining through
    # attempt -> participant -> assessment.
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.PROTECT,
        related_name="results",
    )

    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    correct_count = models.PositiveIntegerField(default=0)
    incorrect_count = models.PositiveIntegerField(default=0)
    partially_correct_count = models.PositiveIntegerField(default=0)
    unanswered_count = models.PositiveIntegerField(default=0)

    evaluation_status = models.CharField(
        max_length=20,
        choices=EvaluationStatus.choices,
        default=EvaluationStatus.PENDING,
    )
    released_at = models.DateTimeField(null=True, blank=True)
    recalculated_at = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-total_score", "attempt"]
        indexes = [
            models.Index(fields=["assessment", "-total_score"]),
            models.Index(fields=["assessment", "released_at"]),
            models.Index(fields=["evaluation_status", "released_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_score__gte=0),
                name="result_total_score_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(max_score__gte=0),
                name="result_max_score_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(revision__gte=1),
                name="result_revision_gte_1",
            ),
        ]

    def __str__(self):
        return f"Result for attempt {self.attempt_id}"


class AssessmentSectionResult(models.Model):
    result = models.ForeignKey(
        AssessmentResult,
        on_delete=models.CASCADE,
        related_name="section_results",
    )
    section_snapshot = models.ForeignKey(
        AssessmentSectionSnapshot,
        on_delete=models.PROTECT,
        related_name="section_results",
    )
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["result", "section_snapshot"],
                name="uniq_section_result_per_section_snapshot",
            ),
            models.CheckConstraint(
                condition=Q(score__gte=0),
                name="section_result_score_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(max_score__gte=0),
                name="section_result_max_score_gte_0",
            ),
        ]

    def __str__(self):
        return f"{self.result} - {self.section_snapshot.title}"