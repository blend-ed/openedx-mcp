"""
Standalone Django settings for the test suite.

Mirrors the Open edX cookiecutter-django-app convention (see edx-notes-api,
blendxai): a minimal settings module so the app's models, admin, auth and rails
can be tested with a real (sqlite) database, without booting the platform. The
`native/` wrappers still call into edx-platform at runtime — those are covered by
mocking the platform functions, or run in-container against a devstack.
"""
from os.path import abspath, dirname, join


def root(*args):
    return join(abspath(dirname(__file__)), *args)


SECRET_KEY = "insecure-test-key"
DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # The app under test — dotted AppConfig path picks the LMS config explicitly
    # (the package defines two configs, so a bare "openedx_mcp" is ambiguous).
    "openedx_mcp.apps.MCPLmsConfig",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

ROOT_URLCONF = "test_settings"  # no urls needed; keeps Django happy
urlpatterns = []

USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
