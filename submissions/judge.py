# submissions/judge.py

import re
import subprocess
import time
from decimal import Decimal
from problems.models import TestCase
from submissions.models import (
    Submission,
    SubmissionResult,
    SubmissionStatusChoices,
)


# ── Dangerous keywords to block ──
BLOCKED_KEYWORDS = [
    # OS and system access
    'import os',
    'import sys',
    'import shutil',
    'import subprocess',
    'import socket',
    'import requests',
    'import urllib',
    'import http',
    'import ftplib',
    'import telnetlib',

    # Dangerous functions
    'os.remove',
    'os.rmdir',
    'os.system',
    'os.popen',
    'os.kill',
    'os.fork',
    'shutil.rmtree',
    'sys.exit',

    # File access
    "open(",
    "file(",

    # Code execution
    'eval(',
    'exec(',
    'compile(',
    '__import__',
    'importlib',

    # Memory bombs
    '10**10',
    '10**9',
    'while True',
    'while 1',

    # Multiprocessing
    'import threading',
    'import multiprocessing',
    'import asyncio',
]


def is_code_safe(code):
    """
    Check if student code is safe to run.
    Returns (is_safe, reason)
    """
    # ── Check for input() with prompt string ──
    if re.search(r'input\s*\(\s*["\']', code):
        return False, "Do not use input() with a prompt string. Use input() without arguments, e.g: input()"

    code_lower = code.lower()

    for keyword in BLOCKED_KEYWORDS:
        if keyword.lower() in code_lower:
            return False, f"Dangerous code detected! '{keyword}' is not allowed."

    return True, None


def run_code(code, input_data, timeout=5):
    """
    Run student code using subprocess.
    Returns actual_output, runtime_ms, error
    """
    start = time.time()

    try:
        result = subprocess.run(
            ['python', '-c', code],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        end = time.time()
        runtime_ms = Decimal(str(round((end - start) * 1000, 2)))

        if result.returncode != 0:
            return None, runtime_ms, result.stderr.strip()

        return result.stdout.strip(), runtime_ms, None

    except subprocess.TimeoutExpired:
        return None, Decimal('0.00'), 'TIME_LIMIT_EXCEEDED'

def judge_submission(submission_id):
    """
    Judge function for Submit only.
    Runs ALL test cases, stops at first failure, updates final submission status.
    Run mode is handled separately by run_code() in views.py.
    """
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        return None

    # ── Step 1: Safety Check ──
    is_safe, reason = is_code_safe(submission.code)

    if not is_safe:
        submission.status = SubmissionStatusChoices.RUNTIME_ERROR
        submission.save(update_fields=['status'])

        test_cases = TestCase.objects.filter(problem=submission.problem).order_by('order_num')
        SubmissionResult.objects.bulk_create([
            SubmissionResult(
                submission=submission,
                test_case=tc,
                status=SubmissionStatusChoices.RUNTIME_ERROR,
                actual_output=reason,
                expected_output=tc.expected_output.strip(),
                runtime_ms=Decimal('0.00'),
            ) for tc in test_cases
        ])
        return submission

    # ── Step 2: Mark as running ──
    submission.status = SubmissionStatusChoices.RUNNING
    submission.save(update_fields=['status'])

    # ── Step 3: All test cases, always ──
    test_cases = TestCase.objects.filter(problem=submission.problem).order_by('order_num')

    if not test_cases.exists():
        submission.status = SubmissionStatusChoices.INTERNAL_ERROR
        submission.save(update_fields=['status'])
        return submission

    has_input = test_cases.filter(input_data__isnull=False).exclude(input_data='').exists()
    if has_input and 'input()' not in submission.code:
        submission.status = SubmissionStatusChoices.RUNTIME_ERROR
        submission.save(update_fields=['status'])

        SubmissionResult.objects.bulk_create([
            SubmissionResult(
                submission=submission,
                test_case=tc,
                status=SubmissionStatusChoices.RUNTIME_ERROR,
                actual_output="You forgot to read the input! Use input() to take the input.",
                expected_output=tc.expected_output.strip(),
                runtime_ms=Decimal('0.00'),
            ) for tc in test_cases
        ])
        return submission

    # ── Step 4: Run code against each test case, stop at first failure ──
    code = submission.code
    max_runtime = Decimal('0.00')
    final_status = SubmissionStatusChoices.ACCEPTED

    for tc in test_cases:
        input_data = tc.input_data.replace('\\n', '\n') if tc.input_data else ''
        expected_output = tc.expected_output.replace('\\n', '\n').strip() if tc.expected_output else ''

        actual_output, runtime_ms, error = run_code(code, input_data)
        if runtime_ms and runtime_ms > max_runtime:
            max_runtime = runtime_ms

        if error == 'TIME_LIMIT_EXCEEDED':
            tc_status = SubmissionStatusChoices.TIME_LIMIT_EXCEEDED
            final_status = SubmissionStatusChoices.TIME_LIMIT_EXCEEDED
            actual_output = ''
        elif error:
            tc_status = SubmissionStatusChoices.RUNTIME_ERROR
            final_status = SubmissionStatusChoices.RUNTIME_ERROR
            actual_output = error
        elif (actual_output or '').replace('\r\n', '\n').strip() == expected_output.replace('\r\n', '\n').strip():
            tc_status = SubmissionStatusChoices.ACCEPTED
        else:
            tc_status = SubmissionStatusChoices.WRONG_ANSWER
            if final_status == SubmissionStatusChoices.ACCEPTED:
                final_status = SubmissionStatusChoices.WRONG_ANSWER

        SubmissionResult.objects.create(
            submission=submission,
            test_case=tc,
            status=tc_status,
            actual_output=actual_output,
            expected_output=expected_output,
            runtime_ms=runtime_ms,
        )

        if tc_status != SubmissionStatusChoices.ACCEPTED:
            break   # always stop at first failure now — no mode check needed

    # ── Step 5: Update final submission ──
    submission.status = final_status
    submission.runtime_ms = max_runtime
    submission.save(update_fields=['status', 'runtime_ms'])

    return submission