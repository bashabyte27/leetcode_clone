import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import AcademicSession, AcademicYear, CollegeMembership, Department, Section
from .services import create_faculty, create_student

User = get_user_model()


@dataclass
class BulkImportRow:
    row_number: int
    raw: Dict[str, Any]
    valid: bool = False
    errors: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BulkImportPreview:
    import_type: str
    college: Any
    rows: List[BulkImportRow]
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    errors_count: int
    is_valid: bool
    row_errors: Dict[int, List[str]] = field(default_factory=dict)

    @property
    def valid_rows(self):
        return [row for row in self.rows if row.valid]


def _normalise_row(row):
    cleaned = {}
    for key, value in row.items():
        normalised_key = (key or "").strip().lower().replace(" ", "_")
        cleaned[normalised_key] = (value or "").strip()
    return cleaned


def _header_aliases(import_type):
    if import_type == "STUDENT":
        return {
            "name": "name",
            "email": "email",
            "roll_number": "roll_number",
            "roll_no": "roll_number",
            "member_number": "roll_number",
            "department": "department",
            "academic_year": "academic_year",
            "section": "section",
            "academic_session": "academic_session",
        }
    if import_type == "FACULTY":
        return {
            "name": "name",
            "email": "email",
            "member_number": "member_number",
            "employee_id": "member_number",
            "employeeid": "member_number",
            "department": "department",
        }
    raise ValueError(f"Unsupported import type: {import_type}")


def _normalise_headers(fieldnames):
    aliases = {}
    for name in fieldnames or []:
        key = (name or "").strip().lower().replace(" ", "_")
        aliases[key] = key
    return aliases


def _read_csv(file_obj, import_type):
    if file_obj is None:
        raise ValueError("CSV file is required.")

    try:
        text = file_obj.read()
    except Exception as exc:
        raise ValueError(f"Unable to read CSV: {exc}") from exc

    if not text or not text.strip():
        raise ValueError("CSV file is empty.")

    if hasattr(file_obj, "seek"):
        file_obj.seek(0)

    if "\x00" in text[:2048]:
        raise ValueError("CSV file contains invalid binary data.")

    try:
        reader = csv.DictReader(io.StringIO(text))
    except Exception as exc:
        raise ValueError(f"CSV parse failed: {exc}") from exc

    if reader.fieldnames is None:
        raise ValueError("CSV file is missing headers.")

    normalized_headers = _normalise_headers(reader.fieldnames)
    aliases = _header_aliases(import_type)
    expected = list(aliases.keys())
    required = [value for value in expected if value in normalized_headers]
    missing = [name for name in required if name not in normalized_headers]
    if missing:
        raise ValueError(f"Missing required headers: {', '.join(missing)}")

    rows = []
    for row_number, row in enumerate(reader, start=2):
        rows.append((row_number, _normalise_row(row)))
    return rows


def _validate_email(value):
    if not value:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()))


def _resolve_department(college, raw_name):
    if not raw_name:
        return None
    lookup = raw_name.strip()
    return (
        Department.objects.filter(college=college, code__iexact=lookup).first()
        or Department.objects.filter(college=college, name__iexact=lookup).first()
    )


def _parse_year(raw_year):
    if raw_year is None:
        return None
    value = str(raw_year).strip()
    if not value:
        return None
    match = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?$", value, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    if re.fullmatch(r"\d+", value):
        return int(value)
    return None


def _resolve_academic_year(department, raw_year):
    year_number = _parse_year(raw_year)
    if year_number is None:
        return None
    return AcademicYear.objects.filter(department=department, year_number=year_number).first()


def _resolve_section(academic_year, raw_name):
    if not raw_name:
        return None
    lookup = raw_name.strip()
    return (
        Section.objects.filter(academic_year=academic_year, name__iexact=lookup).first()
        or Section.objects.filter(academic_year=academic_year, code__iexact=lookup).first()
    )


def _resolve_academic_session(college, raw_name):
    if not raw_name:
        return None
    return AcademicSession.objects.filter(college=college, name__iexact=raw_name.strip()).first()


