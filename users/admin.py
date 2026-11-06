from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.password_validation import validate_password

from .models import Users


class AdminUserCreationForm(forms.ModelForm):
    """Add-user form for the admin: takes the password twice and hashes it."""

    password1 = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Password confirmation", strip=False, widget=forms.PasswordInput)

    class Meta:
        model = Users
        fields = ("email", "user_name")

    def clean_password2(self):
        p1, p2 = self.cleaned_data.get("password1"), self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("The two password fields didn't match.")
        return p2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password2")
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password2", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class AdminUserChangeForm(forms.ModelForm):
    """Edit-user form: the password is shown as its hash, never as an editable text box."""

    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=(
            "Raw passwords are not stored, so there is no way to see this user's password. "
            'You can change it using <a href="../password/">this form</a>.'
        ),
    )

    class Meta:
        model = Users
        fields = "__all__"


@admin.register(Users)
class UsersAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm

    list_display = ("user_name", "email", "role", "is_faculty", "is_staff", "is_active", "created_at")
    list_filter = ("role", "is_faculty", "is_staff", "is_superuser", "is_active", "is_verified", "is_premium")
    search_fields = ("user_name", "email", "mobile_no")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "last_login")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "user_name", "password")}),
        ("Profile", {"fields": ("mobile_no", "avatar_url", "role", "is_verified", "is_premium")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_faculty", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "user_name", "password1", "password2"),
        }),
        ("Access", {"fields": ("role", "is_active", "is_staff", "is_faculty", "is_superuser")}),
    )
