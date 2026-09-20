import uuid

import django
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


# Highest academic year number accepted (1 = first year).
# 4 is normal for B.Tech; 5-6 covers architecture, integrated and pharmacy programs.
# This is a plain Python rule, so it can be changed without a database migration.
MAX_YEAR_NUMBER = 6


def _ordinal(n):
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th', 11 -> '11th'."""
    if 11 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

class College(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        ARCHIVED = "ARCHIVED", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    # code is stored in UPPERCASE, slug in lowercase (see _normalise)
    code = models.CharField(max_length=32, unique=True)
    # max_length=63 so the slug can become a subdomain label later
    slug = models.SlugField(max_length=63, unique=True)
    contact_email = models.EmailField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )

    # Uses AUTH_USER_MODEL, so no import of your User model is needed.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_colleges",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def _normalise(self):
        self.name = (self.name or "").strip()
        self.code = (self.code or "").strip().upper()
        self.slug = (self.slug or "").strip().lower()

    def clean(self):
        super().clean()
        self._normalise()  # runs before the unique check in admin/forms

    def save(self, *args, **kwargs):
        self._normalise()
        super().save(*args, **kwargs)

class Department(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(
        College, on_delete=models.PROTECT, related_name="departments"
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=32)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["college", "code"], name="uniq_department_code_per_college"
            ),
            models.UniqueConstraint(
                fields=["college", "name"], name="uniq_department_name_per_college"
            ),
        ]

    def __str__(self):
        # CHANGED: college code added, so "CSE" of two colleges is not confused
        return f"{self.college.code} / {self.code}"

    def _normalise(self):
        self.name = (self.name or "").strip()
        self.code = (self.code or "").strip().upper()

    # NEW: a department must never move to another college, because its
    # academic years, sections and members would silently move with it.
    def _check_college_unchanged(self):
        if not self.college_id:
            return
        old = (
            Department.objects.filter(pk=self.pk)
            .values_list("college_id", flat=True)
            .first()
        )
        if old is not None and old != self.college_id:
            raise ValidationError(
                {"college": "A department cannot be moved to another college."}
            )

    def clean(self):
        super().clean()
        self._normalise()
        self._check_college_unchanged()  # NEW

    def save(self, *args, **kwargs):
        self._normalise()
        self._check_college_unchanged()  # NEW
        super().save(*args, **kwargs)

