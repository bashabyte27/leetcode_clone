import re
from collections import defaultdict
from io import BytesIO

from openpyxl import Workbook, load_workbook
from pypdf import PdfReader

from django.db import transaction
from django.db.models import Max

from .forms import (
    CodingQuestionForm,
    CodingQuestionLanguageFormSet,
    CodingTestCaseFormSet,
    McqOptionFormSet,
    McqQuestionForm,
)
from .models import (
    Assessment,
    AssessmentQuestion,
    AssessmentSection,
    CodingQuestion,
    McqQuestion,
    ProgrammingLanguage,
)

MAX_IMPORT_SIZE = 10 * 1024 * 1024
MAX_IMPORT_RECORDS = 500
MAX_IMPORT_TEXT = 2 * 1024 * 1024
MCQ_HEADERS = (
    "title",
    "question_type",
    "category",
    "topic",
    "sub_topic",
    "difficulty",
    "statement",
    "programming_language",
    "explanation",
    "allow_multiple",
)
CODING_HEADERS = (
    "question_key",
    "title",
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
)
LANGUAGE_HEADERS = ("question_key", "programming_language", "code_snippet")
TEST_CASE_HEADERS = (
    "question_key",
    "input_data",
    "expected_output",
    "is_sample",
    "weight",
    "explanation",
)
MAX_OPTIONS = 10


class ImportFileError(ValueError):
    pass


def _value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _normalise_header(value):
    return re.sub(r"[\s-]+", "_", _value(value).lower())


def _sheet_rows(sheet):
    rows = iter(sheet.iter_rows(values_only=True))
    headers = next(rows, None)
    if not headers:
        return []
    header_map = {
        _normalise_header(header): index
        for index, header in enumerate(headers)
        if _value(header)
    }
    result = []
    total_text = 0
    for row_number, row in enumerate(rows, start=2):
        if not any(value is not None and _value(value) for value in row):
            continue
        record = {
            header: _value(row[index]) if index < len(row) else ""
            for header, index in header_map.items()
        }
        total_text += sum(len(value) for value in record.values())
        if total_text > MAX_IMPORT_TEXT:
            raise ImportFileError("The workbook contains too much text to import.")
        record["__row_number__"] = row_number
        result.append(record)
        if len(result) > MAX_IMPORT_RECORDS * 20:
            raise ImportFileError("The workbook contains too many rows.")
    return result


def _option_values(row):
    options = []
    for key in sorted(
        (key for key in row if re.fullmatch(r"option_\d+", key)),
        key=lambda key: int(key.split("_")[1]),
    ):
        text = row[key]
        if not text:
            continue
        correct_value = row.get(f"{key}_correct", "").lower()
        options.append(
            {
                "text": text,
                "is_correct": correct_value in {"1", "true", "yes", "y"},
            }
        )
    return options


def _mcq_candidates(rows):
    candidates = []
    for index, row in enumerate(rows, start=2):
        row_number = row.get("__row_number__", index)
        question = {field: row.get(field, "") for field in MCQ_HEADERS}
        question["options"] = _option_values(row)
        if not any(question.values()):
            continue
        candidates.append(
            {"row_number": row_number, "question": question, "errors": []}
        )
    return candidates


def _coding_candidates(question_rows, language_rows, case_rows):
    languages = defaultdict(list)
    test_cases = defaultdict(list)
    support_errors = defaultdict(list)

    for index, row in enumerate(language_rows, start=2):
        row_number = row.get("__row_number__", index)
        key = row.get("question_key", "")
        if not key:
            support_errors[""].append(f"Languages row {row_number}: question_key is required.")
            continue
        languages[key].append(
            {
                "language": row.get("programming_language", ""),
                "code_snippet": row.get("code_snippet", ""),
                "row_number": row_number,
            }
        )

    for index, row in enumerate(case_rows, start=2):
        row_number = row.get("__row_number__", index)
        key = row.get("question_key", "")
        if not key:
            support_errors[""].append(f"TestCases row {row_number}: question_key is required.")
            continue
        test_cases[key].append(
            {
                "input_data": row.get("input_data", ""),
                "expected_output": row.get("expected_output", ""),
                "is_sample": row.get("is_sample", ""),
                "weight": row.get("weight", ""),
                "explanation": row.get("explanation", ""),
                "row_number": row_number,
            }
        )

    candidates = []
    seen_keys = set()
    for index, row in enumerate(question_rows, start=2):
        row_number = row.get("__row_number__", index)
        question = {field: row.get(field, "") for field in CODING_HEADERS}
        key = question["question_key"]
        if not any(question.values()):
            continue
        errors = []
        if not key:
            errors.append(f"Questions row {row_number}: question_key is required.")
        elif key in seen_keys:
            errors.append(f"Questions row {row_number}: duplicate question_key '{key}'.")
        else:
            seen_keys.add(key)
        question["languages"] = languages.pop(key, [])
        question["test_cases"] = test_cases.pop(key, [])
        errors.extend(support_errors.pop(key, []))
        candidates.append(
            {"row_number": row_number, "question": question, "errors": errors}
        )

    for key in sorted(set(languages) | set(test_cases) | set(support_errors)):
        if key:
            support_errors[key].append(f"Unknown question_key '{key}' in supporting sheets.")
        for error in support_errors.get(key, []):
            candidates.append(
                {
                    "row_number": None,
                    "question": {},
                    "errors": [error],
                }
            )
    return candidates


