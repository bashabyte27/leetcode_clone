"""
Course content-sheet importer.

Loads one tab of the course workbook (one tab = one course, one row = one item,
see docs/courses/SHEET_FORMAT.md) into the course models and the shared
question bank:

    COURSE / MODULE / LESSON / OUTCOME   → courses models (matched by `code`)
    STEP                                 → LessonStep (a CODING step with N problems
                                           becomes N consecutive coding steps)
    MCQ                                  → assessment.McqQuestion + options (slug = code)
    PROBLEM / TESTCASE                   → assessment.CodingQuestion + test cases (slug = code)
    HINT                                 → StepHint on the step that holds the problem

Two phases:
1. `parse()` reads and checks every row. It only reads the database (to know
   which languages the judge can run); it never writes.
2. `apply()` writes inside one transaction. A dry run, or any error, rolls it all
   back, so a tab is applied completely or not at all.

Re-importing updates items in place by code. Rows removed from the sheet are
never deleted here (student progress hangs off them); they are reported instead.
"""

import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd
from django.db import transaction
from django.utils.text import slugify

from assessment.models import CodingQuestion, CodingQuestionLanguage, CodingTestCase, McqOption, McqQuestion, ProgrammingLanguage

from .models import Category, Course, LearningOutcome, Lesson, LessonStep, Module, StepHint, StepQuestion
from .steps import CALLOUT_KINDS, MAX_PARSONS_INDENT, STEP_TYPES, VIDEO_PROVIDERS, structure_errors

COLUMNS = [
    "record_type", "code", "parent_code", "order", "module_no", "lesson_no", "title", "step_type",
    "outcome_codes", "difficulty", "body", "option_a", "option_b", "option_c", "option_d", "correct_option",
    "explanation", "starter_code", "solution_code", "input", "expected_output", "is_hidden", "language",
    "points", "meta_json", "status",
]
RECORD_TYPES = ("COURSE", "MODULE", "LESSON", "OUTCOME", "STEP", "MCQ", "PROBLEM", "TESTCASE", "HINT")
LEVELS = {"BEGINNER": "beginner", "INTERMEDIATE": "intermediate", "ADVANCED": "advanced"}
DIFFICULTIES = {"EASY": "easy", "MEDIUM": "medium", "HARD": "hard"}
STATUSES = ("DRAFT", "REVIEW", "READY")
OPTION_LETTERS = "ABCD"
PARSONS_INDENT = 4
LESSONS_PER_MODULE = 6
logger = logging.getLogger(__name__)
PARK = 10000  # temporary positions while re-ordering (2 × PARK + n must fit a smallint)

# Which parent each record type may hang under, and the code prefix it must extend.
_PARENTS = {
    "MODULE": {"COURSE": "-M"},
    "LESSON": {"MODULE": "-L"},
    "OUTCOME": {"COURSE": "-O", "MODULE": "-O", "LESSON": "-O"},
    "STEP": {"LESSON": "-S"},
    "MCQ": {"STEP": None},
    "PROBLEM": {"STEP": None, "MODULE": "-MP"},
    "TESTCASE": {"PROBLEM": "-T"},
    "HINT": {"PROBLEM": "-H"},
}


class SheetError(Exception):
    pass


class _Rollback(Exception):
    pass


# ─────────────────────────── Rows ───────────────────────────


@dataclass
class Row:
    number: int                 # spreadsheet row number, for messages
    cells: Dict[str, str]
    meta: dict = field(default_factory=dict)
    order_int: int = 0

    @property
    def kind(self):
        return self.cells["record_type"].strip().upper()

    @property
    def code(self):
        return self.cells["code"].strip()

    @property
    def parent(self):
        return self.cells["parent_code"].strip()

    @property
    def where(self):
        return f"Row {self.number} ({self.code or self.kind or 'blank code'})"

    def text(self, name):
        return self.cells.get(name, "").strip()

    def raw(self, name):
        """Code-like cells: keep leading spaces, drop only trailing whitespace and Windows newlines."""
        return self.cells.get(name, "").replace("\r\n", "\n").rstrip()

    def codes(self, name="outcome_codes"):
        return [c.strip() for c in re.split(r"[;,\n]", self.cells.get(name, "")) if c.strip()]


@dataclass
class Report:
    dry_run: bool
    tab: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    counts: Dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    statuses: Counter = field(default_factory=Counter)
    course: Optional[Course] = None

    @property
    def ok(self):
        return not self.errors

    @property
    def applied(self):
        return self.ok and not self.dry_run

    def bump(self, kind, created):
        self.counts[kind]["created" if created else "updated"] += 1

    def status_rows(self):
        """[(status, count)] for templates (a Counter's .items can't be reached from a template)."""
        return sorted(self.statuses.items())

    def rows(self):
        order = ["modules", "lessons", "outcomes", "steps", "mcqs", "problems", "test cases", "hints"]
        return [(k.capitalize(), self.counts[k]["created"], self.counts[k]["updated"]) for k in order]


# ─────────────────────────── Reading ───────────────────────────


def list_tabs(source):
    name = getattr(source, "name", str(source)).lower()
    if name.endswith(".csv"):
        return ["(CSV file)"]
    _rewind(source)
    tabs = list(pd.ExcelFile(source).sheet_names)
    _rewind(source)
    return tabs