class CollegeMembership(models.Model):
    class Role(models.TextChoices):
        COLLEGE_ADMIN = "COLLEGE_ADMIN", "College admin"
        HOD = "HOD", "HOD"
        FACULTY = "FACULTY", "Faculty"
        STUDENT = "STUDENT", "Student"

    class Status(models.TextChoices):
        INVITED = "INVITED", "Invited"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        LEFT = "LEFT", "Left"

    # id: BigAutoField (set in apps.py)

    # Uses AUTH_USER_MODEL, so no import of your User model is needed.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="college_memberships",
    )
    college = models.ForeignKey(
        College, on_delete=models.PROTECT, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.INVITED
    )
    home_department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="home_memberships",
    )
    # Roll number / employee ID. NULL when not given.
    member_number = models.CharField(max_length=64, null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_college_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "college"], name="uniq_membership_user_college"
            ),
            # Unique inside one college, only when a number is given.
            models.UniqueConstraint(
                fields=["college", "member_number"],
                condition=Q(member_number__isnull=False),
                name="uniq_membership_member_number_per_college",
            ),
        ]
        indexes = [
            models.Index(
                fields=["college", "role", "status"],
                name="colmem_col_role_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.college.code} - {self.role}"

    def _normalise(self):
        # "" and spaces become NULL, so blank numbers never clash
        self.member_number = (self.member_number or "").strip() or None

    def _check_home_department_college(self):
        # A normal foreign key cannot check this, so we do it here.
        if self.home_department_id and self.college_id:
            if self.home_department.college_id != self.college_id:
                raise ValidationError(
                    {"home_department": "Department must belong to the same college."}
                )

    def clean(self):
        super().clean()
        self._normalise()
        self._check_home_department_college()

    def save(self, *args, **kwargs):
        self._normalise()
        self._check_home_department_college()
        super().save(*args, **kwargs)

class AcademicYear(models.Model):
    """1st Year, 2nd Year ... of a department. NOT a session like 2026-27."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="academic_years"
    )
    # Leave blank to get "1st Year", "2nd Year", ... automatically.
    name = models.CharField(max_length=50, blank=True)
    year_number = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "year_number"],
                name="uniq_academicyear_number_per_department",
            ),
        ]

    def __str__(self):
        return f"{self.department} / {self.name}"

    @property
    def college(self):
        """Python shortcut only. In queries use department__college."""
        return self.department.college

    def _year_number_is_valid(self):
        return (
            isinstance(self.year_number, int)
            and 1 <= self.year_number <= MAX_YEAR_NUMBER
        )

    def _normalise(self):
        self.name = (self.name or "").strip()
        if not self.name and self._year_number_is_valid():
            self.name = f"{_ordinal(self.year_number)} Year"

    def _check_year_number(self):
        if not self._year_number_is_valid():
            raise ValidationError(
                {"year_number": f"Year number must be a whole number from 1 to {MAX_YEAR_NUMBER}."}
            )

    def _check_college_unchanged(self):
        if not self.department_id:
            return
        old = (
            AcademicYear.objects.filter(pk=self.pk)
            .values_list("department__college_id", flat=True)
            .first()
        )
        if old is not None and old != self.department.college_id:
            raise ValidationError(
                {"department": "An academic year cannot be moved to a department of another college."}
            )

    def clean(self):
        super().clean()
        self._normalise()
        if self.year_number is not None:  # a missing value is reported by field validation
            self._check_year_number()
        self._check_college_unchanged()

    def save(self, *args, **kwargs):
        self._normalise()
        self._check_year_number()
        self._check_college_unchanged()
        super().save(*args, **kwargs)


class Section(models.Model):
    """Section A, B, C ... of an academic year."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="sections"
    )
    name = models.CharField(max_length=50)
    # Leave blank to use the name in UPPERCASE (name "a" -> code "A").
    code = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "name"],
                name="uniq_section_name_per_academic_year",
            ),
            models.UniqueConstraint(
                fields=["academic_year", "code"],
                name="uniq_section_code_per_academic_year",
            ),
        ]

    def __str__(self):
        return f"{self.academic_year} / {self.name}"

    @property
    def department(self):
        """Python shortcut only. In queries use academic_year__department."""
        return self.academic_year.department

    @property
    def college(self):
        """Python shortcut only. In queries use academic_year__department__college."""
        return self.academic_year.department.college

    def _normalise(self):
        self.name = (self.name or "").strip()
        self.code = (self.code or "").strip().upper() or self.name.upper()

    def _check_college_unchanged(self):
        if not self.academic_year_id:
            return
        old = (
            Section.objects.filter(pk=self.pk)
            .values_list("academic_year__department__college_id", flat=True)
            .first()
        )
        if old is not None and old != self.academic_year.department.college_id:
            raise ValidationError(
                {"academic_year": "A section cannot be moved to an academic year of another college."}
            )

    def clean(self):
        super().clean()
        self._normalise()
        self._check_college_unchanged()

    def save(self, *args, **kwargs):
        self._normalise()
        self._check_college_unchanged()
        super().save(*args, **kwargs)

def _check_constraint(condition, name):
    """CheckConstraint's `check=` argument was renamed `condition=` in Django 5.1.
    This helper picks the right spelling, so the same code works on 4.2 and 5.x."""
    if django.VERSION >= (5, 1):
        return models.CheckConstraint(condition=condition, name=name)
    return models.CheckConstraint(check=condition, name=name)
 
 
