from datetime import timedelta
from math import ceil

from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from problems.models import DifficultyChoices
from problems.stats import _streaks

from . import services

PAGE_SIZE = 25


def _decorate(rows, prev_ranks, activity):
    """Add tier, rank movement, streak and a 14-day sparkline to each row."""
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(services.ACTIVITY_DAYS - 1, -1, -1)]
    for row in rows:
        row['tier'] = services.tier_for(row['points'])

        before = prev_ranks.get(row['user_id'])
        row['move'] = None if before is None else before - row['rank']
        row['is_new'] = before is None

        per_day = activity.get(row['user_id'], {})
        spark = [per_day.get(d, 0) for d in days]
        peak = max(spark) or 1
        row['spark'] = [{'n': n, 'h': round(n * 100 / peak), 'date': d} for n, d in zip(spark, days)]
        row['active_days'] = sum(1 for n in spark if n)
        row['streak'], _ = _streaks({d for d, n in per_day.items() if n}, today)
        last = max(per_day) if per_day else None
        row['last_active_days'] = (today - last).days if last else None

        solved = row['solved'] or 1
        row['mix'] = {
            'easy': round(row['easy_solved'] * 100 / solved),
            'medium': round(row['medium_solved'] * 100 / solved),
            'hard': round(row['hard_solved'] * 100 / solved),
        }
    return rows


def leaderboard(request):
    """
    GET /leaderboard/
    Ranking by points from unique accepted problems, optionally filtered by period.
    Public: shows only username, avatar and solve counts.
    """
    query = request.GET.get('q', '').strip()
    period = request.GET.get('period', 'all').strip().lower()
    if period not in {'all', 'week', 'month'}:
        period = 'all'

    paginator = Paginator(services.leaderboard_queryset(query, period=period), PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    elided_page_range = paginator.get_elided_page_range(
        number=page_obj.number, on_each_side=2, on_ends=1
    )

    me_id = request.user.pk if request.user.is_authenticated else None
    start = page_obj.start_index()
    rows = [
        {
            'rank': start + offset,
            'user_id': r['user_id'],
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

    # Fixed-cost extras (one query each, independent of the number of users)
    if rows:
        _decorate(
            rows,
            services.previous_ranks(period),
            services.activity_for([r['user_id'] for r in rows]),
        )

    # Signed-in user who isn't on this page gets their own standing.
    my_standing = None
    if me_id is not None and not any(r['is_me'] for r in rows):
        my_standing = services.get_user_standing(me_id, period=period)
        if my_standing['rank']:
            my_standing['page'] = ceil(my_standing['rank'] / PAGE_SIZE)
            my_standing['tier'] = services.tier_for(my_standing['points'])

    # "Who's just above me" — the most motivating gap to show
    me_row = next((r for r in rows if r['is_me']), None)
    me_summary = me_row or my_standing
    rival = None
    if me_summary and me_summary.get('rank') and me_summary['rank'] > 1 and not query:
        above_rank = me_summary['rank'] - 1
        above = next((r for r in rows if r['rank'] == above_rank), None)
        if above is None:
            found = list(services.leaderboard_queryset(period=period)[above_rank - 1:above_rank])
            if found:
                above = {'username': found[0]['user__user_name'], 'points': found[0]['points'], 'rank': above_rank}
        if above:
            rival = {
                'username': above['username'],
                'rank': above_rank,
                'gap': max(above['points'] - me_summary['points'], 0),
            }

    scoring = [
        {'label': label, 'css': value, 'points': services.POINTS[value]}
        for value, label in DifficultyChoices.choices
    ]

    return render(request, 'leaderboard/leaderboard.html', {
        'rows': rows,
        'podium': rows[:3] if page_obj.number == 1 and not query else [],
        'page_obj': page_obj,
        'paginator': paginator,
        'elided_page_range': elided_page_range,
        'my_standing': my_standing,
        'me_row': me_row,
        'rival': rival,
        'scoring': scoring,
        'tiers': services.tier_table(),
        'active_today': services.active_today_count() if rows else 0,
        'query': query,
        'period': period,
        'movement_days': services.MOVEMENT_DAYS,
    })
