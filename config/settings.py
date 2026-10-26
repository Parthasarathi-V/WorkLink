"""WorkLink settings (development defaults). See README for production notes."""
import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security: override via environment variables outside local development ---
SECRET_KEY = os.environ.get("WORKLINK_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("WORKLINK_DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "worklink-webpage.onrender.com",
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "notifications",
    "jobs",
    "applications",
    "trust",
    "ai_assist",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves static files (admin CSS, site.css) when DEBUG is off, e.g. on Render
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.unread_notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"   # `collectstatic` gathers admin + site assets here
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Verification documents live here and are NEVER served via a public URL.
PRIVATE_UPLOADS_ROOT = BASE_DIR / "private_uploads"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- WorkLink business policy (all configurable, none final) ---
WORKLINK = {
    "FREE_PLACEMENTS": 3,                   # first N confirmed placements per business are free
    "PROTECTION_DAYS": 14,                  # early-departure protection window (calendar days)
    "PROPOSED_REFUND_PERCENT": 75,          # proposal only; admin records the actual decision
    "DEFAULT_FEE": Decimal("0.00"),         # final fee is undecided; 0 until policy is set
    "CURRENCY": "INR",
    "FEE_DUE_DAYS": 7,
    "REQUIRE_WORKER_VERIFICATION": True,    # workers must be approved before applying
    "PUBLIC_JOB_BROWSING": True,            # visitors may view published listings
    "MAX_UPLOAD_BYTES": 5 * 1024 * 1024,
}

# --- Optional FREE local AI (Ollama). Off by default; every feature has a rule-based fallback. ---
WORKLINK_AI = {
    "ENABLED": os.environ.get("WORKLINK_AI_ENABLED", "0") == "1",
    "URL": os.environ.get("WORKLINK_AI_URL", "http://localhost:11434"),
    "MODEL": os.environ.get("WORKLINK_AI_MODEL", "llama3.2:3b"),
    "TIMEOUT": int(os.environ.get("WORKLINK_AI_TIMEOUT", "60")),
}


CSRF_TRUSTED_ORIGINS = [
    'https://worklink-webpage.onrender.com',
    'https://*.worklink-webpage.onrender.com',  # For subdomains
    'https://*.ngrok-free.app',
]

# Behind Render's HTTPS proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Serve files straight from STATICFILES_DIRS/app dirs even if collectstatic wasn't run (local use)
WHITENOISE_USE_FINDERS = True
