from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import (
    AcademicSession, AcademicYear, College, CollegeMembership,
    Department, Section, StudentAcademicAssignment,
)
User = get_user_model()


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "slug", "city", "state", "status", "created_at")
    list_filter = ("status", "state")
    search_fields = ("name", "code", "slug", "city", "contact_email")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("created_by",)

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "college", "status")
    list_filter = ("status",)
    search_fields = ("name", "code", "college__name", "college__code")
    list_select_related = ("college",)
    autocomplete_fields = ("college",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CollegeMembership)
class CollegeMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user", "college", "role", "status",
        "home_department", "member_number", "joined_at",
    )
    list_filter = ("role", "status")
    search_fields = (
        "member_number",
        "college__name",
        "college__code",
        # DEPENDS ON YOUR USER MODEL: USERNAME_FIELD works for email or username login
        f"user__{User.USERNAME_FIELD}",
    )
    list_select_related = ("user", "college", "home_department__college")
    raw_id_fields = ("user", "invited_by")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "year_number", "department", "status", "created_at")
    list_filter = ("status", "year_number")
    search_fields = (
        "name",
        "department__name",
        "department__code",
        "department__college__name",
        "department__college__code",
    )
    list_select_related = ("department__college",)
    autocomplete_fields = ("department",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("department__college__name", "department__name", "year_number")


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "academic_year", "status", "created_at")
    list_filter = ("status", "academic_year__year_number")
    search_fields = (
        "name",
        "code",
        "academic_year__name",
        "academic_year__department__name",
        "academic_year__department__code",
        "academic_year__department__college__name",
        "academic_year__department__college__code",
    )
    list_select_related = ("academic_year__department__college",)
    autocomplete_fields = ("academic_year",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = (
        "academic_year__department__college__name",
        "academic_year__department__name",
        "academic_year__year_number",
        "name",
    )


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ("name", "college", "start_date", "end_date", "status")
    list_filter = ("status", "college")
    search_fields = ("name", "college__name", "college__code")
    list_select_related = ("college",)
    autocomplete_fields = ("college",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("college__name", "-start_date")
 
 
@admin.register(StudentAcademicAssignment)
class StudentAcademicAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "student", "member_number", "college",
        "academic_session", "section", "status", "joined_at", "left_at",
    )
    list_filter = (
        "status",
        "academic_session",
        "section__academic_year__department__college",
    )
    search_fields = (
        "student_membership__member_number",
        f"student_membership__user__{User.USERNAME_FIELD}",
        "student_membership__user__user_name",
        "academic_session__name",
        "section__name",
        "section__academic_year__department__code",
        "section__academic_year__department__college__name",
        "section__academic_year__department__college__code",
    )
    list_select_related = (
        "student_membership__user",
        "academic_session__college",
        "section__academic_year__department__college",
    )
    autocomplete_fields = ("student_membership", "academic_session", "section")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-joined_at",)
 
    @admin.display(
        description="Student",
        ordering=f"student_membership__user__{User.USERNAME_FIELD}",
    )
    def student(self, obj):
        return obj.student_membership.user
 
    @admin.display(
        description="Member no.", ordering="student_membership__member_number"
    )
    def member_number(self, obj):
        return obj.student_membership.member_number
 
    @admin.display(
        description="College",
        ordering="section__academic_year__department__college__name",
    )
    def college(self, obj):
        return obj.section.academic_year.department.college
 