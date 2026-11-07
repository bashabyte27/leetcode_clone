import io
import json
import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from assessment.models import CodingQuestion, McqQuestion, ProgrammingLanguage
from courses import services
from courses.models import Course, LearningOutcome, Lesson, LessonStep, Module, StepHint
from courses.sheet_importer import COLUMNS, import_sheet

from .factories import make_user


def R(record_type, code, parent="", order="", **cells):
    meta = cells.pop("meta", None)
    row = {"record_type": record_type, "code": code, "parent_code": parent, "order": str(order), **cells}
    if meta is not None:
        row["meta_json"] = json.dumps(meta)
    return row


def course_rows():
    """A small course shaped like the real Core Python tab."""
    o = "PY-M1-L1-O1"
    return [
        R("COURSE", "PY", "", 1, title="Core Python", difficulty="BEGINNER", body="The gateway course.",
          language="python", meta={"category": "Python", "version": "v2", "est_weeks": 12, "modules": 12,
                                   "course_outcomes": ["PY-O1"]}),
        R("OUTCOME", "PY-O1", "PY", 1, title="Plan before coding", body="Plan a solution before coding."),
        # Introduction module
        R("MODULE", "PY-M0", "PY", 0, title="Introduction: Why Python", body="Meet the language.",
          outcome_codes="PY-M0-O1", meta={"is_introduction": True, "free_preview": True}),
        R("OUTCOME", "PY-M0-O1", "PY-M0", 1, title="Tell the story", body="Explain why Python exists."),
        R("LESSON", "PY-M0-L1", "PY-M0", 1, title="The story of Python", body="History.",
          meta={"est_minutes": 30, "free_preview": True}),
        R("OUTCOME", "PY-M0-L1-O1", "PY-M0-L1", 1, title="Why Python", body="Explain why Python was created.",
          outcome_codes="PY-M0-O1"),
        R("STEP", "PY-M0-L1-S01", "PY-M0-L1", 1, title="Why this matters", step_type="TEXT", body="Christmas 1989."),
        R("STEP", "PY-M0-L1-S02", "PY-M0-L1", 2, title="Quick check", step_type="QUIZ", body="Practice.",
          outcome_codes="PY-M0-L1-O1", meta={"mcq_codes": ["PY-M0-L1-Q01"], "pass_percent": 0}),
        R("MCQ", "PY-M0-L1-Q01", "PY-M0-L1-S02", 1, title="Name", outcome_codes="PY-M0-L1-O1", difficulty="EASY",
          body="Python is named after:", option_a="A snake", option_b="Monty Python", correct_option="B",
          explanation="The comedy show."),
        # Module 1, lesson 1 with every step type
        R("MODULE", "PY-M1", "PY", 1, title="Getting Started", body="Run programs.", outcome_codes="PY-M1-O1"),
        R("OUTCOME", "PY-M1-O1", "PY-M1", 1, title="Run a file", body="Run a Python file.", outcome_codes="PY-O1"),
        R("LESSON", "PY-M1-L1", "PY-M1", 1, title="What is programming?", body="Basics.", outcome_codes=o,
          meta={"est_minutes": 60}),
        R("OUTCOME", o, "PY-M1-L1", 1, title="Programs", body="Explain what a program is.", outcome_codes="PY-M1-O1"),
        R("STEP", "PY-M1-L1-S01", "PY-M1-L1", 1, title="Hook", step_type="TEXT", body="You pay on UPI.",
          outcome_codes=o),
        R("STEP", "PY-M1-L1-S02", "PY-M1-L1", 2, title="Concept video", step_type="VIDEO", body="SCRIPT 0:00 Hook",
          outcome_codes=o, meta={"provider": "youtube", "video_id": "abc123", "duration_sec": 420,
                                 "chapters": [[40, "Computers"], [0, "Hook"]], "complete_at_percent": 80}),
        R("STEP", "PY-M1-L1-S03", "PY-M1-L1", 3, title="Notes", step_type="TEXT", body="## Notes\n\n```python\nprint(1)\n```",
          outcome_codes=o),
        R("STEP", "PY-M1-L1-S04", "PY-M1-L1", 4, title="Predict", step_type="PREDICT", body="Read first.",
          outcome_codes=o, meta={"mcq_codes": ["PY-M1-L1-P01"]}),
        R("MCQ", "PY-M1-L1-P01", "PY-M1-L1-S04", 1, title="Copy then change", outcome_codes=o, difficulty="MEDIUM",
          body="```python\na = 5\nb = a\na = 8\nprint(a, b)\n```", option_a="8 8", option_b="8 5", option_c="5 8",
          option_d="5 5", correct_option="B", language="python"),
        R("STEP", "PY-M1-L1-S05", "PY-M1-L1", 5, title="Try it", step_type="PLAYGROUND", body="Press Run.",
          outcome_codes=o, starter_code='print("Hello")', language="python"),
        R("STEP", "PY-M1-L1-S06", "PY-M1-L1", 6, title="Arrange", step_type="PARSONS", body="Order the lines.",
          outcome_codes=o, solution_code="for i in range(3):\n    print(i)", explanation="Loop first.",
          meta={"lines": ["for i in range(3):", "print(i)"], "distractors": ["print i"]}),
        R("STEP", "PY-M1-L1-S07", "PY-M1-L1", 7, title="Quick check", step_type="QUIZ", body="Five questions.",
          outcome_codes=o, meta={"pass_percent": 60}),
        R("MCQ", "PY-M1-L1-Q01", "PY-M1-L1-S07", 1, title="CPU", difficulty="EASY", body="Who runs instructions?",
          option_a="RAM", option_b="CPU", option_c="SSD", correct_option="B"),
        R("MCQ", "PY-M1-L1-Q02", "PY-M1-L1-S07", 2, title="Pick two", outcome_codes=o, difficulty="EASY",
          body="Which are input devices?", option_a="Keyboard", option_b="Monitor", option_c="Mouse",
          correct_option="A;C", meta={"option_explanations": {"B": "A monitor shows output."}}),
        R("STEP", "PY-M1-L1-S08", "PY-M1-L1", 8, title="Fix the bug", step_type="FIX_BUG", body="It doesn't run.",
          outcome_codes=o, meta={"problem_code": "PY-M1-L1-FB01"}),
        R("PROBLEM", "PY-M1-L1-FB01", "PY-M1-L1-S08", 1, title="Fix the welcome", outcome_codes=o, difficulty="EASY",
          body="Print Welcome.", starter_code='print("Welcome)', solution_code='print("Welcome")', language="python",
          explanation="Close the quote.", meta={"problem_kind": "fix_bug", "time_limit_ms": 2000, "memory_limit_mb": 64}),
        R("TESTCASE", "PY-M1-L1-FB01-T1", "PY-M1-L1-FB01", 1, title="Prints it", expected_output="Welcome",
          is_hidden="FALSE", points="10"),
        R("HINT", "PY-M1-L1-FB01-H1", "PY-M1-L1-FB01", 1, title="Nudge", body="Read the error."),
        R("HINT", "PY-M1-L1-FB01-H3", "PY-M1-L1-FB01", 3, title="Near solution", body="Add the quote."),
        R("STEP", "PY-M1-L1-S09", "PY-M1-L1", 9, title="Coding tasks", step_type="CODING", body="Solve them.",
          outcome_codes=o, meta={"problem_codes": ["PY-M1-L1-C01", "PY-M1-L1-C02"], "min_to_pass": 2}),
        R("PROBLEM", "PY-M1-L1-C01", "PY-M1-L1-S09", 1, title="Hello, World!", outcome_codes=o, difficulty="EASY",
          body="Print Hello, World!", starter_code="# Write your code below\n", language="python",
          meta={"problem_kind": "coding", "no_input": True}),
        R("TESTCASE", "PY-M1-L1-C01-T1", "PY-M1-L1-C01", 1, title="Hello", expected_output="Hello, World!",
          is_hidden="FALSE"),
        R("HINT", "PY-M1-L1-C01-H1", "PY-M1-L1-C01", 1, title="Nudge", body="Use print."),
        R("PROBLEM", "PY-M1-L1-C02", "PY-M1-L1-S09", 2, title="Today's date", outcome_codes=o, difficulty="EASY",
          body="Print the date.", starter_code="", language="python", meta={"problem_kind": "coding"}),
        R("TESTCASE", "PY-M1-L1-C02-T1", "PY-M1-L1-C02", 1, title="Date", expected_output="07/11/2026",
          is_hidden="FALSE"),
        R("TESTCASE", "PY-M1-L1-C02-T2", "PY-M1-L1-C02", 2, title="Hidden date", expected_output="07/11/2026",
          is_hidden="TRUE", points="3"),
        R("PROBLEM", "PY-M1-MP01", "PY-M1", 1, title="Mini-project: intro card", difficulty="MEDIUM",
          body="Print your intro card.", meta={"problem_kind": "mini_project"}),
    ]


