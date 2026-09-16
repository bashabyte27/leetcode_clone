import random

from django.db.models import Exists, OuterRef
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from .models import Problem, TestCase
from submissions.models import Submission, SubmissionStatusChoices



def problem_list(request):
    problems = Problem.objects.filter(is_active=True)  # recommended to add filter
    accepted = Submission.objects.filter(
        user=request.user,
        problem=OuterRef("pk"),
        status=SubmissionStatusChoices.ACCEPTED
    )

    problems = Problem.objects.filter(is_active=True).annotate(
        is_solved=Exists(accepted)
)
    submissions = Submission.objects.filter(user=request.user, status=SubmissionStatusChoices.ACCEPTED)
    # easy_count = problems.filter(difficulty='easy').count()
    # medium_count = problems.filter(difficulty='medium').count()
    # hard_count = problems.filter(difficulty='hard').count()
    total_problems = Problem.objects.count()

    solved_count = Submission.objects.filter(
        user=request.user,
        status=SubmissionStatusChoices.ACCEPTED
    ).values("problem").distinct().count()
    easy_solved = Submission.objects.filter(
        user=request.user,
        status=SubmissionStatusChoices.ACCEPTED,
        problem__difficulty="easy"
    ).values("problem").distinct().count()
    medium_solved = Submission.objects.filter(
        user=request.user,
        status=SubmissionStatusChoices.ACCEPTED,
        problem__difficulty="medium"
    ).values("problem").distinct().count()
    hard_solved = Submission.objects.filter(
        user=request.user,
        status=SubmissionStatusChoices.ACCEPTED,
        problem__difficulty="hard"
    ).values("problem").distinct().count()

    progress = round((solved_count / total_problems) * 100, 2) if total_problems else 0

    context = {
        'problems': problems,
        'total_problems': problems.count(),
        'easy_count': problems.filter(difficulty='easy').count(),
        'medium_count': problems.filter(difficulty='medium').count(),
        'hard_count': problems.filter(difficulty='hard').count(),
        'submissions': submissions,
        'progress': progress,
        'Easy_solved': easy_solved,
        'Medium_solved': medium_solved,
        'Hard_solved': hard_solved
    }
    return render(request, 'problems/problems_list.html', context)

def problem_detail(request, problemname):
    # Fetch the problem by slug
    problem = get_object_or_404(Problem, slug=problemname, is_active=True)

    # Get all tags (many-to-many)
    tags = problem.tags.all()

    # Get sample test cases (is_sample=True)
    sample_cases = problem.test_cases.filter(is_sample=True).order_by('order_num')

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

    context = {
        'problem': problem,
        'serial_no': problem.order_num,
        'title': problem.title,
        'description': problem.description,
        'tags': tags,
        'sample_cases': sample_cases,
        'prev_problem': prev_problem,
        'next_problem': next_problem,
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
    all_problems = Problem.objects.all()

    return render(request,'problems/partials/problem_list_panel.html',{'all_problems':all_problems})

def discussion(request,problemname):
    #for every problem one discussion table
    return HttpResponse("Discussion tab is Under development")


def editorial(request, problemname):
    problem = get_object_or_404(Problem, slug=problemname)
    editorial = getattr(problem, 'editorial', None)
    return render(request, 'problems/partials/editorial.html', {'editorial': editorial})

def submission_history(request, problemname):
    submissions = Submission.objects.filter(
        user=request.user, problem__slug=problemname
    ).order_by('-created_at')
    return render(request, 'problems/partials/submissions.html', {'submissions': submissions})

def get_solution(request, problemname):
    return HttpResponse("solution under development")

def problem_page(request):
    all_problems = Problem.objects.all()
    return render(request,'problems/partials/problem_list.html',{'all_problems':all_problems})