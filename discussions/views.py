"""
discussions/views.py
---------------------
The Discussion tab on each problem page is one auto-created Discussion per
problem. Each problem has a single feeder thread (discussion_type=GENERAL)
that collects ALL comments. Posting a comment or a reply re-renders the
whole tab and returns it as JSON so the front-end can swap the container.
"""

import json

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from problems.models import Problem
from .forms import CommentForm
from .models import (
    Comment,
    Discussion,
    DiscussionTypeChoices,
    Vote,
    VoteValueChoices,
)


def _fallback_user(request):
    """Owner for auto-created Discussions. Priority: problem author → requester → first user."""
    from users.models import Users
    if getattr(request.user, 'is_authenticated', False) and request.user.is_active:
        return request.user
    return (
        Users.objects.filter(is_active=True, is_superuser=True)
        .order_by('created_at')
        .first()
        or Users.objects.filter(is_active=True).order_by('created_at').first()
    )


def _get_discussion(problem, request):
    """
    Returns the single General Discussion thread that carries every comment
    on this problem. Auto-creates it lazily on first view.
    """
    discussion, _ = Discussion.objects.get_or_create(
        problem=problem,
        discussion_type=DiscussionTypeChoices.GENERAL,
        defaults={
            'user': problem.created_by or _fallback_user(request),
            'title': f"Discussion: {problem.title}",
            'content': '',
        },
    )
    return discussion


def _annotate_user_votes(user, comments):
    """Stamps each comment with its user-vote state for active button styling."""
    if not user.is_authenticated or not comments:
        for c in comments:
            c.user_vote = 0
        return
    ct = ContentType.objects.get_for_model(Comment)
    ids = [c.id for c in comments]
    votes = Vote.objects.filter(user=user, content_type=ct, object_id__in=ids)
    vote_map = {v.object_id: v.value for v in votes}
    for c in comments:
        c.user_vote = vote_map.get(c.id, 0)


def _render_tab_json(request, problem, discussion, status=200):
    """Renders the whole discussion tab and returns it as JSON {html: ...}."""
    top_comments = list(
        discussion.comments.filter(parent__isnull=True, is_hidden=False)
        .select_related('user')
        .order_by('-vote_count', 'created_at')
    )
    replies = list(
        Comment.objects.filter(parent_id__in=[c.id for c in top_comments], is_hidden=False)
        .select_related('user')
        .order_by('created_at')
    )
    replies_by_parent = {}
    for r in replies:
        replies_by_parent.setdefault(r.parent_id, []).append(r)

    _annotate_user_votes(request.user, top_comments + replies)

    html = render(request, 'discussions/partials/discussion_tab.html', {
        'problem': problem,
        'discussion': discussion,
        'comments': top_comments,
        'replies_by_parent': replies_by_parent,
        'comment_form': CommentForm(),
    }).content.decode('utf-8')

    return JsonResponse({'html': html}, status=status)


# ─────────────────────────────── Views ─────────────────────────────


def discussion_tab(request, problem_slug):
    """GET — renders the Discussion tab for the lazy-loaded AJAX panel."""
    problem = get_object_or_404(Problem, slug=problem_slug, is_active=True)
    discussion = _get_discussion(problem, request)
    return _render_tab_json(request, problem, discussion)


@login_required
@require_POST
def post_comment(request, problem_slug):
    """POST — creates a top-level comment or a reply (parent_id)."""
    problem = get_object_or_404(Problem, slug=problem_slug, is_active=True)
    discussion = _get_discussion(problem, request)

    form = CommentForm(request.POST or None)
    if not form.is_valid():
        return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)
    content = form.cleaned_data['content'].strip()
    if not content:
        return JsonResponse({'error': 'Comment cannot be empty.'}, status=400)

    parent_id = request.POST.get('parent_id')
    parent = None
    if parent_id:
        parent = get_object_or_404(Comment, id=parent_id, discussion=discussion)
        # Enforce one level of nesting — flatten replies-on-replies to the top
        if parent.parent_id is not None:
            parent = parent.parent

    Comment.objects.create(
        discussion=discussion,
        user=request.user,
        parent=parent,
        content=content,
    )

    discussion.comment_count = discussion.comments.filter(is_hidden=False).count()
    discussion.save(update_fields=['comment_count'])

    return _render_tab_json(request, problem, discussion, status=201)


@login_required
@require_POST
def vote_comment(request, comment_id):
    """POST — toggles +1/-1 vote on a comment via the generic Vote model."""
    comment = get_object_or_404(Comment.objects.select_related('discussion'), id=comment_id)

    # Accept both JSON and form-encoded payloads
    try:
        payload = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, TypeError):
        payload = request.POST

    try:
        value = int(payload.get('value'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid vote value.'}, status=400)

    if value not in (VoteValueChoices.UPVOTE, VoteValueChoices.DOWNVOTE):
        return JsonResponse({'error': 'Vote must be +1 or -1.'}, status=400)

    value = VoteValueChoices.UPVOTE if value > 0 else VoteValueChoices.DOWNVOTE

    content_type = ContentType.objects.get_for_model(Comment)

    vote, created = Vote.objects.get_or_create(
        user=request.user,
        content_type=content_type,
        object_id=comment.id,
        defaults={'value': value},
    )

    if not created:
        if vote.value == value:
            # Same vote again → toggle it off
            vote.delete()
            user_vote = 0
        else:
            vote.value = value
            vote.save(update_fields=['value'])
            user_vote = vote.value
    else:
        user_vote = vote.value

    # Recompute from the actual vote rows (single source of truth)
    total = (
        Vote.objects.filter(content_type=content_type, object_id=comment.id)
        .aggregate(total=Sum('value'))['total'] or 0
    )
    comment.vote_count = total
    comment.save(update_fields=['vote_count'])

    return JsonResponse({
        'vote_count': total,
        'user_vote': user_vote,
        'comment_id': comment.id,
    })