from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from applications.models import Application, Placement
from notifications.services import audit, notify_staff
from . import services
from .forms import ComplaintForm, ComplaintResponseForm, ReviewForm
from .models import Complaint, Review


@login_required
def complaint_create(request, application_id):
    app = get_object_or_404(Application.objects.select_related("job__business__user", "worker__user"), pk=application_id)
    if request.user.id not in (app.worker.user_id, app.job.business.user_id):
        raise PermissionDenied
    form = ComplaintForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        c = services.file_complaint(request.user, app, form.cleaned_data["category"],
                                    form.cleaned_data["description"], form.cleaned_data["evidence_reference"])
        messages.success(request, "Complaint recorded as an allegation. A coordinator will review it fairly.")
        return redirect("complaint_detail", pk=c.pk)
    return render(request, "form.html", {"form": form, "title": "Raise a complaint",
                                         "intro": "A complaint is reviewed by WorkLink; nothing happens automatically. The other party can respond."})


@login_required
def complaint_list(request):
    qs = Complaint.objects.filter(Q(complainant=request.user) | Q(respondent=request.user))
    return render(request, "trust/complaint_list.html", {"complaints": qs})


@login_required
def complaint_detail(request, pk):
    c = get_object_or_404(Complaint, pk=pk)
    if request.user.id not in (c.complainant_id, c.respondent_id) and not request.user.is_staff:
        raise PermissionDenied
    can_respond = (request.user.id == c.respondent_id and c.status in
                   (Complaint.Status.OPEN, Complaint.Status.UNDER_REVIEW, Complaint.Status.WAITING_FOR_RESPONSE))
    return render(request, "trust/complaint_detail.html", {
        "c": c, "can_respond": can_respond, "form": ComplaintResponseForm()})


@login_required
@require_POST
def complaint_respond(request, pk):
    c = get_object_or_404(Complaint, pk=pk, respondent=request.user)
    form = ComplaintResponseForm(request.POST)
    if form.is_valid():
        c.respondent_response = form.cleaned_data["response"]
        if c.status in (Complaint.Status.OPEN, Complaint.Status.WAITING_FOR_RESPONSE):
            c.status = Complaint.Status.UNDER_REVIEW
        c.save(update_fields=["respondent_response", "status"])
        audit(request.user, "complaint_response", c)
        notify_staff("Complaint response received", f"Complaint #{c.pk}", f"/admin/trust/complaint/{c.pk}/change/")
        messages.success(request, "Your response was recorded.")
    return redirect("complaint_detail", pk=pk)


@login_required
def review_create(request, placement_id):
    placement = get_object_or_404(Placement.objects.select_related("application__job__business__user", "application__worker__user"),
                                  pk=placement_id)
    target = services.review_target(request.user, placement)
    if target is None:
        raise PermissionDenied  # not eligible (T-13)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.author, review.target, review.placement = request.user, target, placement
        try:
            with transaction.atomic():
                review.save()
        except IntegrityError:
            messages.error(request, "You've already reviewed this placement.")
        else:
            messages.success(request, "Thanks! Your review will appear after moderation.")
        return redirect("application_detail", pk=placement.application_id)
    return render(request, "form.html", {"form": form, "title": "Leave a review",
                                         "intro": "Reviews are moderated. Describe the work experience, not personal details."})
