import json

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.password_validation import validate_password
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from leaderboard.services import get_user_standing
from problems.models import DifficultyChoices, Problem, TestCase
from submissions.models import Submission, SubmissionStatusChoices, UserSolvedProblem
from users.models import UserProfile, Users

from .services import import_problems, import_users, pdf_response, user_snapshot, xlsx_response

staff_required = user_passes_test(lambda user: user.is_authenticated and user.is_staff, login_url='users:login')


def _page(request, queryset, per_page=25):
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return paginator, page_obj


@staff_required
def dashboard(request):
    context = {
        'user_count': Users.objects.count(),
        'active_user_count': Users.objects.filter(is_active=True).count(),
        'problem_count': Problem.objects.count(),
        'active_problem_count': Problem.objects.filter(is_active=True).count(),
        'submission_count': Submission.objects.count(),
        'accepted_count': Submission.objects.filter(status=SubmissionStatusChoices.ACCEPTED).count(),
        'recent_submissions': Submission.objects.select_related('user', 'problem').order_by('-submitted_at')[:8],
    }
    return render(request, 'staff/dashboard.html', context)


@staff_required
def user_list(request):
    query = request.GET.get('q', '').strip()
    users = Users.objects.filter(is_staff=False).select_related('profile', 'stats').order_by('-created_at')
    if query:
        users = users.filter(Q(user_name__icontains=query) | Q(email__icontains=query))
    paginator, page_obj = _page(request, users)
    return render(request, 'staff/user_list.html', {'page_obj': page_obj, 'paginator': paginator, 'query': query})


@staff_required
def user_create(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        user_name = request.POST.get('user_name', '').strip()
        password = request.POST.get('password', '')
        try:
            if not email or not user_name or not password:
                raise ValueError('Email, username, and password are required.')
            if Users.objects.filter(Q(email__iexact=email) | Q(user_name__iexact=user_name)).exists():
                raise ValueError('Email or username already exists.')
            user = Users(email=email, user_name=user_name, is_verified=True)
            validate_password(password, user)
            user.set_password(password)
            user.full_clean(); user.save()
            messages.success(request, f'Created {user.user_name}.')
            return redirect('staff:user_detail', user_id=user.id)
        except Exception as exc:
            messages.error(request, str(exc))
    return render(request, 'staff/user_form.html', {'mode': 'create'})


@staff_required
def user_import(request):
    result = None
    if request.method == 'POST':
        upload = request.FILES.get('file')
        if not upload or not upload.name.lower().endswith(('.csv', '.xlsx')):
            result = {'created': 0, 'errors': ['Upload a CSV or XLSX file.']}
        else:
            result = import_users(upload)
    return render(request, 'staff/import.html', {'kind': 'users', 'result': result})


@staff_required
def user_detail(request, user_id):
    user = get_object_or_404(Users.objects.select_related('profile', 'stats'), id=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    snapshot = user_snapshot(user)
    solved_paginator, solved_page = _page(request, snapshot['solved'], 20)
    history_paginator, history_page = _page(request, snapshot['submissions'], 20)
    return render(request, 'staff/user_detail.html', {
        'target_user': user, 'profile': profile, 'snapshot': snapshot,
        'standing': snapshot['standing'], 'solved_page': solved_page, 'solved_paginator': solved_paginator,
        'history_page': history_page, 'history_paginator': history_paginator,
    })


@staff_required
def user_toggle_active(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(Users, id=user_id)
        if user.id == request.user.id:
            messages.error(request, 'You cannot block your own staff account.')
        else:
            user.is_active = not user.is_active; user.save(update_fields=['is_active', 'updated_at'])
            messages.success(request, f'{user.user_name} is now {"active" if user.is_active else "blocked"}.')
    return redirect('staff:user_detail', user_id=user_id)


@staff_required
def user_export_xlsx(request, user_id):
    user = get_object_or_404(Users, id=user_id)
    return xlsx_response(user, user_snapshot(user))


@staff_required
def user_export_pdf(request, user_id):
    user = get_object_or_404(Users, id=user_id)
    return pdf_response(user, user_snapshot(user))


@staff_required
def problem_list(request):
    query = request.GET.get('q', '').strip()
    problems = Problem.objects.select_related('created_by').order_by('order_num', 'title')
    if query:
        problems = problems.filter(Q(title__icontains=query) | Q(slug__icontains=query))
    paginator, page_obj = _page(request, problems)
    return render(request, 'staff/problem_list.html', {'page_obj': page_obj, 'paginator': paginator, 'query': query})


@staff_required
def problem_create(request):
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            difficulty = request.POST.get('difficulty', '').strip()
            if not title or not description or difficulty not in DifficultyChoices.values:
                raise ValueError('Title, description, and a valid difficulty are required.')

            raw_cases = request.POST.get('test_cases', '').strip()
            cases = []
            if raw_cases:
                try:
                    cases = json.loads(raw_cases)
                except json.JSONDecodeError as exc:
                    raise ValueError(f'Test cases must be valid JSON: {exc.msg}.') from exc
                if not isinstance(cases, list):
                    raise ValueError('Test cases must be a JSON list.')
                for number, case in enumerate(cases, 1):
                    if not isinstance(case, dict) or not case.get('input_data') or not case.get('expected_output'):
                        raise ValueError(
                            f'Test case {number} needs input_data and expected_output.'
                        )

            problem = Problem(
                title=title,
                slug=slugify(title),
                description=description,
                difficulty=difficulty,
                created_by=request.user,
            )
            order_num = request.POST.get('order_num', '').strip()
            if order_num: problem.order_num = int(order_num)
            problem.is_premium = request.POST.get('is_premium') == 'on'
            with transaction.atomic():
                problem.full_clean()
                problem.save()
                for number, case in enumerate(cases, 1):
                    TestCase.objects.create(
                        problem=problem,
                        order_num=number,
                        input_data=str(case['input_data']),
                        expected_output=str(case['expected_output']),
                        is_sample=bool(case.get('is_sample', False)),
                        explanation=case.get('explanation') or None,
                    )
            messages.success(request, f'Created problem {problem.title}.')
            return redirect('staff:problem_list')
        except Exception as exc:
            messages.error(request, str(exc))
    return render(request, 'staff/problem_form.html', {'difficulties': DifficultyChoices.choices})


@staff_required
def problem_import(request):
    result = None
    if request.method == 'POST':
        upload = request.FILES.get('file')
        if not upload or not upload.name.lower().endswith(('.csv', '.xlsx')):
            result = {'created': 0, 'updated': 0, 'errors': ['Upload a CSV or XLSX file.']}
        else:
            result = import_problems(upload, actor=request.user)
    return render(request, 'staff/import.html', {'kind': 'problems', 'result': result})
