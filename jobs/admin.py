from django.contrib import admin

from accounts.admin import AuditedAdminMixin
from notifications.services import notify
from .models import Job


@admin.register(Job)
class JobAdmin(AuditedAdminMixin, admin.ModelAdmin):
    """Moderation: remove listings with missing terms, suspicious claims or unsafe requests."""
    list_display = ("title", "business", "job_type", "area", "status", "created_at")
    list_filter = ("status", "job_type")
    search_fields = ("title", "business__business_name", "area")
    actions = ["remove_selected"]

    @admin.action(description="Remove selected jobs (moderation)")
    def remove_selected(self, request, queryset):
        for job in queryset:
            job.status = Job.Status.REMOVED
            job.save(update_fields=["status"])
            notify(job.business.user, "A job listing was removed", f"'{job.title}' was removed after moderation review.", "/jobs/mine/")
        self.message_user(request, "Selected jobs removed.")