def _rewind(source):
    if hasattr(source, "seek"):
        source.seek(0)


def read_rows(source, tab=None):
    """Rows of one tab as Row objects (blank rows skipped). Raises SheetError."""
    name = getattr(source, "name", str(source)).lower()
    opts = {"dtype": str, "keep_default_na": False}
    _rewind(source)
    try:
        if name.endswith(".csv"):
            frame = pd.read_csv(source, **opts)
        else:
            tabs = pd.ExcelFile(source).sheet_names
            if tab not in tabs:
                raise SheetError(f"Tab {tab!r} is not in this workbook. Tabs: {', '.join(tabs)}.")
            _rewind(source)
            frame = pd.read_excel(source, sheet_name=tab, **opts)
    except SheetError:
        raise
    except Exception as exc:  # pandas/openpyxl raise many types for unreadable files
        raise SheetError(f"The file could not be read: {exc}") from exc
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise SheetError(f"Missing column(s): {', '.join(missing)}. Row 1 must hold the 26 headers.")
    rows = []
    for index, record in enumerate(frame.to_dict("records"), start=2):
        cells = {c: ("" if record.get(c) is None else str(record.get(c))) for c in COLUMNS}
        if any(v.strip() for v in cells.values()):
            rows.append(Row(index, cells))
    return rows


# ─────────────────────────── Phase 1: parse and check ───────────────────────────


def _int(value, row, label, minimum=0, default=None):
    text = (value or "").strip()
    if not text:
        if default is None:
            raise SheetError(f"{row.where}: {label} is required.")
        return default
    try:
        number = float(text)
    except ValueError:
        raise SheetError(f"{row.where}: {label} must be a whole number (got {text!r}).") from None
    if number != int(number) or number < minimum:
        raise SheetError(f"{row.where}: {label} must be a whole number from {minimum} (got {text!r}).")
    return int(number)


def _bool(value, row, label, default=False):
    text = (value or "").strip().lower()
    if not text:
        return default
    if text in ("true", "yes", "1"):
        return True
    if text in ("false", "no", "0"):
        return False
    raise SheetError(f"{row.where}: {label} must be TRUE or FALSE (got {value!r}).")


