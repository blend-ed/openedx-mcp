"""Minimal Django config for the pure unit tests.

Only a LocMemCache is needed — the tests here exercise openedx_mcp.api.mcp._rails,
which imports nothing from the Open edX platform, so no app registry / DB / full
django.setup() is required.
"""
from django.conf import settings


def pytest_configure():
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            INSTALLED_APPS=[],
            DATABASES={},
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
        )
