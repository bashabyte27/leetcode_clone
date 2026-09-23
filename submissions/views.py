# submissions/views.py

import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from problems.models import Problem, Language, TestCase
from submissions.models import Submission, SubmissionStatusChoices
from submissions.judge import (
    judge_submission,
    is_code_safe,
    _code_reads_input,
    normalize_case_text,
    comparable_case_text,
    run_code as execute_code,
)
from django.shortcuts import get_object_or_404, render


def submission_list(request):
    return HttpResponse("Hello from submission list")


@csrf_exempt
@login_required
def submit_code(request, problem_slug):
    """
    POST /submissions/submit/<problem_slug>/
    Runs code against ALL test cases via Judge0.
    Stops at first failure — same as LeetCode submit behavior.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed!'}, status=405)

    try:
        body = json.loads(request.body)
        code = body.get('code', '').strip()
        language_slug = body.get('language', 'python')

        if not code:
            return JsonResponse({'error': 'Code cannot be empty!'}, status=400)

        # ── Get problem ──
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # ── Get language ──
        try:
            language = Language.objects.get(slug=language_slug)
        except Language.DoesNotExist:
            return JsonResponse({'error': 'Language not found!'}, status=404)

        # ── Solve time (seconds from problem open to submission) ──
        solve_time = None
        start_ts = body.get('elapsed_seconds') or body.get('elapsed')
        if start_ts is not None:
            try:
                elapsed = int(float(start_ts))
                if 0 <= elapsed <= 86400:
                    solve_time = elapsed
            except (TypeError, ValueError):
                pass

        # ── Create submission ──
        submission = Submission.objects.create(
            user=request.user,
            problem=problem,
            language=language,
            code=code,
            status=SubmissionStatusChoices.PENDING,
            solve_time_seconds=solve_time,
        )

        # ── Run judge via Judge0 ──
        result = judge_submission(submission.id)
        if result is None:
            return JsonResponse({'error': 'Submission could not be processed!'}, status=500)

        # ── Build response ──
        test_case_results = []
        for r in result.results.all().order_by('test_case__order_num'):
            if r.test_case.is_sample:
                test_case_results.append({
                    'tc_num': r.test_case.order_num,
                    'status': r.status,
                    'input': normalize_case_text(r.test_case.input_data),
                    'expected': normalize_case_text(r.expected_output),
                    'actual': normalize_case_text(r.actual_output),
                    'runtime_ms': str(r.runtime_ms),
                })
            else:
                test_case_results.append({
                    'tc_num': r.test_case.order_num,
                    'status': r.status,
                    'runtime_ms': str(r.runtime_ms),
                })

        total = result.results.count()
        accepted = result.results.filter(
            status=SubmissionStatusChoices.ACCEPTED
        ).count()
        accepted_submissions = Submission.objects.filter(
            problem=problem,
            language=language,
            status=SubmissionStatusChoices.ACCEPTED,
        ).exclude(runtime_ms__isnull=True)

        return JsonResponse({
            'submission_id': result.id,
            'code': result.code,
            'status': result.status,
            'language': result.language.name if result.language else language.name,
            'runtime_ms': str(result.runtime_ms),
            'memory_kb': str(result.memory_kb) if result.memory_kb else None,
            'accepted': accepted,
            'total': total,
            'submitted_at': result.submitted_at.isoformat(),
            'runtime_percentile': str(result.runtime_percentile) if result.runtime_percentile is not None else None,
            'memory_percentile': str(result.memory_percentile) if result.memory_percentile is not None else None,
            'performance': [
                {
                    'runtime_ms': str(item.runtime_ms) if item.runtime_ms is not None else None,
                    'memory_kb': str(item.memory_kb) if item.memory_kb is not None else None,
                }
                for item in accepted_submissions.only('runtime_ms', 'memory_kb')
            ],
            'test_case_results': test_case_results,
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON!'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)


@csrf_exempt
@login_required
def run_code(request, problem_slug):
    """
    POST /submissions/run/<problem_slug>/
    Runs code against sample test cases via Judge0.
    No Submission object created — this is just a temporary execution.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed!'}, status=405)

    try:
        body = json.loads(request.body)
        code = body.get('code', '').strip()

        if not code:
            return JsonResponse({'error': 'Code cannot be empty!'}, status=400)

        language_slug = body.get('language', 'python')

        # ── Get problem ──
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # ── Get language ──
        try:
            language = Language.objects.get(slug=language_slug)
        except Language.DoesNotExist:
            return JsonResponse({'error': 'Language not found!'}, status=404)

        # ── Safety check ──
        is_safe, reason = is_code_safe(code)
        if not is_safe:
            return JsonResponse({
                'test_case_results': [],
                'error': reason,
            }, status=400)

        # ── Fetch sample test cases ──
        test_cases = TestCase.objects.filter(
            problem=problem,
            is_sample=True
        ).order_by('order_num')

        if not test_cases.exists():
            return JsonResponse({'error': 'No sample test cases found!'}, status=404)

        # ── Check if student forgot to read the input ──
        has_input = test_cases.filter(
            input_data__isnull=False
        ).exclude(input_data='').exists()

        if has_input and not _code_reads_input(code):
            return JsonResponse({
                'test_case_results': [],
                'error': 'You forgot to read the input! Use input(), Scanner, scanf, cin, readline, fmt.Scan, etc. to take the input.',
            }, status=400)

        # ── Run code against each sample test case via Judge0 ──
        test_case_results = []

        for tc in test_cases:
            input_data = normalize_case_text(tc.input_data)
            expected_output = comparable_case_text(tc.expected_output)

            actual_output, runtime_ms, error, status = execute_code(code, language, input_data)

            if status == 'tle':
                status = "Time Limit Exceeded"
                actual_output = ''
            elif status == 'compile_error':
                status = "Compile Error"
                actual_output = error
            elif status == 'runtime_error':
                status = "Runtime Error"
                actual_output = error
            elif status == 'accepted':
                if comparable_case_text(actual_output) == expected_output:
                    status = "success"
                else:
                    status = "Wrong Answer"
            else:
                status = "Wrong Answer"

            test_case_results.append({
                'tc_num': tc.order_num,
                'status': status,
                'input': normalize_case_text(tc.input_data),
                'expected': expected_output,
                'actual': actual_output or '',
                'runtime_ms': str(runtime_ms),
            })

        return JsonResponse({
            'test_case_results': test_case_results,
            'selected_case': body.get('selected_case'),
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON!'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)


@login_required
def submission_list(request, problem_slug):
    """
    GET /submissions/<problem_slug>/
    Shows the logged-in user's submission history for ONE specific problem only.
    """
    problem = get_object_or_404(Problem, slug=problem_slug, is_active=True)

    submissions = Submission.objects.filter(
        user=request.user,
        problem=problem,
    ).select_related('language').order_by('-submitted_at')

    return render(request, 'submissions/submission_list.html', {
        'problem': problem,
        'submissions': submissions,
    })


@login_required
def submission_detail(request, submission_id):
    submissions = Submission.objects.select_related('problem', 'language')
    if not (request.user.is_staff and request.headers.get('X-Staff-Inspection') == '1'):
        submissions = submissions.filter(user=request.user)
    submission = get_object_or_404(submissions, id=submission_id)

    results = submission.results.select_related('test_case').order_by('test_case__order_num')
    accepted_submissions = Submission.objects.filter(
        problem=submission.problem,
        language=submission.language,
        status=SubmissionStatusChoices.ACCEPTED,
    ).exclude(runtime_ms__isnull=True)

    results_data = [{
        'tc_num': r.test_case.order_num,
        'status': r.status,
        'is_sample': r.test_case.is_sample,
        'runtime_ms': str(r.runtime_ms) if r.runtime_ms is not None else None,
        **({'input': r.test_case.input_data, 'expected': r.expected_output, 'actual': r.actual_output}
           if r.test_case.is_sample else {}),
    } for r in results]

    return JsonResponse({
        'submission_id': submission.id,
        'problem': submission.problem.title,
        'code': submission.code,
        'status': submission.status,
        'language': submission.language.name if submission.language else None,
        'runtime_ms': str(submission.runtime_ms) if submission.runtime_ms is not None else None,
        'memory_kb': str(submission.memory_kb) if submission.memory_kb is not None else None,
        'runtime_percentile': str(submission.runtime_percentile) if submission.runtime_percentile is not None else None,
        'memory_percentile': str(submission.memory_percentile) if submission.memory_percentile is not None else None,
        'submitted_at': submission.submitted_at.isoformat(),
        'performance': [
            {
                'runtime_ms': str(item.runtime_ms) if item.runtime_ms is not None else None,
                'memory_kb': str(item.memory_kb) if item.memory_kb is not None else None,
            }
            for item in accepted_submissions.only('runtime_ms', 'memory_kb')
        ],
        'results': results_data,
    })
