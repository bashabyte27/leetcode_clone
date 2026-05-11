# submissions/views.py

import json
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from problems.models import Problem, Language, TestCase
from submissions.models import Submission, SubmissionStatusChoices
from submissions.judge import judge_submission, is_code_safe, run_code as execute_code


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

        # ── Create submission ──
        submission = Submission.objects.create(
            user=request.user,
            problem=problem,
            language=language,
            code=code,
            status=SubmissionStatusChoices.PENDING,
        )

        # ── Run judge in submit mode ──
        # Stops at first failure, updates final submission status
        result = judge_submission(submission.id, mode='submit')

        # ── Build response ──
        test_case_results = []
        for r in result.results.all().order_by('test_case__order_num'):
            if r.test_case.is_sample:
                # Show full details for sample test cases
                test_case_results.append({
                    'tc_num': r.test_case.order_num,
                    'status': r.status,
                    'input': r.test_case.input_data,
                    'expected': r.expected_output,
                    'actual': r.actual_output,
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
        return JsonResponse({'error': 'Only POST method allowed!'}, status=405)

    try:
        body = json.loads(request.body)
        code = body.get('code', '').strip()

        if not code:
            return JsonResponse({'error': 'Code cannot be empty!'}, status=400)

        # ── Get problem ──
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # ── Safety check ──
        is_safe, reason = is_code_safe(code)
        if not is_safe:
            return JsonResponse({
                'test_case_results': [],
                'error': reason,
            }, status=400)

        # ── Fetch sample test cases directly — no Submission needed ──
        test_cases = TestCase.objects.filter(
            problem=problem,
            is_sample=True
        ).order_by('order_num')

        if not test_cases.exists():
            return JsonResponse({'error': 'No sample test cases found!'}, status=404)

        # ── Check if student forgot input() ──
        has_input = test_cases.filter(
            input_data__isnull=False
        ).exclude(input_data='').exists()

        if has_input and 'input()' not in code:
            return JsonResponse({
                'test_case_results': [],
                'error': 'You forgot to read the input! Use input() to take the input.',
            }, status=400)

        # ── Run code against each sample test case ──
        test_case_results = []

        for tc in test_cases:
            input_data = tc.input_data.replace('\\n', '\n')
            expected_output = tc.expected_output.strip()

            actual_output, runtime_ms, error = execute_code(code, input_data)

            if error == 'TIME_LIMIT_EXCEEDED':
                status = SubmissionStatusChoices.TIME_LIMIT_EXCEEDED
                actual_output = ''
            elif error:
                status = SubmissionStatusChoices.RUNTIME_ERROR
                actual_output = error
            elif actual_output == expected_output:
                status = SubmissionStatusChoices.ACCEPTED
            else:
                status = SubmissionStatusChoices.WRONG_ANSWER

            test_case_results.append({
                'tc_num': tc.order_num,
                'status': status,
                'input': tc.input_data,
                'expected': expected_output,
                'actual': actual_output or '',
                'runtime_ms': str(runtime_ms),
            })

        return JsonResponse({
            'test_case_results': test_case_results,
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON!'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)