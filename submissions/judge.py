# submissions/judge.py
"""
Code safety checks and submission judging via Judge0 API.
Replaces the previous subprocess-based execution with Judge0 HTTP calls.
"""

import re
import logging
from decimal import Decimal

from problems.models import TestCase
from submissions import judge0 as judge0_client
from submissions.models import (
    Submission,
    SubmissionResult,
    SubmissionStatusChoices,
)

logger = logging.getLogger(__name__)


def normalize_case_text(value):
    """Preserve multiline testcase content while normalizing stored escapes and line endings."""
    if value is None:
        return ''
    return str(value).replace('\\r\\n', '\n').replace('\\n', '\n').replace('\r\n', '\n').replace('\r', '\n')


def comparable_case_text(value):
    """Normalize output for comparison without flattening internal line breaks."""
    return normalize_case_text(value).strip()


# ── Judge0 status_id → BashaByte status mapping ──

JUDGE0_STATUS_MAP = {
    3:  SubmissionStatusChoices.ACCEPTED,
    4:  SubmissionStatusChoices.WRONG_ANSWER,
    5:  SubmissionStatusChoices.TIME_LIMIT_EXCEEDED,
    6:  SubmissionStatusChoices.COMPILE_ERROR,
    7:  SubmissionStatusChoices.RUNTIME_ERROR,   # SIGSEGV
    8:  SubmissionStatusChoices.RUNTIME_ERROR,   # SIGXFSZ
    9:  SubmissionStatusChoices.RUNTIME_ERROR,   # SIGFPE
    10: SubmissionStatusChoices.RUNTIME_ERROR,   # SIGABRT
    11: SubmissionStatusChoices.RUNTIME_ERROR,   # NZEC
    12: SubmissionStatusChoices.RUNTIME_ERROR,   # Other
    13: SubmissionStatusChoices.INTERNAL_ERROR,
    14: SubmissionStatusChoices.RUNTIME_ERROR,   # Exec Format Error
}


def _map_judge0_status(judge0_result):
    """Map a Judge0 result dict to a BashaByte SubmissionStatusChoices."""
    status_info = judge0_result.get('status', {})
    status_id = status_info.get('id', 13)
    return JUDGE0_STATUS_MAP.get(status_id, SubmissionStatusChoices.INTERNAL_ERROR)