def _parse_workbook(upload, question_type):
    try:
        workbook = load_workbook(upload, read_only=True, data_only=True)
    except Exception as exc:
        raise ImportFileError(f"Could not read the Excel workbook: {exc}") from exc

    try:
        if question_type == "mcq":
            if "MCQ" not in workbook.sheetnames:
                raise ImportFileError("The workbook must contain an 'MCQ' sheet.")
            return _mcq_candidates(_sheet_rows(workbook["MCQ"]))

        required_sheets = {"Coding", "Languages", "TestCases"}
        missing = sorted(required_sheets - set(workbook.sheetnames))
        if missing:
            raise ImportFileError(
                "The workbook is missing required sheets: " + ", ".join(missing)
            )
        return _coding_candidates(
            _sheet_rows(workbook["Coding"]),
            _sheet_rows(workbook["Languages"]),
            _sheet_rows(workbook["TestCases"]),
        )
    finally:
        workbook.close()


def _key_value_records(text):
    records = []
    current = None
    active_key = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        marker = line.upper()
        if marker in {"=== MCQ ===", "=== CODING ==="}:
            if current is not None:
                records.append(current)
            current = {
                "_kind": "mcq" if marker == "=== MCQ ===" else "coding",
                "_values": {},
            }
            active_key = None
            continue
        if marker in {"=== LANGUAGE ===", "=== TEST CASE ==="}:
            if current is not None:
                records.append(current)
            current = {
                "_kind": "language" if marker == "=== LANGUAGE ===" else "test_case",
                "_values": {},
            }
            active_key = None
            continue
        if current is None or not line:
            if not line:
                if current is not None and active_key:
                    current["_values"][active_key] += "\n"
            continue
        if active_key == "code_snippet":
            if marker == "END_CODE_SNIPPET":
                active_key = None
            else:
                current["_values"][active_key] += "\n" + raw_line.rstrip()
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9 _-]*):\s*(.*)$", line)
        if match:
            active_key = _normalise_header(match.group(1))
            current["_values"][active_key] = match.group(2).strip()
        elif active_key:
            current["_values"][active_key] = (
                current["_values"][active_key] + "\n" + raw_line.rstrip()
            ).strip()
    if current is not None:
        records.append(current)
    return records


