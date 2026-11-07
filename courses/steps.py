"""
Step-type registry.

Each lesson step stores its *authored* payload in `LessonStep.content` (JSON).
This module is the single source of truth for what that JSON may contain:

* `structure_errors(content)`  — shape/type problems. Always enforced on save;
  a malformed step can never be stored.
* `publish_problems(step)`     — completeness problems (empty markdown, missing
  video id, no questions attached...). Allowed while drafting, block publishing.
* `default_content()`          — a valid starting payload for a new step.

References to other data (MCQs, coding questions, hints, outcomes) are real
database relations on the step, not JSON — see docs/courses/ARCHITECTURE.md §4.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List

VIDEO_PROVIDERS = ("youtube", "bunny")
CALLOUT_KINDS = ("tip", "mistake", "note")
MAX_PARSONS_INDENT = 6


# ── Small typed readers ──────────────────────────────────────────────

def _is_str(value):
    return isinstance(value, str)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_keys(content, allowed, errors):
    extra = set(content) - set(allowed)
    if extra:
        errors.append(f"Unknown field(s): {', '.join(sorted(extra))}.")


def _check_str(content, key, errors, label=None):
    if key in content and not _is_str(content[key]):
        errors.append(f"{label or key} must be text.")


# ── Per-type structure validators ────────────────────────────────────

def _video_structure(c):
    errors = []
    _check_keys(c, ("provider", "video_id", "duration_s", "chapters", "transcript", "script",
                    "complete_at_percent"), errors)
    if "provider" in c and c["provider"] not in VIDEO_PROVIDERS:
        errors.append(f"Video provider must be one of: {', '.join(VIDEO_PROVIDERS)}.")
    _check_str(c, "video_id", errors, "Video id")
    _check_str(c, "transcript", errors, "Transcript")
    _check_str(c, "script", errors, "Script")
    if "complete_at_percent" in c and not (_is_int(c["complete_at_percent"]) and 1 <= c["complete_at_percent"] <= 100):
        errors.append("Watched-at percentage must be a whole number from 1 to 100.")
    if "duration_s" in c and not (_is_int(c["duration_s"]) and c["duration_s"] >= 0):
        errors.append("Duration must be a whole number of seconds.")
    chapters = c.get("chapters", [])
    if not isinstance(chapters, list):
        errors.append("Chapters must be a list.")
    else:
        for i, ch in enumerate(chapters, 1):
            if not (isinstance(ch, dict) and _is_int(ch.get("t")) and ch["t"] >= 0 and _is_str(ch.get("title"))):
                errors.append(f"Chapter {i} needs a start time in seconds (t) and a title.")
    return errors


def _text_structure(c):
    errors = []
    _check_keys(c, ("markdown", "callouts"), errors)
    _check_str(c, "markdown", errors, "Notes")
    callouts = c.get("callouts", [])
    if not isinstance(callouts, list):
        errors.append("Callouts must be a list.")
    else:
        for i, co in enumerate(callouts, 1):
            if not (isinstance(co, dict) and co.get("kind") in CALLOUT_KINDS and _is_str(co.get("markdown"))):
                errors.append(f"Callout {i} needs a kind ({', '.join(CALLOUT_KINDS)}) and text.")
    return errors


def _intro_structure(c):
    errors = []
    _check_keys(c, ("intro",), errors)
    _check_str(c, "intro", errors, "Intro")
    return errors


def _quiz_structure(c):
    errors = []
    _check_keys(c, ("intro", "pass_percent"), errors)
    _check_str(c, "intro", errors, "Intro")
    if "pass_percent" in c and not (_is_int(c["pass_percent"]) and 0 <= c["pass_percent"] <= 100):
        errors.append("Pass mark must be a whole number from 0 to 100 (0 = practice only).")
    return errors


def _playground_structure(c):
    errors = []
    _check_keys(c, ("language", "starter_code", "stdin", "instructions"), errors)
    for key, label in (("language", "Language"), ("starter_code", "Starter code"),
                       ("stdin", "Sample input"), ("instructions", "Instructions")):
        _check_str(c, key, errors, label)
    return errors


def _parsons_structure(c):
    errors = []
    _check_keys(c, ("language", "instructions", "lines", "distractors", "use_indentation", "explanation"), errors)
    _check_str(c, "language", errors, "Language")
    _check_str(c, "instructions", errors, "Instructions")
    _check_str(c, "explanation", errors, "Explanation")
    if "use_indentation" in c and not isinstance(c["use_indentation"], bool):
        errors.append("use_indentation must be true or false.")
    lines = c.get("lines", [])
    if not isinstance(lines, list):
        errors.append("Lines must be a list.")
    else:
        for i, line in enumerate(lines, 1):
            ok = (isinstance(line, dict) and _is_str(line.get("text"))
                  and _is_int(line.get("indent", 0)) and 0 <= line.get("indent", 0) <= MAX_PARSONS_INDENT)
            if not ok:
                errors.append(f"Line {i} needs text and an indent level from 0 to {MAX_PARSONS_INDENT}.")
    distractors = c.get("distractors", [])
    if not (isinstance(distractors, list) and all(_is_str(d) for d in distractors)):
        errors.append("Distractors must be a list of text lines.")
    return errors


def _coding_structure(c):
    errors = []
    _check_keys(c, ("instructions",), errors)
    _check_str(c, "instructions", errors, "Instructions")
    return errors


# ── Per-type publish (completeness) checks ───────────────────────────

def _video_publish(step):
    c = step.content
    problems = []
    if not c.get("video_id", "").strip():
        problems.append("Add the video id.")
    if not c.get("duration_s"):
        problems.append("Add the video duration (needed to track 80% watched).")
    return problems


def _text_publish(step):
    return [] if step.content.get("markdown", "").strip() else ["Write the notes."]


def _mcq_publish(step):
    questions = list(step.questions.all())
    problems = [] if questions else ["Attach at least one MCQ from the question bank."]
    untagged = [q.position for q in questions if q.outcome_id is None]
    if untagged:
        problems.append(f"Tag every question with a learning outcome (missing on #{', #'.join(map(str, untagged))}).")
    return problems


def _playground_publish(step):
    return [] if step.content.get("starter_code", "").strip() else ["Add starter code."]


def _parsons_publish(step):
    lines = step.content.get("lines", [])
    return [] if len(lines) >= 2 else ["Add at least two code lines to arrange."]


def _coding_publish(step):
    problems = []
    if step.coding_question_id is None:
        problems.append("Attach a coding question.")
    elif step.step_type == "FIX_BUG" and step.coding_question.coding_mode != "fix":
        problems.append('Fix-the-bug steps need a coding question in "Fix the Bug" mode.')
    if not step.outcomes.exists():
        problems.append("Tag the task with a learning outcome.")
    return problems


# ── Registry ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StepType:
    code: str
    label: str
    icon: str                     # Bootstrap icon name
    summary: str
    structure: Callable[[dict], List[str]]
    publish: Callable[[object], List[str]]
    defaults: Dict = field(default_factory=dict)
    uses_mcqs: bool = False
    uses_coding_question: bool = False
    has_hints: bool = False

    def default_content(self):
        import copy
        return copy.deepcopy(self.defaults)


STEP_TYPES = {t.code: t for t in (
    StepType("VIDEO", "Concept video", "play-btn", "A 5–8 minute explainer with chapters and transcript.",
             _video_structure, _video_publish,
             {"provider": "youtube", "video_id": "", "duration_s": 0, "chapters": [], "transcript": "",
              "script": "", "complete_at_percent": 80}),
    StepType("TEXT", "Notes", "journal-text", "Readable notes with code examples and callouts.",
             _text_structure, _text_publish, {"markdown": "", "callouts": []}),
    StepType("PREDICT", "Predict the output", "eye", "Read code, predict what it prints.",
             _intro_structure, _mcq_publish, {"intro": ""}, uses_mcqs=True),
    StepType("PLAYGROUND", "Try it", "terminal", "Free practice in the compiler; not graded.",
             _playground_structure, _playground_publish,
             {"language": "python", "instructions": "", "starter_code": "", "stdin": ""}),
    StepType("PARSONS", "Arrange the code", "list-ol", "Drag lines into the right order and indentation.",
             _parsons_structure, _parsons_publish,
             {"language": "python", "instructions": "", "lines": [], "distractors": [],
              "use_indentation": True, "explanation": ""}),
    StepType("QUIZ", "Quick check", "patch-question", "Short MCQ check on the lesson.",
             _quiz_structure, _mcq_publish, {"intro": "", "pass_percent": 60}, uses_mcqs=True),
    StepType("FIX_BUG", "Fix the bug", "bug", "Repair buggy code until the hidden tests pass.",
             _coding_structure, _coding_publish, {"instructions": ""},
             uses_coding_question=True, has_hints=True),
    StepType("CODING", "Coding task", "code-slash", "Write a solution graded by hidden tests.",
             _coding_structure, _coding_publish, {"instructions": ""},
             uses_coding_question=True, has_hints=True),
)}

STEP_TYPE_CHOICES = [(code, t.label) for code, t in STEP_TYPES.items()]


def structure_errors(step_type, content):
    """Shape problems for `content` of the given type (empty list = valid)."""
    spec = STEP_TYPES.get(step_type)
    if spec is None:
        return [f"Unknown step type {step_type!r}."]
    if not isinstance(content, dict):
        return ["Step content must be an object."]
    return spec.structure(content)