def _parse_decimal(value):
    """Convert a value to Decimal safely, returning None if not possible."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _get_judge_id(language):
    """
    Get Judge0 language_id from a Language model instance.
    Returns int or None if not supported.
    """
    if language and language.judge_id:
        try:
            return int(language.judge_id)
        except (ValueError, TypeError):
            return None
    return None


def is_code_safe(code):
    """
    Basic safety check for student code.
    Judge0 runs code in a sandbox, so we only check for
    input() with prompt strings (which break stdin piping).
    Returns (is_safe, reason).
    """
    if re.search(r'input\s*\(\s*["\']', code):
        return False, "Do not use input() with a prompt string. Use input() without arguments."
    return True, None


# ── Language-agnostic input detection ──

# Patterns that indicate the code reads from stdin (non-exhaustive, covers common langs)
_INPUT_PATTERNS = [
    r'input\s*\(',                          # Python: input()
    r'Scanner\s*\(',                         # Java: new Scanner(System.in)
    r'System\.in',                           # Java: System.in
    r'scanf\s*\(',                           # C: scanf(...)
    r'scanf_s\s*\(',                         # C (MSVC): scanf_s(...)
    r'cin\s*>>',                             # C++: cin >>
    r'cin\.getline\s*\(',                    # C++: cin.getline(...)
    r'std::cin\s*>>',                        # C++: std::cin >>
    r'readline',                             # JS (Node): require('readline')
    r'createInterface\s*\(',                 # JS (Node): readline.createInterface
    r'process\.stdin',                       # JS (Node): process.stdin
    r'require\s*\(\s*["\']readline',         # JS (Node): const readline = require('readline')
    r'prompt-sync',                          # JS: require('prompt-sync')
    r'fmt\.Scan',                            # Go: fmt.Scan*
    r'os\.Stdin',                            # Go: os.Stdin
    r'bufio\.NewReader',                     # Go: bufio.NewReader(os.Stdin)
    r'(?:std::)?io::stdin',                  # Rust: io::stdin() / std::io::stdin()
    r'read_line\s*\(',                       # Rust: io::stdin().read_line()
    r'BufReader::new',                       # Rust: BufReader::new(io::stdin())
]


def _code_reads_input(code):
    """Check if code contains any stdin-reading pattern across common languages."""
    for pattern in _INPUT_PATTERNS:
        if re.search(pattern, code):
            return True
    return False


def run_code(code, language, input_data=''):
    """
    Execute code once via Judge0 (for Run mode).
    Returns (actual_output, runtime_ms, error_or_none, status_string).
    status_string ∈ {'accepted', 'compile_error', 'runtime_error', 'tle', 'wrong_answer'}.
    error_or_none is a friendly message (compiler output for compile errors,
    stderr for runtime errors), or None if execution succeeded.
    """
    judge_id = _get_judge_id(language)
    if judge_id is None:
        return None, Decimal('0.00'), 'Language not supported for execution.', 'runtime_error'

    result = judge0_client.execute_single(judge_id, code, input_data)

    runtime_ms = _parse_decimal(result.get('time'))
    if runtime_ms is not None:
        # Judge0 returns time in seconds, convert to ms
        runtime_ms = (runtime_ms * 1000).quantize(Decimal('0.01'))
    else:
        runtime_ms = Decimal('0.00')

    status = _map_judge0_status(result)
    stdout = (result.get('stdout') or '').strip()
    stderr = (result.get('stderr') or '').strip()
    compile_output = (result.get('compile_output') or '').strip()

    if status == SubmissionStatusChoices.ACCEPTED:
        return stdout, runtime_ms, None, 'accepted'
    elif status == SubmissionStatusChoices.TIME_LIMIT_EXCEEDED:
        return None, runtime_ms, 'TIME_LIMIT_EXCEEDED', 'tle'
    elif status == SubmissionStatusChoices.COMPILE_ERROR:
        return None, runtime_ms, compile_output or stderr or 'Compilation Error', 'compile_error'
    elif status in (SubmissionStatusChoices.RUNTIME_ERROR, SubmissionStatusChoices.INTERNAL_ERROR):
        return None, runtime_ms, stderr or compile_output or 'Runtime Error', 'runtime_error'
    else:
        # Wrong Answer — return stdout for comparison
        return stdout, runtime_ms, None, 'wrong_answer'


def judge_submission(submission_id):
    """
    Judge a full submission (Submit mode) against ALL test cases via Judge0 batch API.
    Creates SubmissionResult for each test case.
    Stops at first failure (same as LeetCode behavior).
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
                expected_output=comparable_case_text(tc.expected_output),
                runtime_ms=Decimal('0.00'),
            ) for tc in test_cases
        ])
        return submission

    # ── Step 2: Mark as running ──
    submission.status = SubmissionStatusChoices.RUNNING
    submission.save(update_fields=['status'])

    # ── Step 3: Fetch test cases ──
    test_cases = list(TestCase.objects.filter(problem=submission.problem).order_by('order_num'))
    if not test_cases:
        submission.status = SubmissionStatusChoices.INTERNAL_ERROR
        submission.save(update_fields=['status'])
        return submission

    # ── Step 4: Check for input-reading code ──
    has_input = any(tc.input_data for tc in test_cases if tc.input_data)
    if has_input and not _code_reads_input(submission.code):
        submission.status = SubmissionStatusChoices.RUNTIME_ERROR
        submission.save(update_fields=['status'])
        SubmissionResult.objects.bulk_create([
            SubmissionResult(
                submission=submission,
                test_case=tc,
                status=SubmissionStatusChoices.RUNTIME_ERROR,
                actual_output="You forgot to read the input! Use input(), Scanner, scanf, cin, readline, fmt.Scan, etc. to take the input.",
                expected_output=comparable_case_text(tc.expected_output),
                runtime_ms=Decimal('0.00'),
            ) for tc in test_cases
        ])
        return submission

    # ── Step 5: Get Judge0 language_id ──
    judge_id = _get_judge_id(submission.language)
    if judge_id is None:
        submission.status = SubmissionStatusChoices.INTERNAL_ERROR
        submission.save(update_fields=['status'])
        return submission

    # ── Step 6: Build batch submissions ──
    batch_items = []
    for tc in test_cases:
        input_data = normalize_case_text(tc.input_data)
        batch_items.append({
            'language_id': judge_id,
            'source_code': submission.code,
            'stdin': input_data,
        })

    # ── Step 7: Execute batch via Judge0 ──
    results = judge0_client.execute_batch(batch_items)

    # ── Step 8: Process results, stop at first failure ──
    max_runtime = Decimal('0.00')
    max_memory = Decimal('0.00')
    final_status = SubmissionStatusChoices.ACCEPTED

    for i, tc in enumerate(test_cases):
        if i >= len(results):
            # Not enough results from Judge0
            tc_status = SubmissionStatusChoices.INTERNAL_ERROR
            actual_output = 'No result returned from Judge0.'
            runtime_ms = Decimal('0.00')
            memory_kb = None
        else:
            j0 = results[i]
            tc_status = _map_judge0_status(j0)

            runtime_ms = _parse_decimal(j0.get('time'))
            if runtime_ms is not None:
                runtime_ms = (runtime_ms * 1000).quantize(Decimal('0.01'))
            else:
                runtime_ms = Decimal('0.00')

            memory_kb = _parse_decimal(j0.get('memory'))
            if memory_kb is not None:
                memory_kb = memory_kb.quantize(Decimal('0.01'))

            stdout = (j0.get('stdout') or '').strip()
            stderr = (j0.get('stderr') or '').strip()
            compile_output = (j0.get('compile_output') or '').strip()
            expected_output = comparable_case_text(tc.expected_output)

            if tc_status == SubmissionStatusChoices.ACCEPTED:
                actual_output = stdout
                if comparable_case_text(stdout) != expected_output:
                    tc_status = SubmissionStatusChoices.WRONG_ANSWER
                    final_status = SubmissionStatusChoices.WRONG_ANSWER
            elif tc_status == SubmissionStatusChoices.WRONG_ANSWER:
                actual_output = stdout
                if final_status == SubmissionStatusChoices.ACCEPTED:
                    final_status = SubmissionStatusChoices.WRONG_ANSWER
            elif tc_status == SubmissionStatusChoices.TIME_LIMIT_EXCEEDED:
                actual_output = ''
                final_status = SubmissionStatusChoices.TIME_LIMIT_EXCEEDED
            elif tc_status == SubmissionStatusChoices.COMPILE_ERROR:
                actual_output = compile_output or stderr
                final_status = SubmissionStatusChoices.COMPILE_ERROR
            elif tc_status in (SubmissionStatusChoices.RUNTIME_ERROR, SubmissionStatusChoices.INTERNAL_ERROR):
                actual_output = stderr or compile_output or 'Runtime Error'
                final_status = tc_status
            else:
                actual_output = stdout
                final_status = tc_status

        if runtime_ms and runtime_ms > max_runtime:
            max_runtime = runtime_ms
        if memory_kb and memory_kb > max_memory:
            max_memory = memory_kb

        expected_output = comparable_case_text(tc.expected_output)

        SubmissionResult.objects.create(
            submission=submission,
            test_case=tc,
            status=tc_status,
            actual_output=actual_output or '',
            expected_output=expected_output,
            runtime_ms=runtime_ms,
            memory_kb=memory_kb,
        )

        if tc_status != SubmissionStatusChoices.ACCEPTED:
            break  # Stop at first failure

    # ── Step 9: Update final submission ──
    submission.status = final_status
    submission.runtime_ms = max_runtime
    submission.memory_kb = max_memory if max_memory > 0 else None
    submission.save(update_fields=['status', 'runtime_ms', 'memory_kb'])

    return submission
