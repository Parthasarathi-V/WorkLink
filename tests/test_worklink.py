from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.forms import VerificationForm
from accounts.models import BusinessProfile, VerificationStatus, VerificationSubmission, WorkerProfile
from applications import services
from applications.models import Application, Placement, PlacementFeeRecord, ProtectionCase
from applications.services import WorkflowError
from jobs.models import Job
from notifications.models import Notification
from trust.models import Complaint, Review

PW = "pass12345!"
APPROVED = VerificationStatus.APPROVED


def make_worker(name="w1", status=APPROVED, **kw):
    u = User.objects.create_user(name, f"{name}@example.com", PW)
    return WorkerProfile.objects.create(user=u, display_name=name, verification_status=status, **kw)


def make_business(name="b1", status=APPROVED):
    u = User.objects.create_user(name, f"{name}@example.com", PW)
    return BusinessProfile.objects.create(user=u, business_name=name, verification_status=status)


def make_job(business, **kw):
    data = dict(title="Cashier", description="d", job_type="PART_TIME", pay_min=100, pay_max=200,
                area="Indiranagar", schedule="weekends", vacancies=1, status=Job.Status.PUBLISHED)
    data.update(kw)
    return Job.objects.create(business=business, **data)


def make_staff():
    return User.objects.create_user("staff", "s@example.com", PW, is_staff=True)


def accepted_application(worker=None, business=None, job=None):
    worker = worker or make_worker()
    business = business or make_business()
    job = job or make_job(business)
    app = services.apply_to_job(worker, job)
    services.change_status(app, "SHORTLISTED", business.user)
    services.change_status(app, "SELECTED", business.user)
    services.change_status(app, "ACCEPTED", worker.user)
    return app


def join(app):
    services.confirm_joining(app, app.worker.user, date.today())
    return services.confirm_joining(app, app.job.business.user, date.today())


class AccessTests(TestCase):
    def test_anonymous_dashboard_redirects_to_login(self):  # T-01
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)

    def test_worker_cannot_open_business_pages(self):  # T-02
        w = make_worker()
        self.client.login(username=w.user.username, password=PW)
        self.assertEqual(self.client.get(reverse("my_jobs")).status_code, 403)
        self.assertEqual(self.client.get(reverse("job_create")).status_code, 403)

    def test_business_cannot_edit_other_business_job(self):  # T-03
        a, b = make_business("a"), make_business("b")
        job = make_job(b)
        self.client.login(username="a", password=PW)
        r = self.client.post(reverse("job_edit", args=[job.pk]), {"title": "hacked"})
        self.assertEqual(r.status_code, 404)
        job.refresh_from_db()
        self.assertEqual(job.title, "Cashier")

    def test_unverified_business_cannot_publish(self):  # T-04
        b = make_business(status=VerificationStatus.PENDING)
        job = make_job(b, status=Job.Status.DRAFT)
        self.client.login(username="b1", password=PW)
        self.client.post(reverse("job_status", args=[job.pk]), {"action": "publish"})
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.DRAFT)

    def test_business_cannot_see_other_applicants(self):
        a, b = make_business("a"), make_business("b")
        job = make_job(b)
        self.client.login(username="a", password=PW)
        self.assertEqual(self.client.get(reverse("job_applicants", args=[job.pk])).status_code, 404)

    def test_other_users_notification_denied(self):  # T-11
        w, other = make_worker("w1"), make_worker("w2")
        n = Notification.objects.create(recipient=w.user, title="x")
        self.client.login(username="w2", password=PW)
        self.assertEqual(self.client.get(reverse("notification_open", args=[n.pk])).status_code, 404)

    def test_verification_file_denied_to_other_user(self):  # T-14
        w, other = make_worker("w1"), make_worker("w2")
        sub = VerificationSubmission.objects.create(user=w.user, account_type="worker",
                                                    document_type="STUDENT_ID", document="verification/none.pdf")
        self.client.login(username="w2", password=PW)
        self.assertEqual(self.client.get(reverse("verification_file", args=[sub.pk])).status_code, 403)

    def test_registration_cannot_make_admin(self):
        self.client.post(reverse("register"), {
            "username": "newbie", "email": "n@example.com", "password1": "Str0ng-pass-99", "password2": "Str0ng-pass-99",
            "role": "worker", "name": "Newbie", "is_staff": "on"})
        u = User.objects.get(username="newbie")
        self.assertFalse(u.is_staff)
        self.assertTrue(hasattr(u, "workerprofile"))


