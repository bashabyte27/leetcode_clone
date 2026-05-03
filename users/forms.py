# users/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import Users


# ─────────────────────── Registration Form ───────────────────────

class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    mobile_no = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your mobile number (optional)'
        })
    )
    user_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = Users
        fields = ['user_name', 'email', 'mobile_no', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if Users.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def clean_user_name(self):
        user_name = self.cleaned_data.get('user_name')
        if Users.objects.filter(user_name=user_name).exists():
            raise forms.ValidationError('This username is already taken.')
        return user_name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.user_name = self.cleaned_data['user_name']
        if commit:
            user.save()
        return user


# ─────────────────────── Login Form ──────────────────────────────

class LoginForm(forms.Form):
    username = None  # ← removes the parent's username field    
    email = forms.EmailField(       # AuthenticationForm calls it username internally
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    def __init__(self, request=None, *args, **kwargs):
        self.request = request  # ← stores request on the form
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean_email(self):
    # Only validate email format/existence
        email = self.cleaned_data.get('email')
        if not Users.objects.filter(email=email).exists():
            raise forms.ValidationError('No account found with this email.')
        return email

    def clean_password(self):
        # Only validate password is not empty etc.
        password = self.cleaned_data.get('password')
        if len(password) < 6:
            raise forms.ValidationError('Password too short.')
        return password

    def clean(self):
        # Cross-field logic lives here — both fields available
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError('Invalid email or password.')
        return self.cleaned_data
    
class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your registered email'
        })
    )
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password'
        })
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )
    otp = forms.CharField(
        required=False,   # not required on step 1 (get-otp)
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '------',
            'maxlength': '6',
        })
    )

    def clean(self):
        p1 = self.cleaned_data.get('new_password1')
        p2 = self.cleaned_data.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match.')
        return self.cleaned_data