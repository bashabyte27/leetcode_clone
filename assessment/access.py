from django.db.models import Q
from django.utils import timezone

from .models import Attempt


def user_has_active_exam(user):
    if not user.is_authenticated:
        return False
    now = timezone.now()
    return Attempt.objects.filter(
        participant__user=user,
        status=Attempt.Status.IN_PROGRESS,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    ).filter(
        Q(assessment_version__end_time__isnull=True)
        | Q(assessment_version__end_time__gt=now),
    ).exists()
