
from django.conf import settings
from django.db import models


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

    class ProgrammingLanguage(models.TextChoices):
        PYTHON = "python", "Python"
        C = "c", "C"
        CPP = "cpp", "C++"
        JAVA = "java", "Java"
        JAVASCRIPT = "javascript", "JavaScript"
        CSHARP = "csharp", "C#"
        SQL = "sql", "SQL"

    # Question ownership
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcq_questions",
    )

    # Basic information
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)

    # Classification
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
    sub_topic = models.CharField(
        max_length=100,
        blank=True,
    )

    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
    )

    # Question content
    statement = models.TextField()
    code_snippet = models.TextField(blank=True)

    programming_language = models.CharField(
        max_length=20,
        choices=ProgrammingLanguage.choices,
        blank=True,
    )

    explanation = models.TextField(blank=True)

    # Answer configuration
    allow_multiple = models.BooleanField(default=False)

    # Status and timestamps
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "difficulty"]),
            models.Index(fields=["question_type", "is_active"]),
            models.Index(fields=["owner", "is_active"]),
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
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="unique_mcq_option_position",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} - Option {self.position}"


from django.conf import settings
from django.db import models


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

    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
    )

    statement = models.TextField()
    input_format = models.TextField(blank=True)
    output_format = models.TextField(blank=True)
    constraints_text = models.TextField(blank=True)

    starter_code = models.TextField(blank=True)
    buggy_code = models.TextField(blank=True)

    explanation = models.TextField(blank=True)

    time_limit_seconds = models.PositiveSmallIntegerField(
        default=2
    )
    memory_limit_kb = models.PositiveIntegerField(
        default=262144
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

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
    position = models.PositiveIntegerField()

    explanation = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="unique_coding_test_position",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} - Test Case {self.position}"

class ProgrammingLanguage(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class CodingQuestionLanguage(models.Model):
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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["question", "language"],
                name="unique_coding_question_language",
            ),
        ]

    def __str__(self):
        return f"{self.question.title} - {self.language.name}"

from django.conf import settings
from django.db import models


class Assessment(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class ResultReleasePolicy(models.TextChoices):
        IMMEDIATE = "immediate", "Immediately After Submission"
        AFTER_END = "after_end", "After Assessment Ends"
        MANUAL = "manual", "Manually Released"

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_assessments",
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name



from django.db import models
from django.db.models import Q


class AssessmentQuestion(models.Model):

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="assessment_questions",
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

    position = models.PositiveIntegerField()

    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
    )

    class Meta:
        ordering = ["position"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(mcq_question__isnull=False,
                      coding_question__isnull=True)
                    |
                    Q(mcq_question__isnull=True,
                      coding_question__isnull=False)
                ),
                name="exactly_one_assessment_question_type",
            ),

            models.CheckConstraint(
                condition=Q(max_score__gt=0),
                name="assessment_question_score_positive",
            ),

            models.UniqueConstraint(
                fields=["assessment", "position"],
                name="unique_assessment_question_position",
            ),

            models.UniqueConstraint(
                fields=["assessment", "mcq_question"],
                condition=Q(mcq_question__isnull=False),
                name="unique_mcq_per_assessment",
            ),

            models.UniqueConstraint(
                fields=["assessment", "coding_question"],
                condition=Q(coding_question__isnull=False),
                name="unique_coding_per_assessment",
            ),
        ]

    def __str__(self):
        if self.mcq_question_id:
            question_title = self.mcq_question.title
        else:
            question_title = self.coding_question.title

        return f"{self.assessment.name} - {question_title}"

from django.conf import settings
from django.db import models


class Participant(models.Model):

    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        STARTED = "started", "Started"
        COMPLETED = "completed", "Completed"
        DISQUALIFIED = "disqualified", "Disqualified"

    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="participants"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessment_participations"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REGISTERED
    )

    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "user"],
                name="unique_assessment_participant"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.assessment.name}"

from django.db import models


class Attempt(models.Model):

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        TIMED_OUT = "timed_out", "Timed Out"
        CANCELLED = "cancelled", "Cancelled"

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="attempts"
    )

    attempt_number = models.PositiveSmallIntegerField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS
    )

    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    class Meta:
        ordering = ["attempt_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["participant", "attempt_number"],
                name="unique_participant_attempt_number"
            )
        ]

    def __str__(self):
        return (
            f"{self.participant.user} - "
            f"{self.participant.assessment.name} - "
            f"Attempt {self.attempt_number}"
        )

from django.db import models


class AttemptAnswer(models.Model):

    attempt = models.ForeignKey(
        Attempt,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    assessment_question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.PROTECT,
        related_name="attempt_answers"
    )

    text_answer = models.TextField(blank=True, default="")

    coding_language = models.ForeignKey(
        ProgrammingLanguage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attempt_answers"
    )

    code_answer = models.TextField(blank=True, default="")

    score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    is_correct = models.BooleanField(null=True, blank=True)

    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "assessment_question"],
                name="unique_answer_per_attempt_question"
            )
        ]

    def __str__(self):
        return (
            f"Attempt {self.attempt_id} - "
            f"Question {self.assessment_question_id}"
        )

class AttemptAnswerOption(models.Model):

    attempt_answer = models.ForeignKey(
        AttemptAnswer,
        on_delete=models.CASCADE,
        related_name="selected_options"
    )

    option = models.ForeignKey(
        McqOption,
        on_delete=models.PROTECT,
        related_name="answer_selections"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt_answer", "option"],
                name="unique_selected_option_per_answer"
            )
        ]

    def __str__(self):
        return (
            f"Answer {self.attempt_answer_id} - "
            f"Option {self.option_id}"
        )

class AssessmentModerator(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="moderators"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="moderated_assessments"
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "user"],
                name="unique_assessment_moderator"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.assessment.name}"

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
        related_name="events"
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices
    )

    details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Attempt {self.attempt_id} - {self.event_type}"

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
        related_name="coding_submissions"
    )

    assessment_question = models.ForeignKey(
        AssessmentQuestion,
        on_delete=models.PROTECT,
        related_name="coding_submissions"
    )

    language = models.ForeignKey(
        ProgrammingLanguage,
        on_delete=models.PROTECT,
        related_name="assessment_submissions"
    )

    source_code = models.TextField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING
    )

    score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    execution_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    memory_used_kb = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    judge0_token = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    evaluated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["attempt", "assessment_question"]),
            models.Index(fields=["status", "submitted_at"]),
        ]

    def __str__(self):
        return (
            f"Attempt {self.attempt_id} - "
            f"Submission {self.pk}"
        )

class AssessmentSubmissionResult(models.Model):
    submission = models.ForeignKey(
        AssessmentSubmission,
        on_delete=models.CASCADE,
        related_name="test_results"
    )

    test_case = models.ForeignKey(
        CodingTestCase,
        on_delete=models.PROTECT,
        related_name="assessment_results"
    )

    is_passed = models.BooleanField(default=False)

    actual_output = models.TextField(blank=True, default="")

    expected_output = models.TextField(blank=True, default="")

    execution_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    memory_used_kb = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    error_message = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "test_case"],
                name="unique_submission_test_case_result"
            )
        ]

    def __str__(self):
        return (
            f"Submission {self.submission_id} - "
            f"Test Case {self.test_case_id}"
        )
