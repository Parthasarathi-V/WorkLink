from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import BusinessProfile, WorkerProfile
from jobs.models import Job


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "APPLIED", "Applied"
        SHORTLISTED = "SHORTLISTED", "Shortlisted"
        INTERVIEW = "INTERVIEW", "Interview"
        SELECTED = "SELECTED", "Selected"
        ACCEPTED = "ACCEPTED", "Accepted by worker"
        JOINED = "JOINED", "Joined"
        REJECTED = "REJECTED", "Rejected"
        DECLINED = "DECLINED", "Declined by worker"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="applications")
    worker = models.ForeignKey(WorkerProfile, on_delete=models.PROTECT, related_name="applications")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.APPLIED, db_index=True)
    cover_note = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "worker"], name="unique_application_per_job_worker"),
        ]

    def __str__(self):
        return f"{self.worker} -> {self.job} ({self.status})"


class ApplicationStatusHistory(models.Model):
    """Append-only: we keep every transition, not just the current status."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    reason = models.CharField(max_length=300, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at", "id"]


class ApplicationMessage(models.Model):
    """Platform-mediated communication; visible only to the two parties and staff coordinators."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class Placement(models.Model):
    """Actual joining, recorded separately from selection/acceptance."""
    class Status(models.TextChoices):
        PENDING = "PENDING", "Awaiting confirmation"
        CONFIRMED = "CONFIRMED", "Confirmed"
        DISPUTED = "DISPUTED", "Disputed (admin review)"

    application = models.OneToOneField(Application, on_delete=models.PROTECT, related_name="placement")
    joined_at = models.DateField()
    confirmed_by_worker = models.BooleanField(default=False)
    confirmed_by_business = models.BooleanField(default=False)
    confirmed_by_admin = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Placement #{self.pk} ({self.status})"

    @property
    def protection_ends(self):
        return self.joined_at + timedelta(days=settings.WORKLINK["PROTECTION_DAYS"])

    @property
    def in_protection_window(self):
        return timezone.localdate() <= self.protection_ends


class PlacementFeeRecord(models.Model):
    """Tracking only. No payment is processed anywhere in the MVP."""
    class Status(models.TextChoices):
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"
        FREE_PLACEMENT = "FREE_PLACEMENT", "Free placement"
        DUE = "DUE", "Fee due"
        PAID = "PAID", "Recorded as paid"
        WAIVED = "WAIVED", "Waived"
        DISPUTED = "DISPUTED", "Disputed"

    placement = models.OneToOneField(Placement, on_delete=models.PROTECT, related_name="fee")
    business = models.ForeignKey(BusinessProfile, on_delete=models.PROTECT, related_name="fee_records")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=16, choices=Status.choices)
    free_placement_applied = models.BooleanField(default=False)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    waived_reason = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"Fee for placement #{self.placement_id}: {self.status}"


class ProtectionCase(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        REPLACEMENT_IN_PROGRESS = "REPLACEMENT_IN_PROGRESS", "Replacement in progress"
        REFUND_CONSIDERATION = "REFUND_CONSIDERATION", "Refund under consideration"
        RESOLVED = "RESOLVED", "Resolved"
        REJECTED = "REJECTED", "Not eligible"

    placement = models.OneToOneField(Placement, on_delete=models.PROTECT, related_name="protection_case")
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="+")
    opened_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    replacement_attempts = models.PositiveSmallIntegerField(default=0)
    refund_percent = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)],
                                                      help_text="Admin-decided percent. Proposed policy: 75. Recorded only; no money moves.")
    decision = models.TextField(blank=True)
    decision_reason = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Protection case for placement #{self.placement_id} ({self.status})"
