# submissions/views.py

import json
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from problems.models import Problem, Language, TestCase
from submissions.models import Submission, SubmissionStatusChoices
from submissions.judge import judge_submission, is_code_safe, run_code as execute_code
from django.shortcuts import get_object_or_404, render


def submission_list(request):
    return HttpResponse("Hello from submission list")


@csrf_exempt
@login_required
def submit_code(request, problem_slug):
    """
    POST /submissions/submit/<problem_slug>/
    Runs code against ALL test cases.
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

        # ── Run judge in submit mode ──
        # Stops at first failure, updates final submission status
        result = judge_submission(submission.id)
        if result is None:                          # ← fixed: guard against None
            return JsonResponse({'error': 'Submission could not be processed!'}, status=500)

        # ── Build response ──
        test_case_results = []
        for r in result.results.all().order_by('test_case__order_num'):
            if r.test_case.is_sample:
                # Show full details for sample test cases
                test_case_results.append({
                    'tc_num': r.test_case.order_num,
                    'status': r.status,
                    'input': r.test_case.input_data.replace('\\n', '\n') if r.test_case.input_data else '',
                    'expected': r.expected_output.replace('\\n', '\n') if r.expected_output else '',
                    'actual': r.actual_output.replace('\\n', '\n') if r.actual_output else '',
                    'runtime_ms': str(r.runtime_ms),
                })
            else:
                # Hide details for hidden test cases, only show status
                test_case_results.append({
                    'tc_num': r.test_case.order_num,
                    'status': r.status,
                    'runtime_ms': str(r.runtime_ms),
                })

        total = result.results.count()
        accepted = result.results.filter(
            status=SubmissionStatusChoices.ACCEPTED
        ).count()

        return JsonResponse({
            'submission_id': result.id,
            'status': result.status,
            'runtime_ms': str(result.runtime_ms),
            'accepted': accepted,
            'total': total,
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
    Runs code against sample test cases ONLY.
    No Submission object created — this is just a temporary execution.
    Never stops early — shows all sample results like LeetCode run behavior.
    """
    if request.method != 'POST':
        print("problem in method")
        return JsonResponse({'error': 'Only POST method allowed!'}, status=405)
    

    try:
        body = json.loads(request.body)
        code = body.get('code', '').strip()

        if not code:
            print("code is empty")
            return JsonResponse({'error': 'Code cannot be empty!'}, status=400)

        # ── Get problem ──
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            print("problem not found")
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # ── Safety check ──
        is_safe, reason = is_code_safe(code)
        if not is_safe:
            print("code is not safe")
            return JsonResponse({
                'test_case_results': [],
                'error': reason,
            }, status=400)

        # ── Fetch sample test cases directly — no Submission needed ──
        test_cases = TestCase.objects.filter(
            problem=problem,
            is_sample=True
        ).order_by('order_num')

        print(f"Found {test_cases.count()} sample test cases")
        if not test_cases.exists():
            print("No sample test cases found")
            return JsonResponse({'error': 'No sample test cases found!'}, status=404)

        # ── Check if student forgot input() ──
        has_input = test_cases.filter(
            input_data__isnull=False
        ).exclude(input_data='').exists()

        if has_input and 'input()' not in code:
            print("forgot to read input")
            return JsonResponse({
                'test_case_results': [],
                'error': 'You forgot to read the input! Use input() to take the input.',
            }, status=400)

        # ── Run code against each sample test case ──
        test_case_results = []

        for tc in test_cases:
            input_data = tc.input_data.replace('\\n', '\n') if tc.input_data else ''
            expected_output = tc.expected_output.replace('\\n', '\n').strip() if tc.expected_output else ''

            actual_output, runtime_ms, error = execute_code(code, input_data)

            if error == 'TIME_LIMIT_EXCEEDED':
                print("code is taking too long to run")
                status = "Time Limit Exceeded"
                actual_output = ''
            elif error:
                print("code is giving runtime error")
                status = "Runtime Error"
                actual_output = error
            elif (actual_output or '').replace('\r\n', '\n').strip() == expected_output.replace('\r\n', '\n').strip():
                print("code is giving correct output")
                status = "success"
                print("code is ran successfully !")
            else:
                print("code is giving wrong output")
                status = "Wrong Answer"

            test_case_results.append({
                'tc_num': tc.order_num,
                'status': status,
                'input': tc.input_data.replace('\\n', '\n') if tc.input_data else '',
                'expected': expected_output,
                'actual': actual_output or '',
                'runtime_ms': str(runtime_ms),
            })
        print(test_case_results)

        return JsonResponse({
            'test_case_results': test_case_results,
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON!'}, status=400)

    except Exception as e:
        print(f"Unexpected error occurred: {str(e)}")
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)

# submissions/views.py
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
    submission = get_object_or_404(
        Submission.objects.select_related('problem', 'language'),
        id=submission_id,
        user=request.user,
    )

    results = submission.results.select_related('test_case').order_by('test_case__order_num')

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
        'code': submission.code,
        'status': submission.status,
        'language': submission.language.name if submission.language else None,
        'runtime_ms': str(submission.runtime_ms) if submission.runtime_ms is not None else None,
        'submitted_at': submission.submitted_at.isoformat(),
        'results': results_data,
    })