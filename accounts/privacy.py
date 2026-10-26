import re

_PHONE = re.compile(r"(?:\d[\s\-.]?){8,}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def contains_contact_details(text):
    """Heuristic only: reduces accidental sharing, cannot stop deliberate circumvention."""
    return bool(text and (_PHONE.search(text) or _EMAIL.search(text)))
