# submissions/views.py

import json
import logging
from functools import wraps

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from problems.models import Problem, Language, TestCase
from submissions.models import Submission, SubmissionStatusChoices
from submissions.judge import (
    is_code_safe,
    _code_reads_input,
    normalize_case_text,
    comparable_case_text,
    run_many,
)
from submissions.queue import enqueue
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

MAX_RUN_CASES = 10
MAX_CODE_LENGTH = 100_000
MAX_CASE_INPUT = 64 * 1024  # characters


def json_login_required(view):
    """Like login_required, but answers API calls with JSON 401 instead of a login-page redirect."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Please log in to run or submit code.', 'login_required': True}, status=401)
        return view(request, *args, **kwargs)
    return wrapper


@json_login_required
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
        if len(code) > MAX_CODE_LENGTH:
            return JsonResponse({'error': 'Code is too long (max 100,000 characters).'}, status=400)

        # ── Get problem ──
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # ── Get language ──
        try:
            language = Language.objects.get(slug=language_slug, is_active=True)
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

        # One submission at a time per student keeps the judge queue fair
        if Submission.objects.filter(
            user=request.user,
            status__in=[SubmissionStatusChoices.PENDING, SubmissionStatusChoices.RUNNING],
            submitted_at__gte=timezone.now() - timedelta(minutes=2),
        ).exists():
            return JsonResponse({'error': 'Your previous submission is still being judged. Please wait a moment.'}, status=429)

        # ── Create submission ──
        submission = Submission.objects.create(
            user=request.user,
            problem=problem,
            language=language,
            code=code,
            status=SubmissionStatusChoices.PENDING,
            solve_time_seconds=solve_time,
        )

        # ── Judge: in the background (browser polls the detail URL) or inline ──
        judged = enqueue(submission.id)
        if judged is None:
            return JsonResponse({
                'submission_id': submission.id,
                'status': SubmissionStatusChoices.PENDING,
                'queued': True,
                'poll_url': reverse('submissions:submission_detail', args=[submission.id]),
            }, status=202)
        return JsonResponse(submission_payload(judged))

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON!'}, status=400)

    except Exception:
        logger.exception("Code execution request failed")
        return JsonResponse({'error': 'Something went wrong on our side. Please try again.'}, status=500)


@json_login_required
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
        if len(code) > MAX_CODE_LENGTH:
            return JsonResponse({'error': 'Code is too long (max 100,000 characters).'}, status=400)

        language_slug = body.get('language', 'python')

        # ── Get problem ──
        try:
            problem = Problem.objects.get(slug=problem_slug, is_active=True)
        except Problem.DoesNotExist:
            return JsonResponse({'error': 'Problem not found!'}, status=404)

        # ── Get language ──
        try:
            language = Language.objects.get(slug=language_slug, is_active=True)
        except Language.DoesNotExist:
            return JsonResponse({'error': 'Language not found!'}, status=404)

        # ── Safety check ──
        is_safe, reason = is_code_safe(code, language)
        if not is_safe:
            return JsonResponse({
                'test_case_results': [],
                'error': reason,
            }, status=400)

        # ── Sample test cases (the reference answers) ──
        samples = list(TestCase.objects.filter(problem=problem, is_sample=True).order_by('order_num'))
        sample_by_input = {}
        for tc in samples:
            sample_by_input.setdefault(comparable_case_text(tc.input_data), tc)

        # ── Cases to run: what the student has in the testcase panel (they may edit them) ──
        requested = body.get('cases')
        cases = []
        if isinstance(requested, list) and requested:
            for i, item in enumerate(requested[:MAX_RUN_CASES], start=1):
                if not isinstance(item, dict):
                    continue
                raw = normalize_case_text(item.get('input', ''))
                if len(raw) > MAX_CASE_INPUT:
                    return JsonResponse({'error': f'Case {i} input is too large (max 64 KB).'}, status=400)
                match = sample_by_input.get(comparable_case_text(raw))
                cases.append({'tc_num': item.get('tc_num') or i, 'input': raw, 'sample': match,
                              'label': str(item.get('label') or '')[:20]})
        else:
            cases = [{'tc_num': tc.order_num, 'input': normalize_case_text(tc.input_data), 'sample': tc, 'label': ''}
                     for tc in samples]

        if not cases:
            return JsonResponse({'error': 'No test cases to run. Add an input in the Testcase panel.'}, status=400)

        # ── Check if student forgot to read the input ──
        if any(c['input'].strip() for c in cases) and not _code_reads_input(code):
            return JsonResponse({
                'test_case_results': [],
                'error': 'You forgot to read the input! Use input(), Scanner, scanf, cin, readline, fmt.Scan, etc. to take the input.',
            }, status=400)

        # ── One Judge0 batch for all cases ──
        outcomes = run_many(code, language, [c['input'] for c in cases], problem=problem)
        test_case_results = []
        for case, (actual_output, runtime_ms, error, status) in zip(cases, outcomes):
            sample = case['sample']
            expected_output = comparable_case_text(sample.expected_output) if sample else ''

            if status == 'tle':
                status, actual_output = "Time Limit Exceeded", ''
            elif status == 'compile_error':
                status, actual_output = "Compile Error", error
            elif status == 'runtime_error':
                status, actual_output = "Runtime Error", error
            elif status == 'accepted' and sample is None:
                status = "success"  # custom input: it ran fine, nothing to compare against
            elif status == 'accepted' and comparable_case_text(actual_output) == expected_output:
                status = "success"
            else:
                status = "Wrong Answer"

            test_case_results.append({
                'tc_num': case['tc_num'],
                'status': status,
                'custom': sample is None,
                'label': case['label'],
                'input': case['input'],
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

    except Exception:
        logger.exception("Code execution request failed")
        return JsonResponse({'error': 'Something went wrong on our side. Please try again.'}, status=500)


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

    submissions = list(submissions)
    accepted_runs = [s for s in submissions if s.status == SubmissionStatusChoices.ACCEPTED]
    runtimes = [s.runtime_ms for s in accepted_runs if s.runtime_ms is not None]
    memories = [s.memory_kb for s in accepted_runs if s.memory_kb is not None]
    summary = {
        'total': len(submissions),
        'accepted': len(accepted_runs),
        'rate': round(len(accepted_runs) * 100 / len(submissions)) if submissions else 0,
        'best_runtime': min(runtimes) if runtimes else None,
        'best_memory': min(memories) if memories else None,
    }

    return render(request, 'submissions/submission_list.html', {
        'problem': problem,
        'submissions': submissions,
        'summary': summary,
    })


PENDING_STATES = (SubmissionStatusChoices.PENDING, SubmissionStatusChoices.RUNNING)


def submission_payload(submission):
    """Everything the editor needs to show a submission's verdict."""
    results = list(submission.results.select_related('test_case').order_by('test_case__order_num'))
    results_data = [{
        'tc_num': r.test_case.order_num,
        'status': r.status,
        'is_sample': r.test_case.is_sample,
        'runtime_ms': str(r.runtime_ms) if r.runtime_ms is not None else None,
        **({'input': normalize_case_text(r.test_case.input_data),
            'expected': normalize_case_text(r.expected_output),
            'actual': normalize_case_text(r.actual_output)}
           if r.test_case.is_sample else {}),
    } for r in results]
    accepted = sum(1 for r in results if r.status == SubmissionStatusChoices.ACCEPTED)
    pending = submission.status in PENDING_STATES
    performance = []
    if not pending:
        recent = (Submission.objects.filter(
            problem_id=submission.problem_id,
            language_id=submission.language_id,
            status=SubmissionStatusChoices.ACCEPTED,
        ).exclude(runtime_ms__isnull=True).order_by('-submitted_at').values('runtime_ms', 'memory_kb')[:500])
        performance = [{
            'runtime_ms': str(item['runtime_ms']) if item['runtime_ms'] is not None else None,
            'memory_kb': str(item['memory_kb']) if item['memory_kb'] is not None else None,
        } for item in recent]
    return {
        'submission_id': submission.id,
        'problem': submission.problem.title,
        'code': submission.code,
        'status': submission.status,
        'pending': pending,
        'language': submission.language.name if submission.language else None,
        'runtime_ms': str(submission.runtime_ms) if submission.runtime_ms is not None else None,
        'memory_kb': str(submission.memory_kb) if submission.memory_kb else None,
        'runtime_percentile': str(submission.runtime_percentile) if submission.runtime_percentile is not None else None,
        'memory_percentile': str(submission.memory_percentile) if submission.memory_percentile is not None else None,
        'submitted_at': submission.submitted_at.isoformat(),
        'accepted': accepted,
        # Judging stops at the first failure, so "total" is every test case of the problem
        'total': submission.problem.test_cases.count(),
        'performance': performance,
        'results': results_data,
        'test_case_results': results_data,
    }


@json_login_required
def submission_detail(request, submission_id):
    submissions = Submission.objects.select_related('problem', 'language')
    if not (request.user.is_staff and request.headers.get('X-Staff-Inspection') == '1'):
        submissions = submissions.filter(user=request.user)
    submission = get_object_or_404(submissions, id=submission_id)
    return JsonResponse(submission_payload(submission))
