from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from applications.models import Application, Placement
from jobs.matching import score_job
from jobs.models import Job
from notifications.services import audit, notify_staff
from .forms import (BusinessProfileForm, RegisterForm, VerificationForm, WorkerProfileForm)
from .models import VerificationStatus, VerificationSubmission
from .permissions import get_role, business_required, worker_required
from .services import is_pending


def home(request):
    return render(request, "home.html", {"open_jobs": Job.objects.open().count()})


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to WorkLink! Complete your profile and submit verification to get started.")
        return redirect("dashboard")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def dashboard(request):
    role = get_role(request.user)
    if role == "admin":
        return redirect("admin:index")
    if role == "worker":
        worker = request.user.workerprofile
        jobs = list(Job.objects.open().select_related("business")[:100])
        for j in jobs:
            j.match = score_job(worker, j)
        jobs.sort(key=lambda j: j.match.score, reverse=True)
        apps = Application.objects.filter(worker=worker).select_related("job__business")[:5]
        return render(request, "accounts/worker_dashboard.html",
                      {"worker": worker, "recommended": jobs[:5], "apps": apps})
    if role == "business":
        business = request.user.businessprofile
        jobs = Job.objects.filter(business=business)
        placements = (Placement.objects.filter(application__job__business=business)
                      .select_related("application__job", "application__worker", "fee"))
        return render(request, "accounts/business_dashboard.html", {
            "business": business, "jobs": jobs[:5],
            "active_jobs": jobs.filter(status=Job.Status.PUBLISHED).count(),
            "applicant_count": Application.objects.filter(job__business=business).count(),
            "placements": placements,
        })
    raise PermissionDenied


@login_required
def profile(request):
    role = get_role(request.user)
    if role == "worker":
        instance, FormClass = request.user.workerprofile, WorkerProfileForm
    elif role == "business":
        instance, FormClass = request.user.businessprofile, BusinessProfileForm
    else:
        raise PermissionDenied
    form = FormClass(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("dashboard")
    return render(request, "form.html", {"form": form, "title": "My profile",
                                         "intro": "Phone and address are private and never shown to the other party."})


@login_required
def verification(request):
    role = get_role(request.user)
    if role not in ("worker", "business"):
        raise PermissionDenied
    prof = request.user.workerprofile if role == "worker" else request.user.businessprofile
    form = VerificationForm(request.POST or None, request.FILES or None, account_type=role)
    if request.method == "POST":
        if prof.verification_status == VerificationStatus.APPROVED:
            messages.info(request, "You are already approved.")
        elif is_pending(request.user, role):
            messages.error(request, "You already have a submission waiting for review.")
        elif form.is_valid():
            sub = form.save(commit=False)
            sub.user = request.user
            sub.account_type = role
            sub.save()
            prof.verification_status = VerificationStatus.PENDING
            prof.save(update_fields=["verification_status", "updated_at"])
            notify_staff("Verification awaiting review", f"{prof} submitted a document.",
                         f"/admin/accounts/verificationsubmission/{sub.pk}/change/")
            audit(request.user, "verification_submitted", sub)
            messages.success(request, "Submitted. A WorkLink coordinator will review it.")
            return redirect("verification")
    return render(request, "accounts/verification.html", {
        "form": form, "profile": prof, "submissions": request.user.verifications.all()})


@login_required
def verification_file(request, pk):
    """Private files are served only to the owner or staff, never via a public URL (T-14)."""
    sub = get_object_or_404(VerificationSubmission, pk=pk)
    if not (sub.user_id == request.user.id or request.user.is_staff):
        raise PermissionDenied
    if request.user.is_staff and sub.user_id != request.user.id:
        audit(request.user, "verification_file_viewed", sub)
    try:
        return FileResponse(sub.document.open("rb"))
    except FileNotFoundError:
        raise Http404
