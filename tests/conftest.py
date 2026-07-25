"""Test configuration.

Django is configured by pytest-django from DJANGO_SETTINGS_MODULE=test_settings
(see pytest.ini). Nothing to do here — DB-backed tests use the `db` /
`django_db` marker; pure tests (the rails) just use the LocMemCache from the test
settings.
"""
