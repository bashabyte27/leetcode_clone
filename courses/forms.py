"""
Staff builder forms.

Structural forms (course, module, lesson, outcome) are plain ModelForms.
Step editing uses one form per step type: each form turns friendly fields
(mm:ss durations, "0:00 Intro" chapter lines, indented Parsons code...) into
the validated JSON stored on `LessonStep.content`, and back again.
"""

import re

from django import forms
from django.core.exceptions import ValidationError

from problems.models import Language

from .models import Course, LearningOutcome, Lesson, LessonStep, Module
from .steps import CALLOUT_KINDS, MAX_PARSONS_INDENT, STEP_TYPES, VIDEO_PROVIDERS, structure_errors

PARSONS_INDENT_SPACES = 4


# ─────────────────────────── Structure ───────────────────────────


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["category", "title", "subtitle", "description", "level", "est_weeks", "access",
                  "thumbnail_url", "capstone_brief", "prerequisites"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "capstone_brief": forms.Textarea(attrs={"rows": 4}),
            "prerequisites": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Course.objects.order_by("title")
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["prerequisites"].queryset = qs
        self.fields["prerequisites"].required = False


class ModuleForm(forms.ModelForm):
    video_provider = forms.ChoiceField(choices=[(p, p.title()) for p in VIDEO_PROVIDERS], required=False)
    video_id = forms.CharField(required=False, max_length=120, label="Intro video id")

    class Meta:
        model = Module
        fields = ["title", "summary", "mini_project_brief", "is_free_preview"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 3}),
                   "mini_project_brief": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        video = self.instance.intro_video or {}
        self.fields["video_provider"].initial = video.get("provider", "youtube")
        self.fields["video_id"].initial = video.get("video_id", "")

    def save(self, commit=True):
        module = super().save(commit=False)
        vid = self.cleaned_data.get("video_id", "").strip()
        module.intro_video = {"provider": self.cleaned_data.get("video_provider") or "youtube", "video_id": vid} if vid else {}
        if commit:
            module.save()
        return module


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "summary", "est_minutes", "is_free_preview"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 3})}


