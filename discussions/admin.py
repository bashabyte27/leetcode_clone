from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import Comment, Discussion, Vote


class ReplyInline(admin.TabularInline):
    model = Comment
    fk_name = 'parent'
    extra = 0


class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'discussion', 'parent', 'vote_count', 'created_at')
    list_filter = ('is_hidden', 'created_at')
    search_fields = ('content', 'user__user_name', 'discussion__title')
    inlines = (ReplyInline,)
    ordering = ('-created_at',)


class DiscussionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'problem', 'user', 'discussion_type', 'comment_count', 'created_at')
    list_filter = ('discussion_type', 'is_hidden', 'is_pinned', 'created_at')
    search_fields = ('title', 'content', 'problem__title', 'user__user_name')
    ordering = ('-created_at',)


class VoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'content_type', 'object_id', 'value', 'created_at')
    list_filter = ('value', 'created_at')
    ordering = ('-created_at',)


admin.site.register(Discussion, DiscussionAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Vote, VoteAdmin)