class Sheet:
    """A checked, indexed tab. Building one runs every check that needs no database."""

    def __init__(self, rows):
        self.rows = rows
        self.errors = []
        self.warnings = []
        self.by_code = {}
        self.children = defaultdict(list)  # parent code → rows
        self.course = None
        self.runnable = set(ProgrammingLanguage.objects.filter(is_active=True, is_judge0_executable=True)
                            .values_list("slug", flat=True))
        self._check()

    # helpers
    def kids(self, row, kind):
        return sorted((r for r in self.children[row.code] if r.kind == kind), key=lambda r: r.order_int)

    def _error(self, message):
        self.errors.append(message)

    def _check(self):
        for row in self.rows:
            try:
                self._check_row(row)
            except SheetError as exc:
                self._error(str(exc))
        if self.errors:
            return
        courses = [r for r in self.rows if r.kind == "COURSE"]
        if len(courses) != 1:
            self._error(f"The tab needs exactly one COURSE row (found {len(courses)}).")
            return
        self.course = courses[0]
        for row in self.rows:
            try:
                self._check_links(row)
            except SheetError as exc:
                self._error(str(exc))
        if not self.errors:
            for row in self.rows:
                try:
                    self._check_content(row)
                except SheetError as exc:
                    self._error(str(exc))

    def _check_row(self, row):
        if row.kind not in RECORD_TYPES:
            raise SheetError(f"Row {row.number}: record_type must be one of {', '.join(RECORD_TYPES)} "
                             f"(got {row.cells['record_type']!r}).")
        if not row.code:
            raise SheetError(f"Row {row.number}: code is required.")
        if row.code in self.by_code:
            raise SheetError(f"{row.where}: code is already used on row {self.by_code[row.code].number}.")
        self.by_code[row.code] = row
        status = row.text("status").upper()
        if status and status not in STATUSES:
            raise SheetError(f"{row.where}: status must be DRAFT, REVIEW or READY (got {status!r}).")
        meta = row.text("meta_json")
        try:
            row.meta = json.loads(meta) if meta else {}
        except json.JSONDecodeError as exc:
            raise SheetError(f"{row.where}: meta_json is not valid JSON ({exc.msg} at character {exc.pos}).") from None
        if not isinstance(row.meta, dict):
            raise SheetError(f"{row.where}: meta_json must be an object like {{\"key\": \"value\"}}.")
        minimum = 0 if row.kind == "MODULE" else 1
        row.order_int = _int(row.text("order"), row, "order", minimum=minimum, default=None if row.kind != "COURSE" else 1)
        if row.kind == "COURSE":
            if row.parent:
                raise SheetError(f"{row.where}: a COURSE row has no parent_code.")
        else:
            self.children[row.parent].append(row)

    def _check_links(self, row):
        if row.kind == "COURSE":
            return
        parent = self.by_code.get(row.parent)
        if parent is None:
            raise SheetError(f"{row.where}: parent_code {row.parent!r} is not defined in this tab.")
        allowed = _PARENTS[row.kind]
        if parent.kind not in allowed:
            raise SheetError(f"{row.where}: a {row.kind} can't sit under a {parent.kind} ({parent.code}).")
        prefix = allowed[parent.kind]
        if row.kind == "MCQ":
            if parent.text("step_type").upper() not in ("PREDICT", "QUIZ"):
                raise SheetError(f"{row.where}: MCQs belong to a PREDICT or QUIZ step, not {parent.code}.")
            lesson = parent.parent
            if not re.fullmatch(re.escape(lesson) + r"-[PQ]\d+", row.code):
                raise SheetError(f"{row.where}: an MCQ code looks like {lesson}-Q01 (or -P01 for predict).")
        elif row.kind == "PROBLEM" and parent.kind == "STEP":
            step_type = parent.text("step_type").upper()
            if step_type not in ("FIX_BUG", "CODING"):
                raise SheetError(f"{row.where}: problems belong to a FIX_BUG or CODING step, not {parent.code}.")
            tag = "FB" if step_type == "FIX_BUG" else "C"
            if not re.fullmatch(re.escape(parent.parent) + rf"-{tag}\d+", row.code):
                raise SheetError(f"{row.where}: this problem's code should look like {parent.parent}-{tag}01.")
        elif not re.fullmatch(re.escape(row.parent + prefix) + r"\d+", row.code):
            raise SheetError(f"{row.where}: code should look like {row.parent}{prefix}1 "
                             f"(the parent's code, then {prefix} and a number).")
        siblings = [r for r in self.children[row.parent] if r.kind == row.kind and r is not row
                    and r.order_int == row.order_int]
        if siblings and siblings[0].number < row.number:
            raise SheetError(f"{row.where}: order {row.order_int} is also used by {siblings[0].code} under {row.parent}.")
        for code in row.codes():
            target = self.by_code.get(code)
            if target is None or target.kind != "OUTCOME":
                raise SheetError(f"{row.where}: outcome {code} is not defined in this tab.")

    def _check_content(self, row):
        check = getattr(self, f"_check_{row.kind.lower()}", None)
        if check:
            check(row)

    def _check_course(self, row):
        if row.text("difficulty").upper() not in LEVELS:
            raise SheetError(f"{row.where}: difficulty must be BEGINNER, INTERMEDIATE or ADVANCED.")
        if not str(row.meta.get("category", "")).strip():
            raise SheetError(f'{row.where}: meta_json needs a "category" (catalog category name).')
        if row.meta.get("access", "free") not in ("free", "premium"):
            raise SheetError(f'{row.where}: "access" must be "free" or "premium".')
        _version(row)
        declared = row.meta.get("course_outcomes")
        actual = {r.code for r in self.kids(row, "OUTCOME")}
        if declared is not None and set(declared) != actual:
            raise SheetError(f"{row.where}: course_outcomes lists {', '.join(declared)} but the course's OUTCOME "
                             f"rows are {', '.join(sorted(actual)) or 'none'}.")
        planned = row.meta.get("modules")
        built = [m for m in self.kids(row, "MODULE") if not m.meta.get("is_introduction")]
        if isinstance(planned, int) and planned != len(built):
            self.warnings.append(f"The course plans {planned} modules; the tab has {len(built)} so far "
                                 f"(plus any introduction).")

    def _check_lesson(self, row):
        self._check_declared_outcomes(row, "lesson")

    def _check_declared_outcomes(self, row, label):
        declared = row.codes()
        actual = {r.code for r in self.kids(row, "OUTCOME")}
        if declared and set(declared) != actual:
            raise SheetError(f"{row.where}: outcome_codes lists {', '.join(declared)} but the {label}'s OUTCOME "
                             f"rows are {', '.join(sorted(actual)) or 'none'}.")

    def _check_module(self, row):
        intro = bool(row.meta.get("is_introduction"))
        if row.order_int == 0 and not intro:
            raise SheetError(f'{row.where}: order 0 is only for a module with "is_introduction": true.')
        lessons = self.kids(row, "LESSON")
        if not intro and len(lessons) != LESSONS_PER_MODULE:
            self.warnings.append(f"{row.code} has {len(lessons)} lessons; modules are designed for {LESSONS_PER_MODULE}.")
        self._check_declared_outcomes(row, "module")

    def _check_outcome(self, row):
        if not row.text("body"):
            raise SheetError(f"{row.where}: body (the outcome statement) is required.")
        if len(row.text("body")) > 300:
            raise SheetError(f"{row.where}: the outcome statement is {len(row.text('body'))} characters; keep it to 300.")
        if len(row.text("title")) > 120:
            raise SheetError(f"{row.where}: the outcome title is over 120 characters.")

    def _check_step(self, row):
        step_type = row.text("step_type").upper()
        if step_type not in STEP_TYPES:
            raise SheetError(f"{row.where}: step_type must be one of {', '.join(STEP_TYPES)} (got {step_type!r}).")
        if step_type in ("PREDICT", "QUIZ"):
            mcqs = self.kids(row, "MCQ")
            if not mcqs:
                self.warnings.append(f"{row.code} has no MCQ rows yet.")
            listed = row.meta.get("mcq_codes")
            if listed is not None and list(listed) != [m.code for m in mcqs]:
                raise SheetError(f"{row.where}: mcq_codes {listed} doesn't match the MCQ rows under this step "
                                 f"({[m.code for m in mcqs]}).")
        if step_type == "FIX_BUG":
            problems = self.kids(row, "PROBLEM")
            if len(problems) != 1:
                raise SheetError(f"{row.where}: a FIX_BUG step needs exactly one PROBLEM row (found {len(problems)}).")
            if row.meta.get("problem_code") not in (None, problems[0].code):
                raise SheetError(f"{row.where}: problem_code {row.meta['problem_code']} doesn't match {problems[0].code}.")
        if step_type == "CODING":
            problems = self.kids(row, "PROBLEM")
            if not problems:
                raise SheetError(f"{row.where}: a CODING step needs at least one PROBLEM row.")
            listed = row.meta.get("problem_codes")
            if listed is not None and list(listed) != [p.code for p in problems]:
                raise SheetError(f"{row.where}: problem_codes {listed} doesn't match the PROBLEM rows "
                                 f"({[p.code for p in problems]}).")
        if step_type == "VIDEO":
            if row.meta.get("provider", "youtube") not in VIDEO_PROVIDERS:
                raise SheetError(f"{row.where}: provider must be one of {', '.join(VIDEO_PROVIDERS)}.")
            if not str(row.meta.get("video_id", "")).strip():
                self.warnings.append(f"{row.code}: no video_id yet (needed before publishing).")
        if step_type == "PARSONS":
            _parsons_lines(row)  # raises on bad indentation or a lines/solution mismatch
        if step_type == "QUIZ":
            _int(str(row.meta.get("pass_percent", 60)), row, "pass_percent", minimum=0)

    def _check_mcq(self, row):
        options = [row.text(f"option_{c.lower()}") for c in OPTION_LETTERS]
        filled = len([o for o in options if o])
        if filled < 2:
            raise SheetError(f"{row.where}: an MCQ needs at least 2 options.")
        if any(not o for o in options[:filled]):
            raise SheetError(f"{row.where}: fill the options from option_a onwards without gaps.")
        correct = [c.strip().upper() for c in row.text("correct_option").split(";") if c.strip()]
        if not correct:
            raise SheetError(f"{row.where}: correct_option is required (e.g. B, or A;C).")
        for letter in correct:
            if letter not in OPTION_LETTERS[:filled]:
                raise SheetError(f"{row.where}: correct_option {letter} points to an empty or unknown option.")
        if row.text("difficulty").upper() not in DIFFICULTIES:
            raise SheetError(f"{row.where}: difficulty must be EASY, MEDIUM or HARD.")
        if not row.text("body"):
            raise SheetError(f"{row.where}: body (the question) is required.")
        outcomes = row.codes()
        if len(outcomes) > 1:
            raise SheetError(f"{row.where}: tag an MCQ with exactly one outcome (found {len(outcomes)}).")

    def _check_problem(self, row):
        kind = row.meta.get("problem_kind")
        if kind not in ("fix_bug", "coding", "mini_project"):
            raise SheetError(f'{row.where}: meta_json needs "problem_kind": "fix_bug", "coding" or "mini_project".')
        parent = self.by_code[row.parent]
        if (kind == "mini_project") != (parent.kind == "MODULE"):
            raise SheetError(f"{row.where}: mini-projects sit under a module; other problems sit under a step.")
        if kind == "mini_project":
            return
        expected = "fix_bug" if parent.text("step_type").upper() == "FIX_BUG" else "coding"
        if kind != expected:
            raise SheetError(f'{row.where}: a problem under a {parent.text("step_type").upper()} step needs '
                             f'"problem_kind": "{expected}".')
        if row.text("difficulty").upper() not in DIFFICULTIES:
            raise SheetError(f"{row.where}: difficulty must be EASY, MEDIUM or HARD.")
        if not row.text("body"):
            raise SheetError(f"{row.where}: body (the task statement) is required.")
        if kind == "fix_bug" and not row.raw("starter_code"):
            raise SheetError(f"{row.where}: a fix_bug problem needs the buggy program in starter_code.")
        language = row.text("language").lower() or "python"
        if language not in self.runnable:
            raise SheetError(f"{row.where}: language {language!r} can't be run by the judge.")
        ms = _int(str(row.meta.get("time_limit_ms", 2000)), row, "time_limit_ms", minimum=1000)
        if ms % 1000:
            raise SheetError(f"{row.where}: time_limit_ms must be whole seconds (1000, 2000, ...).")
        _int(str(row.meta.get("memory_limit_mb", 256)), row, "memory_limit_mb", minimum=16)
        tests = self.kids(row, "TESTCASE")
        if not tests:
            raise SheetError(f"{row.where}: add at least one TESTCASE row.")
        hidden = [t for t in tests if _bool(t.text("is_hidden"), t, "is_hidden")]
        reads_input = not row.meta.get("no_input") and any(t.raw("input") for t in tests)
        if reads_input and not hidden:
            self.warnings.append(f"{row.code} reads input but has no hidden test case.")

    def _check_testcase(self, row):
        _bool(row.text("is_hidden"), row, "is_hidden")
        _int(row.text("points"), row, "points (test weight)", minimum=1, default=1)
        if not row.raw("expected_output"):
            raise SheetError(f"{row.where}: expected_output is required.")

    def _check_hint(self, row):
        if row.order_int not in (1, 2, 3):
            raise SheetError(f"{row.where}: hint order is the level: 1, 2 or 3.")
        if not row.text("body"):
            raise SheetError(f"{row.where}: body (the hint text) is required.")


