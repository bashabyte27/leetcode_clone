from django.shortcuts import render, get_object_or_404
from .models import Problem, TestCase
from django.http import HttpResponse
from submissions.models import Submission

def problem_list(request):
    problems = Problem.objects.filter(is_active=True)  # recommended to add filter
    context = {
        'problems': problems,
        'total_problems': problems.count(),
        'easy_count': problems.filter(difficulty='easy').count(),
        'medium_count': problems.filter(difficulty='medium').count(),
        'hard_count': problems.filter(difficulty='hard').count(),
    }
    return render(request, 'problems/problems_list.html', context)

def problem_detail(request, problemname):
    # Fetch the problem by slug
    problem = get_object_or_404(Problem, slug=problemname, is_active=True)

    # Get all tags (many-to-many)
    tags = problem.tags.all()   # or problem.tags.values_list('name', flat=True)

    # Get sample test cases (is_sample=True)
    sample_cases = problem.test_cases.filter(is_sample=True).order_by('order_num')

    context = {
        'problem': problem,
        'serial_no': problem.order_num,
        'title': problem.title,
        'description': problem.description,
        'tags': tags,
        'sample_cases': sample_cases,
    }
    return render(request, 'problems/problem_detail.html', context)


def problem_get_list(request):
    #left side view of problems list
    return HttpResponse("Under Processing")

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