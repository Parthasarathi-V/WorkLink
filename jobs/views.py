from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import business_required, get_role
from notifications.services import audit
from .forms import JobFilterForm, JobForm
from .matching import score_job
from .models import Job

MAX_SCORED = 300  # cap for in-Python ranking (keeps the MVP responsive)


def job_list(request):
    role = get_role(request.user)
    if not request.user.is_authenticated and not settings.WORKLINK["PUBLIC_JOB_BROWSING"]:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    form = JobFilterForm(request.GET or None)
    qs = Job.objects.open().select_related("business")
    data = form.cleaned_data if form.is_valid() else {}
    if data.get("q"):
        q = data["q"]
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if data.get("area"):
        qs = qs.filter(area__icontains=data["area"])
    if data.get("job_type"):
        qs = qs.filter(job_type=data["job_type"])
    if data.get("min_pay") is not None:
        qs = qs.filter(pay_max__gte=data["min_pay"])
    if data.get("skill"):
        qs = qs.filter(required_skills__icontains=data["skill"])
    if data.get("schedule"):
        qs = qs.filter(schedule__icontains=data["schedule"])
    qs = qs.order_by("-created_at")

    worker = request.user.workerprofile if role == "worker" else None
    if worker and data.get("sort") == "match":
        jobs = list(qs[:MAX_SCORED])
        for j in jobs:
            j.match = score_job(worker, j)
        jobs.sort(key=lambda j: j.match.score, reverse=True)
        page = Paginator(jobs, 10).get_page(request.GET.get("page"))
    else:
        page = Paginator(qs, 10).get_page(request.GET.get("page"))
        if worker:
            for j in page:
                j.match = score_job(worker, j)

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "jobs/list.html", {"form": form, "page": page, "role": role,
                                              "querystring": params.urlencode()})


def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related("business"), pk=pk)
    role = get_role(request.user)
    is_owner = role == "business" and job.business.user_id == request.user.id
    if not (job.is_open or is_owner or role == "admin"):
        raise Http404
    if not request.user.is_authenticated and not settings.WORKLINK["PUBLIC_JOB_BROWSING"]:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    ctx = {"job": job, "role": role, "is_owner": is_owner}
    if role == "worker":
        worker = request.user.workerprofile
        ctx["match"] = score_job(worker, job)
        ctx["existing"] = job.applications.filter(worker=worker).first()
        ctx["worker"] = worker
        ctx["must_verify"] = settings.WORKLINK["REQUIRE_WORKER_VERIFICATION"] and not worker.is_verified
    return render(request, "jobs/detail.html", ctx)


@business_required
def my_jobs(request):
    jobs = Job.objects.filter(business=request.user.businessprofile)
    return render(request, "jobs/my_jobs.html", {"jobs": jobs, "business": request.user.businessprofile})


@business_required
def job_create(request):
    business = request.user.businessprofile
    form = JobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.business = business
        job.save()
        messages.success(request, "Draft saved. Publish it when you're ready.")
        return redirect("my_jobs")
    return render(request, "form.html", {"form": form, "title": "Post a job",
                                         "intro": "Describe the role clearly: pay, hours and area. Do not include phone numbers."})


@business_required
def job_edit(request, pk):
    job = get_object_or_404(Job, pk=pk, business=request.user.businessprofile)  # ownership (T-03)
    if job.status == Job.Status.REMOVED:
        raise PermissionDenied
    form = JobForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Job updated.")
        return redirect("my_jobs")
    return render(request, "form.html", {"form": form, "title": f"Edit: {job.title}"})


ALLOWED_ACTIONS = {
    "publish": ({Job.Status.DRAFT, Job.Status.PAUSED}, Job.Status.PUBLISHED),
    "pause": ({Job.Status.PUBLISHED}, Job.Status.PAUSED),
    "close": ({Job.Status.DRAFT, Job.Status.PUBLISHED, Job.Status.PAUSED}, Job.Status.CLOSED),
}


@business_required
@require_POST
def job_status(request, pk):
    job = get_object_or_404(Job, pk=pk, business=request.user.businessprofile)
    action = request.POST.get("action")
    if action not in ALLOWED_ACTIONS:
        raise Http404
    from_states, to_state = ALLOWED_ACTIONS[action]
    if job.status not in from_states:
        messages.error(request, "That action isn't available for this job's current status.")
    elif action == "publish" and not job.business.is_verified:
        messages.error(request, "Your business must be approved by WorkLink before you can publish jobs.")
    elif action == "publish" and job.closing_at and job.closing_at < date.today():
        messages.error(request, "Closing date has passed. Edit the job to set a new date.")
    else:
        job.status = to_state
        job.save(update_fields=["status"])
        audit(request.user, f"job_{action}", job)
        messages.success(request, f"Job is now {job.get_status_display().lower()}.")
    return redirect("my_jobs")
