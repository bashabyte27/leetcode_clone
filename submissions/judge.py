# submissions/judge.py

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
    Main judge function.
    Takes submission_id, runs code against all test cases,
    saves SubmissionResult for each, updates Submission status.
    """
    try:
        submission = Submission.objects.get(id=submission_id)
    except Submission.DoesNotExist:
        return

    # ── Step 1 Safety Check first ──
    is_safe, reason = is_code_safe(submission.code)

    if not is_safe:
        submission.status = SubmissionStatusChoices.RUNTIME_ERROR
        submission.save()

        # Save one result with the danger message
        test_cases = TestCase.objects.filter(
            problem=submission.problem
        ).order_by('order_num')

        for tc in test_cases:
            SubmissionResult.objects.create(
                submission=submission,
                test_case=tc,
                status=SubmissionStatusChoices.RUNTIME_ERROR,
                actual_output=reason,
                expected_output=tc.expected_output.strip(),
                runtime_ms=Decimal('0.00'),
            )

        return submission

    # ── Step 2 Mark as running ──
    submission.status = SubmissionStatusChoices.RUNNING
    submission.save()

    # ── Step 3 Get all test cases ──
    test_cases = TestCase.objects.filter(
        problem=submission.problem
    ).order_by('order_num')

    if not test_cases.exists():
        submission.status = SubmissionStatusChoices.INTERNAL_ERROR
        submission.save()
        return

    code = submission.code
    total_runtime = Decimal('0.00')
    final_status = SubmissionStatusChoices.ACCEPTED

    # ── Step 4 Run code against each test case ──
    for tc in test_cases:
        input_data = tc.input_data.replace('\\n', '\n')
        expected_output = tc.expected_output.strip()

        actual_output, runtime_ms, error = run_code(code, input_data)
        total_runtime += runtime_ms

        if error == 'TIME_LIMIT_EXCEEDED':
            tc_status = SubmissionStatusChoices.TIME_LIMIT_EXCEEDED
            final_status = SubmissionStatusChoices.TIME_LIMIT_EXCEEDED
            actual_output = ''

        elif error:
            tc_status = SubmissionStatusChoices.RUNTIME_ERROR
            final_status = SubmissionStatusChoices.RUNTIME_ERROR
            actual_output = error

        elif actual_output == expected_output:
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

    # ── Step 5 Update final submission ──
    submission.status = final_status
    submission.runtime_ms = total_runtime
    submission.save()

    return submission