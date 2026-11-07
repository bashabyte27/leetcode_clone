"""
Background judging.

Submit returns immediately with the submission id; a small thread pool inside the
web process judges it while the browser polls /submissions/detail/<id>/.
This keeps web workers free during a submission rush. It is the stepping stone
to a Redis/Celery worker (see docs/hosting-and-scaling-plan.md, phase 2): only
`enqueue` needs to change for that.

If the process restarts mid-judge, `manage.py rebuild_progress` (run on deploy)
closes the stuck submission as an internal error.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import close_old_connections, transaction

logger = logging.getLogger(__name__)

_executor = None
_lock = threading.Lock()


def _pool():
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=getattr(settings, 'JUDGE_WORKERS', 4),
                thread_name_prefix='judge',
            )
        return _executor


def judge_and_record(submission_id):
    from submissions.judge import judge_submission
    from submissions.stats import record_judged_submission

    submission = judge_submission(submission_id)
    if submission is not None:
        try:
            record_judged_submission(submission)
        except Exception:
            logger.exception("Could not update progress for submission %s", submission_id)
    return submission


def _job(submission_id):
    close_old_connections()
    try:
        judge_and_record(submission_id)
    except Exception:
        logger.exception("Background judging crashed for submission %s", submission_id)
    finally:
        close_old_connections()


def enqueue(submission_id):
    """Judge in the background (default) or inline when JUDGE_ASYNC is off (tests, debugging)."""
    if not getattr(settings, 'JUDGE_ASYNC', False):
        return judge_and_record(submission_id)
    transaction.on_commit(lambda: _pool().submit(_job, submission_id))
    return None