def validate_bulk_import(file_obj, *, import_type, college):
    try:
        csv_rows = _read_csv(file_obj, import_type)
    except ValueError as exc:
        return BulkImportPreview(
            import_type=import_type,
            college=college,
            rows=[],
            total_rows=0,
            valid_rows_count=0,
            invalid_rows_count=0,
            errors_count=1,
            is_valid=False,
            row_errors={0: [str(exc)]},
        )

    rows: List[BulkImportRow] = []
    seen_emails: Dict[str, int] = {}

    for row_number, row in csv_rows:
        bulk_row = BulkImportRow(row_number=row_number, raw=row)
        errors: List[str] = []

        if not row or not any((value or "").strip() for value in row.values()):
            errors.append("Row is empty.")
            bulk_row.errors = errors
            rows.append(bulk_row)
            continue

        name = row.get("name", "")
        email = row.get("email", "")
        if not name:
            errors.append("Name is required.")
        if not _validate_email(email):
            errors.append("Valid email is required.")
        else:
            normalized = email.strip().lower()
            if normalized in seen_emails:
                errors.append(f"Duplicate email appears in rows {seen_emails[normalized]} and {row_number}.")
            else:
                seen_emails[normalized] = row_number

        if import_type == "STUDENT":
            department_name = row.get("department", "")
            academic_year_value = row.get("academic_year", "")
            section_name = row.get("section", "")
            session_name = row.get("academic_session", "")
            member_number = row.get("roll_number") or row.get("member_number") or ""

            department = _resolve_department(college, department_name)
            year_obj = None
            section_obj = None
            session_obj = None

            if not department:
                errors.append(f"Department '{department_name}' does not exist in this college.")
            else:
                year_obj = _resolve_academic_year(department, academic_year_value)
                if not year_obj:
                    errors.append(f"Academic year '{academic_year_value}' does not exist for department '{department.code}'.")
                else:
                    section_obj = _resolve_section(year_obj, section_name)
                    if not section_obj:
                        errors.append(f"Section '{section_name}' does not belong to {department.code} {year_obj.name}.")

                    session_obj = _resolve_academic_session(college, session_name)
                    if not session_obj:
                        errors.append(f"Academic session '{session_name}' does not exist in this college.")
                    elif section_obj and session_obj.college_id != section_obj.academic_year.department.college_id:
                        errors.append("Section and academic session must belong to the same college.")

            if not member_number:
                errors.append("Roll number is required.")
            elif CollegeMembership.objects.filter(college=college, member_number=member_number).exists():
                errors.append(f"Member number '{member_number}' already exists in this college.")

            if email and CollegeMembership.objects.filter(user__email__iexact=email, college=college).exists():
                errors.append("Email already has a membership in this college.")

            if not errors and department and year_obj and section_obj and session_obj:
                bulk_row.valid = True
                bulk_row.payload = {
                    "name": name,
                    "email": email.strip(),
                    "member_number": member_number,
                    "department": department,
                    "academic_year": year_obj,
                    "section": section_obj,
                    "academic_session": session_obj,
                }

        elif import_type == "FACULTY":
            department_name = row.get("department", "")
            member_number = row.get("member_number") or row.get("employee_id") or ""

            department = _resolve_department(college, department_name)
            if not department:
                errors.append(f"Department '{department_name}' does not exist in this college.")

            if not member_number:
                errors.append("Employee ID is required.")
            elif CollegeMembership.objects.filter(college=college, member_number=member_number).exists():
                errors.append(f"Member number '{member_number}' already exists in this college.")

            if email and CollegeMembership.objects.filter(user__email__iexact=email, college=college).exists():
                errors.append("Email already has a membership in this college.")

            if not errors and department:
                bulk_row.valid = True
                bulk_row.payload = {
                    "name": name,
                    "email": email.strip(),
                    "member_number": member_number,
                    "department": department,
                }

        bulk_row.errors = errors
        rows.append(bulk_row)

    invalid_rows = [row for row in rows if not row.valid]
    valid_rows = [row for row in rows if row.valid]
    preview = BulkImportPreview(
        import_type=import_type,
        college=college,
        rows=rows,
        total_rows=len(rows),
        valid_rows_count=len(valid_rows),
        invalid_rows_count=len(invalid_rows),
        errors_count=sum(len(row.errors) for row in rows if row.errors),
        is_valid=(len(invalid_rows) == 0 and bool(rows)),
        row_errors={row.row_number: row.errors for row in rows if row.errors},
    )
    return preview


def import_bulk_records(preview: BulkImportPreview):
    if not preview.is_valid:
        return {"success": False, "message": "Import blocked: validation failed.", "records": 0}

    created_users = 0
    reused_users = 0
    memberships = 0
    assignments = 0

    try:
        with transaction.atomic():
            for row in preview.valid_rows:
                payload = row.payload
                email = payload["email"]
                user = User.objects.filter(email__iexact=email).first()
                if user is None:
                    user_name = payload["name"].strip().lower().replace(" ", "_")
                    if not user_name:
                        user_name = f"user_{email.split('@')[0]}"
                    if User.objects.filter(user_name__iexact=user_name).exists():
                        user_name = f"{user_name}_{abs(hash(email)) % 100000}"
                    user = User.objects.create_user(
                        email=email,
                        user_name=user_name,
                        password="TempPass123!",
                        is_verified=True,
                    )
                    created_users += 1
                else:
                    reused_users += 1

                if preview.import_type == "STUDENT":
                    existing_membership = CollegeMembership.objects.filter(user=user, college=preview.college).first()
                    if existing_membership:
                        raise ValidationError(f"User {email} already has a membership in this college.")
                    create_student(
                        email=user.email,
                        user_name=user.user_name,
                        password="TempPass123!",
                        college=preview.college,
                        department=payload["department"],
                        member_number=payload["member_number"],
                        academic_session=payload["academic_session"],
                        section=payload["section"],
                        home_department=payload["department"],
                        user=user,
                    )
                    memberships += 1
                    assignments += 1
                elif preview.import_type == "FACULTY":
                    existing_membership = CollegeMembership.objects.filter(user=user, college=preview.college).first()
                    if existing_membership:
                        raise ValidationError(f"User {email} already has a membership in this college.")
                    create_faculty(
                        email=user.email,
                        user_name=user.user_name,
                        password="TempPass123!",
                        college=preview.college,
                        department=payload["department"],
                        member_number=payload["member_number"],
                        user=user,
                    )
                    memberships += 1
    except Exception as exc:
        return {"success": False, "message": f"Import failed and rolled back: {exc}", "records": 0}

    return {
        "success": True,
        "message": "Import completed successfully.",
        "total_rows": preview.total_rows,
        "successfully_imported": preview.valid_rows_count,
        "new_global_users_created": created_users,
        "existing_global_users_reused": reused_users,
        "memberships_created": memberships,
        "student_assignments_created": assignments,
        "skipped_rows": 0,
    }
