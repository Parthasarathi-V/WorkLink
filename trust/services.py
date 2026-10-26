from django.urls import reverse

from applications.models import Placement
from notifications.services import audit, notify, notify_staff
from .models import Complaint, Review


def review_target(user, placement):
    """Return the other party's user if `user` may review this placement, else None."""
    if placement.status != Placement.Status.CONFIRMED:
        return None  # only completed, verified interactions can be reviewed (T-13)
    app = placement.application
    worker_user, business_user = app.worker.user, app.job.business.user
    if user.id == worker_user.id:
        return business_user
    if user.id == business_user.id:
        return worker_user
    return None


def file_complaint(complainant, application, category, description, evidence):
    worker_user, business_user = application.worker.user, application.job.business.user
    if complainant.id == worker_user.id:
        respondent = business_user
    elif complainant.id == business_user.id:
        respondent = worker_user
    else:
        raise PermissionError("Not a party to this application.")
    c = Complaint.objects.create(complainant=complainant, respondent=respondent, application=application,
                                 category=category, description=description, evidence_reference=evidence)
    # Recorded as an allegation only: no automatic rating penalty or account action.
    audit(complainant, "complaint_filed", c)
    notify(respondent, "A complaint involving you was filed", "You can view it and add your response.",
           reverse("complaint_detail", args=[c.pk]))
    notify_staff("New complaint", f"Complaint #{c.pk}: {c.get_category_display()}", f"/admin/trust/complaint/{c.pk}/change/")
    return c
