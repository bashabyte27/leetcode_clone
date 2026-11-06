"""
problems/stats.py
-----------------
Read-side numbers for the problems page: per-problem acceptance rates,
a user's practice calendar (submission heatmap + streaks), and the
"today's pick" suggestion.

Acceptance is computed live from submissions, the same way LeetCode
defines it: accepted / judged submissions.  Pending and running
submissions are excluded because they have no verdict yet.
"""

from datetime import date, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from submissions.models import Submission, SubmissionStatusChoices

UNJUDGED = (SubmissionStatusChoices.PENDING, SubmissionStatusChoices.RUNNING)
CALENDAR_DAYS = 365


def annotate_acceptance(queryset):
    """Add judged_count / accepted_count to a Problem queryset."""
    return queryset.annotate(
        judged_count=Count(
            "submissions", filter=~Q(submissions__status__in=UNJUDGED), distinct=True
        ),
        accepted_count=Count(
            "submissions",
            filter=Q(submissions__status=SubmissionStatusChoices.ACCEPTED),
            distinct=True,
        ),
    )


def acceptance_percent(problem):
    """Acceptance as a float rounded to 1 dp, or None when nothing was judged."""
    judged = getattr(problem, "judged_count", 0)
    if not judged:
        return None
    return round(problem.accepted_count * 100 / judged, 1)


def _level(count):
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count <= 3:
        return 2
    if count <= 6:
        return 3
    return 4


def _streaks(active_days, today):
    """(current, longest) runs of consecutive active days."""
    if not active_days:
        return 0, 0
    ordered = sorted(active_days)
    longest = run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        longest = max(longest, run)

    # A streak stays alive until the end of today, so start from
    # yesterday when nothing has been submitted yet today.
    cursor = today if today in active_days else today - timedelta(days=1)
    current = 0
    while cursor in active_days:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


def practice_calendar(user, today=None):
    """
    Submission heatmap for the last year, laid out as week columns
    (Sunday first), plus active-day and streak totals.
    """
    tz = timezone.get_current_timezone()
    today = today or timezone.localdate()

    per_day = dict(
        Submission.objects.filter(user=user)
        .order_by()
        .annotate(day=TruncDate("submitted_at", tzinfo=tz))
        .values("day")
        .annotate(n=Count("id"))
        .values_list("day", "n")
    )
    all_active = {d for d, n in per_day.items() if n}

    start = today - timedelta(days=CALENDAR_DAYS - 1)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back up to Sunday

    weeks, months = [], []
    year_total = 0
    year_active = 0
    cursor = start
    last_month = None
    while cursor <= today:
        week = []
        for _ in range(7):
            if cursor > today:
                week.append(None)
            else:
                n = per_day.get(cursor, 0)
                if cursor >= today - timedelta(days=CALENDAR_DAYS - 1):
                    year_total += n
                    year_active += 1 if n else 0
                week.append({"date": cursor, "count": n, "level": _level(n)})
            cursor += timedelta(days=1)
        first = next(c for c in week if c)
        if first["date"].month != last_month:
            # Skip a label squeezed into the first partial week
            if weeks or first["date"].day <= 7:
                months.append({"col": len(weeks) + 1, "label": first["date"].strftime("%b")})
            last_month = first["date"].month
        weeks.append(week)

    # A label needs ~3 columns of room; drop one that would spill off the end
    months = [m for m in months if m["col"] <= len(weeks) - 2]

    current, longest = _streaks(all_active, today)
    return {
        "weeks": weeks,
        "months": months,
        "total": year_total,
        "active_days": year_active,
        "current_streak": current,
        "max_streak": longest,
        "practiced_today": today in all_active,
    }


def todays_pick(problems, today=None):
    """
    Deterministic daily suggestion: the same problem all day, rotating
    through unsolved problems first.
    """
    if not problems:
        return None
    today = today or timezone.localdate()
    pool = [p for p in problems if not getattr(p, "is_solved", False)] or list(problems)
    return pool[(today - date(2024, 1, 1)).days % len(pool)]
