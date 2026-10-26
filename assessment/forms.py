from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils.text import slugify

from .models import (
    Assessment,
    AssessmentQuestion,
    AssessmentSection,
    CodingQuestion,
    CodingQuestionLanguage,
    CodingTestCase,
    McqOption,
    McqQuestion,
    ProgrammingLanguage,
)


def _generate_unique_slug(model_class, value, exclude_pk=None):
    base = slugify(value or "") or "item"
    candidate = base
    suffix = 1
    queryset = model_class.objects.filter(slug=candidate)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    while queryset.exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
        queryset = model_class.objects.filter(slug=candidate)
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
    return candidate


class McqQuestionForm(forms.ModelForm):
    class Meta:
        model = McqQuestion
        fields = [
            "title",
            "slug",
            "question_type",
            "category",
            "topic",
            "sub_topic",
            "difficulty",
            "statement",
            "code_snippet",
            "programming_language",
            "explanation",
            "allow_multiple",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "sub_topic": forms.TextInput(attrs={"class": "form-control"}),
            "difficulty": forms.Select(attrs={"class": "form-select"}),
            "question_type": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "statement": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "code_snippet": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "explanation": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "programming_language": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "allow_multiple": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["programming_language"].queryset = (
            ProgrammingLanguage.objects.filter(is_active=True).order_by("name")
        )

    def clean_slug(self):
        slug_value = (self.cleaned_data.get("slug") or "").strip()
        title = (self.cleaned_data.get("title") or "").strip()
        if slug_value:
            return slug_value
        return _generate_unique_slug(McqQuestion, title, exclude_pk=self.instance.pk)

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get("question_type")
        programming_language = cleaned_data.get("programming_language")
        if question_type == McqQuestion.QuestionType.REGULAR and programming_language is not None:
            cleaned_data["programming_language"] = programming_language
        return cleaned_data


class McqOptionForm(forms.ModelForm):
    class Meta:
        model = McqOption
        fields = ["text", "is_correct", "position"]
        widgets = {
            "text": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_correct": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }

    def clean_text(self):
        value = self.cleaned_data.get("text")
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise forms.ValidationError("Option text is required.")
        return value

    def clean_position(self):
        position = self.cleaned_data.get("position")
        if position is None:
            raise forms.ValidationError("Position is required.")
        if position < 1:
            raise forms.ValidationError("Position must start at 1.")
        return position


class BaseMcqOptionFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "form")
        super().__init__(*args, **kwargs)

    def validate_unique(self):
        return None

    def clean(self):
        super().clean()
        valid_forms = []
        seen_positions = set()

        for form in self.forms:
            if self._should_delete_form(form):
                continue

            raw_text = (self.data or {}).get(f"{form.prefix}-text", "")
            raw_position = (self.data or {}).get(f"{form.prefix}-position", "")
            if not raw_text.strip():
                continue

            valid_forms.append(form)
            if raw_position == "":
                continue
            try:
                position = int(raw_position)
            except (TypeError, ValueError):
                continue
            if position in seen_positions:
                form.add_error("position", "Duplicate positions are not allowed.")
            else:
                seen_positions.add(position)

        if len(valid_forms) < 2:
            raise ValidationError("At least two non-empty options are required.")

        question = getattr(self, "instance", None)
        allow_multiple = bool(getattr(question, "allow_multiple", False))
        if question is None and self.data:
            allow_multiple = self.data.get("allow_multiple") in {"on", "True", "true", "1"}

        correct_count = sum(
            1 for form in valid_forms if (form.cleaned_data or {}).get("is_correct")
        )
        if allow_multiple:
            if correct_count < 1:
                raise ValidationError(
                    "At least one correct option is required for multiple-answer MCQs."
                )
        elif correct_count != 1:
            raise ValidationError(
                "Single-answer MCQs must have exactly one correct option."
            )


McqOptionFormSet = inlineformset_factory(
    McqQuestion,
    McqOption,
    form=McqOptionForm,
    formset=BaseMcqOptionFormSet,
    extra=4,
    can_delete=True,
    fields=("text", "is_correct", "position"),
    fk_name="question",
)

McqOptionFormSet.prefix = "form"


class CodingQuestionForm(forms.ModelForm):
    class Meta:
        model = CodingQuestion
        fields = [
            "title",
            "slug",
            "coding_mode",
            "topic",
            "subtopic",
            "difficulty",
            "statement",
            "input_format",
            "output_format",
            "constraints_text",
            "explanation",
            "time_limit_seconds",
            "memory_limit_kb",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "coding_mode": forms.Select(attrs={"class": "form-select"}),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "subtopic": forms.TextInput(attrs={"class": "form-control"}),
            "difficulty": forms.Select(attrs={"class": "form-select"}),
            "statement": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "input_format": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "output_format": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "constraints_text": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "explanation": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "time_limit_seconds": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "memory_limit_kb": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_slug(self):
        slug_value = (self.cleaned_data.get("slug") or "").strip()
        title = (self.cleaned_data.get("title") or "").strip()
        if slug_value:
            return slug_value
        return _generate_unique_slug(CodingQuestion, title, exclude_pk=self.instance.pk)

    def clean_time_limit_seconds(self):
        value = self.cleaned_data.get("time_limit_seconds")
        if value is not None and value < 1:
            raise forms.ValidationError("Time limit must be at least 1 second.")
        return value

    def clean_memory_limit_kb(self):
        value = self.cleaned_data.get("memory_limit_kb")
        if value is not None and value < 1:
            raise forms.ValidationError("Memory limit must be at least 1 KB.")
        return value


class CodingQuestionLanguageForm(forms.ModelForm):
    class Meta:
        model = CodingQuestionLanguage
        fields = ["language", "starter_code", "buggy_code"]
        widgets = {
            "language": forms.Select(attrs={"class": "form-select"}),
            "starter_code": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "buggy_code": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["language"].queryset = (
            ProgrammingLanguage.objects.filter(is_active=True, is_judge0_executable=True).order_by("name")
        )

    def clean_language(self):
        language = self.cleaned_data.get("language")
        if language is not None and not language.is_active:
            raise forms.ValidationError("Please select an active language.")
        return language


class BaseCodingQuestionLanguageFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "form")
        super().__init__(*args, **kwargs)

    def validate_unique(self):
        return None

    def clean(self):
        super().clean()
        valid_rows = []
        seen_languages = set()
        for form in self.forms:
            if self._should_delete_form(form):
                continue

            raw_language = (self.data or {}).get(f"{form.prefix}-language")
            if not raw_language:
                continue
            try:
                language_id = int(raw_language)
            except (TypeError, ValueError):
                continue
            if language_id in seen_languages:
                form.add_error("language", "Each language can only be selected once.")
            else:
                seen_languages.add(language_id)
            valid_rows.append(form)

        if not valid_rows:
            raise ValidationError("At least one supported language is required.")


CodingQuestionLanguageFormSet = inlineformset_factory(
    CodingQuestion,
    CodingQuestionLanguage,
    form=CodingQuestionLanguageForm,
    formset=BaseCodingQuestionLanguageFormSet,
    extra=2,
    can_delete=True,
    fields=("language", "starter_code", "buggy_code"),
    fk_name="question",
)

CodingQuestionLanguageFormSet.prefix = "form"


class CodingTestCaseForm(forms.ModelForm):
    class Meta:
        model = CodingTestCase
        fields = ["input_data", "expected_output", "is_sample", "weight", "position", "explanation"]
        widgets = {
            "input_data": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "expected_output": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_sample": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "weight": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "explanation": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_expected_output(self):
        value = self.cleaned_data.get("expected_output")
        if value is None or value == "":
            raise forms.ValidationError("Expected output is required.")
        return value

    def clean_weight(self):
        value = self.cleaned_data.get("weight")
        if value is not None and value < 1:
            raise forms.ValidationError("Weight must be positive.")
        return value

    def clean_position(self):
        position = self.cleaned_data.get("position")
        if position is None:
            raise forms.ValidationError("Position is required.")
        if position < 1:
            raise forms.ValidationError("Position must start at 1.")
        return position


class BaseCodingTestCaseFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "form")
        super().__init__(*args, **kwargs)

    def validate_unique(self):
        return None

    def clean(self):
        super().clean()
        positions = []
        valid_rows = []
        for form in self.forms:
            if self._should_delete_form(form):
                continue
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            if not any(
                form.cleaned_data.get(field) not in (None, "")
                for field in ("input_data", "expected_output", "explanation")
            ):
                continue
            valid_rows.append(form)
            position = form.cleaned_data.get("position")
            if position is None:
                continue
            if position in positions:
                form.add_error("position", "Duplicate test case positions are not allowed.")
                raise ValidationError("Duplicate test case positions are not allowed.")
            else:
                positions.append(position)

        if not valid_rows:
            return


CodingTestCaseFormSet = inlineformset_factory(
    CodingQuestion,
    CodingTestCase,
    form=CodingTestCaseForm,
    formset=BaseCodingTestCaseFormSet,
    extra=3,
    can_delete=True,
    fields=("input_data", "expected_output", "is_sample", "weight", "position", "explanation"),
    fk_name="question",
)

CodingTestCaseFormSet.prefix = "form"


class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            "name",
            "slug",
            "description",
            "start_time",
            "end_time",
            "duration_minutes",
            "status",
            "max_attempts",
            "result_release_policy",
            "results_release_at",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "start_time": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "max_attempts": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "result_release_policy": forms.Select(attrs={"class": "form-select"}),
            "results_release_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_slug(self):
        slug_value = (self.cleaned_data.get("slug") or "").strip()
        title = (self.cleaned_data.get("name") or "").strip()
        if slug_value:
            return slug_value
        return _generate_unique_slug(Assessment, title, exclude_pk=self.instance.pk)

    def clean_duration_minutes(self):
        value = self.cleaned_data.get("duration_minutes")
        if value is not None and value < 1:
            raise forms.ValidationError("Duration must be at least 1 minute.")
        return value

    def clean_max_attempts(self):
        value = self.cleaned_data.get("max_attempts")
        if value is not None and value < 1:
            raise forms.ValidationError("Maximum attempts must be at least 1.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        if start_time and end_time and start_time >= end_time:
            self.add_error("end_time", "Assessment start time must be earlier than the end time.")

        policy = cleaned_data.get("result_release_policy")
        release_at = cleaned_data.get("results_release_at")
        if policy == Assessment.ResultReleasePolicy.SCHEDULED and not release_at:
            self.add_error(
                "results_release_at",
                "A scheduled result release date/time is required.",
            )
        return cleaned_data


class AssessmentSectionForm(forms.ModelForm):
    class Meta:
        model = AssessmentSection
        exclude = ("assessment",)
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "instructions": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "time_limit_minutes": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
        }

    def __init__(self, *args, assessment=None, **kwargs):
        self.assessment = assessment
        super().__init__(*args, **kwargs)

    def clean_position(self):
        value = self.cleaned_data.get("position")
        if value is None:
            raise forms.ValidationError("Position is required.")
        if value < 1:
            raise forms.ValidationError("Position must be at least 1.")
        return value

    def clean_time_limit_minutes(self):
        value = self.cleaned_data.get("time_limit_minutes")
        if value is not None and value < 1:
            raise forms.ValidationError("Time limit must be at least 1 minute.")
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.assessment is not None:
            instance.assessment = self.assessment
        if commit:
            instance.save()
        return instance


class AssessmentQuestionForm(forms.ModelForm):
    class Meta:
        model = AssessmentQuestion
        exclude = ("assessment", "section")
        widgets = {
            "mcq_question": forms.Select(attrs={"class": "form-select"}),
            "coding_question": forms.Select(attrs={"class": "form-select"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "max_score": forms.NumberInput(attrs={"class": "form-control", "min": 0.01, "step": "0.01"}),
            "negative_marks": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
        }

    def __init__(self, *args, assessment=None, section=None, user=None, **kwargs):
        self.assessment = assessment
        self.section = section
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["mcq_question"].queryset = self._mcq_queryset()
        self.fields["coding_question"].queryset = self._coding_queryset()

    def _mcq_queryset(self):
        queryset = McqQuestion.objects.filter(is_active=True).order_by("title")
        if self.assessment is not None:
            queryset = queryset.exclude(
                assessment_assignments__assessment=self.assessment
            ).distinct()
        if self.user is not None:
            if not getattr(self.user, "is_staff", False) and not getattr(self.user, "is_faculty", False):
                queryset = queryset.filter(owner=self.user)
            elif getattr(self.user, "is_faculty", False):
                queryset = queryset.filter(owner=self.user)
        return queryset

    def _coding_queryset(self):
        queryset = CodingQuestion.objects.filter(is_active=True).order_by("title")
        if self.assessment is not None:
            queryset = queryset.exclude(
                assessment_assignments__assessment=self.assessment
            ).distinct()
        if self.user is not None:
            if not getattr(self.user, "is_staff", False) and not getattr(self.user, "is_faculty", False):
                queryset = queryset.filter(owner=self.user)
            elif getattr(self.user, "is_faculty", False):
                queryset = queryset.filter(owner=self.user)
        return queryset

    def clean(self):
        cleaned_data = super().clean()
        mcq_question = cleaned_data.get("mcq_question")
        coding_question = cleaned_data.get("coding_question")

        if (mcq_question is None) == (coding_question is None):
            self.add_error(
                None,
                "Select exactly one question type: either an MCQ or a coding question.",
            )

        if self.assessment is not None and self.section is not None:
            if self.section.assessment_id != self.assessment.pk:
                raise forms.ValidationError(
                    "The selected section does not belong to this assessment."
                )

        max_score = cleaned_data.get("max_score")
        if max_score is not None and max_score <= 0:
            self.add_error("max_score", "Maximum score must be positive.")

        negative_marks = cleaned_data.get("negative_marks")
        if negative_marks is not None and negative_marks < 0:
            self.add_error("negative_marks", "Negative marks cannot be negative.")

        if self.section is not None:
            cleaned_data["section"] = self.section
        if self.assessment is not None:
            cleaned_data["assessment"] = self.assessment

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.assessment is not None:
            instance.assessment = self.assessment
        if self.section is not None:
            instance.section = self.section
        if commit:
            instance.save()
        return instance
