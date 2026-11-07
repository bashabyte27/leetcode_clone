"""
BashaByte Courses: content models (Phase 1).

    Category ─┐
              Course ─┬─ Module ─┬─ Lesson ─── LessonStep ─┬─ StepQuestion → assessment.McqQuestion
    CareerPath┘ (ordered)        │                         ├─ coding_question → assessment.CodingQuestion
                     │           │                         └─ StepHint (levels 1–3)
                     └───────────┴─ LearningOutcome (course / module / lesson level, linked upward)

`code` fields (PY, PY-M1, PY-M1-L2, PY-M1-L2-S04 ...) are the stable identities
used by the content-sheet importer (courses/sheet_importer.py); items built by
hand in the staff builder may leave them blank.

Step payloads are validated per type by `courses.steps`. Progress, enrollment,
exams and certificates arrive in later phases (docs/courses/ARCHITECTURE.md).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from .steps import STEP_TYPE_CHOICES, STEP_TYPES, structure_errors


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def _unique_slug(instance, value, scope=None, max_length=120):
    """Slugify `value`, adding -2, -3… until unique within `scope` (a filter dict)."""
    base = slugify(value)[:max_length] or "item"
    model = type(instance)
    slug, n = base, 2
    qs = model.objects.filter(**(scope or {})).exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug = f"{base[:max_length - len(suffix)]}{suffix}"
        n += 1
    return slug


# ─────────────────────────── Catalog ───────────────────────────


class Category(TimeStampedModel):
    title = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    position = models.PositiveSmallIntegerField(default=0)
    icon = models.CharField(max_length=50, blank=True, help_text="Bootstrap icon name, e.g. 'braces'.")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "title"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Course(TimeStampedModel):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class Access(models.TextChoices):
        FREE = "free", "Free"
        PREMIUM = "premium", "Premium"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="courses")
    code = models.CharField(max_length=20, unique=True, null=True, blank=True,
                            help_text="Stable id from the content sheet, e.g. PY. Blank for hand-built items.")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=140)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.BEGINNER)
    version = models.PositiveSmallIntegerField(default=1)
    prerequisites = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="required_by")
    est_weeks = models.PositiveSmallIntegerField(default=4)
    access = models.CharField(max_length=10, choices=Access.choices, default=Access.FREE)
    thumbnail_url = models.URLField(blank=True, help_text="Hosted image URL (CDN). Uploads are not used.")
    capstone_brief = models.TextField(blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_courses",
    )

    class Meta:
        ordering = ["category__position", "title"]
        constraints = [
            models.UniqueConstraint(fields=["slug", "version"], name="uniq_course_slug_version"),
        ]
        indexes = [models.Index(fields=["is_published", "category"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.title, {"version": self.version})
        super().save(*args, **kwargs)

    def mark_published(self):
        self.is_published = True
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=["is_published", "published_at", "updated_at"])

    def __str__(self):
        return f"{self.title} (v{self.version})"


class CareerPath(TimeStampedModel):
    class Goal(models.TextChoices):
        PLACEMENT = "placement", "Placement"
        BACKEND = "backend", "Backend"
        DATA = "data", "Data"
        AI = "ai", "AI"
        QA = "qa", "QA"
        DEVOPS = "devops", "DevOps"

    title = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    goal = models.CharField(max_length=20, choices=Goal.choices)
    description = models.TextField(blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    courses = models.ManyToManyField(Course, through="CareerPathCourse", related_name="career_paths")

    class Meta:
        ordering = ["position", "title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CareerPathCourse(models.Model):
    path = models.ForeignKey(CareerPath, on_delete=models.CASCADE, related_name="path_courses")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="path_entries")
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["path", "position"], name="uniq_path_position"),
            models.UniqueConstraint(fields=["path", "course"], name="uniq_path_course"),
        ]

    def __str__(self):
        return f"{self.path} #{self.position}: {self.course}"


# ─────────────────────────── Structure ───────────────────────────


class Module(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    code = models.CharField(max_length=40, unique=True, null=True, blank=True,
                            help_text="Stable id from the content sheet, e.g. PY-M1. Blank for hand-built items.")
    position = models.PositiveSmallIntegerField(help_text="0 is reserved for an introduction module.")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=140)
    summary = models.TextField(blank=True)
    intro_video = models.JSONField(default=dict, blank=True, help_text='{"provider": "youtube", "video_id": "..."}')
    mini_project_brief = models.TextField(blank=True)
    is_free_preview = models.BooleanField(default=False)
    is_introduction = models.BooleanField(
        default=False, help_text="A welcome module (position 0): no exam and no six-lesson rule.")

    class Meta:
        ordering = ["course", "position"]
        constraints = [
            models.UniqueConstraint(fields=["course", "position"], name="uniq_module_position"),
            models.UniqueConstraint(fields=["course", "slug"], name="uniq_module_slug"),
            models.CheckConstraint(condition=Q(position__gte=1) | Q(is_introduction=True),
                                   name="module_position_0_only_for_intro"),
        ]

    def clean(self):
        if self.position == 0 and not self.is_introduction:
            raise ValidationError({"position": "Position 0 is only for an introduction module."})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.title, {"course_id": self.course_id})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"M{self.position}. {self.title}"


class Lesson(TimeStampedModel):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons")
    code = models.CharField(max_length=40, unique=True, null=True, blank=True,
                            help_text="Stable id from the content sheet, e.g. PY-M1-L2. Blank for hand-built items.")
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=140)
    summary = models.TextField(blank=True)
    est_minutes = models.PositiveSmallIntegerField(default=45)
    is_free_preview = models.BooleanField(default=False)
    min_coding_passes = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Coding tasks a student must pass. Blank = the smaller of 2 and the number of coding tasks.")

    class Meta:
        ordering = ["module", "position"]
        constraints = [
            models.UniqueConstraint(fields=["module", "position"], name="uniq_lesson_position"),
            models.UniqueConstraint(fields=["module", "slug"], name="uniq_lesson_slug"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.title, {"module_id": self.module_id})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"L{self.position}. {self.title}"


class LearningOutcome(TimeStampedModel):
    """
    What a student can do afterwards, at course, module or lesson level.
    Every graded item is tagged to one; `supports` links an outcome to the
    higher-level outcome(s) it builds toward (lesson → module → course).
    """

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="outcomes")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, null=True, blank=True, related_name="outcomes")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True, related_name="outcomes")
    code = models.CharField(max_length=40, unique=True, help_text="e.g. PY-M3-L2-O1")
    title = models.CharField(max_length=120, blank=True)
    text = models.CharField(max_length=300)
    position = models.PositiveSmallIntegerField(default=0)
    supports = models.ManyToManyField("self", symmetrical=False, blank=True, related_name="supported_by")

    class Meta:
        ordering = ["code"]

    @property
    def level(self):
        return "lesson" if self.lesson_id else "module" if self.module_id else "course"

    def clean(self):
        if self.lesson_id and not self.module_id:
            raise ValidationError({"module": "A lesson outcome needs its module too."})
        if self.lesson_id and self.module_id and self.lesson.module_id != self.module_id:
            raise ValidationError({"lesson": "The lesson must belong to the same module."})
        if self.module_id and self.course_id and self.module.course_id != self.course_id:
            raise ValidationError({"module": "The module must belong to the same course."})

    def __str__(self):
        return f"{self.code}: {self.text}"


# ─────────────────────────── Steps ───────────────────────────


class LessonStep(TimeStampedModel):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="steps")
    code = models.CharField(max_length=60, unique=True, null=True, blank=True,
                            help_text="Stable id from the content sheet, e.g. PY-M1-L2-S04. Blank for hand-built items.")
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    step_type = models.CharField(max_length=20, choices=STEP_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    required = models.BooleanField(default=True)
    content = models.JSONField(default=dict, blank=True)
    coding_question = models.ForeignKey(
        "assessment.CodingQuestion", on_delete=models.PROTECT, null=True, blank=True, related_name="lesson_steps",
    )
    outcomes = models.ManyToManyField(LearningOutcome, blank=True, related_name="steps")

    class Meta:
        ordering = ["lesson", "position"]
        constraints = [
            models.UniqueConstraint(fields=["lesson", "position"], name="uniq_step_position"),
            models.CheckConstraint(
                condition=Q(coding_question__isnull=True) | Q(step_type__in=["CODING", "FIX_BUG"]),
                name="step_coding_question_only_on_coding_types",
            ),
        ]

    @property
    def spec(self):
        return STEP_TYPES[self.step_type]

    def clean(self):
        errors = structure_errors(self.step_type, self.content)
        if errors:
            raise ValidationError({"content": errors})
        if self.coding_question_id and not self.spec.uses_coding_question:
            raise ValidationError({"coding_question": "Only coding and fix-the-bug steps take a coding question."})

    def save(self, *args, **kwargs):
        if not self.content and self.step_type in STEP_TYPES:
            self.content = self.spec.default_content()
        errors = structure_errors(self.step_type, self.content)
        if errors:  # never store a malformed payload, even outside forms
            raise ValidationError({"content": errors})
        super().save(*args, **kwargs)

    def publish_problems(self):
        return self.spec.publish(self)

    def __str__(self):
        return f"{self.lesson} · {self.position}. {self.title}"


class StepQuestion(models.Model):
    """Ordered MCQ on a PREDICT / QUIZ step, tagged to a learning outcome."""

    step = models.ForeignKey(LessonStep, on_delete=models.CASCADE, related_name="questions")
    mcq = models.ForeignKey("assessment.McqQuestion", on_delete=models.PROTECT, related_name="lesson_steps")
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    outcome = models.ForeignKey(
        LearningOutcome, on_delete=models.SET_NULL, null=True, blank=True, related_name="step_questions",
    )

    class Meta:
        ordering = ["step", "position"]
        constraints = [
            models.UniqueConstraint(fields=["step", "position"], name="uniq_step_question_position"),
            models.UniqueConstraint(fields=["step", "mcq"], name="uniq_step_question_mcq"),
        ]

    def clean(self):
        if self.step_id and not self.step.spec.uses_mcqs:
            raise ValidationError("Only predict and quiz steps take MCQs.")

    def __str__(self):
        return f"{self.step} · Q{self.position}"


class StepHint(models.Model):
    step = models.ForeignKey(LessonStep, on_delete=models.CASCADE, related_name="hints")
    level = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    text = models.TextField()

    class Meta:
        ordering = ["step", "level"]
        constraints = [
            models.UniqueConstraint(fields=["step", "level"], name="uniq_step_hint_level"),
            models.CheckConstraint(condition=Q(level__gte=1) & Q(level__lte=3), name="step_hint_level_1_3"),
        ]

    def __str__(self):
        return f"{self.step} · hint {self.level}"


# ─────────────────────────── Enrollment (Phase 2) ───────────────────────────


class Enrollment(TimeStampedModel):
    """A student taking a course. One row per (user, course); re-enrolling reactivates it."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        DROPPED = "dropped", "Dropped"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                                    help_text="Where 'Continue' takes the student.")

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["user", "course"], name="uniq_enrollment_user_course")]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.user} → {self.course} ({self.status})"
