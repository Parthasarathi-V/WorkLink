"""Transparent, rule-based job matching. NOT AI. Weights are illustrative and configurable."""
import re
from dataclasses import dataclass, field

WEIGHTS = {"skills": 40, "location": 25, "availability": 20, "job_type": 10, "completeness": 5}
LABELS = {"skills": "skills", "location": "area", "availability": "availability", "job_type": "job-type preference"}


@dataclass
class MatchResult:
    score: int
    reasons: list = field(default_factory=list)
    incomplete: list = field(default_factory=list)  # components skipped because data is missing


def _tokens(text):
    return {t.strip().lower() for t in re.split(r"[,;/\n]+", text or "") if t.strip()}


def score_job(worker, job):
    """Return a MatchResult. Missing data is omitted (not treated as a mismatch)."""
    parts = {}   # component -> fraction 0..1
    reasons = []

    ws, js = _tokens(worker.skills), _tokens(job.required_skills)
    if ws and js:
        overlap = ws & js
        parts["skills"] = len(overlap) / len(js)
        if overlap:
            reasons.append("Skills overlap: " + ", ".join(sorted(overlap)))

    wa, ja = (worker.preferred_area or "").strip().lower(), (job.area or "").strip().lower()
    if wa and ja:
        fits = wa in ja or ja in wa
        parts["location"] = 1.0 if fits else 0.0
        if fits:
            reasons.append("In your preferred area")

    avail, schedule = _tokens(worker.availability), (job.schedule or "").lower()
    if avail and schedule:
        hits = sorted(t for t in avail if t in schedule)
        parts["availability"] = 1.0 if hits else 0.0
        if hits:
            reasons.append("Matches your availability: " + ", ".join(hits))

    prefs = set(worker.job_type_list())
    if prefs:
        fits = job.job_type in prefs
        parts["job_type"] = 1.0 if fits else 0.0
        if fits:
            reasons.append("Matches your preferred job type")

    parts["completeness"] = worker.completeness()

    total = sum(WEIGHTS[k] for k in parts)
    score = round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()) / total)
    incomplete = [LABELS[k] for k in LABELS if k not in parts]
    return MatchResult(score=score, reasons=reasons, incomplete=incomplete)
