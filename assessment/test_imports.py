from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from assessment.imports import (
    ImportFileError,
    build_import_template,
    parse_question_file,
)
from assessment.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentSection,
    CodingQuestion,
    McqQuestion,
    ProgrammingLanguage,
)
from users.models import Users


class BulkQuestionImportTests(TestCase):
    def setUp(self):
        self.user = Users.objects.create_user(
            email="importer@example.com",
            user_name="importer",
            password="StrongPass123!",
            is_faculty=True,
        )
        self.language = ProgrammingLanguage.objects.create(
            name="Python",
            slug="python",
            is_active=True,
            is_judge0_executable=True,
            judge0_language_id=71,
        )
        self.assessment = Assessment.objects.create(
            created_by=self.user,
            name="Import assessment",
            slug="import-assessment",
            duration_minutes=45,
        )
        self.section = AssessmentSection.objects.create(
            assessment=self.assessment,
            title="MCQs",
            position=1,
        )
        self.client.force_login(self.user)

    def _workbook_upload(
        self,
        question_type,
        *,
        invalid_row=False,
        multiple_answers=False,
    ):
        workbook_buffer = build_import_template(question_type)
        workbook = load_workbook(workbook_buffer)
        if question_type == "mcq":
            workbook["MCQ"].append(
                [
                    "What is 2 + 2?",
                    "regular",
                    "quant",
                    "Arithmetic",
                    "Addition",
                    "easy",
                    "Choose the correct answer.",
                    "",
                    "Add the two numbers.",
                    str(multiple_answers).lower(),
                    "3",
                    "true" if multiple_answers else "false",
                    "4",
                    "true",
                ]
            )
        else:
            workbook["Coding"].append(
                [
                    "sum-two",
                    "Sum two numbers",
                    "scratch",
                    "Algorithms",
                    "Basics",
                    "easy",
                    "Read two integers and return their sum.",
                    "Two integers",
                    "Their sum",
                    "",
                    "",
                    2,
                    262144,
                ]
            )
            workbook["Languages"].append(["sum-two", "Python", ""])
            workbook["TestCases"].append(["sum-two", "2 3", "5", "true", 1, ""])
        if invalid_row:
            if question_type == "mcq":
                workbook["MCQ"].append(
                    [
                        "",
                        "regular",
                        "quant",
                        "Arithmetic",
                        "Addition",
                        "easy",
                        "Question with a missing title.",
                        "Python",
                        "",
                        "false",
                        "A",
                        "true",
                        "B",
                        "false",
                    ]
                )
            else:
                workbook["Coding"].append(
                    [
                        "missing-title",
                        "",
                        "scratch",
                        "Algorithms",
                        "Basics",
                        "easy",
                        "Question with a missing title.",
                        "",
                        "",
                        "",
                        "",
                        2,
                        262144,
                    ]
                )
                workbook["Languages"].append(["missing-title", "Python", ""])
                workbook["TestCases"].append(
                    ["missing-title", "1 2", "3", "false", 1, ""]
                )
        output = BytesIO()
        workbook.save(output)
        workbook.close()
        return SimpleUploadedFile(
            f"{question_type}-questions.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def _labelled_pdf_upload(self, text):
        writer = PdfWriter()
        page = writer.add_blank_page(width=400, height=600)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): writer._add_object(font)}
                )
            }
        )
        commands = ["BT", "/F1 12 Tf", "50 550 Td"]
        for line in text.splitlines():
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.extend([f"({escaped}) Tj", "0 -16 Td"])
        commands.append("ET")
        content = DecodedStreamObject()
        content.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
        output = BytesIO()
        writer.write(output)
        return SimpleUploadedFile(
            "questions.pdf",
            output.getvalue(),
            content_type="application/pdf",
        )

    def test_mcq_workbook_import_saves_questions_and_assigns_them_to_section(self):
        response = self.client.post(
            reverse("assessment:question_import", args=["mcq"]),
            {
                "assessment": str(self.assessment.pk),
                "section": str(self.section.pk),
                "file": self._workbook_upload("mcq"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        self.assertEqual(response.context["skipped"], [])
        question = McqQuestion.objects.get(title="What is 2 + 2?")
        self.assertEqual(question.owner, self.user)
        self.assertIsNone(question.programming_language)
        self.assertEqual(
            list(question.options.order_by("position").values_list("position", flat=True)),
            [1, 2],
        )
        self.assertEqual(
            AssessmentQuestion.objects.get(mcq_question=question).section,
            self.section,
        )

    def test_mcq_workbook_import_saves_multiple_correct_answers(self):
        response = self.client.post(
            reverse("assessment:question_import", args=["mcq"]),
            {"file": self._workbook_upload("mcq", multiple_answers=True)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        question = McqQuestion.objects.get(title="What is 2 + 2?")
        self.assertTrue(question.allow_multiple)
        self.assertEqual(question.options.filter(is_correct=True).count(), 2)

    def test_coding_workbook_import_saves_languages_cases_and_section_assignment(self):
        response = self.client.post(
            reverse("assessment:question_import", args=["coding"]),
            {
                "assessment": str(self.assessment.pk),
                "section": str(self.section.pk),
                "file": self._workbook_upload("coding"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        question = CodingQuestion.objects.get(title="Sum two numbers")
        self.assertEqual(question.owner, self.user)
        self.assertTrue(question.is_active)
        self.assertEqual(question.supported_languages.get().language, self.language)
        self.assertEqual(question.test_cases.get().expected_output, "5")
        self.assertTrue(
            AssessmentQuestion.objects.filter(
                coding_question=question,
                section=self.section,
            ).exists()
        )

    def test_invalid_workbook_rows_are_skipped_while_valid_rows_are_imported(self):
        response = self.client.post(
            reverse("assessment:question_import", args=["mcq"]),
            {
                "file": self._workbook_upload("mcq", invalid_row=True),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        self.assertTrue(response.context["skipped"])
        self.assertTrue(
            any(
                "title" in error.lower()
                for item in response.context["skipped"]
                for error in item["errors"]
            )
        )
        self.assertEqual(McqQuestion.objects.filter(owner=self.user).count(), 1)

    def test_labelled_pdf_mcq_import(self):
        response = self.client.post(
            reverse("assessment:question_import", args=["mcq"]),
            {
                "file": self._labelled_pdf_upload(
                    "=== MCQ ===\n"
                    "title: PDF question\n"
                    "question_type: regular\n"
                    "category: quant\n"
                    "topic: Arithmetic\n"
                    "sub_topic: Addition\n"
                    "difficulty: easy\n"
                    "statement: What is 1 + 1?\n"
                    "option_1: 1\n"
                    "option_2: 2\n"
                    "correct_options: 2"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        question = McqQuestion.objects.get(title="PDF question")
        self.assertIsNone(question.programming_language)
        self.assertEqual(question.options.filter(is_correct=True).count(), 1)

    def test_labelled_pdf_mcq_import_saves_multiple_correct_answers(self):
        response = self.client.post(
            reverse("assessment:question_import", args=["mcq"]),
            {
                "file": self._labelled_pdf_upload(
                    "=== MCQ ===\n"
                    "title: Multi-answer PDF question\n"
                    "question_type: regular\n"
                    "category: quant\n"
                    "topic: Arithmetic\n"
                    "sub_topic: Addition\n"
                    "difficulty: easy\n"
                    "statement: Choose both even numbers.\n"
                    "allow_multiple: true\n"
                    "option_1: 2\n"
                    "option_2: 3\n"
                    "option_3: 4\n"
                    "correct_options: 1,3"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        question = McqQuestion.objects.get(title="Multi-answer PDF question")
        self.assertTrue(question.allow_multiple)
        self.assertEqual(question.options.filter(is_correct=True).count(), 2)

    def test_labelled_pdf_coding_import(self):
        response = self.client.post(
            reverse("assessment:question_import", args=["coding"]),
            {
                "file": self._labelled_pdf_upload(
                    "=== CODING ===\n"
                    "question_key: pdf-sum\n"
                    "title: PDF coding question\n"
                    "coding_mode: scratch\n"
                    "topic: Algorithms\n"
                    "subtopic: Basics\n"
                    "difficulty: easy\n"
                    "statement: Add two integers.\n"
                    "\n"
                    "=== LANGUAGE ===\n"
                    "question_key: pdf-sum\n"
                    "programming_language: Python\n"
                    "\n"
                    "=== TEST CASE ===\n"
                    "question_key: pdf-sum\n"
                    "input_data: 2 3\n"
                    "expected_output: 5\n"
                    "is_sample: true\n"
                    "weight: 1"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        question = CodingQuestion.objects.get(title="PDF coding question")
        self.assertEqual(question.supported_languages.get().language, self.language)
        self.assertEqual(question.test_cases.get().expected_output, "5")

    def test_import_templates_are_downloadable(self):
        response = self.client.get(
            reverse("assessment:question_import_template", args=["coding"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("coding-questions-template.xlsx", response["Content-Disposition"])

    def test_import_page_includes_copyable_type_specific_ai_instructions(self):
        mcq_response = self.client.get(
            reverse("assessment:question_import", args=["mcq"])
        )
        self.assertContains(mcq_response, "Copy AI prompt")
        self.assertContains(mcq_response, "Programming language is optional")
        self.assertContains(mcq_response, "Leave programming_language blank")
        self.assertContains(mcq_response, "exact header order")

        coding_response = self.client.get(
            reverse("assessment:question_import", args=["coding"])
        )
        self.assertContains(coding_response, "END_CODE_SNIPPET")
        self.assertContains(coding_response, "question_key")
        self.assertContains(coding_response, "=== TEST CASE ===")
        self.assertContains(coding_response, "programming_language, code_snippet")
        self.assertContains(coding_response, "Do not add a position column")
        self.assertContains(coding_response, "text file renamed with an .xlsx extension")
        self.assertContains(coding_response, "For fix, put the intentionally buggy program")
        self.assertNotContains(coding_response, "Use only the problems, code, and test cases in my source")

    def test_scan_only_pdf_returns_clear_error(self):
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        output = BytesIO()
        writer.write(output)
        upload = SimpleUploadedFile("scan.pdf", output.getvalue(), content_type="application/pdf")

        with self.assertRaisesMessage(ImportFileError, "No selectable text"):
            parse_question_file(upload, "mcq")

    def test_import_entry_points_are_shown_on_assessment_and_section(self):
        response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk])
            + "?tab=questions"
        )

        self.assertNotContains(response, "Import in bulk")
        self.assertContains(response, "Import questions")