class OutcomeForm(forms.ModelForm):
    class Meta:
        model = LearningOutcome
        fields = ["code", "text", "lesson"]

    def __init__(self, *args, module=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.module = module or self.instance.module
        self.instance.module = self.module  # model.clean() checks module/course consistency during validation
        self.instance.course = self.module.course
        self.fields["lesson"].queryset = self.module.lessons.order_by("position")
        self.fields["lesson"].required = False
        self.fields["lesson"].empty_label = "Whole module"

    def save(self, commit=True):
        outcome = super().save(commit=False)
        outcome.module = self.module
        outcome.course = self.module.course
        if commit:
            outcome.save()
        return outcome


# ─────────────────────────── Step editors ───────────────────────────


def _language_choices():
    langs = list(Language.objects.filter(is_active=True).order_by("name").values_list("slug", "name"))
    return langs or [("python", "Python")]


def parse_duration(text):
    """'7:30' -> 450, '1:02:03' -> 3723, '95' -> 95. Raises ValidationError on junk."""
    text = (text or "").strip()
    if not text:
        return 0
    if not re.fullmatch(r"\d+(:\d{1,2}){0,2}", text):
        raise ValidationError("Use seconds or mm:ss, e.g. 7:30.")
    seconds = 0
    for part in text.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def format_duration(seconds):
    seconds = int(seconds or 0)
    if not seconds:
        return ""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class StepFormBase(forms.Form):
    """Common fields; subclasses add their own and implement to_content / initial_from."""

    title = forms.CharField(max_length=200)
    required = forms.BooleanField(required=False, initial=True, help_text="Required to complete the lesson.")
    outcomes = forms.ModelMultipleChoiceField(queryset=LearningOutcome.objects.none(), required=False,
                                              widget=forms.CheckboxSelectMultiple)

    step_type = None

    def __init__(self, *args, step=None, lesson=None, **kwargs):
        self.step = step
        self.lesson = lesson or step.lesson
        if step is not None and "initial" not in kwargs:
            kwargs["initial"] = {"title": step.title, "required": step.required,
                                 "outcomes": list(step.outcomes.all()), **self.initial_from(step.content)}
        super().__init__(*args, **kwargs)
        self.fields["outcomes"].queryset = LearningOutcome.objects.filter(module=self.lesson.module).order_by("code")
        self.fields["outcomes"].label_from_instance = lambda o: f"{o.code} · {o.text}"

    # Subclasses override
    def initial_from(self, content):
        return dict(content)

    def to_content(self):
        return {}

    def clean(self):
        data = super().clean()
        if not self.errors:
            errors = structure_errors(self.step_type, self.to_content())
            if errors:
                raise ValidationError(errors)
        return data

    def save(self, position=None):
        step = self.step or LessonStep(lesson=self.lesson, step_type=self.step_type, position=position)
        step.title = self.cleaned_data["title"]
        step.required = self.cleaned_data["required"]
        step.content = self.to_content()
        self.apply_relations(step)
        step.save()
        step.outcomes.set(self.cleaned_data["outcomes"])
        self.after_save(step)
        return step

    def apply_relations(self, step):
        pass

    def after_save(self, step):
        pass


class VideoStepForm(StepFormBase):
    step_type = "VIDEO"
    provider = forms.ChoiceField(choices=[(p, p.title()) for p in VIDEO_PROVIDERS])
    video_id = forms.CharField(required=False, max_length=120, help_text="YouTube id (e.g. dQw4w9WgXcQ) or Bunny video GUID.")
    duration = forms.CharField(required=False, max_length=10, help_text="mm:ss — needed to mark 80% watched.")
    chapters = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}),
                               help_text='One per line: "0:00 Introduction".')
    transcript = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 6}))
    complete_at_percent = forms.IntegerField(min_value=1, max_value=100, initial=80, required=False,
                                             label="Counts as watched at (%)", help_text="Blank = 80%.")
    script = forms.CharField(required=False, label="Production script (staff only)",
                             widget=forms.Textarea(attrs={"rows": 8}))

    def initial_from(self, c):
        chapters = "\n".join(f"{format_duration(ch['t']) or '0:00'} {ch['title']}" for ch in c.get("chapters", []))
        return {"provider": c.get("provider", "youtube"), "video_id": c.get("video_id", ""),
                "duration": format_duration(c.get("duration_s")), "chapters": chapters,
                "transcript": c.get("transcript", ""), "script": c.get("script", ""),
                "complete_at_percent": c.get("complete_at_percent", 80)}

    def clean_duration(self):
        return parse_duration(self.cleaned_data.get("duration"))

    def clean_chapters(self):
        chapters = []
        for i, line in enumerate((self.cleaned_data.get("chapters") or "").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            stamp, _, title = line.partition(" ")
            try:
                t = parse_duration(stamp)
            except ValidationError:
                raise ValidationError(f'Chapter line {i} should look like "2:15 Title".')
            if not title.strip():
                raise ValidationError(f"Chapter line {i} needs a title after the time.")
            chapters.append({"t": t, "title": title.strip()})
        return sorted(chapters, key=lambda ch: ch["t"])

    def to_content(self):
        d = self.cleaned_data
        return {"provider": d.get("provider", "youtube"), "video_id": (d.get("video_id") or "").strip(),
                "duration_s": d.get("duration") or 0, "chapters": d.get("chapters") or [],
                "transcript": d.get("transcript") or "", "script": d.get("script") or "",
                "complete_at_percent": d.get("complete_at_percent") or 80}


class TextStepForm(StepFormBase):
    step_type = "TEXT"
    markdown = forms.CharField(required=False, label="Notes (Markdown)",
                               widget=forms.Textarea(attrs={"rows": 16, "class": "is-code"}))
    tip = forms.CharField(required=False, label="Tip callout", widget=forms.Textarea(attrs={"rows": 3}))
    mistake = forms.CharField(required=False, label="Common mistakes callout", widget=forms.Textarea(attrs={"rows": 3}))
    note = forms.CharField(required=False, label="Note callout", widget=forms.Textarea(attrs={"rows": 3}))

    def initial_from(self, c):
        initial = {"markdown": c.get("markdown", "")}
        for co in c.get("callouts", []):
            initial[co["kind"]] = co["markdown"]
        return initial

    def to_content(self):
        d = self.cleaned_data
        callouts = [{"kind": k, "markdown": d[k].strip()} for k in CALLOUT_KINDS if (d.get(k) or "").strip()]
        return {"markdown": d.get("markdown") or "", "callouts": callouts}


class PredictStepForm(StepFormBase):
    step_type = "PREDICT"
    intro = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}),
                            help_text="Shown above the questions.")

    def to_content(self):
        return {"intro": self.cleaned_data.get("intro") or ""}


class QuizStepForm(PredictStepForm):
    step_type = "QUIZ"
    pass_percent = forms.IntegerField(min_value=0, max_value=100, initial=60, label="Pass mark (%)",
                                      help_text="0 = practice only; it doesn't count toward completing the lesson.")

    def to_content(self):
        return {"intro": self.cleaned_data.get("intro") or "", "pass_percent": self.cleaned_data["pass_percent"]}


