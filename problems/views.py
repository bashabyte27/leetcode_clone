import random

from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from .models import Problem, TestCase
from submissions.models import Submission, SubmissionStatusChoices
from submissions.judge import normalize_case_text
from assessment.access import user_has_active_exam
from leaderboard import services as leaderboard_services

from .stats import acceptance_percent, annotate_acceptance, practice_calendar, todays_pick


def problem_list(request):
    user = request.user if request.user.is_authenticated else None

    problems = annotate_acceptance(
        Problem.objects.filter(is_active=True).order_by("order_num", "id")
    )
    if user:
        problems = problems.annotate(
            is_solved=Exists(
                Submission.objects.filter(
                    user=user,
                    problem=OuterRef("pk"),
                    status=SubmissionStatusChoices.ACCEPTED,
                )
            )
        )
    problems = list(problems)

    counts = {"easy": 0, "medium": 0, "hard": 0}
    solved = {"easy": 0, "medium": 0, "hard": 0}
    for problem in problems:
        problem.acceptance = acceptance_percent(problem)
        if problem.difficulty in counts:
            counts[problem.difficulty] += 1
            if getattr(problem, "is_solved", False):
                solved[problem.difficulty] += 1

    total = len(problems)
    solved_total = sum(solved.values())
    context = {
        "problems": problems,
        "total_problems": total,
        "easy_count": counts["easy"],
        "medium_count": counts["medium"],
        "hard_count": counts["hard"],
        "easy_solved": solved["easy"],
        "medium_solved": solved["medium"],
        "hard_solved": solved["hard"],
        "solved_total": solved_total,
        "progress": round(solved_total * 100 / total) if total else 0,
        "daily_pick": todays_pick(problems),
    }

    if user:
        context["calendar"] = practice_calendar(user)
        totals = Submission.objects.filter(user=user).exclude(
            status__in=(SubmissionStatusChoices.PENDING, SubmissionStatusChoices.RUNNING)
        ).aggregate(
            submissions=Count("id"),
            accepted=Count("id", filter=Q(status=SubmissionStatusChoices.ACCEPTED)),
        )
        totals["rate"] = (
            round(totals["accepted"] * 100 / totals["submissions"], 1) if totals["submissions"] else None
        )
        context["user_totals"] = totals
        context["standing"] = leaderboard_services.get_user_standing(user.id)
        context["recent_submissions"] = list(
            Submission.objects.filter(user=user)
            .select_related("problem")
            .only("status", "submitted_at", "problem__title", "problem__slug")[:5]
        )
    return render(request, "problems/problems_list.html", context)


def problem_detail(request, problemname):
    # Fetch the problem by slug
    problem = get_object_or_404(Problem, slug=problemname, is_active=True)

    # Get all tags (many-to-many)
    tags = problem.tags.all()

    # Get sample test cases (is_sample=True)
    sample_cases = [
        {
            'order_num': case.order_num,
            'input_data': normalize_case_text(case.input_data),
            'expected_output': normalize_case_text(case.expected_output),
            'explanation': case.explanation,
        }
        for case in problem.test_cases.filter(is_sample=True).order_by('order_num')
    ]

    # Previous / Next by order_num
    prev_problem = None
    next_problem = None
    if problem.order_num is not None:
        prev_problem = (
            Problem.objects.filter(is_active=True, order_num__lt=problem.order_num)
            .order_by('-order_num')
            .first()
        )
        next_problem = (
            Problem.objects.filter(is_active=True, order_num__gt=problem.order_num)
            .order_by('order_num')
            .first()
        )

    # Display-only extras: live acceptance, solved state, editorial reference complexity
    stats = annotate_acceptance(Problem.objects.filter(pk=problem.pk)).values(
        'judged_count', 'accepted_count'
    ).first() or {'judged_count': 0, 'accepted_count': 0}
    judged = stats['judged_count']
    is_solved = request.user.is_authenticated and Submission.objects.filter(
        user=request.user, problem=problem, status=SubmissionStatusChoices.ACCEPTED
    ).exists()
    editorial = getattr(problem, 'editorial', None)
    reference_complexity = None
    if editorial and editorial.is_published and (editorial.time_complexity or editorial.space_complexity):
        reference_complexity = {
            'time': editorial.time_complexity or '',
            'space': editorial.space_complexity or '',
        }

    context = {
        'acceptance': round(stats['accepted_count'] * 100 / judged, 1) if judged else None,
        'judged_count': judged,
        'accepted_count': stats['accepted_count'],
        'is_solved': is_solved,
        'reference_complexity': reference_complexity,
        'problem': problem,
        'serial_no': problem.order_num,
        'title': problem.title,
        'description': problem.description,
        'tags': tags,
        'hints': problem.hints.all(),
        'sample_cases': sample_cases,
        'prev_problem': prev_problem,
        'next_problem': next_problem,
        'coding_mode': 'practice',
    }
    return render(request, 'problems/problem_detail.html', context)


def shuffle_problem(request):
    """Redirect to a random active problem."""
    slugs = list(
        Problem.objects.filter(is_active=True, order_num__isnull=False)
        .values_list('slug', flat=True)
    )
    if not slugs:
        # Fallback: any active problem
        slugs = list(
            Problem.objects.filter(is_active=True).values_list('slug', flat=True)
        )
    if slugs:
        target = random.choice(slugs)
        return HttpResponseRedirect(reverse('problems:problem', args=[target]))
    return HttpResponseRedirect(reverse('problems:problem_list'))


def problem_get_list(request):
    #left side view of problems list
    all_problems = Problem.objects.filter(is_active=True).order_by('order_num')

    return render(request,'problems/partials/problem_list_panel.html',{'all_problems':all_problems})


def editorial(request, problemname):
    if user_has_active_exam(request.user):
        return HttpResponse(
            "Editorial content is unavailable during an assessment.",
            status=403,
        )
    problem = get_object_or_404(Problem, slug=problemname)
    editorial = getattr(problem, 'editorial', None)
    return render(request, 'problems/partials/editorial.html', {'editorial': editorial})