def _version(row):
    raw = str(row.meta.get("version", 1)).strip().lower().lstrip("v")
    if not raw.isdigit() or int(raw) < 1:
        raise SheetError(f'{row.where}: "version" must look like "v2" or 2.')
    return int(raw)


def _parsons_lines(row):
    use_indent = row.meta.get("use_indentation", True)
    if not isinstance(use_indent, bool):
        raise SheetError(f"{row.where}: use_indentation must be true or false.")
    lines = []
    for i, raw in enumerate(row.raw("solution_code").replace("\t", " " * PARSONS_INDENT).split("\n"), start=1):
        if not raw.strip():
            continue
        spaces = len(raw) - len(raw.lstrip(" "))
        if use_indent and spaces % PARSONS_INDENT:
            raise SheetError(f"{row.where}: solution_code line {i} is indented by {spaces} spaces; "
                             f"use multiples of {PARSONS_INDENT}.")
        indent = spaces // PARSONS_INDENT if use_indent else 0
        if indent > MAX_PARSONS_INDENT:
            raise SheetError(f"{row.where}: solution_code line {i} is nested too deeply.")
        lines.append({"text": raw.strip(), "indent": indent})
    if len(lines) < 2:
        raise SheetError(f"{row.where}: a Parsons step needs at least two lines in solution_code.")
    listed = row.meta.get("lines")
    if listed is not None and [str(x).strip() for x in listed] != [ln["text"] for ln in lines]:
        raise SheetError(f"{row.where}: the \"lines\" list in meta_json doesn't match solution_code.")
    distractors = row.meta.get("distractors", [])
    if not (isinstance(distractors, list) and all(isinstance(d, str) for d in distractors)):
        raise SheetError(f"{row.where}: distractors must be a list of text lines.")
    return lines


