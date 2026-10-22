"""Create demo/test data. Local development ONLY: passwords here are public."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import BusinessProfile, VerificationStatus, WorkerProfile
from jobs.models import Job

DEMO_PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Create demo admin, workers, businesses and jobs (test data only)."

    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@example.com"})
        if created:
            admin.is_staff = admin.is_superuser = True
            admin.set_password("admin12345")
            admin.save()

        def make_user(username, email):
            user, new = User.objects.get_or_create(username=username, defaults={"email": email})
            if new:
                user.set_password(DEMO_PASSWORD)
                user.save()
            return user

        workers = [
            ("asha", "Asha Rao", "BCom 2nd year", "billing, excel, hindi, customer service", "Indiranagar",
             "weekends, evenings", "PART_TIME,WEEKEND", VerificationStatus.APPROVED),
            ("ravi", "Ravi Kumar", "BSc 1st year", "delivery, photoshop", "Koramangala",
             "mornings, weekends", "TEMPORARY,SHORT_TERM", VerificationStatus.APPROVED),
            ("neha", "Neha Singh", "", "", "", "", "", VerificationStatus.NOT_SUBMITTED),
        ]
        for username, name, edu, skills, area, avail, types, status in workers:
            u = make_user(username, f"{username}@example.com")
            WorkerProfile.objects.get_or_create(user=u, defaults=dict(
                display_name=name, education=edu, skills=skills, preferred_area=area,
                availability=avail, preferred_job_types=types, verification_status=status))

        businesses = [
            ("chaipoint", "Chai Point Cafe", "Cafe", "Indiranagar", VerificationStatus.APPROVED),
            ("quickprint", "QuickPrint Studio", "Printing", "Koramangala", VerificationStatus.APPROVED),
            ("newmart", "New Mart (unverified)", "Retail", "Jayanagar", VerificationStatus.PENDING),
        ]
        profiles = {}
        for username, name, cat, area, status in businesses:
            u = make_user(username, f"{username}@example.com")
            profiles[username], _ = BusinessProfile.objects.get_or_create(user=u, defaults=dict(
                business_name=name, category=cat, area=area, verification_status=status))

        jobs = [
            ("chaipoint", "Weekend cashier", "PART_TIME", 150, 200, "HOUR", "Indiranagar",
             "weekends 10am-6pm", "billing, customer service", 2),
            ("chaipoint", "Evening counter helper", "PART_TIME", 120, 160, "HOUR", "Indiranagar",
             "evenings 5pm-9pm", "customer service", 1),
            ("quickprint", "Print shop assistant", "TEMPORARY", 600, 800, "DAY", "Koramangala",
             "mornings, weekdays", "photoshop, excel", 1),
            ("quickprint", "Flyer delivery (one-off)", "SHORT_TERM", 500, 500, "DAY", "Koramangala",
             "weekend morning", "delivery", 3),
        ]
        for key, title, jtype, pmin, pmax, period, area, sched, skills, vac in jobs:
            Job.objects.get_or_create(business=profiles[key], title=title, defaults=dict(
                description=f"{title} at {profiles[key].business_name}. Training provided.",
                duties="Customer handling, basic billing/support, keeping the area tidy.",
                job_type=jtype, pay_min=pmin, pay_max=pmax, pay_period=period, area=area,
                schedule=sched, required_skills=skills, vacancies=vac,
                status=Job.Status.PUBLISHED, closing_at=date.today() + timedelta(days=30)))

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready.\n  Admin:    admin / admin12345\n"
            f"  Workers:  asha, ravi (approved), neha (unverified) / {DEMO_PASSWORD}\n"
            f"  Business: chaipoint, quickprint (approved), newmart (pending) / {DEMO_PASSWORD}"))
