import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ["SECRET_KEY"]
DEBUG = False
CSRF_TRUSTED_ORIGINS = [v for v in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if v]
if os.getenv("TRUST_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "0") == "1"
SECURE_REDIRECT_EXEMPT = [r"^api/health$"]
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "catalog",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=60)}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_TZ = True
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
MAX_PDF_BYTES = 100 * 1024 * 1024
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CONTENT_TYPE_NOSNIFF = True
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
