from django.utils import timezone

from notifications.services import audit, notify
from .models import VerificationStatus


def profile_for(user, account_type):
    return user.workerprofile if account_type == "worker" else user.businessprofile


def apply_verification_decision(submission, reviewer):
    """Sync the account's status with a reviewed submission, notify the owner, write an audit event."""
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.save(update_fields=["reviewed_by", "reviewed_at"])
    profile = profile_for(submission.user, submission.account_type)
    profile.verification_status = submission.status
    profile.save(update_fields=["verification_status", "updated_at"])
    notify(submission.user, "Your verification status has changed",
           f"Status: {submission.get_status_display()}. " + (submission.decision_reason or ""), "/accounts/verification/")
    audit(reviewer, f"verification_{submission.status.lower()}", submission, submission.decision_reason)


def is_pending(user, account_type):
    return user.verifications.filter(account_type=account_type, status=VerificationStatus.PENDING).exists()