class AcademicSession(models.Model):
    """A real academic period of ONE college: 2025-26, 2026-27 ...
 
    NOT the same as AcademicYear (1st / 2nd / 3rd / 4th year).
    """
 
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        ARCHIVED = "ARCHIVED", "Archived"
 
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    college = models.ForeignKey(
        College, on_delete=models.PROTECT, related_name="academic_sessions"
    )
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    # New sessions start as PLANNED, so nothing becomes ACTIVE by accident.
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PLANNED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["college", "name"],
                name="uniq_academicsession_name_per_college",
            ),
            # Partial unique index: at most ONE active session per college.
            # The literal "ACTIVE" is used because Meta cannot see the Status class.
            models.UniqueConstraint(
                fields=["college"],
                condition=Q(status="ACTIVE"),
                name="uniq_active_academicsession_per_college",
            ),
            _check_constraint(
                Q(end_date__gt=F("start_date")),
                "academicsession_end_after_start",
            ),
        ]
 
    def __str__(self):
        return f"{self.college.code} / {self.name}"
 
    def _normalise(self):
        self.name = (self.name or "").strip()
 
    def _check_name(self):
        if not self.name:
            raise ValidationError({"name": "Name is required."})
 
    def _check_dates(self):
        if self.start_date is None:
            raise ValidationError({"start_date": "Start date is required."})
        if self.end_date is None:
            raise ValidationError({"end_date": "End date is required."})
        if self.end_date <= self.start_date:
            raise ValidationError(
                {"end_date": "End date must be after the start date."}
            )
 
    # A session must never move to another college, because student assignments
    # that point to it would silently become cross-college.
    def _check_college_unchanged(self):
        if not self.college_id:
            return
        old = (
            AcademicSession.objects.filter(pk=self.pk)
            .values_list("college_id", flat=True)
            .first()
        )
        if old is not None and old != self.college_id:
            raise ValidationError(
                {"college": "An academic session cannot be moved to another college."}
            )
 
    # Friendly message for forms/admin. The database constraint above is what
    # really guarantees the rule (it also protects against two requests racing).
    def _check_single_active(self):
        if self.status != self.Status.ACTIVE or not self.college_id:
            return
        clash = AcademicSession.objects.filter(
            college_id=self.college_id, status=self.Status.ACTIVE
        ).exclude(pk=self.pk)
        if clash.exists():
            raise ValidationError(
                {
                    "status": (
                        "This college already has an ACTIVE academic session. "
                        "Complete it before activating another one."
                    )
                }
            )
 
    def clean(self):
        super().clean()
        self._normalise()
        # Missing dates are reported by normal field validation.
        if self.start_date is not None and self.end_date is not None:
            self._check_dates()
        self._check_college_unchanged()
        self._check_single_active()
 
    def save(self, *args, **kwargs):
        self._normalise()
        self._check_name()
        self._check_dates()
        self._check_college_unchanged()
        # "Only one ACTIVE" is NOT checked here on purpose: a second ACTIVE session
        # raises IntegrityError from the database (same as the other unique rules
        # in this app). full_clean() gives the friendly ValidationError instead.
        super().save(*args, **kwargs)
 
 
