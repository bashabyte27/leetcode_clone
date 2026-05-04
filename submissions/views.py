# submissions/views.py

import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from problems.models import Problem, Language
from submissions.models import Submission, SubmissionStatusChoices
from submissions.judge import judge_submission

def submission_list(request):
    return HttpResponse("Hello from seubmission list")


@csrf_exempt
@login_required
def submit_code(request, problem_slug):
    """
    POST /submissions/submit/<problem_slug>/
    Receives student code and runs it through judge.
    Returns JSON result.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed!'}, status=405)

    try:
        body = json.loads(request.body)
        code = body.get('code', '').strip()
        language_slug = body.get('language', 'python')

        if not code:
            return JsonResponse({'error': 'Code cannot be empty!'}, status=400)

        # Get problem
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # Get language
        try:
            language = Language.objects.get(slug=language_slug)
        except Language.DoesNotExist:
            return JsonResponse({'error': 'Language not found!'}, status=404)

        # Create submission
        submission = Submission.objects.create(
            user=request.user,
            problem=problem,
            language=language,
            code=code,
            status=SubmissionStatusChoices.PENDING,
        )

        # Run judge
        result = judge_submission(submission.id)

        # Build response
        test_case_results = []
        for r in result.results.all().order_by('test_case__order_num'):
            # Only show sample test case details to student
            if r.test_case.is_sample:
                test_case_results.append({
                    'tc_num': r.test_case.order_num,
                    'status': r.status,
                    'input': r.test_case.input_data,
                    'expected': r.expected_output,
                    'actual': r.actual_output,
                    'runtime_ms': str(r.runtime_ms),
                })
            else:
                # For non sample test cases only show status no details
                test_case_results.append({
                    'tc_num': r.test_case.order_num,
                    'status': r.status,
                    'runtime_ms': str(r.runtime_ms),
                })

        # Count accepted test cases
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
    Runs code against custom input — no submission saved.
    Returns stdout and stderr.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed!'}, status=405)

    try:
        body = json.loads(request.body)
        code = body.get('code', '').strip()
        custom_input = body.get('custom_input', '').strip()

        if not code:
            return JsonResponse({'error': 'Code cannot be empty!'}, status=400)

        # Get problem
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # Safety check first
        from submissions.judge import is_code_safe, run_code as execute_code
        is_safe, reason = is_code_safe(code)

        if not is_safe:
            return JsonResponse({
                'status': 'runtime_error',
                'stdout': '',
                'stderr': reason,
                'runtime_ms': '0.00',
            })

        # Run code against custom input
        actual_output, runtime_ms, error = execute_code(code, custom_input)

        return JsonResponse({
            'status': 'success' if not error else 'runtime_error',
            'stdout': actual_output or '',
            'stderr': error or '',
            'runtime_ms': str(runtime_ms),
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON!'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Internal error: {str(e)}'}, status=500)