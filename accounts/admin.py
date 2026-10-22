from django.contrib import admin
from django.utils.html import format_html

from notifications.services import audit
from .models import BusinessProfile, VerificationStatus, VerificationSubmission, WorkerProfile
from .services import apply_verification_decision


class AuditedAdminMixin:
    """Logs which fields changed (names only, never values) for sensitive models."""

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "admin_change" if change else "admin_create", obj,
              "fields: " + ", ".join(form.changed_data))


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "verification_status", "preferred_area")
    list_filter = ("verification_status",)
    search_fields = ("display_name", "user__username", "user__email")
    readonly_fields = ("verification_status",)  # change status via VerificationSubmission review


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "category", "area", "verification_status")
    list_filter = ("verification_status",)
    search_fields = ("business_name", "user__username")
    readonly_fields = ("verification_status",)


@admin.register(VerificationSubmission)
class VerificationSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "account_type", "document_type", "status", "submitted_at", "reviewed_by")
    list_filter = ("status", "account_type")
    search_fields = ("user__username",)
    readonly_fields = ("user", "account_type", "document_type", "document_link", "submitted_at", "reviewed_by", "reviewed_at")
    exclude = ("document",)
    actions = ["approve_selected"]

    @admin.display(description="Document (private, access-logged)")
    def document_link(self, obj):
        if not obj.pk:
            return "-"
        return format_html('<a href="/accounts/verification/{}/file/" target="_blank">Open document</a>', obj.pk)

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data and obj.status != VerificationStatus.PENDING:
            apply_verification_decision(obj, request.user)

    @admin.action(description="Approve selected submissions")
    def approve_selected(self, request, queryset):
        for sub in queryset.filter(status=VerificationStatus.PENDING):
            sub.status = VerificationStatus.APPROVED
            sub.save(update_fields=["status"])
            apply_verification_decision(sub, request.user)
