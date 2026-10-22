from django.contrib import admin, messages
from django.utils import timezone

from accounts.admin import AuditedAdminMixin
from notifications.services import audit, notify
from . import services
from .models import (Application, ApplicationMessage, ApplicationStatusHistory, Placement,
                     PlacementFeeRecord, ProtectionCase)


class HistoryInline(admin.TabularInline):
    model = ApplicationStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "changed_by", "reason", "changed_at")

    def has_add_permission(self, request, obj=None):
        return False


class MessageInline(admin.TabularInline):
    model = ApplicationMessage
    extra = 0
    readonly_fields = ("sender", "body", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    """Read-mostly: status changes by admin go through audited services on the app page."""
    list_display = ("id", "worker", "job", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("worker__display_name", "job__title")
    readonly_fields = ("job", "worker", "status", "cover_note", "applied_at", "updated_at")
    inlines = [HistoryInline, MessageInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "joined_at", "status", "confirmed_by_worker", "confirmed_by_business")
    list_filter = ("status",)
    readonly_fields = ("application", "joined_at", "confirmed_by_worker", "confirmed_by_business",
                       "confirmed_by_admin", "status", "created_at")
    actions = ["admin_confirm_joining"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Confirm joining (admin, resolves disputes; audited)")
    def admin_confirm_joining(self, request, queryset):
        for placement in queryset:
            try:
                services.confirm_joining(placement.application, request.user, placement.joined_at,
                                         reason="Confirmed by WorkLink coordinator after review")
                self.message_user(request, f"Placement #{placement.pk} confirmed.")
            except services.WorkflowError as exc:
                self.message_user(request, f"Placement #{placement.pk}: {exc}", level=messages.ERROR)


@admin.register(PlacementFeeRecord)
class PlacementFeeRecordAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "business", "placement", "status", "amount", "free_placement_applied", "due_at")
    list_filter = ("status", "free_placement_applied")
    readonly_fields = ("placement", "business", "free_placement_applied")

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data and obj.status == PlacementFeeRecord.Status.PAID and not obj.paid_at:
            obj.paid_at = timezone.now()
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data:
            notify(obj.business.user, "Placement fee status updated", obj.get_status_display())

    def has_add_permission(self, request):
        return False


@admin.register(ProtectionCase)
class ProtectionCaseAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "placement", "status", "replacement_attempts", "refund_percent", "opened_at")
    list_filter = ("status",)
    readonly_fields = ("placement", "opened_by", "opened_at", "reason")

    def save_model(self, request, obj, form, change):
        if obj.status in (ProtectionCase.Status.RESOLVED, ProtectionCase.Status.REJECTED) and not obj.resolved_at:
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data or "decision" in form.changed_data:
            notify(obj.placement.application.job.business.user, "Protection case update",
                   "A decision or status change has been recorded.")

    def has_add_permission(self, request):
        return False
