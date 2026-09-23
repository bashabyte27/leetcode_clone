from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CollegeMembership, StudentAcademicAssignment

User = get_user_model()


def _validate_department_for_college(college, department):
    if department is None:
        return
    if department.college_id != college.pk:
        raise ValidationError({"department": "Department must belong to the same college."})


def _build_membership(*, user, college, role, department=None, member_number=None, invited_by=None):
    membership = CollegeMembership(
        user=user,
        college=college,
        role=role,
        status=CollegeMembership.Status.ACTIVE,
        home_department=department,
        member_number=member_number,
        invited_by=invited_by,
        joined_at=timezone.now(),
    )
    membership.full_clean()
    membership.save()
    return membership


@transaction.atomic
def create_hod(*, email, user_name, password, college, department, member_number=None, invited_by=None, user=None):
    _validate_department_for_college(college, department)
    if user is None:
        user = User.objects.create_user(
            email=email,
            user_name=user_name,
            password=password,
            is_verified=True,
        )
    return _build_membership(
        user=user,
        college=college,
        role=CollegeMembership.Role.HOD,
        department=department,
        member_number=member_number,
        invited_by=invited_by,
    )


@transaction.atomic
def create_faculty(*, email, user_name, password, college, department, member_number=None, invited_by=None, user=None):
    _validate_department_for_college(college, department)
    if user is None:
        user = User.objects.create_user(
            email=email,
            user_name=user_name,
            password=password,
            is_verified=True,
        )
    return _build_membership(
        user=user,
        college=college,
        role=CollegeMembership.Role.FACULTY,
        department=department,
        member_number=member_number,
        invited_by=invited_by,
    )


@transaction.atomic
def create_student(
    *,
    email,
    user_name,
    password,
    college,
    department,
    member_number=None,
    academic_session=None,
    section=None,
    invited_by=None,
    home_department=None,
    user=None,
):
    _validate_department_for_college(college, department)
    if home_department is not None:
        _validate_department_for_college(college, home_department)

    if user is None:
        user = User.objects.create_user(
            email=email,
            user_name=user_name,
            password=password,
            is_verified=True,
        )

    membership = _build_membership(
        user=user,
        college=college,
        role=CollegeMembership.Role.STUDENT,
        department=home_department or department,
        member_number=member_number,
        invited_by=invited_by,
    )

    if academic_session is None and section is None:
        return membership

    if academic_session is None or section is None:
        raise ValidationError({"academic_session": "Both academic_session and section are required for a student assignment."})

    assignment = StudentAcademicAssignment(
        student_membership=membership,
        academic_session=academic_session,
        section=section,
        status=StudentAcademicAssignment.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    assignment.full_clean()
    assignment.save()
    return membership