class PlaygroundStepForm(StepFormBase):
    step_type = "PLAYGROUND"
    language = forms.ChoiceField(choices=())
    instructions = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    starter_code = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 12, "class": "is-code"}))
    stdin = forms.CharField(required=False, label="Sample input", widget=forms.Textarea(attrs={"rows": 3, "class": "is-code"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["language"].choices = _language_choices()

    def to_content(self):
        d = self.cleaned_data
        return {k: d.get(k) or "" for k in ("language", "instructions", "starter_code", "stdin")}


class ParsonsStepForm(StepFormBase):
    step_type = "PARSONS"
    language = forms.ChoiceField(choices=())
    instructions = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    solution = forms.CharField(required=False, label="Correct program",
                               widget=forms.Textarea(attrs={"rows": 10, "class": "is-code"}),
                               help_text=f"Write the program in the right order. Indent with {PARSONS_INDENT_SPACES} spaces; "
                                         "students see the lines shuffled and must rebuild it.")
    distractors = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "is-code"}),
                                  help_text="Optional wrong lines, one per line.")
    use_indentation = forms.BooleanField(required=False, initial=True, label="Check indentation",
                                         help_text="Untick for order-only puzzles (e.g. terminal commands).")
    explanation = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}),
                                  help_text="Shown after the student solves it.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["language"].choices = _language_choices()

    def initial_from(self, c):
        solution = "\n".join(" " * (PARSONS_INDENT_SPACES * ln.get("indent", 0)) + ln["text"] for ln in c.get("lines", []))
        return {"language": c.get("language", "python"), "instructions": c.get("instructions", ""),
                "solution": solution, "distractors": "\n".join(c.get("distractors", [])),
                "use_indentation": c.get("use_indentation", True), "explanation": c.get("explanation", "")}

    def clean_solution(self):
        lines = []
        for i, raw in enumerate((self.cleaned_data.get("solution") or "").replace("\t", " " * PARSONS_INDENT_SPACES).splitlines(), 1):
            if not raw.strip():
                continue
            spaces = len(raw) - len(raw.lstrip(" "))
            if spaces % PARSONS_INDENT_SPACES:
                raise ValidationError(f"Line {i} is indented by {spaces} spaces; use multiples of {PARSONS_INDENT_SPACES}.")
            indent = spaces // PARSONS_INDENT_SPACES
            if indent > MAX_PARSONS_INDENT:
                raise ValidationError(f"Line {i} is nested deeper than {MAX_PARSONS_INDENT} levels.")
            lines.append({"text": raw.strip(), "indent": indent})
        return lines

    def to_content(self):
        d = self.cleaned_data
        distractors = [ln.strip() for ln in (d.get("distractors") or "").splitlines() if ln.strip()]
        return {"language": d.get("language", "python"), "instructions": d.get("instructions") or "",
                "lines": d.get("solution") or [], "distractors": distractors,
                "use_indentation": bool(d.get("use_indentation")), "explanation": d.get("explanation") or ""}


class CodingStepForm(StepFormBase):
    step_type = "CODING"
    instructions = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}),
                                   help_text="Optional lesson-specific framing shown above the task statement.")
    coding_question = forms.IntegerField(required=False, widget=forms.HiddenInput)
    hint_1 = forms.CharField(required=False, label="Hint 1 · nudge", widget=forms.Textarea(attrs={"rows": 2}))
    hint_2 = forms.CharField(required=False, label="Hint 2 · approach", widget=forms.Textarea(attrs={"rows": 2}))
    hint_3 = forms.CharField(required=False, label="Hint 3 · near-solution", widget=forms.Textarea(attrs={"rows": 2}))

    def initial_from(self, c):
        initial = {"instructions": c.get("instructions", "")}
        if self.step is not None:
            initial["coding_question"] = self.step.coding_question_id
            for hint in self.step.hints.all():
                initial[f"hint_{hint.level}"] = hint.text
        return initial

    def clean_coding_question(self):
        from assessment.models import CodingQuestion
        pk = self.cleaned_data.get("coding_question")
        if not pk:
            return None
        question = CodingQuestion.objects.filter(pk=pk, is_active=True).first()
        if question is None:
            raise ValidationError("That coding question no longer exists.")
        return question

    def to_content(self):
        return {"instructions": self.cleaned_data.get("instructions") or ""}

    def apply_relations(self, step):
        step.coding_question = self.cleaned_data.get("coding_question")

    def after_save(self, step):
        from .models import StepHint
        for level in (1, 2, 3):
            text = (self.cleaned_data.get(f"hint_{level}") or "").strip()
            if text:
                StepHint.objects.update_or_create(step=step, level=level, defaults={"text": text})
            else:
                StepHint.objects.filter(step=step, level=level).delete()


class FixBugStepForm(CodingStepForm):
    step_type = "FIX_BUG"


STEP_FORMS = {cls.step_type: cls for cls in (
    VideoStepForm, TextStepForm, PredictStepForm, QuizStepForm, PlaygroundStepForm,
    ParsonsStepForm, CodingStepForm, FixBugStepForm,
)}
assert set(STEP_FORMS) == set(STEP_TYPES), "every step type needs an editor form"
