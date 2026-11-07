# submissions/judge0.py
"""
Thin HTTP client for the Judge0 code execution API.
Handles submission creation, polling, and result parsing.
"""

import time
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

JUDGE0_BASE = settings.JUDGE0_URL.rstrip('/')
JUDGE0_TIMEOUT = settings.JUDGE0_TIMEOUT


def _headers():
    """Build request headers with optional auth token."""
    h = {'Content-Type': 'application/json'}
    if settings.JUDGE0_AUTH_TOKEN:
        h['X-Auth-Token'] = settings.JUDGE0_AUTH_TOKEN
    return h


def _wait_for_result(token, poll_interval=0.3):
    """
    Poll Judge0 until the submission is judged (status.id >= 3).
    Returns the final submission dict.
    """
    url = f"{JUDGE0_BASE}/submissions/{token}?base64_encoded=false"
    deadline = time.time() + JUDGE0_TIMEOUT
    attempts = 0
    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=_headers(), timeout=5)
            resp.raise_for_status()
            data = resp.json()
            status_id = data.get('status', {}).get('id', 1)
            # Judge0 status ids: 1=In Queue, 2=Processing, >=3 = judged
            if status_id >= 3:
                return data
        except requests.RequestException as e:
            logger.warning("Judge0 poll error (attempt %d): %s", attempts, e)
        attempts += 1
        time.sleep(poll_interval)

    # Timeout — fetch final state
    try:
        resp = requests.get(url, headers=_headers(), timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {
            'status': {'id': 13, 'description': 'Internal Error (poll timeout)'},
            'stdout': '',
            'stderr': 'Execution timed out while waiting for Judge0 response.',
            'time': None,
            'memory': None,
        }


def execute_single(language_id, source_code, stdin=''):
    """
    Execute a single code submission via Judge0.
    Returns the raw Judge0 response dict with stdout, stderr, status, time, memory.
    """
    payload = {
        'language_id': int(language_id),
        'source_code': source_code,
        'stdin': stdin,
    }
    url = f"{JUDGE0_BASE}/submissions?base64_encoded=false&wait=false"
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=10)
        resp.raise_for_status()
        token = resp.json()['token']
    except requests.RequestException as e:
        logger.error("Judge0 submit error: %s", e)
        return {
            'status': {'id': 13, 'description': 'Internal Error'},
            'stdout': '',
            'stderr': f'Failed to submit code to Judge0: {e}',
            'time': None,
            'memory': None,
        }

    return _wait_for_result(token)


# Judge0 CE upper bounds; anything above is rejected by the server.
_MAX_LIMITS = {'cpu_time_limit': 15, 'wall_time_limit': 20, 'memory_limit': 512000}


def _payload_item(s):
    item = {
        'language_id': int(s['language_id']),
        'source_code': s['source_code'],
        'stdin': s.get('stdin', ''),
    }
    for key, cap in _MAX_LIMITS.items():
        if s.get(key):
            item[key] = min(float(s[key]), cap) if key != 'memory_limit' else min(int(s[key]), cap)
    return item


def execute_batch(submissions):
    """
    Execute multiple code submissions at once via Judge0 batch API.
    Each item in submissions: {'language_id': int, 'source_code': str, 'stdin': str}
    Returns list of result dicts in the same order.
    """
    payload = {'submissions': [_payload_item(s) for s in submissions]}
    url = f"{JUDGE0_BASE}/submissions/batch?base64_encoded=false&wait=false"
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=10)
        resp.raise_for_status()
        resp_data = resp.json()
        # Judge0 batch API returns a list directly, or may return {"submissions": [...]}
        items = resp_data if isinstance(resp_data, list) else resp_data.get('submissions', [])
        # An item without a token was rejected by Judge0 (e.g. bad language id)
        tokens = [item.get('token') if isinstance(item, dict) else None for item in items]
    except (requests.RequestException, ValueError) as e:
        logger.error("Judge0 batch submit error: %s", e)
        return [_error_result(f'Failed to submit batch to Judge0: {e}') for _ in submissions]

    results = {i: _error_result('Judge0 rejected this test case.') for i, t in enumerate(tokens) if not t}
    pending = {i: t for i, t in enumerate(tokens) if t}

    # Poll every pending token with ONE request per round (batch status endpoint)
    deadline = time.time() + JUDGE0_TIMEOUT
    while pending and time.time() < deadline:
        for idx, data in _fetch_batch(pending).items():
            if data.get('status', {}).get('id', 1) >= 3:
                results[idx] = data
                pending.pop(idx, None)
        if pending:
            time.sleep(0.3)

    # Whatever is still queued after the deadline is reported as a timeout
    for idx in pending:
        results[idx] = _error_result('Judging timed out. The judge is busy, please try again.')

    count = max(len(tokens), len(submissions))
    return [results.get(i) or _error_result('No result returned from Judge0.') for i in range(count)]


_FIELDS = 'token,status,stdout,stderr,compile_output,time,memory'


def _fetch_batch(pending):
    """GET /submissions/batch for all pending tokens; returns {index: result} for those received."""
    order = list(pending.items())
    try:
        r = requests.get(
            f"{JUDGE0_BASE}/submissions/batch",
            params={'tokens': ','.join(t for _, t in order), 'base64_encoded': 'false', 'fields': _FIELDS},
            headers=_headers(), timeout=10,
        )
        r.raise_for_status()
        rows = r.json().get('submissions', [])
    except (requests.RequestException, ValueError) as e:
        logger.warning("Judge0 batch poll error: %s", e)
        return {}
    by_token = {row.get('token'): row for row in rows if isinstance(row, dict)}
    return {idx: by_token[t] for idx, t in order if t in by_token}


def _error_result(message):
    return {
        'status': {'id': 13, 'description': 'Internal Error'},
        'stdout': '',
        'stderr': message,
        'time': None,
        'memory': None,
    }