def workbook(rows, tab="Core Python", name="courses.xlsx", extra_tabs=("Java",)):
    wb = Workbook()
    ws = wb.active
    ws.title = tab
    ws.append(COLUMNS)
    for row in rows:
        ws.append([row.get(c, "") for c in COLUMNS])
    for extra in extra_tabs:
        wb.create_sheet(extra).append(COLUMNS)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    buffer.name = name
    return buffer


def replace(rows, code, **changes):
    out = []
    for row in rows:
        if row["code"] == code:
            row = dict(row, **changes)
            if "meta" in changes:
                row["meta_json"] = json.dumps(row.pop("meta"))
        out.append(row)
    return out


class SheetTestCase(TestCase):
    def setUp(self):
        self.staff = make_user(staff=True)
        ProgrammingLanguage.objects.get_or_create(slug="python", defaults={
            "name": "Python", "is_active": True, "is_judge0_executable": True, "judge0_language_id": 71})

    def run_import(self, rows, dry_run=False, **kwargs):
        return import_sheet(workbook(rows, **kwargs), tab=kwargs.get("tab", "Core Python"),
                            owner=self.staff, dry_run=dry_run)


class ImportTests(SheetTestCase):
    def test_dry_run_counts_everything_and_saves_nothing(self):
        report = self.run_import(course_rows(), dry_run=True)
        self.assertTrue(report.ok, report.errors)
        counts = {label: created for label, created, _ in report.rows()}
        self.assertEqual(counts, {"Modules": 2, "Lessons": 2, "Outcomes": 5, "Steps": 12, "Mcqs": 4,
                                  "Problems": 3, "Test cases": 4, "Hints": 3})
        self.assertTrue(any("plans 12 modules" in w for w in report.warnings))
        self.assertFalse(Course.objects.exists())
        self.assertFalse(McqQuestion.objects.exists())

    def test_apply_builds_a_publishable_course(self):
        report = self.run_import(course_rows())
        self.assertTrue(report.applied, report.errors)
        course = Course.objects.get(code="PY")
        self.assertEqual((course.title, course.version, course.level, course.category.title),
                         ("Core Python", 2, "beginner", "Python"))

        intro, m1 = course.modules.order_by("position")
        self.assertEqual((intro.position, intro.is_introduction, intro.is_free_preview), (0, True, True))
        self.assertEqual((m1.position, m1.code), (1, "PY-M1"))
        self.assertIn("Mini-project: intro card", m1.mini_project_brief)

        lesson = Lesson.objects.get(code="PY-M1-L1")
        self.assertEqual((lesson.est_minutes, lesson.min_coding_passes), (60, 2))
        steps = list(lesson.steps.order_by("position"))
        self.assertEqual([s.step_type for s in steps], ["TEXT", "VIDEO", "TEXT", "PREDICT", "PLAYGROUND", "PARSONS",
                                                        "QUIZ", "FIX_BUG", "CODING", "CODING"])
        self.assertEqual([s.code for s in steps[-2:]], ["PY-M1-L1-S09.C01", "PY-M1-L1-S09.C02"])
        self.assertEqual([s.title for s in steps[-2:]], ["Hello, World!", "Today's date"])
        self.assertEqual(steps[-1].content, {"instructions": "Solve them."})

        video = steps[1].content
        self.assertEqual((video["duration_s"], video["script"], video["chapters"][0]), (420, "SCRIPT 0:00 Hook",
                                                                                         {"t": 0, "title": "Hook"}))
        self.assertEqual(steps[5].content["lines"][1], {"text": "print(i)", "indent": 1})
        self.assertEqual(steps[5].content["explanation"], "Loop first.")

        quiz = steps[6]
        self.assertEqual(list(quiz.questions.values_list("mcq__slug", "outcome__code")),
                         [("py-m1-l1-q01", "PY-M1-L1-O1"), ("py-m1-l1-q02", "PY-M1-L1-O1")])
        pick_two = McqQuestion.objects.get(slug="py-m1-l1-q02")
        self.assertTrue(pick_two.allow_multiple)
        self.assertEqual(list(pick_two.options.values_list("text", "is_correct", "explanation")),
                         [("Keyboard", True, ""), ("Monitor", False, "A monitor shows output."), ("Mouse", True, "")])
        self.assertEqual(list(McqQuestion.objects.get(slug="py-m1-l1-p01").options.values_list("text", flat=True)),
                         ["8 8", "8 5", "5 8", "5 5"])

        fix = CodingQuestion.objects.get(slug="py-m1-l1-fb01")
        variant = fix.supported_languages.get()
        self.assertEqual((fix.coding_mode, variant.buggy_code, variant.starter_code, fix.memory_limit_kb),
                         ("fix", 'print("Welcome)', "", 65536))
        self.assertEqual(list(StepHint.objects.filter(step=steps[7]).values_list("level", flat=True)), [1, 3])
        date = CodingQuestion.objects.get(slug="py-m1-l1-c02")
        self.assertEqual(list(date.test_cases.values_list("expected_output", "is_sample", "weight")),
                         [("07/11/2026", True, 1), ("07/11/2026", False, 3)])

        self.assertEqual(LearningOutcome.objects.get(code="PY-O1").level, "course")
        self.assertEqual(list(LearningOutcome.objects.get(code="PY-M1-L1-O1").supports.values_list("code", flat=True)),
                         ["PY-M1-O1"])
        self.assertEqual(LessonStep.objects.get(code="PY-M0-L1-S02").content["pass_percent"], 0)

        publish = services.publish_report(course)
        self.assertEqual(publish.blocking, [], [i.message for i in publish.blocking])
        # Only the 1-lesson Module 1 is flagged; the 1-lesson introduction is exempt from the 6-lesson rule.
        self.assertEqual([i.where for i in publish.warnings], ["Module 1 · Getting Started"])

    def test_reimport_updates_in_place_and_keeps_removed_rows(self):
        self.run_import(course_rows())
        step_ids = set(LessonStep.objects.values_list("pk", flat=True))
        rows = replace(course_rows(), "PY-M1-L1-S01", title="Hook v2")
        rows = replace(rows, "PY-M1-L1-P01", option_a="8, 8")
        rows = [r for r in rows if r["code"] != "PY-M1-L1-S03"]  # notes step removed from the sheet

        report = self.run_import(rows)
        self.assertTrue(report.applied, report.errors)
        self.assertEqual(report.counts["steps"]["created"], 0)
        self.assertEqual(set(LessonStep.objects.values_list("pk", flat=True)), step_ids)
        self.assertEqual(LessonStep.objects.get(code="PY-M1-L1-S01").title, "Hook v2")
        self.assertEqual(McqQuestion.objects.get(slug="py-m1-l1-p01").options.get(position=1).text, "8, 8")
        self.assertTrue(any("PY-M1-L1-S03" in w and "no longer in the sheet" in w for w in report.warnings))
        lesson = Lesson.objects.get(code="PY-M1-L1")
        positions = list(lesson.steps.order_by("position").values_list("code", flat=True))
        self.assertEqual(positions[-1], "PY-M1-L1-S03")  # kept, moved after the imported steps
        self.assertEqual(lesson.steps.count(), 10)

    def test_content_errors_name_the_row_and_save_nothing(self):
        rows = course_rows()
        rows = replace(rows, "PY-M1-L1-Q01", correct_option="D")
        rows = replace(rows, "PY-M1-L1-FB01", starter_code="")
        rows = replace(rows, "PY-M1-L1-S04", meta={"mcq_codes": ["PY-M1-L1-P09"]})
        rows = replace(rows, "PY-M1-O1", body="x" * 301)
        rows = replace(rows, "PY-M0", meta={"free_preview": True})  # order 0 without is_introduction
        rows.append(R("HINT", "PY-M1-L1-C01-H9", "PY-M1-L1-C01", 9, title="Too deep", body="?"))
        report = self.run_import(rows)
        errors = "\n".join(report.errors)
        for expected in ("correct_option D points to an empty or unknown option",
                         "a fix_bug problem needs the buggy program in starter_code",
                         "mcq_codes ['PY-M1-L1-P09'] doesn't match",
                         "keep it to 300",
                         "order 0 is only for a module with \"is_introduction\": true",
                         "hint order is the level: 1, 2 or 3"):
            self.assertIn(expected, errors)
        self.assertTrue(all(e.startswith("Row ") for e in report.errors))
        self.assertFalse(Course.objects.exists())

    def test_structure_errors(self):
        rows = course_rows() + [
            R("STEP", "PY-M1-L1-S01", "PY-M1-L1", 10, title="Dup", step_type="TEXT"),       # duplicate code
            R("MCQ", "PY-M1-L1-Q09", "PY-M1-L1-S01", 1, title="Wrong parent", difficulty="EASY"),
            R("STEP", "PY-M1-X1", "PY-M1-L1", 11, title="Bad code", step_type="TEXT"),
            R("STEP", "PY-M1-L1-S13", "PY-M1-L1", 13, title="Bad JSON", step_type="TEXT", meta_json="{'a': 1}"),
            R("DANCE", "PY-D1", "PY", 1),
        ]
        errors = "\n".join(self.run_import(rows).errors)
        for expected in ("code is already used on row", "record_type must be one of", "meta_json is not valid JSON"):
            self.assertIn(expected, errors)
        # Link checks run once the rows themselves are valid.
        rows = course_rows() + [
            R("MCQ", "PY-M1-L1-Q09", "PY-M1-L1-S01", 1, title="Wrong parent", difficulty="EASY"),
            R("STEP", "PY-M1-X1", "PY-M1-L1", 11, title="Bad code", step_type="TEXT"),
            R("STEP", "PY-M1-L1-S14", "PY-M1-L1", 1, title="Same order", step_type="TEXT"),
            R("STEP", "PY-M1-L1-S15", "PY-M1-L1", 15, title="Untagged", step_type="TEXT", outcome_codes="PY-NOPE"),
            R("STEP", "PY-M1-L1-S16", "PY-M9-L1", 16, title="Orphan", step_type="TEXT"),
        ]
        errors = "\n".join(self.run_import(rows).errors)
        for expected in ("MCQs belong to a PREDICT or QUIZ step", "code should look like PY-M1-L1-S1",
                         "order 1 is also used by PY-M1-L1-S01", "outcome PY-NOPE is not defined",
                         "parent_code 'PY-M9-L1' is not defined"):
            self.assertIn(expected, errors)

    def test_changing_a_step_type_is_refused(self):
        self.run_import(course_rows())
        rows = replace(course_rows(), "PY-M1-L1-S01", step_type="PLAYGROUND", starter_code="print(1)")
        report = self.run_import(rows)
        self.assertIn("is a Notes step in the app", "\n".join(report.errors))
        self.assertEqual(LessonStep.objects.get(code="PY-M1-L1-S01").step_type, "TEXT")

    def test_reads_csv_and_reports_unknown_tabs(self):
        rows = course_rows()
        buffer = io.StringIO()
        import csv
        writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})
        upload = io.BytesIO(buffer.getvalue().encode())
        upload.name = "core.csv"
        self.assertTrue(import_sheet(upload, owner=self.staff, dry_run=True).ok)
        report = import_sheet(workbook(rows), tab="Kotlin", owner=self.staff)
        self.assertIn("Tab 'Kotlin' is not in this workbook. Tabs: Core Python, Java.", report.errors[0])

    def test_hidden_test_warning_only_when_input_is_read(self):
        rows = replace(course_rows(), "PY-M1-L1-FB01-T1", input="5")
        report = self.run_import(rows, dry_run=True)
        self.assertTrue(any("PY-M1-L1-FB01" in w and "hidden" in w for w in report.warnings))
        clean = self.run_import(course_rows(), dry_run=True)
        self.assertFalse(any("hidden" in w for w in clean.warnings))