def _pdf_candidates(upload, question_type):
    try:
        reader = PdfReader(upload, strict=True)
        if len(reader.pages) > 100:
            raise ImportFileError("PDF imports are limited to 100 pages.")
        page_texts = []
        text_size = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_size += len(page_text)
            if text_size > MAX_IMPORT_TEXT:
                raise ImportFileError("The PDF contains too much text to import.")
            page_texts.append(page_text)
        text = "\n".join(page_texts)
    except ImportFileError:
        raise
    except Exception as exc:
        raise ImportFileError(f"Could not read the PDF: {exc}") from exc

    if not text.strip():
        raise ImportFileError(
            "No selectable text was found. Scanned PDFs and OCR are not supported."
        )

    records = _key_value_records(text)
    questions = [record for record in records if record["_kind"] in {"mcq", "coding"}]
    languages = defaultdict(list)
    test_cases = defaultdict(list)
    for record in records:
        values = record["_values"]
        key = values.get("question_key", "")
        if record["_kind"] == "language":
            languages[key].append(
                {
                    "language": values.get("programming_language", ""),
                    "code_snippet": values.get("code_snippet", ""),
                    "row_number": None,
                }
            )
        elif record["_kind"] == "test_case":
            test_cases[key].append(
                {
                    "input_data": values.get("input_data", ""),
                    "expected_output": values.get("expected_output", ""),
                    "is_sample": values.get("is_sample", ""),
                    "weight": values.get("weight", ""),
                    "explanation": values.get("explanation", ""),
                    "row_number": None,
                }
            )

    candidates = []
    seen_keys = set()
    for row_number, record in enumerate(questions, start=1):
        values = record["_values"]
        if record["_kind"] != question_type:
            continue
        if question_type == "mcq":
            question = {field: values.get(field, "") for field in MCQ_HEADERS}
            question["options"] = []
            correct_options = {
                item.strip()
                for item in values.get("correct_options", "").split(",")
                if item.strip()
            }
            option_numbers = sorted(
                {
                    match.group(1)
                    for key in values
                    if (match := re.fullmatch(r"option_(\d+)", key))
                },
                key=int,
            )
            for number in option_numbers:
                text_value = values.get(f"option_{number}", "")
                if text_value:
                    question["options"].append(
                        {
                            "text": text_value,
                            "is_correct": (
                                number in correct_options
                                or values.get(f"option_{number}_correct", "").lower()
                                in {"1", "true", "yes", "y"}
                            ),
                        }
                    )
        else:
            question = {field: values.get(field, "") for field in CODING_HEADERS}
            key = question["question_key"]
            errors = []
            if not key:
                errors.append("question_key is required.")
            elif key in seen_keys:
                errors.append(f"duplicate question_key '{key}'.")
            else:
                seen_keys.add(key)
            question["languages"] = languages.pop(key, [])
            question["test_cases"] = test_cases.pop(key, [])
        if question_type == "mcq":
            errors = []
        candidates.append(
            {"row_number": row_number, "question": question, "errors": errors}
        )

    if question_type == "coding":
        for key in sorted(set(languages) | set(test_cases)):
            candidates.append(
                {
                    "row_number": None,
                    "question": {},
                    "errors": [f"Unknown question_key '{key}' in supporting PDF blocks."],
                }
            )

    if not candidates:
        raise ImportFileError(
            f"No {question_type.upper()} records were found. Use the labelled format shown on this page."
        )
    return candidates


def parse_question_file(upload, question_type):
    if question_type not in {"mcq", "coding"}:
        raise ImportFileError("Choose either MCQ or coding questions.")
    if upload.size > MAX_IMPORT_SIZE:
        raise ImportFileError("Files must be 10 MB or smaller.")
    suffix = upload.name.lower().rsplit(".", 1)[-1] if "." in upload.name else ""
    if suffix == "xlsx":
        candidates = _parse_workbook(upload, question_type)
    elif suffix == "pdf":
        candidates = _pdf_candidates(upload, question_type)
    else:
        raise ImportFileError("Choose an .xlsx or text-based .pdf file.")
    if not candidates:
        raise ImportFileError("The file contains no question records.")
    if len(candidates) > MAX_IMPORT_RECORDS:
        raise ImportFileError(
            f"Files may contain at most {MAX_IMPORT_RECORDS} question records."
        )
    return candidates


