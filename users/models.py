"""
users/models.py
---------------
Handles authentication, profiles, social follows, notifications, and audit logging.

IMPORTANT: Add the following to settings.py
    AUTH_USER_MODEL = 'users.Users'
"""

import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.utils import timezone


# ─────────────────────────── Choices ────────────────────────────


class UserRoleChoices(models.TextChoices):
    USER = 'user', 'User'
    MODERATOR = 'moderator', 'Moderator'
    ADMIN = 'admin', 'Admin'


class NotificationTypeChoices(models.TextChoices):
    SUBMISSION = 'submission', 'Submission Result'
    COMMENT = 'comment', 'New Comment'
    CONTEST = 'contest', 'Contest Reminder'
    BADGE = 'badge', 'Badge Earned'
    FOLLOW = 'follow', 'New Follower'
    SYSTEM = 'system', 'System Message'


class AuditActionChoices(models.TextChoices):
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    LOGIN = 'login', 'Login'
    LOGOUT = 'logout', 'Logout'
    PASSWORD_CHANGE = 'password_change', 'Password Change'


# ─────────────────────────── Manager ────────────────────────────


class UserManager(BaseUserManager):
    def create_user(self, email: str, user_name: str, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        if not user_name:
            raise ValueError("Username is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, user_name=user_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, user_name: str, password=None, **extra_fields):
        extra_fields.setdefault('role', UserRoleChoices.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(email, user_name, password, **extra_fields)


# ──────────────────────── Core Auth Models ───────────────────────


class Users(AbstractBaseUser, PermissionsMixin):
    """
    Primary user model using UUID PK for security.
    Uses AbstractBaseUser so Django's auth framework handles
    password hashing, session management, and permissions properly.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_name = models.CharField(
        max_length=100,
        unique=True,
        validators=[
            MinLengthValidator(3),
            RegexValidator(
                r'^[a-zA-Z0-9_]+$',
                'Username may only contain letters, numbers, and underscores.'
            ),
        ],
    )
    email = models.EmailField(unique=True)
    mobile_no = models.CharField(
        max_length=15,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid mobile number.')],
    )
    avatar_url = models.URLField(blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=UserRoleChoices.choices,
        default=UserRoleChoices.USER,
        db_index=True,
    )
    is_verified = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    groups = models.ManyToManyField(
    'auth.Group',
    blank=True,
    related_name='custom_user_set'      # ← add this
)
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='custom_user_set'      # ← add this
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_name']

    objects = UserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_name']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['is_premium', 'is_active']),
        ]

    # ── Convenience properties ──

    @property
    def is_admin(self) -> bool:
        return self.role == UserRoleChoices.ADMIN

    @property
    def is_moderator(self) -> bool:
        return self.role in (UserRoleChoices.MODERATOR, UserRoleChoices.ADMIN)

    def __str__(self) -> str:
        return f"{self.user_name} <{self.email}>"


class UserProfile(models.Model):
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True, max_length=500)
    location = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'

    def __str__(self) -> str:
        return f"Profile: {self.user.user_name}"


class UserStats(models.Model):
    """
    Denormalized stats table — updated via signals or celery tasks
    after each accepted submission. Avoids expensive COUNT() queries
    on the submissions table on every profile page load.
    """
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name='stats')
    easy_solved = models.PositiveIntegerField(default=0)
    medium_solved = models.PositiveIntegerField(default=0)
    hard_solved = models.PositiveIntegerField(default=0)
    global_rank = models.PositiveIntegerField(default=0, db_index=True)
    # ELO-style contest rating; 1500 is standard starting point
    contest_rating = models.PositiveIntegerField(default=1500, db_index=True)
    streak_days = models.PositiveIntegerField(default=0)
    max_streak_days = models.PositiveIntegerField(default=0)
    total_submissions = models.PositiveIntegerField(default=0)
    accepted_submissions = models.PositiveIntegerField(default=0)
    reputation_points = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(auto_now=True)

    class Meta:
        verbose_name = 'User Stats'

    # ── Computed properties (not stored) ──

    @property
    def total_solved(self) -> int:
        return self.easy_solved + self.medium_solved + self.hard_solved

    @property
    def acceptance_rate(self) -> float:
        if self.total_submissions == 0:
            return 0.0
        return round((self.accepted_submissions / self.total_submissions) * 100, 2)

    def __str__(self) -> str:
        return f"Stats: {self.user.user_name} | Solved: {self.total_solved}"


# ─────────────────────────── Sessions / OAuth ────────────────────


class Session(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='sessions')
    token_hash = models.CharField(max_length=255, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=512)
    device_type = models.CharField(max_length=50, blank=True, null=True)  # mobile | desktop | tablet
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Session'
        indexes = [
            models.Index(fields=['user', 'expires_at']),
        ]

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    def __str__(self) -> str:
        return f"Session: {self.user.user_name} | IP: {self.ip_address}"


class OAuthProvider(models.Model):
    """Stores OAuth tokens for social login providers (Google, GitHub, LinkedIn)."""
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='oauth_providers')
    provider_name = models.CharField(max_length=50)   # google | github | linkedin
    provider_user_id = models.CharField(max_length=255, unique=True)
    access_token = models.TextField()                  # encrypted at rest in production
    refresh_token = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'OAuth Provider'
        unique_together = ('user', 'provider_name')

    def __str__(self) -> str:
        return f"{self.user.user_name} | {self.provider_name}"


# ─────────────────────── Token Models ───────────────────────────


class PasswordResetToken(models.Model):
    """
    Short-lived tokens for password reset flow.
    Hash the raw token before storing — never store plaintext tokens.
    """
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='password_resets')
    token_hash = models.CharField(max_length=255, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Password Reset Token'

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(hours=1)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_used and not self.is_expired

    def __str__(self) -> str:
        return f"PasswordReset: {self.user.email}"


class EmailVerificationToken(models.Model):
    """
    One-time token sent to verify email address.
    OneToOne because a user should only have one active verification token.
    """
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name='email_verification')
    token_hash = models.CharField(max_length=255, unique=True, db_index=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Email Verification Token'

    @property
    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self) -> str:
        return f"EmailVerify: {self.user.email}"


# ─────────────────────────── Social ─────────────────────────────


class UserFollow(models.Model):
    """
    Self-referential follow relationship.
    follower follows following.
    """
    follower = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        verbose_name = 'User Follow'
        indexes = [
            models.Index(fields=['follower']),
            models.Index(fields=['following']),
        ]

    def clean(self):
        if self.follower_id == self.following_id:
            raise ValidationError("A user cannot follow themselves.")

    def __str__(self) -> str:
        return f"{self.follower.user_name} → {self.following.user_name}"


# ─────────────────────── Notifications ──────────────────────────


class Notification(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=NotificationTypeChoices.choices, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    # Flexible payload: e.g. {"submission_id": 42, "problem_slug": "two-sum"}
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Notification'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'type']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.user.user_name} | {self.type} | {self.title}"


# ─────────────────────────── Audit ──────────────────────────────


class AuditLog(models.Model):
    """
    Immutable append-only log for admin/security auditing.
    SET_NULL on user so logs survive account deletion.
    """
    user = models.ForeignKey(
        Users,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=30, choices=AuditActionChoices.choices, db_index=True)
    model_name = models.CharField(max_length=100, blank=True, null=True)
    object_id = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Audit Log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self) -> str:
        return f"AuditLog: {self.user} | {self.action} | {self.model_name}"