class ImportViewTests(SheetTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)
        self.url = reverse("course_builder:sheet_import")

    def upload(self, rows=None, name="courses.xlsx"):
        return SimpleUploadedFile(name, workbook(rows or course_rows()).getvalue())

    def test_upload_pick_tab_check_apply(self):
        response = self.client.post(self.url, {"action": "upload", "file": self.upload()})
        self.assertContains(response, '<option value="Core Python" selected>')
        self.assertContains(response, '<option value="Java"')
        response = self.client.post(self.url, {"action": "check", "tab": "Core Python"})
        self.assertContains(response, "Check passed")
        self.assertFalse(Course.objects.exists())
        response = self.client.post(self.url, {"action": "apply", "digest": response.context["digest"]})
        course = Course.objects.get(code="PY")
        self.assertRedirects(response, reverse("course_builder:course", args=[course.pk]))
        self.assertEqual(Module.objects.filter(course=course).count(), 2)
        self.assertIsNone(self.client.session.get("course_sheet_import"))

    def test_failed_check_and_forged_digest_never_apply(self):
        rows = replace(course_rows(), "PY-M1-L1-Q01", correct_option="Z")
        self.client.post(self.url, {"action": "upload", "file": self.upload(rows)})
        response = self.client.post(self.url, {"action": "check", "tab": "Core Python"})
        self.assertContains(response, "problem to fix in the sheet")
        self.assertNotContains(response, 'value="apply"')
        self.client.post(self.url, {"action": "upload", "file": self.upload()})
        self.client.post(self.url, {"action": "check", "tab": "Core Python"})
        response = self.client.post(self.url, {"action": "apply", "digest": "forged"}, follow=True)
        self.assertContains(response, "Check the file again")
        self.assertFalse(Course.objects.exists())

    def test_rejects_bad_files_and_unknown_tabs(self):
        response = self.client.post(self.url, {"action": "upload", "file": SimpleUploadedFile("a.txt", b"x")}, follow=True)
        self.assertContains(response, "Choose the course workbook")
        response = self.client.post(self.url, {"action": "upload", "file": SimpleUploadedFile("a.xlsx", b"junk")}, follow=True)
        self.assertContains(response, "could not be read")
        self.client.post(self.url, {"action": "upload", "file": self.upload()})
        response = self.client.post(self.url, {"action": "check", "tab": "Kotlin"}, follow=True)
        self.assertContains(response, "Pick one of the tabs")

    def test_staff_only(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.post(self.url, {"action": "upload", "file": self.upload()})
        self.assertIsNone(self.client.session.get("course_sheet_import"))


class CommandTests(SheetTestCase):
    def setUp(self):
        super().setUp()
        self.staff.is_superuser = True
        self.staff.save()
        handle, self.path = tempfile.mkstemp(suffix=".xlsx")
        os.close(handle)
        with open(self.path, "wb") as f:
            f.write(workbook(course_rows()).getvalue())

    def tearDown(self):
        os.remove(self.path)

    def test_dry_run_then_apply(self):
        out = io.StringIO()
        call_command("import_course_sheet", self.path, tab="Core Python", stdout=out)
        self.assertIn("Check passed", out.getvalue())
        self.assertFalse(Course.objects.exists())
        call_command("import_course_sheet", self.path, tab="Core Python", apply=True, stdout=out)
        self.assertTrue(Course.objects.filter(code="PY").exists())

    def test_requires_a_tab_and_a_real_owner(self):
        with self.assertRaises(CommandError):
            call_command("import_course_sheet", self.path, stdout=io.StringIO())
        with self.assertRaises(CommandError):
            call_command("import_course_sheet", self.path, tab="Core Python", owner="nobody@example.com",
                         stdout=io.StringIO())