class ApplicationFlowTests(TestCase):
    def test_duplicate_application_blocked(self):  # T-05
        w, b = make_worker(), make_business()
        job = make_job(b)
        services.apply_to_job(w, job)
        with self.assertRaises(WorkflowError):
            services.apply_to_job(w, job)
        self.assertEqual(Application.objects.count(), 1)

    def test_closed_or_expired_job_rejected(self):  # T-06
        w, b = make_worker(), make_business()
        with self.assertRaises(WorkflowError):
            services.apply_to_job(w, make_job(b, status=Job.Status.CLOSED))
        with self.assertRaises(WorkflowError):
            services.apply_to_job(w, make_job(b, title="old", closing_at=date.today() - timedelta(days=1)))

    def test_unverified_worker_cannot_apply(self):
        w, b = make_worker(status=VerificationStatus.NOT_SUBMITTED), make_business()
        with self.assertRaises(WorkflowError):
            services.apply_to_job(w, make_job(b))

    def test_invalid_transition_rejected(self):  # T-07
        w, b = make_worker(), make_business()
        app = services.apply_to_job(w, make_job(b))
        with self.assertRaises(WorkflowError):
            services.change_status(app, "ACCEPTED", b.user)
        with self.assertRaises(WorkflowError):
            services.change_status(app, "JOINED", b.user)
        app.refresh_from_db()
        self.assertEqual(app.status, "APPLIED")

    def test_worker_cannot_select_themselves(self):
        w, b = make_worker(), make_business()
        app = services.apply_to_job(w, make_job(b))
        with self.assertRaises(WorkflowError):
            services.change_status(app, "SELECTED", w.user)

    def test_status_change_writes_history_and_notification(self):  # T-08
        w, b = make_worker(), make_business()
        app = services.apply_to_job(w, make_job(b))
        services.change_status(app, "SHORTLISTED", b.user)
        app.refresh_from_db()
        self.assertEqual(app.status, "SHORTLISTED")
        self.assertEqual(list(app.history.values_list("to_status", flat=True)), ["APPLIED", "SHORTLISTED"])
        self.assertTrue(Notification.objects.filter(recipient=w.user, title__icontains="shortlisted").exists())

    def test_selected_is_not_joined(self):  # T-09
        app = accepted_application()
        self.assertEqual(Placement.objects.count(), 0)
        self.assertEqual(PlacementFeeRecord.objects.count(), 0)

    def test_joining_needs_both_sides_and_counts_once(self):  # T-10
        app = accepted_application()
        p = services.confirm_joining(app, app.worker.user, date.today())
        self.assertEqual(p.status, Placement.Status.PENDING)
        self.assertEqual(PlacementFeeRecord.objects.count(), 0)
        p = services.confirm_joining(app, app.job.business.user, date.today())
        self.assertEqual(p.status, Placement.Status.CONFIRMED)
        services.confirm_joining(app, app.job.business.user, date.today())  # repeat: no double count
        self.assertEqual(PlacementFeeRecord.objects.count(), 1)
        app.refresh_from_db()
        self.assertEqual(app.status, "JOINED")

    def test_future_joining_date_rejected(self):
        app = accepted_application()
        with self.assertRaises(WorkflowError):
            services.confirm_joining(app, app.worker.user, date.today() + timedelta(days=3))

    def test_fee_due_after_free_allowance(self):  # T-16
        b = make_business()
        for i in range(4):
            w = make_worker(f"w{i}")
            join(accepted_application(worker=w, business=b, job=make_job(b, title=f"J{i}")))
        statuses = list(PlacementFeeRecord.objects.order_by("placement_id").values_list("status", flat=True))
        self.assertEqual(statuses, ["FREE_PLACEMENT"] * 3 + ["DUE"])

    def test_job_pay_validation(self):  # T-17
        self.client.login(username=make_business().user.username, password=PW)
        r = self.client.post(reverse("job_create"), {
            "title": "x", "description": "d", "job_type": "PART_TIME", "pay_min": 500, "pay_max": 100,
            "pay_period": "HOUR", "area": "a", "schedule": "s", "vacancies": 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Job.objects.count(), 0)

    def test_messages_block_phone_numbers(self):
        app = accepted_application()
        self.client.login(username=app.worker.user.username, password=PW)
        self.client.post(reverse("application_message", args=[app.pk]), {"body": "call me 98765 43210"})
        self.assertEqual(app.messages.count(), 0)
        self.client.post(reverse("application_message", args=[app.pk]), {"body": "I can start Saturday"})
        self.assertEqual(app.messages.count(), 1)


class TrustTests(TestCase):
    def test_complaint_is_allegation_only(self):  # T-12
        app = accepted_application()
        self.client.login(username=app.job.business.user.username, password=PW)
        self.client.post(reverse("complaint_create", args=[app.pk]),
                         {"category": "NO_SHOW", "description": "Did not turn up", "evidence_reference": ""})
        c = Complaint.objects.get()
        self.assertEqual(c.status, Complaint.Status.OPEN)
        app.worker.user.refresh_from_db()
        self.assertTrue(app.worker.user.is_active)
        self.assertEqual(app.worker.reputation, "New")

    def test_review_requires_confirmed_placement(self):  # T-13
        app = accepted_application()
        self.client.login(username=app.worker.user.username, password=PW)
        placement = Placement.objects.create(application=app, joined_at=date.today())  # still PENDING
        self.assertEqual(self.client.get(reverse("review_create", args=[placement.pk])).status_code, 403)

    def test_review_after_join_is_unique_and_moderated(self):
        app = accepted_application()
        placement = join(app)
        self.client.login(username=app.worker.user.username, password=PW)
        data = {"rating": 5, "reason_code": "CLEAR_TERMS", "comment": "Great"}
        self.client.post(reverse("review_create", args=[placement.pk]), data)
        self.client.post(reverse("review_create", args=[placement.pk]), data)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.get().moderation_status, "PENDING")
        self.assertEqual(app.job.business.reputation, "New")  # unpublished reviews don't count yet

    def test_protection_case_within_window(self):  # T-15
        app = accepted_application()
        placement = join(app)
        case = services.open_protection_case(app, app.job.business.user, "Worker left on day 5")
        self.assertEqual(case.status, ProtectionCase.Status.OPEN)
        self.assertEqual(case.refund_percent, 0)  # nothing automatic
        with self.assertRaises(WorkflowError):
            services.open_protection_case(app, app.job.business.user, "again")
        # outside the window
        app2 = accepted_application(worker=make_worker("w9"), business=app.job.business, job=make_job(app.job.business, title="J2"))
        services.confirm_joining(app2, app2.worker.user, date.today() - timedelta(days=30))
        services.confirm_joining(app2, app2.job.business.user)
        with self.assertRaises(WorkflowError):
            services.open_protection_case(app2, app2.job.business.user, "late")


class UploadValidationTests(TestCase):
    def form(self, name, content):
        return VerificationForm({"document_type": "STUDENT_ID"}, {"document": SimpleUploadedFile(name, content)},
                                account_type="worker")

    def test_rejects_wrong_extension(self):  # T-18
        self.assertFalse(self.form("a.exe", b"MZ....").is_valid())

    def test_rejects_extension_content_mismatch(self):
        self.assertFalse(self.form("a.pdf", b"not really a pdf").is_valid())

    @override_settings(WORKLINK={"MAX_UPLOAD_BYTES": 10})
    def test_rejects_oversized(self):
        self.assertFalse(self.form("a.pdf", b"%PDF" + b"x" * 100).is_valid())

    def test_accepts_valid_pdf(self):
        self.assertTrue(self.form("a.pdf", b"%PDF-1.4 hello").is_valid())
