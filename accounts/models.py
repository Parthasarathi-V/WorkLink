import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import RegexValidator
from django.db import models

from .constants import JOB_TYPE_CHOICES


def private_storage():
    return FileSystemStorage(location=str(settings.PRIVATE_UPLOADS_ROOT))


def verification_upload_path(instance, filename):
    # Generated filename: never trust the user's file name.
    return f"verification/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class VerificationStatus(models.TextChoices):
    NOT_SUBMITTED = "NOT_SUBMITTED", "Not submitted"
    PENDING = "PENDING", "Pending review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    NEEDS_CORRECTION = "NEEDS_CORRECTION", "Needs correction"


phone_validator = RegexValidator(r"^[0-9+\-\s]{7,15}$", "Enter a valid phone number.")


def _csv(text):
    return [t.strip() for t in (text or "").split(",") if t.strip()]


class ReputationMixin:
    @property
    def reputation(self):
        """New users show 'New' (never a default perfect score)."""
        from django.db.models import Avg, Count
        from trust.models import Review

        agg = Review.objects.filter(target=self.user, moderation_status="PUBLISHED").aggregate(
            avg=Avg("rating"), n=Count("id")
        )
        if not agg["n"]:
            return "New"
        s = "" if agg["n"] == 1 else "s"
        return f"{agg['avg']:.1f}/5 ({agg['n']} review{s})"


class WorkerProfile(ReputationMixin, models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator],
                             help_text="Private. Never shown to businesses; coordinators use it.")
    education = models.CharField(max_length=200, blank=True)
    skills = models.TextField(blank=True, help_text="Comma-separated, e.g. billing, Excel, Hindi, delivery")
    preferred_area = models.CharField(max_length=120, blank=True, help_text="Locality / area, not your home address")
    availability = models.CharField(max_length=200, blank=True, help_text="e.g. weekends, evenings, mornings")
    preferred_job_types = models.CharField(max_length=200, blank=True)
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices,
                                           default=VerificationStatus.NOT_SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name

    @property
    def is_verified(self):
        return self.verification_status == VerificationStatus.APPROVED

    def skill_list(self):
        return _csv(self.skills)

    def job_type_list(self):
        return _csv(self.preferred_job_types)

    def completeness(self):
        parts = [self.display_name, self.education, self.skills, self.preferred_area,
                 self.availability, self.preferred_job_types]
        return sum(1 for p in parts if p) / len(parts)


class BusinessProfile(ReputationMixin, models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, blank=True, help_text="e.g. Cafe, Retail, Printing")
    area = models.CharField(max_length=120, blank=True, help_text="Public, approximate area")
    address = models.CharField(max_length=250, blank=True, help_text="Private. Not shown publicly.")
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator],
                             help_text="Private. Coordinator-mediated contact is the default.")
    description = models.TextField(blank=True)
    verification_status = models.CharField(max_length=20, choices=VerificationStatus.choices,
                                           default=VerificationStatus.NOT_SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name

    @property
    def is_verified(self):
        return self.verification_status == VerificationStatus.APPROVED


class VerificationSubmission(models.Model):
    class DocumentType(models.TextChoices):
        STUDENT_ID = "STUDENT_ID", "Student ID card"
        BUSINESS_REG = "BUSINESS_REG", "Business registration / licence"
        OTHER = "OTHER", "Other accepted proof"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="verifications")
    account_type = models.CharField(max_length=10, choices=[("worker", "Worker"), ("business", "Business")])
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    document = models.FileField(upload_to=verification_upload_path, storage=private_storage)
    status = models.CharField(max_length=20, choices=VerificationStatus.choices, default=VerificationStatus.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.user} - {self.get_document_type_display()} ({self.status})"

    def clean(self):
        needs_reason = (VerificationStatus.REJECTED, VerificationStatus.NEEDS_CORRECTION)
        if self.status in needs_reason and not self.decision_reason.strip():
            raise ValidationError({"decision_reason": "A reason is required for rejection or correction requests."})
