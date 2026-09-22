from math import ceil

from django.core.paginator import Paginator
from django.shortcuts import render

from problems.models import DifficultyChoices

from . import services

PAGE_SIZE = 25


def leaderboard(request):
    """
    GET /leaderboard/
    All-time ranking by points from unique accepted problems.
    Public: shows only username, avatar and solve counts.
    """
    paginator = Paginator(services.leaderboard_queryset(), PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    elided_page_range = paginator.get_elided_page_range(
        number=page_obj.number, on_each_side=2, on_ends=1
    )

    me_id = request.user.pk if request.user.is_authenticated else None
    start = page_obj.start_index()
    rows = [
        {
            'rank': start + offset,
            'username': r['user__user_name'],
            'avatar_url': r['user__avatar_url'],
            'easy_solved': r['easy_solved'],
            'medium_solved': r['medium_solved'],
            'hard_solved': r['hard_solved'],
            'solved': r['solved'],
            'points': r['points'],
            'is_me': me_id is not None and r['user_id'] == me_id,
        }
        for offset, r in enumerate(page_obj.object_list)
    ]

    # Signed-in user who isn't on this page gets their own standing.
    my_standing = None
    if me_id is not None and not any(r['is_me'] for r in rows):
        my_standing = services.get_user_standing(me_id)
        if my_standing['rank']:
            my_standing['page'] = ceil(my_standing['rank'] / PAGE_SIZE)

    scoring = [
        {'label': label, 'css': value, 'points': services.POINTS[value]}
        for value, label in DifficultyChoices.choices
    ]

    return render(request, 'leaderboard/leaderboard.html', {
        'rows': rows,
        'page_obj': page_obj,
        'paginator': paginator,
        'elided_page_range': elided_page_range,
        'my_standing': my_standing,
        'scoring': scoring,
    })