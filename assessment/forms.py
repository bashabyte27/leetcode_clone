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
            "programming_language",
            "explanation",
            "allow_multiple",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.HiddenInput(),
            "topic": forms.TextInput(attrs={"class": "form-control"}),
            "sub_topic": forms.TextInput(attrs={"class": "form-control"}),
            "difficulty": forms.Select(attrs={"class": "form-select"}),
            "question_type": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "statement": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "explanation": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "programming_language": forms.Select(attrs={"class": "form-select"}),
            "allow_multiple": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["sub_topic"].required = True
        self.fields["difficulty"].initial = McqQuestion.Difficulty.EASY
        self.fields["programming_language"].required = False
        self.fields["programming_language"].help_text = (
            "Required only for Programming MCQs."
        )
        self.fields["programming_language"].queryset = (
            ProgrammingLanguage.objects.filter(is_active=True).order_by("name")
        )

    def clean_slug(self):
        slug_value = (self.cleaned_data.get("slug") or "").strip()
        if self.instance.pk and slug_value:
            return slug_value
        title = (self.cleaned_data.get("title") or "").strip()
        return _generate_unique_slug(McqQuestion, title, exclude_pk=self.instance.pk)

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get("question_type")
        programming_language = cleaned_data.get("programming_language")
        if (
            question_type == McqQuestion.QuestionType.PROGRAMMING
            and programming_language is None
        ):
            self.add_error(
                "programming_language",
                "Choose a programming language for Programming MCQs.",
            )
        return cleaned_data


class McqOptionForm(forms.ModelForm):
    class Meta:
        model = McqOption
        fields = ["text", "is_correct"]
        widgets = {
            "text": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_correct": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_text(self):
        value = self.cleaned_data.get("text")
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise forms.ValidationError("Option text is required.")
        return value


class BaseMcqOptionFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "form")
        super().__init__(*args, **kwargs)

    def validate_unique(self):
        return None

    def clean(self):
        super().clean()
        valid_forms = []
        for form in self.forms:
            if getattr(form, "cleaned_data", {}).get("text"):
                valid_forms.append(form)

        if len(valid_forms) < 2:
            raise ValidationError("At least two non-empty options are required.")

        correct_count = sum(
            1 for form in valid_forms if (form.cleaned_data or {}).get("is_correct")
        )
        question = getattr(self, "instance", None)
        allow_multiple = bool(getattr(question, "allow_multiple", False))
        if allow_multiple and correct_count < 1:
            raise ValidationError(
                "At least one correct option is required for multiple-answer MCQs."
            )
        if not allow_multiple and correct_count != 1:
            raise ValidationError(
                "Single-answer MCQs must have exactly one correct option."
            )

    def save(self, commit=True):
        next_position = max(
            (option.position for option in self.get_queryset()),
            default=0,
        ) + 1
        for form in self.forms:
            if not getattr(form, "cleaned_data", {}).get("text"):
                continue
            if form.instance.pk is None:
                form.instance.position = next_position
                next_position += 1
        return super().save(commit=commit)


McqOptionFormSet = inlineformset_factory(
    McqQuestion,
    McqOption,
    form=McqOptionForm,
    formset=BaseMcqOptionFormSet,
    extra=2,
    can_delete=False,
    fields=("text", "is_correct"),
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
        self.fields["starter_code"].label = "Code snippet"
        self.fields["buggy_code"].label = "Code snippet"
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
        extra = kwargs.pop("extra", None)
        kwargs.setdefault("prefix", "form")
        super().__init__(*args, **kwargs)
        if extra is not None:
            self.extra = extra

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
    extra=1,
    can_delete=False,
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
    extra=1,
    can_delete=False,
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
            "passing_marks",
            "allow_paste_in_editor",
            "status",
            "max_attempts",
            "result_release_policy",
            "results_release_at",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "start_time": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"class": "form-control", "type": "datetime-local"},
            ),
            "end_time": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"class": "form-control", "type": "datetime-local"},
            ),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "passing_marks": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": "0.01"}
            ),
            "allow_paste_in_editor": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "max_attempts": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "result_release_policy": forms.Select(attrs={"class": "form-select"}),
            "results_release_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"class": "form-control", "type": "datetime-local"},
            ),
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


class AssessmentDetailsForm(AssessmentForm):
    class Meta(AssessmentForm.Meta):
        fields = ["name", "slug", "start_time", "end_time", "duration_minutes"]


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
        if (
            self.assessment is not None
            and AssessmentSection.objects.filter(
                assessment=self.assessment,
                position=value,
            ).exclude(pk=self.instance.pk).exists()
        ):
            raise forms.ValidationError(
                "This section position is already used in the assessment."
            )
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
            position = cleaned_data.get("position")
            if (
                position is not None
                and AssessmentQuestion.objects.filter(
                    assessment=self.assessment,
                    section=self.section,
                    position=position,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                self.add_error(
                    "position",
                    "This position is already used in the section.",
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


class AssessmentQuestionAddForm(forms.Form):
    QUESTION_TYPES = (
        ("mcq", "MCQ"),
        ("coding", "Coding"),
    )

    question_type = forms.ChoiceField(choices=QUESTION_TYPES, widget=forms.HiddenInput)
    question_id = forms.IntegerField(widget=forms.HiddenInput)
    section = forms.ModelChoiceField(
        queryset=AssessmentSection.objects.none(),
        required=False,
        empty_label="Select a section",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    max_score = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=0.01,
        initial=1,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0.01", "step": "0.01"}
        ),
    )
    negative_marks = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0", "step": "0.01"}
        ),
    )

    def __init__(self, *args, assessment, user, section=None, **kwargs):
        self.assessment = assessment
        self.user = user
        self.section = section
        super().__init__(*args, **kwargs)
        self.fields["question_type"].initial = "coding"
        if section is not None:
            self.fields.pop("section")
        else:
            self.fields["section"].queryset = assessment.sections.order_by("position")
        self.selected_question = None

    def clean(self):
        cleaned_data = super().clean()
        section = self.section or cleaned_data.get("section")
        if section and section.assessment_id != self.assessment.pk:
            self.add_error("section", "Select a section from this assessment.")
        elif section is None and self.section is None and self.assessment.sections.exists():
            self.add_error("section", "Select a section for this question.")

        question_type = cleaned_data.get("question_type")
        question_id = cleaned_data.get("question_id")
        if question_type and question_id is not None:
            model = McqQuestion if question_type == "mcq" else CodingQuestion
            queryset = model.objects.filter(is_active=True)
            if not self.user.is_staff:
                queryset = queryset.filter(owner=self.user)
            queryset = queryset.exclude(
                assessment_assignments__assessment=self.assessment
            )
            self.selected_question = queryset.filter(pk=question_id).first()
            if self.selected_question is None:
                self.add_error(
                    "question_id",
                    "This question is unavailable or already assigned to the assessment.",
                )
        return cleaned_data
