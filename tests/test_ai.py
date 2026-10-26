from django.test import TestCase

from ai_assist import services
from ai_assist.models import ListingReview
from tests.test_worklink import make_business, make_job, make_worker


class AiFallbackTests(TestCase):
    """AI is disabled in tests, so these verify the free rule-based fallbacks."""

    def test_rule_flags_catch_upfront_fee_and_contact(self):
        job = make_job(make_business(), description="Pay registration fee first. WhatsApp 98765 43210 now!")
        flags = services.rule_flags(job)
        self.assertTrue(any("upfront" in f for f in flags))
        self.assertTrue(any("off-platform" in f for f in flags))
        self.assertTrue(any("phone" in f for f in flags))

    def test_clean_listing_not_flagged(self):
        job = make_job(make_business(), description="Handle billing and serve customers on weekend evenings at our cafe.")
        self.assertFalse(services.review_listing(job).flagged)

    def test_flagged_listing_is_stored_but_not_removed(self):
        job = make_job(make_business(), description="Guaranteed income, pay security deposit to start.")
        services.review_listing(job)
        job.refresh_from_db()
        self.assertEqual(job.status, "PUBLISHED")
        self.assertTrue(ListingReview.objects.get(job=job).flagged)

    def test_draft_job_falls_back_to_rough_text(self):
        data, used_ai = services.draft_job("weekend cashier needed")
        self.assertFalse(used_ai)
        self.assertEqual(data["description"], "weekend cashier needed")

    def test_cover_note_fallback_uses_profile_facts_only(self):
        w = make_worker(skills="billing, excel", availability="weekends", phone="9876543210")
        note, used_ai = services.draft_cover_note(w, make_job(make_business()))
        self.assertFalse(used_ai)
        self.assertIn("billing", note)
        self.assertNotIn("9876543210", note)
