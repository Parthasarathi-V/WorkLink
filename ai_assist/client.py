"""Tiny client for a LOCAL Ollama server (free, no API key, data stays on your machine).
Returns None when AI is disabled or unreachable, so callers always have a rule-based fallback."""
import json
import urllib.error
import urllib.request

from django.conf import settings


def generate(prompt, as_json=False):
    cfg = settings.WORKLINK_AI
    if not cfg["ENABLED"]:
        return None
    payload = {"model": cfg["MODEL"], "prompt": prompt, "stream": False,
               "options": {"temperature": 0.3}}
    if as_json:
        payload["format"] = "json"
    req = urllib.request.Request(cfg["URL"].rstrip("/") + "/api/generate",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=cfg["TIMEOUT"]) as resp:
            text = json.load(resp).get("response", "").strip()
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if not text:
        return None
    if as_json:
        try:
            data = json.loads(text)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None
    return text
