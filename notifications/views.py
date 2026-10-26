from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    page = Paginator(request.user.notifications.all(), 20).get_page(request.GET.get("page"))
    return render(request, "notifications/list.html", {"page": page})


@login_required
def notification_open(request, pk):
    # Scoped to the logged-in user: other people's notifications give 404 (T-11).
    note = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=["is_read"])
    if note.link and note.link.startswith("/"):
        return redirect(note.link)
    return redirect("notification_list")


@login_required
@require_POST
def notification_read_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notification_list")
