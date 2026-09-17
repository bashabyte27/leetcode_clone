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


def execute_batch(submissions):
    """
    Execute multiple code submissions at once via Judge0 batch API.
    Each item in submissions: {'language_id': int, 'source_code': str, 'stdin': str}
    Returns list of result dicts in the same order.
    """
    payload = {
        'submissions': [
            {
                'language_id': int(s['language_id']),
                'source_code': s['source_code'],
                'stdin': s.get('stdin', ''),
            } for s in submissions
        ]
    }
    url = f"{JUDGE0_BASE}/submissions/batch?base64_encoded=false&wait=false"
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=10)
        resp.raise_for_status()
        resp_data = resp.json()
        # Judge0 batch API returns a list directly, or may return {"submissions": [...]}
        if isinstance(resp_data, list):
            tokens = [item['token'] for item in resp_data]
        else:
            tokens = [item['token'] for item in resp_data.get('submissions', [])]
    except requests.RequestException as e:
        logger.error("Judge0 batch submit error: %s", e)
        return [
            {
                'status': {'id': 13, 'description': 'Internal Error'},
                'stdout': '',
                'stderr': f'Failed to submit batch to Judge0: {e}',
                'time': None,
                'memory': None,
            } for _ in submissions
        ]

    # Poll all tokens until judged or timeout
    results = {}
    deadline = time.time() + JUDGE0_TIMEOUT
    pending = list(enumerate(tokens))

    while pending and time.time() < deadline:
        still_pending = []
        for idx, token in pending:
            if idx in results:
                continue
            try:
                r = requests.get(
                    f"{JUDGE0_BASE}/submissions/{token}?base64_encoded=false",
                    headers=_headers(), timeout=5,
                )
                r.raise_for_status()
                d = r.json()
                status_id = d.get('status', {}).get('id', 1)
                if status_id >= 3:
                    results[idx] = d
                else:
                    still_pending.append((idx, token))
            except requests.RequestException:
                still_pending.append((idx, token))
        pending = still_pending
        if pending:
            time.sleep(0.3)

    # Grab final state for any still-pending submissions
    for idx, token in pending:
        if idx not in results:
            try:
                r = requests.get(
                    f"{JUDGE0_BASE}/submissions/{token}?base64_encoded=false",
                    headers=_headers(), timeout=5,
                )
                results[idx] = r.json()
            except requests.RequestException:
                results[idx] = {
                    'status': {'id': 13, 'description': 'Internal Error (timeout)'},
                    'stdout': '',
                    'stderr': 'Polling timed out.',
                    'time': None,
                    'memory': None,
                }

    # Return in original order
    return [results[i] for i in range(len(tokens))]