def parse(source, tab=None):
    """Read and check a tab. Returns (Sheet or None, errors)."""
    try:
        rows = read_rows(source, tab)
    except SheetError as exc:
        return None, [str(exc)]
    if not rows:
        return None, ["The tab has no rows below the headers."]
    sheet = Sheet(rows)
    return sheet, sheet.errors


# ─────────────────────────── Phase 2: apply ───────────────────────────


def import_sheet(source, tab=None, owner=None, dry_run=True):
    """Check and (unless `dry_run`) apply one tab. Returns a Report; never raises for content problems."""
    report = Report(dry_run=dry_run, tab=tab or "")
    sheet, errors = parse(source, tab)
    if sheet is None or errors:
        report.errors.extend(errors)
        return report
    report.warnings.extend(sheet.warnings)
    report.statuses.update(r.text("status").upper() or "—" for r in sheet.rows)
    if owner is None:
        report.errors.append("An owner (staff user) is needed for the question-bank items.")
        return report
    try:
        with transaction.atomic():
            _Writer(sheet, owner, report).run()
            if dry_run or report.errors:
                raise _Rollback
            transaction.on_commit(lambda: _bust_after_import(report))
    except _Rollback:
        pass
    except SheetError as exc:
        report.errors.append(str(exc))
    except Exception as exc:  # a database rule the checks missed: report it, never half-apply
        logger.exception("Course sheet import failed")
        report.errors.append(f"The import stopped unexpectedly and nothing was saved: {exc}")
    if dry_run:
        report.course = None
    return report


def _bust_after_import(report):
    from . import catalog
    catalog.bust(report.course.pk if report.course else None)