def build_import_template(question_type):
    workbook = Workbook()
    if question_type == "mcq":
        sheet = workbook.active
        sheet.title = "MCQ"
        headers = list(MCQ_HEADERS)
        for number in range(1, MAX_OPTIONS + 1):
            headers.extend((f"option_{number}", f"option_{number}_correct"))
        sheet.append(headers)
        instructions = workbook.create_sheet("Instructions")
        instructions.append(["MCQ import template"])
        instructions.append(
            ["Add one question per row on the MCQ sheet; remove no header columns."]
        )
        instructions.append(
            ["Use regular/programming, aptitude/quant/reasoning/verbal/programming, and easy/medium/hard."]
        )
        instructions.append(
            ["Add at least two options. Programming language is optional except for programming MCQs."]
        )
        instructions.append(
            ["Set allow_multiple to true when more than one answer is correct; mark each correct option true."]
        )
    else:
        sheet = workbook.active
        sheet.title = "Coding"
        sheet.append(CODING_HEADERS)
        language_sheet = workbook.create_sheet("Languages")
        language_sheet.append(LANGUAGE_HEADERS)
        cases_sheet = workbook.create_sheet("TestCases")
        cases_sheet.append(TEST_CASE_HEADERS)
        instructions = workbook.create_sheet("Instructions")
        instructions.append(["Coding question import template"])
        instructions.append(["Add one question per row on the Coding sheet."])
        instructions.append(["Use the same unique question_key on related Languages and TestCases rows."])
        instructions.append(["Use scratch, complete, or fix for coding_mode."])
        instructions.append(["Complete/fix questions require a code_snippet for every language."])
        instructions.append(["Use an active executable programming-language name."])
        instructions.append(
            [
                "Example question",
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
        instructions.append(
            ["Example language", "sum-two", "Python", ""]
        )
        instructions.append(
            ["Example test case", "sum-two", "2 3", "5", "true", 1, ""]
        )

    output = BytesIO()
    workbook.save(output)
    workbook.close()
    output.seek(0)
    return output


def _form_errors(form, label):
    errors = form.errors
    if hasattr(errors, "values"):
        field_errors = [
            f"{form.fields[field].label}: {error}"
            if field in form.fields
            else error
            for field, values in errors.items()
            for error in values
        ]
    else:
        field_errors = []
        for form_instance, form_errors in zip(form.forms, errors):
            field_errors.extend(
                f"{form_instance.fields[field].label}: {error}"
                if field in form_instance.fields
                else error
                for field, values in form_errors.items()
                for error in values
            )
    return [f"{label}: {error}" for error in field_errors] + [
        f"{label}: {error}" for error in form.non_field_errors()
    ]


def _language_by_name(name, *, coding=False):
    queryset = ProgrammingLanguage.objects.filter(
        name__iexact=name,
        is_active=True,
    )
    if coding:
        queryset = queryset.filter(is_judge0_executable=True)
    return queryset.order_by("pk").first()


def _mcq_formset_data(options):
    data = {
        "form-TOTAL_FORMS": str(len(options)),
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": str(max(len(options), 1)),
    }
    for index, option in enumerate(options):
        data[f"form-{index}-text"] = option.get("text", "")
        data[f"form-{index}-is_correct"] = (
            "on" if option.get("is_correct") else ""
        )
    return data


def _coding_formset_data(question, question_data):
    mode = question_data["coding_mode"]
    languages = question_data["languages"]
    language_data = {
        "languages-TOTAL_FORMS": str(len(languages)),
        "languages-INITIAL_FORMS": "0",
        "languages-MIN_NUM_FORMS": "0",
        "languages-MAX_NUM_FORMS": str(max(len(languages), 1)),
    }
    errors = []
    for index, row in enumerate(languages):
        language = _language_by_name(row["language"], coding=True)
        if language is None:
            errors.append(
                f"Language row {row.get('row_number') or index + 1}: "
                f"'{row['language']}' is not an active supported coding language."
            )
            continue
        if mode != CodingQuestion.CodingMode.SCRATCH and not row["code_snippet"]:
            errors.append(
                f"Language row {row.get('row_number') or index + 1}: "
                "a code snippet is required for this coding mode."
            )
            continue
        language_data[f"languages-{index}-language"] = str(language.pk)
        language_data[f"languages-{index}-starter_code"] = (
            row["code_snippet"] if mode == CodingQuestion.CodingMode.COMPLETE else ""
        )
        language_data[f"languages-{index}-buggy_code"] = (
            row["code_snippet"] if mode == CodingQuestion.CodingMode.FIX else ""
        )

    if errors:
        return None, None, errors

    language_formset = CodingQuestionLanguageFormSet(
        data=language_data,
        instance=question,
        prefix="languages",
    )
    language_valid = language_formset.is_valid()
    errors.extend(_form_errors(language_formset, "Languages") if not language_valid else [])

    cases = question_data["test_cases"]
    case_data = {
        "test-cases-TOTAL_FORMS": str(len(cases)),
        "test-cases-INITIAL_FORMS": "0",
        "test-cases-MIN_NUM_FORMS": "0",
        "test-cases-MAX_NUM_FORMS": str(max(len(cases), 1)),
    }
    for index, row in enumerate(cases):
        case_data[f"test-cases-{index}-input_data"] = row["input_data"]
        case_data[f"test-cases-{index}-expected_output"] = row["expected_output"]
        case_data[f"test-cases-{index}-is_sample"] = (
            "on" if row["is_sample"].lower() in {"1", "true", "yes", "y"} else ""
        )
        case_data[f"test-cases-{index}-weight"] = row["weight"] or "1"
        case_data[f"test-cases-{index}-position"] = str(index + 1)
        case_data[f"test-cases-{index}-explanation"] = row["explanation"]

    case_formset = CodingTestCaseFormSet(
        data=case_data,
        instance=question,
        prefix="test-cases",
    )
    case_valid = case_formset.is_valid()
    errors.extend(_form_errors(case_formset, "Test cases") if not case_valid else [])
    if not language_valid or not case_valid:
        return None, None, errors
    return language_formset, case_formset, errors


@transaction.atomic
def import_question_candidates(
    candidates,
    question_type,
    owner,
    *,
    assessment=None,
    section=None,
):
    if assessment is not None:
        assessment = Assessment.objects.select_for_update().get(pk=assessment.pk)
    if section is not None:
        section = AssessmentSection.objects.select_for_update().get(
            pk=section.pk,
            assessment=assessment,
        )

    imported = []
    skipped = []
    for candidate in candidates:
        row_number = candidate.get("row_number")
        row_label = f"Record {row_number}" if row_number is not None else "Supporting data"
        errors = list(candidate.get("errors", []))
        question_data = candidate.get("question", {})
        if errors:
            skipped.append({"record": row_label, "errors": errors})
            continue

        if question_type == "mcq":
            programming_mcq = (
                question_data.get("question_type")
                == McqQuestion.QuestionType.PROGRAMMING
            )
            language_name = question_data.get("programming_language", "")
            language = (
                _language_by_name(language_name) if programming_mcq or language_name else None
            )
            if programming_mcq and language is None:
                errors.append(
                    "Programming language is required and must be an active language."
                )
            elif language_name and language is None:
                errors.append("Programming language is not active or was not found.")
            question_form_data = {
                field: question_data.get(field, "")
                for field in (
                    "title",
                    "question_type",
                    "category",
                    "topic",
                    "sub_topic",
                    "difficulty",
                    "statement",
                    "explanation",
                )
            }
            question_form_data["allow_multiple"] = (
                "on"
                if question_data.get("allow_multiple", "").lower()
                in {"1", "true", "yes", "y"}
                else ""
            )
            question_form_data["programming_language"] = str(language.pk) if language else ""
            question_form = McqQuestionForm(data=question_form_data)
            if not question_form.is_valid():
                errors.extend(_form_errors(question_form, "Question"))

            option_formset = McqOptionFormSet(
                data=_mcq_formset_data(question_data.get("options", [])),
                instance=question_form.instance,
            )
            if not option_formset.is_valid():
                errors.extend(_form_errors(option_formset, "Options"))

            if errors:
                skipped.append({"record": row_label, "errors": errors})
                continue

            with transaction.atomic():
                question = question_form.save(commit=False)
                question.owner = owner
                question.save()
                option_formset.instance = question
                option_formset.save()
        else:
            question_form_data = {
                field: question_data.get(field, "")
                for field in (
                    "title",
                    "coding_mode",
                    "topic",
                    "subtopic",
                    "difficulty",
                    "statement",
                    "input_format",
                    "output_format",
                    "constraints_text",
                    "explanation",
                )
            }
            question_form_data["time_limit_seconds"] = (
                question_data.get("time_limit_seconds") or "2"
            )
            question_form_data["memory_limit_kb"] = (
                question_data.get("memory_limit_kb") or "262144"
            )
            question_form_data["is_active"] = "on"
            question_form = CodingQuestionForm(data=question_form_data)
            if not question_form.is_valid():
                errors.extend(_form_errors(question_form, "Question"))
            language_formset, case_formset, formset_errors = _coding_formset_data(
                question_form.instance,
                question_data,
            )
            errors.extend(formset_errors)
            if errors:
                skipped.append({"record": row_label, "errors": errors})
                continue

            with transaction.atomic():
                question = question_form.save(commit=False)
                question.owner = owner
                question.save()
                language_formset.instance = question
                case_formset.instance = question
                language_formset.save()
                case_formset.save()

        if assessment is not None:
            target_section = section
            if target_section is None:
                target_section, _ = AssessmentSection.objects.get_or_create(
                    assessment=assessment,
                    position=1,
                    defaults={"title": "Questions"},
                )
            target_section = AssessmentSection.objects.select_for_update().get(
                pk=target_section.pk,
                assessment=assessment,
            )
            last_position = target_section.questions.aggregate(
                last_position=Max("position")
            )["last_position"]
            question_field = (
                "mcq_question" if question_type == "mcq" else "coding_question"
            )
            AssessmentQuestion.objects.create(
                assessment=assessment,
                section=target_section,
                position=(last_position or 0) + 1,
                max_score=1,
                negative_marks=0,
                **{question_field: question},
            )
        imported.append(question)
    return imported, skipped
