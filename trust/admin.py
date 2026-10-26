from django.contrib import admin
from django.utils import timezone

from accounts.admin import AuditedAdminMixin
from notifications.services import notify
from .models import Complaint, Review


@admin.register(Complaint)
class ComplaintAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "category", "complainant", "respondent", "status", "created_at")
    list_filter = ("status", "category")
    readonly_fields = ("complainant", "respondent", "application", "category", "description",
                       "evidence_reference", "respondent_response", "created_at")

    actions = ["ai_summary"]

    @admin.action(description="AI summary (assistive, not a verdict)")
    def ai_summary(self, request, queryset):
        from ai_assist.services import summarise_complaint
        for c in queryset[:5]:
            self.message_user(request, f"Complaint #{c.pk}: {summarise_complaint(c)}")

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        closing = (Complaint.Status.RESOLVED, Complaint.Status.DISMISSED)
        if obj.status in closing and not obj.resolved_at:
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data or "admin_decision" in form.changed_data:
            for u in (obj.complainant, obj.respondent):
                notify(u, "Complaint update", "Your complaint case status has changed.", f"/trust/complaints/{obj.pk}/")


@admin.register(Review)
class ReviewAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("id", "author", "target", "rating", "reason_code", "moderation_status")
    list_filter = ("moderation_status", "reason_code")
    readonly_fields = ("author", "target", "placement", "rating", "reason_code", "comment", "created_at")
    actions = ["publish", "hide"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Publish selected reviews")
    def publish(self, request, queryset):
        queryset.update(moderation_status=Review.Moderation.PUBLISHED)

    @admin.action(description="Hide selected reviews")
    def hide(self, request, queryset):
        queryset.update(moderation_status=Review.Moderation.HIDDEN)
