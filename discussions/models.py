"""
discussions/models.py
----------------------
Handles problem discussions, nested comments, and generic voting.

Key improvements vs original:
  - Comment.parent FK enables nested replies (one level)
  - DiscussionTypeChoices distinguishes solution posts from questions
  - Vote.value uses IntegerChoices — enforces only +1 / -1 at the DB level
  - is_hidden flag on both Discussion and Comment for moderation
  - comment_count denormalized on Discussion for cheap listing queries
  - updated_at on both Discussion and Comment
"""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


# ─────────────────────────── Choices ────────────────────────────


class DiscussionTypeChoices(models.TextChoices):
    GENERAL = 'general', 'General'
    SOLUTION = 'solution', 'Solution'
    QUESTION = 'question', 'Question'
    EDITORIAL = 'editorial', 'Editorial'


class VoteValueChoices(models.IntegerChoices):
    """
    Bug fix (original): Vote.value was a bare SmallIntegerField with no
    constraint, allowing arbitrary integers.
    IntegerChoices limits valid values to +1 and -1 at the ORM level.
    """
    DOWNVOTE = -1, 'Downvote'
    UPVOTE = 1, 'Upvote'


# ──────────────────────── Discussion ─────────────────────────────


class Discussion(models.Model):
    """
    A top-level thread attached to a problem.
    `language` is optional — useful when the post shares a code solution.
    `is_hidden` is set by moderators, not deleted, so the thread can be
    reinstated if a report was wrong.
    """
    problem = models.ForeignKey(
        'problems.Problem',
        on_delete=models.CASCADE,
        related_name='discussions',
    )
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='discussions',
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    discussion_type = models.CharField(
        max_length=20,
        choices=DiscussionTypeChoices.choices,
        default=DiscussionTypeChoices.GENERAL,
        db_index=True,
    )
    # Optional: which language the solution is written in
    language = models.ForeignKey(
        'problems.Language',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discussions',
    )
    views = models.PositiveIntegerField(default=0)
    vote_count = models.IntegerField(default=0)
    # Denormalized comment count — updated by a post_save signal on Comment
    comment_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_hidden = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Discussion'
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['problem', 'discussion_type']),
            models.Index(fields=['problem', 'is_pinned', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['vote_count']),  # for sorting by top votes
        ]

    def __str__(self) -> str:
        return f"Discussion: {self.title} by {self.user.user_name}"


# ──────────────────────── Comments ───────────────────────────────


class Comment(models.Model):
    """
    A comment on a discussion thread.
    `parent` enables one level of nested replies.
    Limit nesting to depth=1 in the view layer (parent__isnull check)
    to keep queries simple.
    """
    discussion = models.ForeignKey(
        Discussion,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='comments',
    )
    # Null parent = top-level comment; non-null parent = reply
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
    )
    content = models.TextField()
    vote_count = models.IntegerField(default=0)
    is_hidden = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Comment'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['discussion', 'parent', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    @property
    def is_reply(self) -> bool:
        return self.parent_id is not None

    def __str__(self) -> str:
        prefix = "Reply" if self.is_reply else "Comment"
        return f"{prefix} by {self.user.user_name} on '{self.discussion.title}'"


# ─────────────────────────── Vote ────────────────────────────────


class Vote(models.Model):
    """
    Generic vote — works on both Discussion and Comment via ContentType.

    Usage:
        content_type = ContentType.objects.get_for_model(Discussion)
        Vote.objects.create(
            user=request.user,
            content_type=content_type,
            object_id=discussion.pk,
            value=VoteValueChoices.UPVOTE,
        )

    After saving a Vote, update the target object's vote_count via signal:
        discussion.vote_count = Vote.objects.filter(...).aggregate(
            total=Sum('value')
        )['total'] or 0
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='votes',
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    value = models.SmallIntegerField(choices=VoteValueChoices.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')
        verbose_name = 'Vote'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['user']),
        ]

    def __str__(self) -> str:
        return (
            f"{self.user.user_name} "
            f"{'↑' if self.value == VoteValueChoices.UPVOTE else '↓'} "
            f"{self.content_type}"
        )