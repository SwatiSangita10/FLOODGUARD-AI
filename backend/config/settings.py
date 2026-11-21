"""Settings for the FLOODGUARD AI API."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("Set DJANGO_SECRET_KEY in the environment before starting Django.")


def _boolean_environment_setting(name, default):
    value = os.environ.get(name, default).strip().lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} must be set to 'true' or 'false'.")
    return value == "true"


def _csv_environment_setting(name, default):
    return [
        value.strip()
        for value in os.environ.get(name, default).split(",")
        if value.strip()
    ]


DEBUG = _boolean_environment_setting("DJANGO_DEBUG", "false")
ALLOWED_HOSTS = _csv_environment_setting(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost",
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# SQLite is included only for Django framework defaults in local development.
# FloodGuard data storage will be added separately with PyMongo.
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

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
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = _csv_environment_setting(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = _boolean_environment_setting(
    "DJANGO_SECURE_SSL_REDIRECT",
    "false",
)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))

if not DEBUG:
    if not os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip():
        raise RuntimeError(
            "Set DJANGO_ALLOWED_HOSTS to the production API hostnames."
        )
    if not os.environ.get("CORS_ALLOWED_ORIGINS", "").strip():
        raise RuntimeError(
            "Set CORS_ALLOWED_ORIGINS to the production frontend origins."
        )
    if any("*" in value for value in ALLOWED_HOSTS):
        raise RuntimeError(
            "Wildcards are not allowed in production DJANGO_ALLOWED_HOSTS."
        )
    if any("*" in value for value in CORS_ALLOWED_ORIGINS):
        raise RuntimeError(
            "Wildcards are not allowed in production CORS_ALLOWED_ORIGINS."
        )
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if any(host.strip("[]").lower() in local_hosts for host in ALLOWED_HOSTS):
        raise RuntimeError(
            "Localhost and loopback hosts are not allowed in production DJANGO_ALLOWED_HOSTS."
        )
    if any(urlsplit(origin).hostname in local_hosts for origin in CORS_ALLOWED_ORIGINS):
        raise RuntimeError(
            "Localhost and loopback origins are not allowed in production CORS_ALLOWED_ORIGINS."
        )
