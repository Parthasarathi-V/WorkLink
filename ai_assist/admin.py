from django.contrib import admin

from .models import ListingReview


@admin.register(ListingReview)
class ListingReviewAdmin(admin.ModelAdmin):
    """Advisory only: a moderator decides whether to remove a listing."""
    list_display = ("job", "flagged", "checked_at")
    list_filter = ("flagged",)
    readonly_fields = ("job", "rule_flags", "ai_notes", "flagged", "checked_at")

    def has_add_permission(self, request):
        return False
