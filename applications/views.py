from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.permissions import business_required, get_role, worker_required
from jobs.matching import score_job
from jobs.models import Job
from notifications.services import notify
from . import services
from .forms import ApplyForm, MessageForm
from .models import Application, ApplicationMessage
from .services import BUSINESS_TRANSITIONS, WORKER_TRANSITIONS, WorkflowError

S = Application.Status


def _app_for_user(request, pk):
    """Fetch an application only if the user is its worker, the job's business, or staff."""
    app = get_object_or_404(Application.objects.select_related("job__business__user", "worker__user"), pk=pk)
    role = get_role(request.user)
    if role == "worker" and app.worker.user_id == request.user.id:
        return app, role
    if role == "business" and app.job.business.user_id == request.user.id:
        return app, role
    if role == "admin":
        return app, role
    raise PermissionDenied


@worker_required
@require_POST
def apply(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    form = ApplyForm(request.POST)
    if not form.is_valid():
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
        return redirect("job_detail", pk=job.pk)
    try:
        app = services.apply_to_job(request.user.workerprofile, job, form.cleaned_data["cover_note"])
    except WorkflowError as exc:
        messages.error(request, str(exc))
        return redirect("job_detail", pk=job.pk)
    messages.success(request, "Application sent. You'll be notified of any updates.")
    return redirect("application_detail", pk=app.pk)


@worker_required
def my_applications(request):
    apps = Application.objects.filter(worker=request.user.workerprofile).select_related("job__business")
    return render(request, "applications/mine.html", {"apps": apps})


@business_required
def job_applicants(request, job_id):
    job = get_object_or_404(Job, pk=job_id, business=request.user.businessprofile)  # own jobs only
    apps = list(job.applications.select_related("worker"))
    for a in apps:
        a.match = score_job(a.worker, job)
    return render(request, "applications/applicants.html", {"job": job, "apps": apps})


@login_required
def application_detail(request, pk):
    app, role = _app_for_user(request, pk)
    placement = getattr(app, "placement", None)
    actions = []
    if role == "business":
        actions = [(s.value, s.label) for s in BUSINESS_TRANSITIONS.get(S(app.status), [])]
    elif role == "worker":
        actions = [(s.value, s.label) for s in WORKER_TRANSITIONS.get(S(app.status), [])]
    can_confirm_joining = (role in ("worker", "business") and app.status == S.ACCEPTED
                           and not (placement and placement.status in ("CONFIRMED", "DISPUTED")))
    if placement and role == "worker" and placement.confirmed_by_worker:
        can_confirm_joining = False
    if placement and role == "business" and placement.confirmed_by_business:
        can_confirm_joining = False
    case = getattr(placement, "protection_case", None) if placement else None
    can_open_case = (role == "business" and placement is not None and placement.status == "CONFIRMED"
                     and placement.in_protection_window and case is None)
    reviewed = False
    if placement and placement.status == "CONFIRMED":
        reviewed = request.user.reviews_written.filter(placement=placement).exists()
    ctx = {
        "app": app, "role": role, "placement": placement, "actions": actions,
        "can_confirm_joining": can_confirm_joining, "can_dispute": placement is not None and placement.status == "PENDING" and role in ("worker", "business"),
        "case": case, "can_open_case": can_open_case, "message_form": MessageForm(),
        "can_review": placement is not None and placement.status == "CONFIRMED" and not reviewed and role in ("worker", "business"),
        "today": date.today(),
    }
    return render(request, "applications/detail.html", ctx)


@login_required
@require_POST
def application_status(request, pk):
    app, _ = _app_for_user(request, pk)
    try:
        services.change_status(app, request.POST.get("new_status", ""), request.user, request.POST.get("reason", ""))
        messages.success(request, "Status updated.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("application_detail", pk=pk)


@login_required
@require_POST
def application_joined(request, pk):
    app, _ = _app_for_user(request, pk)
    raw = request.POST.get("joined_at", "")
    try:
        joined_at = date.fromisoformat(raw) if raw else None
    except ValueError:
        messages.error(request, "Enter a valid joining date.")
        return redirect("application_detail", pk=pk)
    try:
        placement = services.confirm_joining(app, request.user, joined_at, request.POST.get("reason", ""))
        if placement.status == "CONFIRMED":
            messages.success(request, "Joining confirmed by both sides and recorded.")
        else:
            messages.success(request, "Your confirmation is recorded. Waiting for the other party.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("application_detail", pk=pk)


@login_required
@require_POST
def application_dispute(request, pk):
    app, _ = _app_for_user(request, pk)
    try:
        services.dispute_joining(app, request.user, request.POST.get("reason", ""))
        messages.success(request, "Dispute recorded. A WorkLink coordinator will review it.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("application_detail", pk=pk)


@login_required
@require_POST
def application_protection(request, pk):
    app, _ = _app_for_user(request, pk)
    try:
        services.open_protection_case(app, request.user, request.POST.get("reason", ""))
        messages.success(request, "Protection case opened for admin review. No refund is issued automatically.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("application_detail", pk=pk)


@login_required
@require_POST
def application_message(request, pk):
    app, role = _app_for_user(request, pk)
    form = MessageForm(request.POST, enforce_privacy=(role != "admin"))
    if form.is_valid():
        ApplicationMessage.objects.create(application=app, sender=request.user, body=form.cleaned_data["body"])
        link = reverse("application_detail", args=[pk])
        for u in {app.worker.user, app.job.business.user} - {request.user}:
            notify(u, "New message", app.job.title, link)
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("application_detail", pk=pk)
