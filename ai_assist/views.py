from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounts.permissions import business_required, worker_required
from jobs.forms import JobForm
from jobs.models import Job
from . import services


@business_required
def job_draft(request):
    if request.method == "POST" and request.POST.get("rough"):
        data, used_ai = services.draft_job(request.POST["rough"])
        if used_ai:
            intro = "AI-drafted suggestion. Check every field (pay and area are left for you) before saving."
        else:
            messages.info(request, "AI is off or unavailable, so your text was copied into the description.")
            intro = "Edit the fields and save as a draft."
        form = JobForm(initial=data)
        return render(request, "form.html", {"form": form, "title": "Review your job draft", "intro": intro,
                                             "action": reverse("job_create")})
    return render(request, "ai_assist/job_draft.html")


@worker_required
def cover_note(request, job_id):
    job = get_object_or_404(Job.objects.select_related("business"), pk=job_id)
    if not job.is_open:
        messages.error(request, "This job is no longer open.")
    note, used_ai = services.draft_cover_note(request.user.workerprofile, job)
    return render(request, "ai_assist/cover_note.html", {"job": job, "note": note, "used_ai": used_ai})
