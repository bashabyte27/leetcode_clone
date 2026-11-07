from django.contrib import admin

from .models import (
    CareerPath, CareerPathCourse, Category, Course, LearningOutcome, Lesson, LessonStep, Module,
    StepHint, StepQuestion,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("title", "position", "is_active")
    list_editable = ("position", "is_active")
    prepopulated_fields = {"slug": ("title",)}


class CareerPathCourseInline(admin.TabularInline):
    model = CareerPathCourse
    extra = 0
    autocomplete_fields = ("course",)


@admin.register(CareerPath)
class CareerPathAdmin(admin.ModelAdmin):
    list_display = ("title", "goal", "position", "is_active")
    list_filter = ("goal", "is_active")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [CareerPathCourseInline]


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 0
    fields = ("position", "title", "slug", "is_free_preview")
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "level", "version", "access", "is_published")
    list_filter = ("category", "level", "access", "is_published")
    search_fields = ("title", "subtitle")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("prerequisites",)
    readonly_fields = ("published_at", "created_at", "updated_at")
    inlines = [ModuleInline]


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ("position", "title", "slug", "est_minutes", "is_free_preview")
    show_change_link = True


class OutcomeInline(admin.TabularInline):
    model = LearningOutcome
    extra = 0
    fields = ("code", "text", "lesson")


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("__str__", "course", "position")
    list_filter = ("course",)
    search_fields = ("title",)
    inlines = [LessonInline, OutcomeInline]


class StepInline(admin.TabularInline):
    model = LessonStep
    extra = 0
    fields = ("position", "step_type", "title", "required")
    show_change_link = True


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("__str__", "module", "est_minutes")
    list_filter = ("module__course",)
    search_fields = ("title",)
    inlines = [StepInline]


class StepQuestionInline(admin.TabularInline):
    model = StepQuestion
    extra = 0
    raw_id_fields = ("mcq",)


class StepHintInline(admin.TabularInline):
    model = StepHint
    extra = 0


@admin.register(LessonStep)
class LessonStepAdmin(admin.ModelAdmin):
    list_display = ("__str__", "step_type", "required")
    list_filter = ("step_type", "lesson__module__course")
    search_fields = ("title", "lesson__title")
    raw_id_fields = ("coding_question",)
    filter_horizontal = ("outcomes",)
    inlines = [StepQuestionInline, StepHintInline]


@admin.register(LearningOutcome)
class LearningOutcomeAdmin(admin.ModelAdmin):
    list_display = ("code", "text", "module", "lesson")
    search_fields = ("code", "text")
    list_filter = ("module__course",)
