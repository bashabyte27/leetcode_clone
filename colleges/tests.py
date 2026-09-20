from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.models import ProtectedError
from django.test import TestCase
from datetime import date, timedelta
from django.utils import timezone
from .models import AcademicSession,StudentAcademicAssignment

from .models import (
    MAX_YEAR_NUMBER,
    AcademicYear,
    College,
    CollegeMembership,
    Department,
    Section,
)
User = get_user_model()


def make_user(n):
    # Matches your users.Users model: login is email, user_name is required.
    # No password given, so no slow password hashing in tests.
    return User.objects.create_user(
        email=f"user{n}@example.com",
        user_name=f"user{n}",
    )


def make_college(code="ABC", slug=None, name=None):
    return College.objects.create(
        name=name or f"{code} College",
        code=code,
        slug=slug or f"{code.lower()}-college",
    )


def make_dept(college, code="CSE", name="Computer Science"):
    return Department.objects.create(college=college, code=code, name=name)

def make_year(department, year_number=1, **extra):
    return AcademicYear.objects.create(
        department=department, year_number=year_number, **extra
    )


def make_section(academic_year, name="A", **extra):
    return Section.objects.create(academic_year=academic_year, name=name, **extra)


class CollegeTests(TestCase):
    # 1. College creation
    def test_college_creation(self):
        user = make_user(1)
        college = College.objects.create(
            name="ABC College",
            code="ABC",
            slug="abc-college",
            contact_email="info@abc.edu",
            city="Hyderabad",
            state="Telangana",
            created_by=user,
        )
        college.refresh_from_db()
        self.assertEqual(college.status, College.Status.ACTIVE)
        self.assertEqual(college.created_by, user)
        self.assertIsNotNone(college.id)
        self.assertIsNotNone(college.created_at)
        self.assertEqual(str(college), "ABC College (ABC)")

    def test_code_and_slug_are_normalised(self):
        college = College.objects.create(
            name="  ABC College ", code=" abc ", slug="ABC-College"
        )
        self.assertEqual(college.name, "ABC College")
        self.assertEqual(college.code, "ABC")
        self.assertEqual(college.slug, "abc-college")

    # 2. Code globally unique
    def test_code_must_be_globally_unique(self):
        make_college("ABC", slug="abc-one")
        with self.assertRaises(IntegrityError), transaction.atomic():
            College.objects.create(name="Other", code="ABC", slug="abc-two")

    def test_code_uniqueness_ignores_case(self):
        make_college("ABC", slug="abc-one")
        with self.assertRaises(IntegrityError), transaction.atomic():
            College.objects.create(name="Other", code="abc", slug="abc-two")

    # 3. Slug globally unique
    def test_slug_must_be_globally_unique(self):
        make_college("ABC", slug="same-slug")
        with self.assertRaises(IntegrityError), transaction.atomic():
            College.objects.create(name="Other", code="XYZ", slug="same-slug")

    def test_created_by_set_null_when_user_deleted(self):
        user = make_user(1)
        college = College.objects.create(
            name="ABC", code="ABC", slug="abc", created_by=user
        )
        user.delete()
        college.refresh_from_db()
        self.assertIsNone(college.created_by)

    def test_college_with_departments_cannot_be_deleted(self):
        college = make_college("ABC")
        make_dept(college)
        with self.assertRaises(ProtectedError):
            college.delete()


class DepartmentTests(TestCase):
    # 4. Department belongs to College
    def test_department_belongs_to_college(self):
        college = make_college("ABC")
        dept = make_dept(college)
        self.assertEqual(dept.college, college)
        self.assertIn(dept, college.departments.all())
        self.assertEqual(dept.status, Department.Status.ACTIVE)

    # 5. Same code in different colleges
    def test_same_code_allowed_in_different_colleges(self):
        d1 = make_dept(make_college("ABC"), code="CSE")
        d2 = make_dept(make_college("XYZ"), code="CSE")
        self.assertNotEqual(d1.college, d2.college)
        self.assertEqual(d1.code, d2.code)

    # 6. Duplicate code in same college
    def test_duplicate_code_in_same_college_rejected(self):
        college = make_college("ABC")
        make_dept(college, code="CSE", name="Computer Science")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_dept(college, code="cse", name="Another Name")

    # 7. Duplicate name in same college
    def test_duplicate_name_in_same_college_rejected(self):
        college = make_college("ABC")
        make_dept(college, code="CSE", name="Computer Science")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_dept(college, code="CS2", name="Computer Science")

    def test_same_name_allowed_in_different_colleges(self):
        make_dept(make_college("ABC"), code="CSE", name="Computer Science")
        make_dept(make_college("XYZ"), code="CSE", name="Computer Science")
        self.assertEqual(Department.objects.count(), 2)


