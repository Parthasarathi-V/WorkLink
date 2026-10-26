from django.db import models

from jobs.models import Job


class ListingReview(models.Model):
    """Advisory flags for admin moderators. Never blocks or punishes anyone automatically."""
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name="listing_review")
    rule_flags = models.TextField(blank=True)
    ai_notes = models.TextField(blank=True)
    flagged = models.BooleanField(default=False)
    checked_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review of job #{self.job_id} ({'flagged' if self.flagged else 'ok'})"