class StudentAcademicAssignment(models.Model):
    """Where one student sits during one academic session.
 
    student_membership -> academic_session -> section -> academic_year
                                                      -> department -> college
 
    college / department / academic_year are NOT stored here. They are derived
    through the section (see the properties below).
 
    IMPORTANT for future bulk imports
    ---------------------------------
    The cross-model rules (student role, same college, home department) run in
    clean() and save(). Django skips BOTH of these for:
        * StudentAcademicAssignment.objects.bulk_create([...])
        * StudentAcademicAssignment.objects.filter(...).update(...)
        * raw SQL
    The database still enforces the constraints (one ACTIVE assignment per
    student per session, left_at not before joined_at), but it can NOT check
    role / college / department. Any bulk code must validate each row first
    (call full_clean() on every instance) or use a service function that does.
    """
 
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        TRANSFERRED = "TRANSFERRED", "Transferred"
        CANCELLED = "CANCELLED", "Cancelled"
 
    # BigAutoField, same as CollegeMembership: this is a high-volume "link" row
    # (every student x every session), not a structural record like College.
    id = models.BigAutoField(primary_key=True)
    # CASCADE: if a membership is deleted (for example its user is deleted), its
    # placement rows go with it, so deleting a user keeps working.
    student_membership = models.ForeignKey(
        CollegeMembership,
        on_delete=models.CASCADE,
        related_name="academic_assignments",
    )
    # PROTECT: sessions and sections that hold student history cannot be deleted.
    academic_session = models.ForeignKey(
        AcademicSession,
        on_delete=models.PROTECT,
        related_name="student_assignments",
    )
    section = models.ForeignKey(
        Section, on_delete=models.PROTECT, related_name="student_assignments"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE
    )
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ["-joined_at"]
        constraints = [
            # A student may have many rows per session (history), but only ONE
            # of them can be ACTIVE.
            models.UniqueConstraint(
                fields=["student_membership", "academic_session"],
                condition=Q(status="ACTIVE"),
                name="uniq_active_assignment_per_student_session",
            ),
            _check_constraint(
                Q(left_at__isnull=True) | Q(left_at__gte=F("joined_at")),
                "studentassignment_left_not_before_joined",
            ),
        ]
 
    def __str__(self):
        return (
            f"{self.student_membership.user} / {self.academic_session.name} / "
            f"{self.section} [{self.status}]"
        )
 
    # Python shortcuts only. In queries use section__academic_year__department__college.
    @property
    def academic_year(self):
        return self.section.academic_year
 
    @property
    def department(self):
        return self.section.academic_year.department
 
    @property
    def college(self):
        return self.section.academic_year.department.college
 
    def _check_consistency(self):
        """Cross-model rules. Collects every problem, then raises once."""
        if not (
            self.student_membership_id
            and self.academic_session_id
            and self.section_id
        ):
            return  # missing values are reported by field validation / the database
 
        membership = self.student_membership
        session = self.academic_session
        section_department = self.section.academic_year.department
        section_college_id = section_department.college_id
 
        errors = {}
 
        def add(field, message):
            errors.setdefault(field, []).append(message)
 
        is_student = membership.role == CollegeMembership.Role.STUDENT
        if not is_student:
            add(
                "student_membership",
                "Only a STUDENT membership can be assigned to a section.",
            )
        if membership.college_id != session.college_id:
            add(
                "academic_session",
                "Academic session must belong to the same college as the student.",
            )
        same_college_as_student = membership.college_id == section_college_id
        if not same_college_as_student:
            add(
                "section",
                "Section must belong to the same college as the student.",
            )
        if session.college_id != section_college_id:
            add(
                "section",
                "Section must belong to the same college as the academic session.",
            )
 
        # Home department rule. Only meaningful for a student in the right college,
        # otherwise the messages above already explain the problem.
        if is_student and same_college_as_student:
            if membership.home_department_id is None:
                add(
                    "student_membership",
                    "This student has no home department. Set it on the "
                    "membership before assigning a section.",
                )
            elif membership.home_department_id != section_department.pk:
                add(
                    "section",
                    "Section must belong to the student's home department.",
                )
 
        if errors:
            raise ValidationError(errors)
 
    def _check_dates(self):
        if (
            self.left_at is not None
            and self.joined_at is not None
            and self.left_at < self.joined_at
        ):
            raise ValidationError(
                {"left_at": "Left date cannot be before the joined date."}
            )
 
    # Friendly message for forms/admin. The database constraint is the real guard.
    def _check_single_active(self):
        if self.status != self.Status.ACTIVE:
            return
        if not (self.student_membership_id and self.academic_session_id):
            return
        clash = StudentAcademicAssignment.objects.filter(
            student_membership_id=self.student_membership_id,
            academic_session_id=self.academic_session_id,
            status=self.Status.ACTIVE,
        )
        if self.pk is not None:
            clash = clash.exclude(pk=self.pk)
        if clash.exists():
            raise ValidationError(
                {
                    "status": (
                        "This student already has an ACTIVE assignment in this "
                        "academic session. Complete or transfer it first."
                    )
                }
            )
 
    def clean(self):
        super().clean()
        self._check_consistency()
        self._check_dates()
        self._check_single_active()
 
    def save(self, *args, **kwargs):
        self._check_consistency()
        self._check_dates()
        # A second ACTIVE row for the same student + session raises IntegrityError
        # from the database. full_clean() gives the friendly ValidationError.
        super().save(*args, **kwargs)
 