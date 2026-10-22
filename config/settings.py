"""WorkLink settings (development defaults). See README for production notes."""
import os
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security: override via environment variables outside local development ---
SECRET_KEY = os.environ.get("WORKLINK_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("WORKLINK_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("WORKLINK_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
