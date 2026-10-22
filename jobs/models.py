from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from accounts.constants import JOB_TYPE_CHOICES
from accounts.models import BusinessProfile


class JobQuerySet(models.QuerySet):
    def open(self):
        """Published and not past its closing date: what ordinary search shows."""
        return self.filter(status=Job.Status.PUBLISHED).filter(
            Q(closing_at__isnull=True) | Q(closing_at__gte=date.today())
        )


class Job(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        PAUSED = "PAUSED", "Paused"
        CLOSED = "CLOSED", "Closed"
        EXPIRED = "EXPIRED", "Expired"
        REMOVED = "REMOVED", "Removed by admin"

    class PayPeriod(models.TextChoices):
        HOUR = "HOUR", "per hour"
        DAY = "DAY", "per day"
        WEEK = "WEEK", "per week"
        MONTH = "MONTH", "per month"

    business = models.ForeignKey(BusinessProfile, on_delete=models.PROTECT, related_name="jobs")
    title = models.CharField(max_length=150)
    description = models.TextField()
    duties = models.TextField(blank=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES)
    pay_min = models.PositiveIntegerField(help_text="Whole rupees")
    pay_max = models.PositiveIntegerField(help_text="Whole rupees")
    pay_period = models.CharField(max_length=10, choices=PayPeriod.choices, default=PayPeriod.HOUR)
    area = models.CharField(max_length=120, help_text="Approximate area, not the full address")
    schedule = models.CharField(max_length=200, help_text="e.g. weekends 10am-6pm, evenings")
    required_skills = models.TextField(blank=True, help_text="Comma-separated")
    vacancies = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    closing_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(pay_min__lte=F("pay_max")), name="job_pay_min_lte_max"),
        ]

    def __str__(self):
        return f"{self.title} @ {self.business}"

    def clean(self):
        if self.pay_min is not None and self.pay_max is not None and self.pay_min > self.pay_max:
            raise ValidationError({"pay_max": "Maximum pay must be at least the minimum pay."})
        if self.closing_at and not self.pk and self.closing_at < date.today():
            raise ValidationError({"closing_at": "Closing date cannot be in the past."})

    @property
    def is_open(self):
        return self.status == self.Status.PUBLISHED and (self.closing_at is None or self.closing_at >= date.today())

    @property
    def pay_display(self):
        rng = f"₹{self.pay_min}" if self.pay_min == self.pay_max else f"₹{self.pay_min}–₹{self.pay_max}"
        return f"{rng} {self.get_pay_period_display()}"

    def skill_list(self):
        return [s.strip() for s in self.required_skills.split(",") if s.strip()]