class _Writer:
    def __init__(self, sheet, owner, report):
        self.sheet = sheet
        self.owner = owner
        self.report = report
        self.outcomes = {}
        self.languages = {l.slug: l for l in ProgrammingLanguage.objects.filter(is_active=True)}

    def run(self):
        course = self.course()
        self.report.course = course
        modules = self.place(course.modules.all(), Module,
                             [(r, self.module_fields(r, course)) for r in self.sheet.kids(self.sheet.course, "MODULE")],
                             "modules", parent={"course": course})
        lesson_rows = {}
        for mrow, module in modules:
            pairs = [(r, self.lesson_fields(r)) for r in self.sheet.kids(mrow, "LESSON")]
            for lrow, lesson in self.place(module.lessons.all(), Lesson, pairs, "lessons", parent={"module": module}):
                lesson_rows[lrow.code] = (lrow, lesson)
        self.outcome_rows(course, dict(modules_by_code(modules)), lesson_rows)
        for lrow, lesson in lesson_rows.values():
            self.lesson_steps(lrow, lesson)
        self.report_missing(course, modules, lesson_rows)

    # ── course ──
    def course(self):
        row = self.sheet.course
        meta = row.meta
        category, _ = Category.objects.get_or_create(title=str(meta["category"]).strip()[:120])
        course = Course.objects.filter(code=row.code).first()
        if course is None:
            course = Course(code=row.code)
        course.category = category
        course.title = row.text("title")[:200]
        course.subtitle = str(meta.get("subtitle", course.subtitle or ""))[:255]
        course.description = row.text("body")
        course.level = LEVELS[row.text("difficulty").upper()]
        course.version = _version(row)
        course.est_weeks = int(meta.get("est_weeks", course.est_weeks or 4))
        course.access = meta.get("access", "free")
        course.capstone_brief = str(meta.get("capstone_brief", course.capstone_brief or ""))
        if not course.created_by_id:
            course.created_by = self.owner
        course.save()
        prereqs = list(Course.objects.filter(code__in=meta.get("prerequisites", [])))
        missing = set(meta.get("prerequisites", [])) - {c.code for c in prereqs}
        if missing:
            self.report.warnings.append(f"Prerequisite course(s) not imported yet: {', '.join(sorted(missing))}.")
        course.prerequisites.set(prereqs)
        return course

    # ── ordered children (modules, lessons, steps) ──
    def place(self, siblings, model, pairs, kind, parent):
        """
        Upsert `pairs` [(row, field dict)] by code under one parent and give them the sheet's order.
        Modules keep their sheet number (0 = introduction); lessons and steps are numbered 1..n.
        Existing siblings that are not in the sheet move after the imported ones, untouched.
        """
        (parent_field, parent_obj), = parent.items()
        siblings = list(siblings)
        for obj in siblings:  # park everything so new positions never collide
            obj.position += PARK
        model.objects.bulk_update(siblings, ["position"])
        existing = {obj.code: obj for obj in siblings if obj.code}
        placed = []
        for n, (row, fields) in enumerate(pairs, start=1):
            obj = existing.get(row.code) or model.objects.filter(code=row.code).first()
            created = obj is None
            if obj is not None and getattr(obj, f"{parent_field}_id") != parent_obj.pk:
                raise SheetError(f"{row.where}: code {row.code} already belongs to another "
                                 f"{model._meta.verbose_name}; codes must be unique.")
            if obj is not None and model is LessonStep and obj.step_type != fields["step_type"]:
                raise SheetError(f"{row.where}: {row.code} is a {obj.get_step_type_display()} step in the app; "
                                 f"delete it in the builder before importing it as {fields['step_type']}.")
            obj = obj or model(code=row.code, **parent)
            for name, value in fields.items():
                setattr(obj, name, value)
            obj.position = PARK * 2 + n
            obj.save()
            placed.append((row, obj))
            self.report.bump(kind, created)
        for n, (row, obj) in enumerate(placed, start=1):
            obj.position = row.order_int if model is Module else n
        seen = {obj.pk for _, obj in placed}
        leftovers = sorted((o for o in siblings if o.pk not in seen), key=lambda o: o.position)
        top = max([obj.position for _, obj in placed] + [0])
        for n, obj in enumerate(leftovers, start=1):
            obj.position = top + n
        model.objects.bulk_update([obj for _, obj in placed] + leftovers, ["position"])
        return placed

    def module_fields(self, row, course):
        meta = row.meta
        projects = self.sheet.kids(row, "PROBLEM")
        mini = "\n\n".join(f"### {p.text('title')}\n\n{p.text('body')}" for p in projects)
        video = meta.get("intro_video") or {}
        return {
            "title": row.text("title")[:200], "summary": row.text("body"),
            "is_introduction": bool(meta.get("is_introduction")),
            "is_free_preview": bool(meta.get("free_preview")),
            "intro_video": video if isinstance(video, dict) else {},
            "mini_project_brief": mini,
        }

    def lesson_fields(self, row):
        meta = row.meta
        coding_steps = [s for s in self.sheet.kids(row, "STEP") if s.text("step_type").upper() == "CODING"]
        min_pass = meta.get("min_coding_to_pass")
        if min_pass is None:
            listed = [s.meta.get("min_to_pass") for s in coding_steps if s.meta.get("min_to_pass") is not None]
            min_pass = listed[0] if listed else None
        return {
            "title": row.text("title")[:200], "summary": row.text("body"),
            "est_minutes": int(meta.get("est_minutes", 45)),
            "is_free_preview": bool(meta.get("free_preview")),
            "min_coding_passes": int(min_pass) if min_pass is not None else None,
        }

    # ── outcomes ──
    def outcome_rows(self, course, modules, lessons):
        rows = sorted((r for r in self.sheet.rows if r.kind == "OUTCOME"), key=lambda r: (r.parent, r.order_int))
        for row in rows:
            parent = self.sheet.by_code[row.parent]
            module = lesson = None
            if parent.kind == "MODULE":
                module = modules[parent.code]
            elif parent.kind == "LESSON":
                lesson = lessons[parent.code][1]
                module = lesson.module
            outcome = LearningOutcome.objects.filter(code=row.code).first()
            if outcome is not None and outcome.course_id != course.pk:
                raise SheetError(f"{row.where}: outcome code {row.code} already belongs to another course.")
            created = outcome is None
            outcome = outcome or LearningOutcome(code=row.code)
            outcome.course, outcome.module, outcome.lesson = course, module, lesson
            outcome.title, outcome.text, outcome.position = row.text("title"), row.text("body"), row.order_int
            outcome.save()
            self.outcomes[row.code] = outcome
            self.report.bump("outcomes", created)
        for row in rows:
            self.outcomes[row.code].supports.set([self.outcomes[c] for c in row.codes()])

    def tags(self, codes):
        return [self.outcomes[c] for c in codes]

    # ── steps ──
    def lesson_steps(self, lrow, lesson):
        specs = []
        for srow in self.sheet.kids(lrow, "STEP"):
            specs.extend(self.step_specs(srow))
        pairs = [(spec["row"], spec["fields"]) for spec in specs]
        placed = self.place(lesson.steps.all(), LessonStep, pairs, "steps", parent={"lesson": lesson})
        for spec, (_, step) in zip(specs, placed):
            step.outcomes.set(spec["outcomes"])
            self.sync_questions(step, spec.get("mcqs", []))
            self.sync_hints(step, spec.get("hints", []))

    def step_specs(self, srow):
        """One sheet STEP row → one or more LessonStep specs."""
        step_type = srow.text("step_type").upper()
        meta = srow.meta
        base = {"step_type": step_type, "title": srow.text("title")[:200], "required": True, "coding_question": None}
        outcomes = self.tags(srow.codes())

        if step_type in ("FIX_BUG", "CODING"):
            specs = []
            problems = self.sheet.kids(srow, "PROBLEM")
            for n, prow in enumerate(problems, start=1):
                question = self.coding_question(prow, srow)
                split = step_type == "CODING"
                code = f"{srow.code}.{prow.code[len(srow.parent) + 1:]}" if split else srow.code
                title = prow.text("title") if split else srow.text("title")
                fields = dict(base, title=title[:200], coding_question=question,
                              content={"instructions": srow.text("body")})
                specs.append({"row": _Coded(srow, code), "fields": self.with_content(srow, fields),
                              "outcomes": self.tags(prow.codes()) or outcomes,
                              "hints": [(h.order_int, h.text("body")) for h in self.sheet.kids(prow, "HINT")]})
            return specs

        content = self.content(srow, step_type, meta)
        spec = {"row": srow, "fields": self.with_content(srow, dict(base, content=content)), "outcomes": outcomes}
        if step_type in ("PREDICT", "QUIZ"):
            spec["mcqs"] = [(self.mcq(m, srow), self.tags(m.codes())[:1] or outcomes[:1])
                            for m in self.sheet.kids(srow, "MCQ")]
        return [spec]

    def with_content(self, row, fields):
        errors = structure_errors(fields["step_type"], fields["content"])
        if errors:
            raise SheetError(f"{row.where}: {' '.join(errors)}")
        return fields

    def content(self, row, step_type, meta):
        if step_type == "TEXT":
            callouts = meta.get("callouts", [])
            if not (isinstance(callouts, list) and all(isinstance(c, dict) and c.get("kind") in CALLOUT_KINDS
                                                       for c in callouts)):
                raise SheetError(f"{row.where}: callouts must be a list of {{\"kind\": \"tip|mistake|note\", \"markdown\": \"...\"}}.")
            return {"markdown": row.text("body"), "callouts": callouts}
        if step_type == "VIDEO":
            return {"provider": meta.get("provider", "youtube"), "video_id": str(meta.get("video_id", "")).strip(),
                    "duration_s": _int(str(meta.get("duration_sec", 0)), row, "duration_sec", minimum=0),
                    "chapters": _chapters(row, meta.get("chapters", [])),
                    "transcript": str(meta.get("transcript", "")), "script": row.text("body"),
                    "complete_at_percent": _int(str(meta.get("complete_at_percent", 80)), row,
                                                "complete_at_percent", minimum=1)}
        if step_type == "PREDICT":
            return {"intro": row.text("body")}
        if step_type == "QUIZ":
            return {"intro": row.text("body"), "pass_percent": int(meta.get("pass_percent", 60))}
        if step_type == "PLAYGROUND":
            return {"language": row.text("language").lower() or "python", "instructions": row.text("body"),
                    "starter_code": row.raw("starter_code"), "stdin": row.raw("input")}
        if step_type == "PARSONS":
            return {"language": row.text("language").lower() or "python", "instructions": row.text("body"),
                    "lines": _parsons_lines(row), "distractors": meta.get("distractors", []),
                    "use_indentation": meta.get("use_indentation", True), "explanation": row.text("explanation")}
        raise SheetError(f"{row.where}: unsupported step type {step_type}.")

    def sync_questions(self, step, mcqs):
        step.questions.all().delete()
        StepQuestion.objects.bulk_create(
            StepQuestion(step=step, mcq=mcq, outcome=(tag[0] if tag else None), position=n)
            for n, (mcq, tag) in enumerate(mcqs, start=1))

    def sync_hints(self, step, hints):
        levels = {level for level, _ in hints}
        StepHint.objects.filter(step=step).exclude(level__in=levels).delete()
        for level, text in hints:
            _, created = StepHint.objects.update_or_create(step=step, level=level, defaults={"text": text})
            self.report.bump("hints", created)

    # ── question bank ──
    def mcq(self, row, srow):
        meta = row.meta
        slug = row.code.lower()
        question = McqQuestion.objects.filter(slug=slug).first()
        created = question is None
        question = question or McqQuestion(slug=slug, owner=self.owner)
        tags = meta.get("tags") or []
        lesson_title = self.sheet.by_code[srow.parent].text("title")
        correct = {c.strip().upper() for c in row.text("correct_option").split(";") if c.strip()}
        question.title = row.text("title")[:255] or row.code
        question.question_type = McqQuestion.QuestionType.PROGRAMMING
        question.category = McqQuestion.Category.PROGRAMMING
        question.topic = (str(tags[0]) if tags else lesson_title)[:100]
        question.sub_topic = (str(tags[1]) if len(tags) > 1 else "")[:100]
        question.difficulty = DIFFICULTIES[row.text("difficulty").upper()]
        question.statement = row.text("body")
        question.programming_language = self.languages.get(row.text("language").lower())
        question.explanation = row.text("explanation")
        question.allow_multiple = len(correct) > 1
        question.is_active = True
        question.save()
        per_option = meta.get("option_explanations") or {}
        options = [(c, row.text(f"option_{c.lower()}")) for c in OPTION_LETTERS if row.text(f"option_{c.lower()}")]
        existing = {o.position: o for o in question.options.all()}
        for position, (letter, text) in enumerate(options, start=1):
            option = existing.pop(position, None) or McqOption(question=question, position=position)
            option.text, option.is_correct = text, letter in correct
            option.explanation = str(per_option.get(letter, ""))
            option.save()
        McqOption.objects.filter(pk__in=[o.pk for o in existing.values()]).delete()
        self.report.bump("mcqs", created)
        return question

    def coding_question(self, row, srow):
        meta = row.meta
        slug = row.code.lower()
        question = CodingQuestion.objects.filter(slug=slug).first()
        created = question is None
        question = question or CodingQuestion(slug=slug, owner=self.owner)
        fix = meta["problem_kind"] == "fix_bug"
        question.title = row.text("title")[:255]
        question.coding_mode = CodingQuestion.CodingMode.FIX if fix else CodingQuestion.CodingMode.SCRATCH
        question.topic = self.sheet.by_code[srow.parent].text("title")[:255]
        question.difficulty = DIFFICULTIES[row.text("difficulty").upper()]
        question.statement = row.text("body")
        question.input_format = str(meta.get("input_format", ""))
        question.output_format = str(meta.get("output_format", ""))
        question.constraints_text = str(meta.get("constraints", ""))
        question.explanation = row.text("explanation")
        question.time_limit_seconds = math.ceil(int(meta.get("time_limit_ms", 2000)) / 1000)
        question.memory_limit_kb = int(meta.get("memory_limit_mb", 256)) * 1024
        question.is_active = True
        question.save()
        language = self.languages[row.text("language").lower() or "python"]
        code = row.raw("starter_code")
        CodingQuestionLanguage.objects.update_or_create(
            question=question, language=language,
            defaults={"starter_code": "" if fix else code, "buggy_code": code if fix else ""})
        tests = self.sheet.kids(row, "TESTCASE")
        existing = {t.position: t for t in question.test_cases.all()}
        for trow in tests:
            test = existing.pop(trow.order_int, None)
            created_test = test is None
            test = test or CodingTestCase(question=question, position=trow.order_int)
            test.input_data = trow.raw("input")
            test.expected_output = trow.raw("expected_output")
            test.is_sample = not _bool(trow.text("is_hidden"), trow, "is_hidden")
            test.weight = _int(trow.text("points"), trow, "points", minimum=1, default=1)
            test.explanation = trow.text("title")
            test.save()
            self.report.bump("test cases", created_test)
        CodingTestCase.objects.filter(pk__in=[t.pk for t in existing.values()]).delete()
        self.report.bump("problems", created)
        return question

    # ── reporting ──
    def report_missing(self, course, modules, lessons):
        codes = set(self.sheet.by_code)
        step_codes = {s.code for s in LessonStep.objects.filter(lesson__module__course=course).exclude(code=None)}
        sheet_steps = set()
        for lrow, _ in lessons.values():
            for srow in self.sheet.kids(lrow, "STEP"):
                if srow.text("step_type").upper() == "CODING":
                    sheet_steps |= {f"{srow.code}.{p.code[len(srow.parent) + 1:]}" for p in self.sheet.kids(srow, "PROBLEM")}
                else:
                    sheet_steps.add(srow.code)
        stale = sorted(
            [m.code for m in course.modules.exclude(code=None) if m.code not in codes]
            + [l.code for l in Lesson.objects.filter(module__course=course).exclude(code=None) if l.code not in codes]
            + [o.code for o in course.outcomes.all() if o.code not in codes]
            + sorted(step_codes - sheet_steps))
        if stale:
            self.report.warnings.append(f"In the app but no longer in the sheet (left untouched; delete in the "
                                        f"builder if intended): {', '.join(stale)}.")


@dataclass
class _Coded:
    """A sheet row standing in for a derived step code (split CODING steps)."""
    row: Row
    code: str

    @property
    def where(self):
        return self.row.where

    @property
    def order_int(self):
        return self.row.order_int


def modules_by_code(modules):
    return [(row.code, module) for row, module in modules]


def _chapters(row, raw):
    chapters = []
    if not isinstance(raw, list):
        raise SheetError(f"{row.where}: chapters must be a list like [[0, \"Hook\"], [45, \"Next\"]].")
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            t, title = item
        elif isinstance(item, dict):
            t, title = item.get("t"), item.get("title")
        else:
            raise SheetError(f"{row.where}: each chapter is [seconds, \"title\"].")
        if not (isinstance(t, int) and t >= 0 and isinstance(title, str) and title.strip()):
            raise SheetError(f"{row.where}: each chapter is [seconds, \"title\"] (got {item!r}).")
        chapters.append({"t": t, "title": title.strip()})
    return sorted(chapters, key=lambda c: c["t"])
