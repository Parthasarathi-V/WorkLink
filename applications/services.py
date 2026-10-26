"""Business operations for hiring. All state changes go through here, inside transactions."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import get_role
from notifications.services import audit, notify, notify_staff
from .models import (Application, ApplicationStatusHistory, Placement, PlacementFeeRecord, ProtectionCase)

S = Application.Status


class WorkflowError(Exception):
    """Raised for user-facing rule violations (shown as a message, nothing is saved)."""


BUSINESS_TRANSITIONS = {
    S.APPLIED: {S.SHORTLISTED, S.INTERVIEW, S.REJECTED},
    S.SHORTLISTED: {S.INTERVIEW, S.SELECTED, S.REJECTED},
    S.INTERVIEW: {S.SELECTED, S.REJECTED},
}
WORKER_TRANSITIONS = {
    S.SELECTED: {S.ACCEPTED, S.DECLINED},
    S.APPLIED: {S.WITHDRAWN},
    S.SHORTLISTED: {S.WITHDRAWN},
    S.INTERVIEW: {S.WITHDRAWN},
}


def _link(app):
    return reverse("application_detail", args=[app.pk])


def _record(app, new_status, actor, reason=""):
    old = app.status
    app.status = new_status
    app.save(update_fields=["status", "updated_at"])
    ApplicationStatusHistory.objects.create(
        application=app, from_status=old, to_status=new_status,
        changed_by=actor if getattr(actor, "pk", None) else None, reason=reason[:300],
    )


def _locked(application):
    return (Application.objects.select_for_update()
            .select_related("job__business__user", "worker__user").get(pk=application.pk))


@transaction.atomic
def apply_to_job(worker, job, cover_note=""):
    """Create exactly one application per worker/job."""
    if not job.is_open:
        raise WorkflowError("This job is closed or no longer accepting applications.")
    if settings.WORKLINK["REQUIRE_WORKER_VERIFICATION"] and not worker.is_verified:
        raise WorkflowError("Your profile must be approved before you can apply. Submit verification from your dashboard.")
    app, created = Application.objects.get_or_create(job=job, worker=worker, defaults={"cover_note": cover_note[:1000]})
    if not created:
        raise WorkflowError(f"You have already applied to this job (status: {app.get_status_display()}).")
    ApplicationStatusHistory.objects.create(application=app, from_status="", to_status=S.APPLIED, changed_by=worker.user)
    notify(job.business.user, "New application", f"{worker.display_name} applied for {job.title}.", _link(app))
    return app


@transaction.atomic
def change_status(application, new_status, actor, reason=""):
    app = _locked(application)
    role = get_role(actor)
    old = S(app.status)
    new_status = S(new_status) if new_status in S.values else None
    if new_status is None:
        raise WorkflowError("Unknown status.")
    if new_status == S.JOINED:
        raise WorkflowError("Joining is recorded through the joining confirmation step, not a status change.")

    if role == "business" and app.job.business.user_id == actor.id:
        allowed = BUSINESS_TRANSITIONS.get(old, set())
    elif role == "worker" and app.worker.user_id == actor.id:
        allowed = WORKER_TRANSITIONS.get(old, set())
    elif role == "admin":
        if not reason.strip():
            raise WorkflowError("An audited reason is required for admin overrides.")
        allowed = set(S) - {old, S.JOINED}
    else:
        raise WorkflowError("You cannot change this application.")
    if new_status not in allowed:
        raise WorkflowError(f"Cannot move from {S(old).label} to {new_status.label}.")

    _record(app, new_status, actor, reason)
    if role == "admin":
        audit(actor, "application_status_override", app, f"{old} -> {new_status}: {reason}")

    link = _link(app)
    job_title = app.job.title
    worker_msgs = {
        S.SHORTLISTED: "Your application was shortlisted",
        S.INTERVIEW: "You've moved to the interview stage",
        S.SELECTED: "You have been selected. Review the details and accept or decline",
        S.REJECTED: "Your application was not taken forward",
    }
    business_msgs = {
        S.ACCEPTED: "A worker accepted. Confirm joining once they start",
        S.DECLINED: "A worker declined your selection",
        S.WITHDRAWN: "A worker withdrew their application",
    }
    if new_status in worker_msgs:
        notify(app.worker.user, worker_msgs[new_status], job_title, link)
    if new_status in business_msgs:
        notify(app.job.business.user, business_msgs[new_status], f"{app.worker.display_name}: {job_title}", link)
    if role == "admin":
        for u in (app.worker.user, app.job.business.user):
            notify(u, "Application status updated by WorkLink", job_title, link)
    return app


def _evaluate_fee(placement):
    """Idempotent: one fee record per confirmed placement. Free allowance is configurable."""
    business = placement.application.job.business
    prior = (Placement.objects.filter(application__job__business=business, status=Placement.Status.CONFIRMED)
             .exclude(pk=placement.pk).count())
    cfg = settings.WORKLINK
    if prior < cfg["FREE_PLACEMENTS"]:
        defaults = {"business": business, "amount": 0, "currency": cfg["CURRENCY"],
                    "status": PlacementFeeRecord.Status.FREE_PLACEMENT, "free_placement_applied": True}
    else:
        defaults = {"business": business, "amount": cfg["DEFAULT_FEE"], "currency": cfg["CURRENCY"],
                    "status": PlacementFeeRecord.Status.DUE, "free_placement_applied": False,
                    "due_at": timezone.now() + timedelta(days=cfg["FEE_DUE_DAYS"])}
    fee, created = PlacementFeeRecord.objects.get_or_create(placement=placement, defaults=defaults)
    if created and fee.status == PlacementFeeRecord.Status.DUE:
        notify(business.user, "Placement fee recorded as due",
               "A placement service fee has been recorded under the current policy.", _link(placement.application))
    return fee


def _finalize(placement, actor):
    app = placement.application
    placement.status = Placement.Status.CONFIRMED
    placement.save(update_fields=["status"])
    if app.status != S.JOINED:
        _record(app, S.JOINED, actor, "Joining confirmed")
    _evaluate_fee(placement)
    audit(actor, "joining_confirmed", placement)
    for u in (app.worker.user, app.job.business.user):
        notify(u, "Joining confirmed", app.job.title, _link(app))


@transaction.atomic
def confirm_joining(application, actor, joined_at=None, reason=""):
    app = _locked(application)
    role = get_role(actor)
    today = timezone.localdate()
    if app.status not in (S.ACCEPTED, S.JOINED):
        raise WorkflowError("Joining can only be confirmed after the worker has accepted the selection.")
    if role == "worker" and app.worker.user_id != actor.id:
        raise WorkflowError("Not your application.")
    if role == "business" and app.job.business.user_id != actor.id:
        raise WorkflowError("Not your job.")
    if role not in ("worker", "business", "admin"):
        raise WorkflowError("Not allowed.")
    if role == "admin" and not reason.strip():
        raise WorkflowError("An audited reason is required for admin confirmation.")
    if joined_at and joined_at > today:
        raise WorkflowError("Joining date cannot be in the future. Confirm after the worker actually starts.")

    placement, created = Placement.objects.select_for_update().get_or_create(
        application=app, defaults={"joined_at": joined_at or today})
    if placement.status == Placement.Status.CONFIRMED:
        return placement  # idempotent: never double-count (T-10)
    if placement.status == Placement.Status.DISPUTED and role != "admin":
        raise WorkflowError("Joining is disputed and awaiting WorkLink admin review.")

    if joined_at and (created or role == "admin"):
        placement.joined_at = joined_at
    if role == "worker":
        placement.confirmed_by_worker = True
    elif role == "business":
        placement.confirmed_by_business = True
    else:
        placement.confirmed_by_admin = True
        audit(actor, "joining_admin_confirm", placement, reason)
    placement.save()

    if placement.confirmed_by_admin or (placement.confirmed_by_worker and placement.confirmed_by_business):
        _finalize(placement, actor)
    else:
        other = app.job.business.user if role == "worker" else app.worker.user
        notify(other, "Please confirm joining", f"{app.job.title}: the other party recorded joining on {placement.joined_at}.", _link(app))
    return placement


@transaction.atomic
def dispute_joining(application, actor, reason):
    app = _locked(application)
    role = get_role(actor)
    if role not in ("worker", "business") or actor.id not in (app.worker.user_id, app.job.business.user_id):
        raise WorkflowError("Not allowed.")
    if not reason.strip():
        raise WorkflowError("Please explain what you are disputing.")
    placement = Placement.objects.filter(application=app).first()
    if placement is None or placement.status == Placement.Status.CONFIRMED:
        raise WorkflowError("There is no pending joining record to dispute.")
    placement.status = Placement.Status.DISPUTED
    placement.save(update_fields=["status"])
    audit(actor, "joining_disputed", placement, reason)
    notify_staff("Joining disputed", f"Application #{app.pk}: {reason[:150]}", reverse("admin:applications_placement_change", args=[placement.pk]))
    return placement


@transaction.atomic
def open_protection_case(application, actor, reason):
    app = _locked(application)
    if get_role(actor) != "business" or app.job.business.user_id != actor.id:
        raise WorkflowError("Only the hiring business can open a protection case.")
    placement = Placement.objects.filter(application=app, status=Placement.Status.CONFIRMED).first()
    if placement is None:
        raise WorkflowError("Protection cases apply only to confirmed placements.")
    if not placement.in_protection_window:
        raise WorkflowError("The protection window for this placement has ended.")
    if not reason.strip():
        raise WorkflowError("Please describe what happened.")
    if ProtectionCase.objects.filter(placement=placement).exists():
        raise WorkflowError("A protection case already exists for this placement.")
    case = ProtectionCase.objects.create(placement=placement, opened_by=actor, reason=reason[:2000])
    audit(actor, "protection_case_opened", case)
    notify_staff("Protection case opened", f"Placement #{placement.pk}", reverse("admin:applications_protectioncase_change", args=[case.pk]))
    return case
