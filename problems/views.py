from django.shortcuts import render, get_object_or_404
from .models import Problem, TestCase
from django.http import HttpResponse

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

def get_solution(request):
    return HttpResponse("Under Development")

def problem_get_list(request):
    return HttpResponse("Under Processing")
    