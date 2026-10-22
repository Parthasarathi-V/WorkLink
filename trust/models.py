from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from applications.models import Application, Placement


class Complaint(models.Model):
    """A complaint is an allegation, not a verdict. Allegation, response and decision are stored separately."""
    class Category(models.TextChoices):
        NO_SHOW = "NO_SHOW", "No-show / left early"
        MISLEADING = "MISLEADING", "Misleading job or profile"
        UNSAFE = "UNSAFE", "Unsafe request or conditions"
        PAYMENT = "PAYMENT", "Pay dispute"
        HARASSMENT = "HARASSMENT", "Harassment or abuse"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        WAITING_FOR_RESPONSE = "WAITING_FOR_RESPONSE", "Waiting for response"
        RESOLVED = "RESOLVED", "Resolved"
        DISMISSED = "DISMISSED", "Dismissed"
        APPEALED = "APPEALED", "Appealed"

    complainant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="complaints_filed")
    respondent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="complaints_received")
    application = models.ForeignKey(Application, null=True, blank=True, on_delete=models.SET_NULL, related_name="complaints")
    category = models.CharField(max_length=12, choices=Category.choices)
    description = models.TextField(max_length=2000)
    evidence_reference = models.CharField(max_length=300, blank=True,
                                          help_text="Describe or reference your evidence (e.g. message dates). Don't paste ID numbers.")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    respondent_response = models.TextField(blank=True, max_length=2000)
    admin_decision = models.TextField(blank=True)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Complaint #{self.pk} ({self.status})"


class Review(models.Model):
    class Reason(models.TextChoices):
        PUNCTUAL = "PUNCTUAL", "Punctual / reliable"
        SKILLED = "SKILLED", "Did the job well"
        RESPECTFUL = "RESPECTFUL", "Respectful"
        CLEAR_TERMS = "CLEAR_TERMS", "Clear and honest terms"
        LATE = "LATE", "Late or unreliable"
        UNPROFESSIONAL = "UNPROFESSIONAL", "Unprofessional"
        MISLEADING = "MISLEADING", "Terms differed from listing"
        OTHER = "OTHER", "Other"

    class Moderation(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PUBLISHED = "PUBLISHED", "Published"
        HIDDEN = "HIDDEN", "Hidden"
        REMOVED = "REMOVED_AFTER_REVIEW", "Removed after review"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written")
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received")
    placement = models.ForeignKey(Placement, on_delete=models.PROTECT, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    reason_code = models.CharField(max_length=20, choices=Reason.choices)
    comment = models.TextField(blank=True, max_length=500)
    moderation_status = models.CharField(max_length=24, choices=Moderation.choices, default=Moderation.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["author", "placement"], name="one_review_per_author_per_placement"),
        ]

    def __str__(self):
        return f"Review {self.rating}/5 by {self.author_id} ({self.moderation_status})"