class CollegeMembershipTests(TestCase):
    # 8. User can have a membership
    def test_user_can_have_membership(self):
        user, college = make_user(1), make_college("ABC")
        m = CollegeMembership.objects.create(
            user=user, college=college, role=CollegeMembership.Role.STUDENT
        )
        self.assertIsInstance(m.pk, int)
        self.assertEqual(m.status, CollegeMembership.Status.INVITED)
        self.assertIn(m, user.college_memberships.all())
        self.assertIn(m, college.memberships.all())

    # 9. Same user, same college: not allowed
    def test_same_user_cannot_have_two_memberships_in_same_college(self):
        user, college = make_user(1), make_college("ABC")
        CollegeMembership.objects.create(
            user=user, college=college, role=CollegeMembership.Role.STUDENT
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CollegeMembership.objects.create(
                user=user, college=college, role=CollegeMembership.Role.FACULTY
            )

    # 10. Same user, two colleges: allowed
    def test_same_user_can_belong_to_two_colleges(self):
        user = make_user(1)
        for code in ("ABC", "XYZ"):
            CollegeMembership.objects.create(
                user=user, college=make_college(code),
                role=CollegeMembership.Role.STUDENT,
            )
        self.assertEqual(user.college_memberships.count(), 2)

    # 11. member_number can repeat across colleges
    def test_member_number_can_repeat_across_colleges(self):
        c1, c2 = make_college("ABC"), make_college("XYZ")
        CollegeMembership.objects.create(
            user=make_user(1), college=c1,
            role=CollegeMembership.Role.STUDENT, member_number="24CSE001",
        )
        CollegeMembership.objects.create(
            user=make_user(2), college=c2,
            role=CollegeMembership.Role.STUDENT, member_number="24CSE001",
        )
        self.assertEqual(CollegeMembership.objects.filter(member_number="24CSE001").count(), 2)

    # 12. member_number cannot repeat inside one college
    def test_member_number_cannot_repeat_within_college(self):
        college = make_college("ABC")
        CollegeMembership.objects.create(
            user=make_user(1), college=college,
            role=CollegeMembership.Role.STUDENT, member_number="24CSE001",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CollegeMembership.objects.create(
                user=make_user(2), college=college,
                role=CollegeMembership.Role.STUDENT, member_number="24CSE001",
            )

    def test_blank_member_numbers_are_allowed_many_times(self):
        college = make_college("ABC")
        for n, blank in ((1, None), (2, ""), (3, "  ")):
            m = CollegeMembership.objects.create(
                user=make_user(n), college=college,
                role=CollegeMembership.Role.FACULTY, member_number=blank,
            )
            self.assertIsNone(m.member_number)

    def test_home_department_must_belong_to_same_college(self):
        college_a, college_b = make_college("AAA"), make_college("BBB")
        dept_b = make_dept(college_b)
        m = CollegeMembership(
            user=make_user(1), college=college_a,
            role=CollegeMembership.Role.STUDENT, home_department=dept_b,
        )
        with self.assertRaises(ValidationError):
            m.full_clean()
        with self.assertRaises(ValidationError):
            m.save()

    def test_home_department_same_college_is_accepted(self):
        college = make_college("ABC")
        dept = make_dept(college)
        m = CollegeMembership.objects.create(
            user=make_user(1), college=college,
            role=CollegeMembership.Role.STUDENT, home_department=dept,
        )
        self.assertEqual(m.home_department, dept)

    def test_home_department_set_null_when_department_deleted(self):
        college = make_college("ABC")
        dept = make_dept(college)
        m = CollegeMembership.objects.create(
            user=make_user(1), college=college,
            role=CollegeMembership.Role.STUDENT, home_department=dept,
        )
        dept.delete()
        m.refresh_from_db()
        self.assertIsNone(m.home_department)


class UserModelUnchangedTests(TestCase):
    # 13. Existing User model is not modified
    def test_user_has_no_fields_pointing_to_college_models(self):
        college_models = (College, Department, CollegeMembership)
        for field in User._meta.concrete_fields:
            self.assertNotIn(field.related_model, college_models, field.name)
            self.assertFalse(field.name.startswith("college"), field.name)
        self.assertNotEqual(User._meta.app_label, "colleges")

    def test_users_migrations_do_not_depend_on_colleges(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        for (app_label, name), migration in loader.disk_migrations.items():
            if app_label == User._meta.app_label:
                for dep_app, _dep_name in migration.dependencies:
                    self.assertNotEqual(
                        dep_app, "colleges", f"{app_label}.{name} depends on colleges"
                    )

class AcademicYearTests(TestCase):
    def setUp(self):
        self.college = make_college("ABC")
        self.cse = make_dept(self.college, code="CSE", name="Computer Science")
        self.ece = make_dept(self.college, code="ECE", name="Electronics")

    # 1. Create academic year for department
    def test_create_academic_year_for_department(self):
        year = AcademicYear.objects.create(
            department=self.cse, name="2nd Year", year_number=2
        )
        year.refresh_from_db()
        self.assertEqual(year.department, self.cse)
        self.assertEqual(year.name, "2nd Year")
        self.assertEqual(year.year_number, 2)
        self.assertEqual(year.status, AcademicYear.Status.ACTIVE)
        self.assertIsNotNone(year.id)
        self.assertEqual(str(year), "ABC / CSE / 2nd Year")

    def test_blank_name_is_filled_from_year_number(self):
        names = {n: make_year(self.cse, n).name for n in (1, 2, 3, 4)}
        self.assertEqual(
            names, {1: "1st Year", 2: "2nd Year", 3: "3rd Year", 4: "4th Year"}
        )

    # 2. Same department cannot repeat a year_number
    def test_same_department_cannot_have_duplicate_year_number(self):
        make_year(self.cse, 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_year(self.cse, 2, name="Second Year")

    # 3. Different departments can use the same year_number
    def test_different_departments_can_have_same_year_number(self):
        make_year(self.cse, 2)
        make_year(self.ece, 2)
        other_college_dept = make_dept(make_college("XYZ"), code="CSE")
        make_year(other_college_dept, 2)
        self.assertEqual(AcademicYear.objects.filter(year_number=2).count(), 3)

    # 4. Belongs to the correct department
    def test_academic_year_belongs_to_correct_department(self):
        year = make_year(self.cse, 1)
        make_year(self.ece, 1)
        self.assertEqual(year.department, self.cse)
        self.assertEqual(list(self.cse.academic_years.all()), [year])
        self.assertEqual(self.ece.academic_years.count(), 1)

    # 5. Status
    def test_status_works(self):
        year = make_year(self.cse, 1)
        self.assertEqual(year.status, AcademicYear.Status.ACTIVE)
        year.status = AcademicYear.Status.INACTIVE
        year.save()
        self.assertEqual(
            AcademicYear.objects.filter(status=AcademicYear.Status.INACTIVE).count(), 1
        )
        self.assertEqual(
            AcademicYear.objects.filter(status=AcademicYear.Status.ACTIVE).count(), 0
        )
        year.status = "ARCHIVED"  # not a valid choice for this model
        with self.assertRaises(ValidationError):
            year.full_clean()

    # 6. Invalid year_number
    def test_invalid_year_number_is_rejected(self):
        for bad in (0, -1, MAX_YEAR_NUMBER + 1, None):
            with self.subTest(year_number=bad):
                with self.assertRaises(ValidationError):
                    AcademicYear.objects.create(department=self.cse, year_number=bad)
        self.assertEqual(AcademicYear.objects.count(), 0)

    def test_invalid_year_number_is_reported_by_full_clean(self):
        with self.assertRaises(ValidationError) as ctx:
            AcademicYear(department=self.cse, year_number=0).full_clean()
        self.assertIn("year_number", ctx.exception.message_dict)

    def test_year_numbers_above_four_are_allowed_up_to_max(self):
        for n in range(1, MAX_YEAR_NUMBER + 1):
            make_year(self.cse, n)
        self.assertEqual(self.cse.academic_years.count(), MAX_YEAR_NUMBER)


class SectionTests(TestCase):
    def setUp(self):
        self.college = make_college("ABC")
        self.cse = make_dept(self.college, code="CSE", name="Computer Science")
        self.ece = make_dept(self.college, code="ECE", name="Electronics")
        self.cse_2 = make_year(self.cse, 2)
        self.cse_3 = make_year(self.cse, 3)
        self.ece_2 = make_year(self.ece, 2)

    # 7. Create section under academic year
    def test_create_section_under_academic_year(self):
        section = Section.objects.create(academic_year=self.cse_2, name="A")
        section.refresh_from_db()
        self.assertEqual(section.name, "A")
        self.assertEqual(section.code, "A")
        self.assertEqual(section.status, Section.Status.ACTIVE)
        self.assertIsNotNone(section.id)
        self.assertEqual(str(section), "ABC / CSE / 2nd Year / A")

    def test_code_can_be_given_and_is_uppercased(self):
        section = make_section(self.cse_2, name="Section A", code="a")
        self.assertEqual(section.name, "Section A")
        self.assertEqual(section.code, "A")

    # 8. Duplicate name in same academic year
    def test_duplicate_section_name_in_same_academic_year_rejected(self):
        make_section(self.cse_2, "A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_section(self.cse_2, "A")

    def test_duplicate_section_code_in_same_academic_year_rejected(self):
        make_section(self.cse_2, "A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_section(self.cse_2, name="Section A", code="A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_section(self.cse_2, "a")  # code becomes "A"

    # 9. Same name under different academic years
    def test_same_section_name_allowed_under_different_academic_years(self):
        make_section(self.cse_2, "A")
        make_section(self.cse_3, "A")
        self.assertEqual(Section.objects.filter(name="A").count(), 2)

    # 10. Same name for different departments (and colleges)
    def test_same_section_name_allowed_for_different_departments(self):
        make_section(self.cse_2, "A")
        make_section(self.ece_2, "A")
        other_year = make_year(make_dept(make_college("XYZ"), code="CSE"), 2)
        make_section(other_year, "A")
        self.assertEqual(Section.objects.filter(name="A").count(), 3)

    # 11. Belongs to the correct academic year
    def test_section_belongs_to_correct_academic_year(self):
        section = make_section(self.cse_2, "A")
        make_section(self.cse_3, "A")
        self.assertEqual(section.academic_year, self.cse_2)
        self.assertEqual(list(self.cse_2.sections.all()), [section])

    # 12. Status
    def test_status_works(self):
        section = make_section(self.cse_2, "A")
        self.assertEqual(section.status, Section.Status.ACTIVE)
        section.status = Section.Status.INACTIVE
        section.save()
        self.assertEqual(
            Section.objects.filter(status=Section.Status.INACTIVE).count(), 1
        )
        self.assertEqual(
            Section.objects.filter(status=Section.Status.ACTIVE).count(), 0
        )
        section.status = "ARCHIVED"  # not a valid choice for this model
        with self.assertRaises(ValidationError):
            section.full_clean()


class AcademicHierarchyTests(TestCase):
    def setUp(self):
        self.college_a = make_college("AAA")
        self.college_b = make_college("BBB")
        self.dept_a = make_dept(self.college_a, code="CSE", name="Computer Science")
        self.dept_b = make_dept(self.college_b, code="ECE", name="Electronics")
        self.year_a = make_year(self.dept_a, 2)
        self.year_b = make_year(self.dept_b, 3)
        self.section_a = make_section(self.year_a, "A")
        self.section_b = make_section(self.year_b, "B")

    # 13. Section -> AcademicYear -> Department -> College
    def test_section_chain_reaches_college(self):
        s = self.section_a
        self.assertEqual(s.academic_year, self.year_a)
        self.assertEqual(s.academic_year.department, self.dept_a)
        self.assertEqual(s.academic_year.department.college, self.college_a)
        self.assertEqual(s.department, self.dept_a)
        self.assertEqual(s.college, self.college_a)
        self.assertEqual(self.year_a.college, self.college_a)

    def test_sections_can_be_filtered_by_college(self):
        qs = Section.objects.filter(academic_year__department__college=self.college_a)
        self.assertEqual(list(qs), [self.section_a])

    # 14. A section cannot end up in another college
    def test_no_direct_college_field_on_year_or_section(self):
        for model in (AcademicYear, Section):
            names = {f.name for f in model._meta.get_fields()}
            self.assertNotIn("college", names)

    def test_section_cannot_move_to_academic_year_of_another_college(self):
        section = self.section_a
        section.academic_year = self.year_b
        with self.assertRaises(ValidationError) as ctx:
            section.full_clean()
        self.assertIn("academic_year", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            section.save()
        section.refresh_from_db()
        self.assertEqual(section.academic_year, self.year_a)

    def test_academic_year_cannot_move_to_department_of_another_college(self):
        year = self.year_a
        year.department = self.dept_b
        with self.assertRaises(ValidationError) as ctx:
            year.full_clean()
        self.assertIn("department", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            year.save()
        year.refresh_from_db()
        self.assertEqual(year.department, self.dept_a)

    def test_department_cannot_move_to_another_college(self):
        dept = self.dept_a
        dept.college = self.college_b
        with self.assertRaises(ValidationError) as ctx:
            dept.full_clean()
        self.assertIn("college", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            dept.save()
        dept.refresh_from_db()
        self.assertEqual(dept.college, self.college_a)

    def test_moving_inside_the_same_college_is_allowed(self):
        year_a3 = make_year(self.dept_a, 3)
        section = self.section_a
        section.academic_year = year_a3
        section.save()
        section.refresh_from_db()
        self.assertEqual(section.academic_year, year_a3)

    def test_normal_updates_are_not_blocked(self):
        self.dept_a.name = "Computer Science and Engineering"
        self.dept_a.save()
        self.year_a.status = AcademicYear.Status.INACTIVE
        self.year_a.save()
        self.section_a.name = "Alpha"
        self.section_a.code = "AL"
        self.section_a.save()
        self.section_a.refresh_from_db()
        self.assertEqual(self.section_a.code, "AL")

    def test_department_string_includes_college_code(self):
        self.assertEqual(str(self.dept_a), "AAA / CSE")

def make_session(college, name="2026-27", start=None, end=None, **extra):
    return AcademicSession.objects.create(
        college=college,
        name=name,
        start_date=start or date(2026, 6, 1),
        end_date=end or date(2027, 5, 31),
        **extra,
    )
 
 
def make_student(n, college, department, role=CollegeMembership.Role.STUDENT):
    return CollegeMembership.objects.create(
        user=make_user(n),
        college=college,
        role=role,
        home_department=department,
        status=CollegeMembership.Status.ACTIVE,
    )
 
 
def make_assignment(student, session, section, **extra):
    return StudentAcademicAssignment.objects.create(
        student_membership=student,
        academic_session=session,
        section=section,
        **extra,
    )
 
 
def message_list(exc, field):
    """All messages Django collected for one field of a ValidationError."""
    return exc.message_dict.get(field, [])
 
 
class AcademicSessionTests(TestCase):
    def setUp(self):
        self.college = make_college("ABC")
        self.other = make_college("XYZ")
 
    # 1. Can create session
    def test_can_create_session(self):
        session = AcademicSession.objects.create(
            college=self.college,
            name="2026-27",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
        )
        session.refresh_from_db()
        self.assertEqual(session.college, self.college)
        self.assertEqual(session.name, "2026-27")
        self.assertEqual(session.start_date, date(2026, 6, 1))
        self.assertEqual(session.end_date, date(2027, 5, 31))
        self.assertEqual(session.status, AcademicSession.Status.PLANNED)
        self.assertIsNotNone(session.id)
        self.assertIsNotNone(session.created_at)
        self.assertEqual(str(session), "ABC / 2026-27")
        self.assertIn(session, self.college.academic_sessions.all())
        session.full_clean()  # a valid session passes full validation
 
    def test_name_is_stripped_and_required(self):
        session = make_session(self.college, name="  2026-27  ")
        self.assertEqual(session.name, "2026-27")
        for blank in ("", "   "):
            with self.subTest(name=blank):
                with self.assertRaises(ValidationError) as ctx:
                    make_session(self.college, name=blank)
                self.assertIn("name", ctx.exception.message_dict)
 
    def test_dates_are_required(self):
        with self.assertRaises(ValidationError):
            AcademicSession.objects.create(
                college=self.college, name="X", start_date=None, end_date=date(2027, 1, 1)
            )
        with self.assertRaises(ValidationError):
            AcademicSession.objects.create(
                college=self.college, name="X", start_date=date(2026, 1, 1), end_date=None
            )
        with self.assertRaises(ValidationError) as ctx:
            AcademicSession(college=self.college, name="X").full_clean()
        self.assertIn("start_date", ctx.exception.message_dict)
        self.assertIn("end_date", ctx.exception.message_dict)
 
    # 2. Same college cannot have duplicate session name
    def test_duplicate_name_in_same_college_rejected(self):
        make_session(self.college, "2026-27")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_session(self.college, "2026-27")
 
    def test_duplicate_name_is_detected_after_stripping_spaces(self):
        make_session(self.college, "2026-27")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_session(self.college, "  2026-27 ")
 
    # 3. Different colleges can have the same session name
    def test_same_name_allowed_in_different_colleges(self):
        make_session(self.college, "2026-27")
        make_session(self.other, "2026-27")
        self.assertEqual(AcademicSession.objects.filter(name="2026-27").count(), 2)
 
    # 4. end_date must be after start_date
    def test_end_date_must_be_after_start_date(self):
        same_day = date(2026, 6, 1)
        cases = {
            "end before start": (date(2026, 6, 1), date(2026, 5, 31)),
            "end equals start": (same_day, same_day),
        }
        for label, (start, end) in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(ValidationError) as ctx:
                    make_session(self.college, "bad", start=start, end=end)
                self.assertIn("end_date", ctx.exception.message_dict)
                bad = AcademicSession(
                    college=self.college, name="bad", start_date=start, end_date=end
                )
                with self.assertRaises(ValidationError) as ctx:
                    bad.full_clean()
                self.assertIn("end_date", ctx.exception.message_dict)
        self.assertEqual(AcademicSession.objects.count(), 0)
 
    def test_database_also_rejects_bad_dates_when_validation_is_bypassed(self):
        # bulk_create() skips save()/clean(); the CHECK constraint still fires.
        bad = AcademicSession(
            college=self.college,
            name="bad",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 5, 1),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicSession.objects.bulk_create([bad])
 
    # 5. Status works
    def test_status_works(self):
        session = make_session(self.college)
        self.assertEqual(session.status, AcademicSession.Status.PLANNED)
        for status in (
            AcademicSession.Status.ACTIVE,
            AcademicSession.Status.COMPLETED,
            AcademicSession.Status.ARCHIVED,
            AcademicSession.Status.PLANNED,
        ):
            with self.subTest(status=status):
                session.status = status
                session.save()
                session.refresh_from_db()
                self.assertEqual(session.status, status)
        session.status = "PAUSED"  # not a valid choice
        with self.assertRaises(ValidationError):
            session.full_clean()
 
    # 6. At most one ACTIVE session per college
    def test_second_active_session_in_same_college_is_rejected_by_database(self):
        make_session(self.college, "2025-26", status=AcademicSession.Status.ACTIVE)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_session(self.college, "2026-27", status=AcademicSession.Status.ACTIVE)
        # also when an existing session is switched to ACTIVE
        planned = make_session(self.college, "2027-28")
        planned.status = AcademicSession.Status.ACTIVE
        with self.assertRaises(IntegrityError), transaction.atomic():
            planned.save()
 
    def test_second_active_session_is_reported_by_full_clean(self):
        make_session(self.college, "2025-26", status=AcademicSession.Status.ACTIVE)
        second = AcademicSession(
            college=self.college,
            name="2026-27",
            start_date=date(2026, 6, 1),
            end_date=date(2027, 5, 31),
            status=AcademicSession.Status.ACTIVE,
        )
        with self.assertRaises(ValidationError) as ctx:
            second.full_clean()
        self.assertIn("status", ctx.exception.message_dict)
 
    def test_editing_the_only_active_session_does_not_clash_with_itself(self):
        active = make_session(self.college, status=AcademicSession.Status.ACTIVE)
        active.end_date = date(2027, 6, 15)
        active.full_clean()
        active.save()
 
    def test_a_new_session_can_be_activated_after_the_old_one_is_completed(self):
        old = make_session(self.college, "2025-26", status=AcademicSession.Status.ACTIVE)
        new = make_session(self.college, "2026-27")
        old.status = AcademicSession.Status.COMPLETED
        old.save()
        new.status = AcademicSession.Status.ACTIVE
        new.full_clean()
        new.save()
        self.assertEqual(
            AcademicSession.objects.filter(
                college=self.college, status=AcademicSession.Status.ACTIVE
            ).count(),
            1,
        )
 
    def test_each_college_can_have_its_own_active_session(self):
        make_session(self.college, "2026-27", status=AcademicSession.Status.ACTIVE)
        make_session(self.other, "2026-27", status=AcademicSession.Status.ACTIVE)
        self.assertEqual(
            AcademicSession.objects.filter(status=AcademicSession.Status.ACTIVE).count(), 2
        )
 
    def test_many_non_active_sessions_are_allowed(self):
        make_session(self.college, "2023-24", status=AcademicSession.Status.ARCHIVED)
        make_session(self.college, "2024-25", status=AcademicSession.Status.COMPLETED)
        make_session(self.college, "2026-27", status=AcademicSession.Status.PLANNED)
        make_session(self.college, "2027-28", status=AcademicSession.Status.PLANNED)
        self.assertEqual(self.college.academic_sessions.count(), 4)
 
    def test_active_rule_still_enforced_by_database_on_queryset_update(self):
        make_session(self.college, "2025-26", status=AcademicSession.Status.ACTIVE)
        other = make_session(self.college, "2026-27")
        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicSession.objects.filter(pk=other.pk).update(
                status=AcademicSession.Status.ACTIVE
            )
 
    def test_session_cannot_move_to_another_college(self):
        session = make_session(self.college)
        session.college = self.other
        with self.assertRaises(ValidationError) as ctx:
            session.full_clean()
        self.assertIn("college", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            session.save()
        session.refresh_from_db()
        self.assertEqual(session.college, self.college)
 
    def test_college_with_sessions_cannot_be_deleted(self):
        make_session(self.college)
        with self.assertRaises(ProtectedError):
            self.college.delete()
 
 
class StudentAcademicAssignmentTests(TestCase):
    def setUp(self):
        # College ABC, fully built
        self.college = make_college("ABC")
        self.cse = make_dept(self.college, code="CSE", name="Computer Science")
        self.ece = make_dept(self.college, code="ECE", name="Electronics")
        self.cse_1 = make_year(self.cse, 1)
        self.cse_2 = make_year(self.cse, 2)
        self.ece_2 = make_year(self.ece, 2)
        self.cse_1_a = make_section(self.cse_1, "A")
        self.cse_2_a = make_section(self.cse_2, "A")
        self.cse_2_b = make_section(self.cse_2, "B")
        self.ece_2_a = make_section(self.ece_2, "A")
        self.s2025 = make_session(
            self.college, "2025-26", date(2025, 6, 1), date(2026, 5, 31)
        )
        self.s2026 = make_session(self.college, "2026-27")
        self.ahmed = make_student(1, self.college, self.cse)
 
        # College XYZ, fully built
        self.other = make_college("XYZ")
        self.other_cse = make_dept(self.other, code="CSE", name="Computer Science")
        self.other_year = make_year(self.other_cse, 2)
        self.other_section = make_section(self.other_year, "A")
        self.other_session = make_session(self.other, "2026-27")
 
    # 7. Valid student assignment can be created
    def test_valid_assignment_can_be_created(self):
        a = StudentAcademicAssignment(
            student_membership=self.ahmed,
            academic_session=self.s2026,
            section=self.cse_2_a,
        )
        a.full_clean()  # passes the whole validation path
        a.save()
        a.refresh_from_db()
        self.assertIsInstance(a.pk, int)
        self.assertEqual(a.student_membership, self.ahmed)
        self.assertEqual(a.academic_session, self.s2026)
        self.assertEqual(a.section, self.cse_2_a)
        self.assertEqual(a.status, StudentAcademicAssignment.Status.ACTIVE)
        self.assertIsNotNone(a.joined_at)
        self.assertIsNone(a.left_at)
        self.assertIn(a, self.ahmed.academic_assignments.all())
        self.assertIn(a, self.s2026.student_assignments.all())
        self.assertIn(a, self.cse_2_a.student_assignments.all())
 
    def test_college_department_and_year_are_derived_not_stored(self):
        a = make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        self.assertEqual(a.college, self.college)
        self.assertEqual(a.department, self.cse)
        self.assertEqual(a.academic_year, self.cse_2)
        names = {f.name for f in StudentAcademicAssignment._meta.get_fields()}
        for redundant in ("college", "department", "academic_year"):
            self.assertNotIn(redundant, names)
        qs = StudentAcademicAssignment.objects.filter(
            section__academic_year__department__college=self.college
        )
        self.assertEqual(list(qs), [a])
 
    # 8. Non-STUDENT membership cannot be assigned
    def test_non_student_membership_cannot_be_assigned(self):
        roles = (
            CollegeMembership.Role.FACULTY,
            CollegeMembership.Role.HOD,
            CollegeMembership.Role.COLLEGE_ADMIN,
        )
        for i, role in enumerate(roles):
            with self.subTest(role=role):
                member = make_student(10 + i, self.college, self.cse, role=role)
                bad = StudentAcademicAssignment(
                    student_membership=member,
                    academic_session=self.s2026,
                    section=self.cse_2_a,
                )
                with self.assertRaises(ValidationError) as ctx:
                    bad.full_clean()
                self.assertIn("student_membership", ctx.exception.message_dict)
                with self.assertRaises(ValidationError):
                    make_assignment(member, self.s2026, self.cse_2_a)
        self.assertEqual(StudentAcademicAssignment.objects.count(), 0)
 
    # 9. Student and AcademicSession must belong to same college
    def test_student_and_session_must_be_in_same_college(self):
        bad = StudentAcademicAssignment(
            student_membership=self.ahmed,        # ABC
            academic_session=self.other_session,  # XYZ
            section=self.cse_2_a,                 # ABC
        )
        with self.assertRaises(ValidationError) as ctx:
            bad.full_clean()
        self.assertIn("academic_session", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            bad.save()
        self.assertEqual(StudentAcademicAssignment.objects.count(), 0)
 
    # 10. Student and Section must belong to same college
    def test_student_and_section_must_be_in_same_college(self):
        bad = StudentAcademicAssignment(
            student_membership=self.ahmed,     # ABC
            academic_session=self.s2026,       # ABC
            section=self.other_section,        # XYZ
        )
        with self.assertRaises(ValidationError) as ctx:
            bad.full_clean()
        messages = message_list(ctx.exception, "section")
        self.assertTrue(any("same college as the student" in m for m in messages))
        with self.assertRaises(ValidationError):
            bad.save()
        self.assertEqual(StudentAcademicAssignment.objects.count(), 0)
 
    # 11. AcademicSession and Section must belong to same college
    def test_session_and_section_must_be_in_same_college(self):
        bad = StudentAcademicAssignment(
            student_membership=self.ahmed,     # ABC
            academic_session=self.other_session,  # XYZ
            section=self.cse_2_a,              # ABC
        )
        with self.assertRaises(ValidationError) as ctx:
            bad.full_clean()
        messages = message_list(ctx.exception, "section")
        self.assertTrue(
            any("same college as the academic session" in m for m in messages)
        )
 
    # 12. Student home_department must match section department
    def test_home_department_must_match_section_department(self):
        bad = StudentAcademicAssignment(
            student_membership=self.ahmed,   # home department CSE
            academic_session=self.s2026,
            section=self.ece_2_a,            # ECE, same college
        )
        with self.assertRaises(ValidationError) as ctx:
            bad.full_clean()
        messages = message_list(ctx.exception, "section")
        self.assertTrue(any("home department" in m for m in messages))
        with self.assertRaises(ValidationError):
            bad.save()
        self.assertEqual(StudentAcademicAssignment.objects.count(), 0)
 
    def test_student_without_home_department_cannot_be_assigned(self):
        no_dept = make_student(2, self.college, None)
        bad = StudentAcademicAssignment(
            student_membership=no_dept,
            academic_session=self.s2026,
            section=self.cse_2_a,
        )
        with self.assertRaises(ValidationError) as ctx:
            bad.full_clean()
        self.assertIn("student_membership", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            bad.save()
        # after the home department is set on the membership, it works
        no_dept.home_department = self.cse
        no_dept.save()
        make_assignment(no_dept, self.s2026, self.cse_2_a)
 
    # 13. Historical assignments are allowed
    def test_historical_assignments_are_allowed(self):
        first = make_assignment(
            self.ahmed, self.s2025, self.cse_1_a,
            status=StudentAcademicAssignment.Status.COMPLETED,
        )
        second = make_assignment(self.ahmed, self.s2026, self.cse_2_b)
        self.assertEqual(self.ahmed.academic_assignments.count(), 2)
        self.assertEqual(first.academic_year.year_number, 1)
        self.assertEqual(second.academic_year.year_number, 2)
        active = self.ahmed.academic_assignments.filter(
            status=StudentAcademicAssignment.Status.ACTIVE
        )
        self.assertEqual(list(active), [second])
 
    def test_section_transfer_inside_same_session_is_allowed(self):
        first = make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        first.status = StudentAcademicAssignment.Status.COMPLETED
        first.save()
        second = make_assignment(self.ahmed, self.s2026, self.cse_2_b)
        self.assertEqual(
            self.ahmed.academic_assignments.filter(academic_session=self.s2026).count(), 2
        )
        self.assertEqual(second.status, StudentAcademicAssignment.Status.ACTIVE)
 
    def test_many_non_active_rows_in_one_session_are_allowed(self):
        S = StudentAcademicAssignment.Status
        make_assignment(self.ahmed, self.s2026, self.cse_2_a, status=S.COMPLETED)
        make_assignment(self.ahmed, self.s2026, self.cse_2_b, status=S.TRANSFERRED)
        make_assignment(self.ahmed, self.s2026, self.cse_2_a, status=S.CANCELLED)
        make_assignment(self.ahmed, self.s2026, self.cse_2_b, status=S.ACTIVE)
        self.assertEqual(self.ahmed.academic_assignments.count(), 4)
 
    # 14. Two ACTIVE assignments for same student and session are not allowed
    def test_two_active_assignments_same_student_and_session_rejected(self):
        make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        # different section
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_assignment(self.ahmed, self.s2026, self.cse_2_b)
        # same section
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        self.assertEqual(self.ahmed.academic_assignments.count(), 1)
 
    def test_second_active_assignment_is_reported_by_full_clean(self):
        make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        second = StudentAcademicAssignment(
            student_membership=self.ahmed,
            academic_session=self.s2026,
            section=self.cse_2_b,
        )
        with self.assertRaises(ValidationError) as ctx:
            second.full_clean()
        self.assertIn("status", ctx.exception.message_dict)
 
    def test_reactivating_an_old_row_while_another_is_active_is_rejected(self):
        S = StudentAcademicAssignment.Status
        old = make_assignment(self.ahmed, self.s2026, self.cse_2_a, status=S.COMPLETED)
        make_assignment(self.ahmed, self.s2026, self.cse_2_b)
        old.status = S.ACTIVE
        with self.assertRaises(ValidationError):
            old.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            old.save()
 
    def test_editing_the_only_active_row_does_not_clash_with_itself(self):
        a = make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        a.section = self.cse_2_b
        a.full_clean()
        a.save()
        a.refresh_from_db()
        self.assertEqual(a.section, self.cse_2_b)
 
    def test_active_rule_still_enforced_by_database_when_validation_is_bypassed(self):
        make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        dup = StudentAcademicAssignment(
            student_membership=self.ahmed,
            academic_session=self.s2026,
            section=self.cse_2_b,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudentAcademicAssignment.objects.bulk_create([dup])
        S = StudentAcademicAssignment.Status
        done = make_assignment(self.ahmed, self.s2026, self.cse_2_b, status=S.COMPLETED)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudentAcademicAssignment.objects.filter(pk=done.pk).update(status=S.ACTIVE)
 
    # 15. Same student can have different assignments in different sessions
    def test_same_student_can_have_assignments_in_different_sessions(self):
        S = StudentAcademicAssignment.Status
        make_assignment(self.ahmed, self.s2025, self.cse_1_a, status=S.COMPLETED)
        make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        sessions = set(
            self.ahmed.academic_assignments.values_list("academic_session_id", flat=True)
        )
        self.assertEqual(sessions, {self.s2025.pk, self.s2026.pk})
 
    def test_many_students_can_share_a_section_and_session(self):
        for n in range(20, 25):
            make_assignment(make_student(n, self.college, self.cse), self.s2026, self.cse_2_a)
        make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        self.assertEqual(
            self.cse_2_a.student_assignments.filter(academic_session=self.s2026).count(), 6
        )
 
    # 16. Section must belong to the AcademicSession's college
    def test_section_must_belong_to_the_sessions_college(self):
        with self.assertRaises(ValidationError):
            make_assignment(self.ahmed, self.s2026, self.other_section)
        other_student = make_student(2, self.other, self.other_cse)
        with self.assertRaises(ValidationError):
            make_assignment(other_student, self.other_session, self.cse_2_a)
        self.assertEqual(StudentAcademicAssignment.objects.count(), 0)
 
    # 17. Invalid cross-college assignment must fail
    def test_fully_cross_college_assignment_fails(self):
        third = make_college("THR")
        third_student = make_student(2, third, make_dept(third, code="CSE"))
        bad = StudentAcademicAssignment(
            student_membership=third_student,   # THR
            academic_session=self.s2026,        # ABC
            section=self.other_section,         # XYZ
        )
        with self.assertRaises(ValidationError) as ctx:
            bad.full_clean()
        self.assertIn("academic_session", ctx.exception.message_dict)
        self.assertIn("section", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            bad.save()
        with self.assertRaises(ValidationError):
            StudentAcademicAssignment.objects.create(
                student_membership=third_student,
                academic_session=self.s2026,
                section=self.other_section,
            )
        self.assertEqual(StudentAcademicAssignment.objects.count(), 0)
 
    def test_valid_assignment_can_not_be_edited_into_another_college(self):
        a = make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        a.section = self.other_section
        with self.assertRaises(ValidationError):
            a.save()
        a.refresh_from_db()
        self.assertEqual(a.section, self.cse_2_a)
 
    # 18. Status changes work
    def test_status_changes_work(self):
        S = StudentAcademicAssignment.Status
        a = make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        for status in (S.COMPLETED, S.TRANSFERRED, S.CANCELLED, S.ACTIVE):
            with self.subTest(status=status):
                a.status = status
                a.full_clean()
                a.save()
                a.refresh_from_db()
                self.assertEqual(a.status, status)
        a.status = "PAUSED"  # not a valid choice
        with self.assertRaises(ValidationError):
            a.full_clean()
 
    # 19. left_at can be used for completed / transferred records
    def test_left_at_can_be_used_for_completed_and_transferred_records(self):
        S = StudentAcademicAssignment.Status
        joined = timezone.now() - timedelta(days=200)
        left = timezone.now() - timedelta(days=10)
        for status, section in ((S.COMPLETED, self.cse_2_a), (S.TRANSFERRED, self.cse_2_b)):
            with self.subTest(status=status):
                a = make_assignment(
                    self.ahmed, self.s2026, section,
                    status=status, joined_at=joined, left_at=left,
                )
                a.full_clean()
                a.refresh_from_db()
                self.assertEqual(a.left_at, left)
        active = make_assignment(self.ahmed, self.s2026, self.cse_2_b)
        self.assertIsNone(active.left_at)  # left_at stays optional
 
    def test_left_at_cannot_be_before_joined_at(self):
        joined = timezone.now()
        bad = StudentAcademicAssignment(
            student_membership=self.ahmed,
            academic_session=self.s2026,
            section=self.cse_2_a,
            status=StudentAcademicAssignment.Status.COMPLETED,
            joined_at=joined,
            left_at=joined - timedelta(days=1),
        )
        with self.assertRaises(ValidationError) as ctx:
            bad.full_clean()
        self.assertIn("left_at", ctx.exception.message_dict)
        with self.assertRaises(ValidationError):
            bad.save()
        # the database backs this up when validation is bypassed
        good = make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StudentAcademicAssignment.objects.filter(pk=good.pk).update(
                left_at=good.joined_at - timedelta(days=1)
            )
 
    # Deletion behaviour
    def test_session_and_section_with_assignments_cannot_be_deleted(self):
        make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        with self.assertRaises(ProtectedError):
            self.s2026.delete()
        with self.assertRaises(ProtectedError):
            self.cse_2_a.delete()
 
    def test_deleting_a_user_still_works_and_removes_their_assignments(self):
        make_assignment(self.ahmed, self.s2026, self.cse_2_a)
        self.ahmed.user.delete()
        self.assertEqual(CollegeMembership.objects.filter(pk=self.ahmed.pk).count(), 0)
        self.assertEqual(StudentAcademicAssignment.objects.count(), 0)
 
 
class BulkOperationLimitationTests(TestCase):
    """Documents WHY future bulk student imports must validate every row.
 
    bulk_create() and QuerySet.update() never call save() or clean(), so the
    Python rules (student role, same college, home department) are skipped.
    If these rules are ever enforced somewhere else (a service function, a
    database trigger), update or delete these tests.
    """
 
    def setUp(self):
        self.college = make_college("ABC")
        self.cse = make_dept(self.college, code="CSE", name="Computer Science")
        self.section = make_section(make_year(self.cse, 2), "A")
        self.session = make_session(self.college)
        self.other = make_college("XYZ")
        self.other_section = make_section(
            make_year(make_dept(self.other, code="CSE"), 2), "A"
        )
        self.student = make_student(1, self.college, self.cse)
 
    def test_bulk_create_skips_cross_college_validation(self):
        bad = StudentAcademicAssignment(
            student_membership=self.student,
            academic_session=self.session,
            section=self.other_section,  # wrong college
        )
        StudentAcademicAssignment.objects.bulk_create([bad])  # no error: bypassed
        row = StudentAcademicAssignment.objects.get()
        # ... but validating the row afterwards catches it:
        with self.assertRaises(ValidationError):
            row.full_clean()
 
    def test_queryset_update_skips_cross_college_validation(self):
        good = make_assignment(self.student, self.session, self.section)
        StudentAcademicAssignment.objects.filter(pk=good.pk).update(
            section=self.other_section
        )
        good.refresh_from_db()
        self.assertEqual(good.section, self.other_section)  # bypassed
        with self.assertRaises(ValidationError):
            good.full_clean()
 
 
class Phase3ExistingBehaviourTests(TestCase):
    # 20. Existing College, Department, AcademicYear, Section and User are unaffected
    def test_existing_models_have_no_fields_pointing_to_new_models(self):
        new_models = (AcademicSession, StudentAcademicAssignment)
        for model in (College, Department, CollegeMembership, AcademicYear, Section, User):
            for field in model._meta.concrete_fields:
                self.assertNotIn(field.related_model, new_models, f"{model.__name__}.{field.name}")
 
    def test_user_model_and_migrations_still_independent_of_colleges(self):
        self.assertNotEqual(User._meta.app_label, "colleges")
        loader = MigrationLoader(None, ignore_no_migrations=True)
        for (app_label, name), migration in loader.disk_migrations.items():
            if app_label == User._meta.app_label:
                for dep_app, _dep_name in migration.dependencies:
                    self.assertNotEqual(dep_app, "colleges", f"{app_label}.{name}")
 
    def test_existing_models_still_create_and_normalise_as_before(self):
        college = College.objects.create(name=" ABC College ", code=" abc ", slug="ABC-College")
        self.assertEqual((college.name, college.code, college.slug), ("ABC College", "ABC", "abc-college"))
        dept = make_dept(college, code="cse", name="Computer Science")
        year = make_year(dept, 2)
        section = make_section(year, "a")
        self.assertEqual(dept.code, "CSE")
        self.assertEqual(year.name, "2nd Year")
        self.assertEqual(section.code, "A")
        self.assertEqual(section.college, college)
 
    def test_existing_college_guards_still_work_with_assignments_present(self):
        college, other = make_college("ABC"), make_college("XYZ")
        dept = make_dept(college, code="CSE")
        year = make_year(dept, 2)
        section = make_section(year, "A")
        make_assignment(make_student(1, college, dept), make_session(college), section)
        year.department = make_dept(other, code="CSE")
        with self.assertRaises(ValidationError):
            year.save()
        section.academic_year = make_year(make_dept(other, code="ECE", name="Electronics"), 2)
        with self.assertRaises(ValidationError):
            section.save()
        dept.college = other
        with self.assertRaises(ValidationError):
            dept.save()
 