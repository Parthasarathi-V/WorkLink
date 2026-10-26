import re

from accounts.privacy import contains_contact_details
from jobs.models import Job
from .client import generate
from .models import ListingReview

JOB_TYPES = {"PART_TIME", "TEMPORARY", "SHORT_TERM", "WEEKEND"}

# ---- 1. Rule-based listing risk flags (free, always on, no AI needed) ----
_PATTERNS = [
    (r"registration fee|security deposit|pay (?:to|for) (?:join|training|kit|uniform)|advance payment|processing fee",
     "Asks workers to pay money upfront"),
    (r"whatsapp|telegram|call me|dm me", "Pushes contact off-platform"),
    (r"earn (?:lakhs|thousands)|guaranteed income|get rich|no work.{0,10}high (?:pay|salary)", "Unrealistic earnings claim"),
    (r"only (?:male|female|boys|girls)|(?:males|females) only", "Gender-restricted wording"),
]
_PAY_LIMITS = {"HOUR": 1000, "DAY": 5000, "WEEK": 25000, "MONTH": 100000}


def rule_flags(job):
    text = f"{job.title} {job.description} {job.duties}".lower()
    flags = [msg for pat, msg in _PATTERNS if re.search(pat, text)]
    if contains_contact_details(f"{job.title} {job.description} {job.duties}"):
        flags.append("Contains a phone number or email")
    if job.pay_max > _PAY_LIMITS.get(job.pay_period, 10**9):
        flags.append("Pay looks unusually high for the period")
    if len(job.description.strip()) < 40:
        flags.append("Description is very short")
    return flags


def review_listing(job):
    """Rule flags + optional local-AI notes, stored for admin moderators."""
    flags = rule_flags(job)
    notes = ""
    ai = generate(
        "You help moderators of a part-time jobs site spot unsafe or misleading job ads. "
        "In at most 3 short bullet points list concerns (scam signs, vague terms, unsafe requests). "
        "If there are none, reply exactly: No concerns.\n\n"
        f"TITLE: {job.title}\nPAY: {job.pay_display}\nSCHEDULE: {job.schedule}\n"
        f"DESCRIPTION: {job.description[:1500]}\nDUTIES: {job.duties[:800]}"
    )
    if ai and ai.strip().lower().rstrip(".") != "no concerns":
        notes = ai[:1000]
    review, _ = ListingReview.objects.update_or_create(
        job=job, defaults={"rule_flags": "\n".join(flags), "ai_notes": notes, "flagged": bool(flags or notes)})
    return review


# ---- 2. Draft a job post from a rough description ----
def draft_job(rough_text):
    """Return (initial_form_data, used_ai). Output is only a draft; the business reviews and saves it."""
    rough_text = rough_text.strip()[:1500]
    data = generate(
        "Turn this rough description of a part-time job into a clear job post. Reply as JSON with keys: "
        "title, description, duties, job_type (one of PART_TIME, TEMPORARY, SHORT_TERM, WEEKEND), "
        "required_skills (comma-separated), schedule. Do NOT invent pay, phone numbers, emails or addresses; "
        "leave a key as an empty string if unknown. Be honest and plain.\n\nROUGH TEXT: " + rough_text,
        as_json=True)
    if not data:
        return {"title": "", "description": rough_text}, False
    out = {}
    for key in ("title", "description", "duties", "required_skills", "schedule"):
        val = str(data.get(key, "") or "").strip()
        out[key] = "" if contains_contact_details(val) else val
    if str(data.get("job_type", "")).upper() in JOB_TYPES:
        out["job_type"] = str(data["job_type"]).upper()
    out["title"] = out["title"][:150]
    return out, True


# ---- 3. Draft a short note for a worker's application ----
def draft_cover_note(worker, job):
    """Uses only matching-relevant profile fields: never phone, documents or identity details."""
    skills = ", ".join(worker.skill_list()[:8])
    fallback = (f"Hello, I'm interested in the {job.title} role at {job.business.business_name}. "
                + (f"My skills include {skills}. " if skills else "")
                + (f"I'm available {worker.availability}. " if worker.availability else "")
                + "Thank you for considering me.")
    text = generate(
        "Write a short, polite application note (max 4 sentences, first person) for a student applying to a "
        "part-time job. Use only the facts given. Do not include phone numbers, emails or made-up experience.\n\n"
        f"JOB: {job.title} at {job.business.business_name}, {job.area}. Schedule: {job.schedule}.\n"
        f"STUDENT: education: {worker.education or 'n/a'}; skills: {skills or 'n/a'}; "
        f"availability: {worker.availability or 'n/a'}.")
    if not text or contains_contact_details(text):
        return fallback, False
    return text[:1000], True


# ---- 4. Summarise a complaint for admins (assistive, not a verdict) ----
def summarise_complaint(c):
    base = (f"{c.get_category_display()}. Allegation: {c.description[:300]}"
            + (f" Response: {c.respondent_response[:300]}" if c.respondent_response else " No response yet."))
    text = generate(
        "Summarise this dispute neutrally in 3 short sentences for a moderator: what is alleged, what the other "
        "side says, and what evidence is missing. Do not decide who is right.\n\n"
        f"CATEGORY: {c.get_category_display()}\nALLEGATION: {c.description[:1500]}\n"
        f"EVIDENCE REFERENCE: {c.evidence_reference}\nRESPONSE: {c.respondent_response[:1500] or 'none'}")
    return text or base
