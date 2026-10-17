"""URLconf for admin tests: just the Django admin (test_settings has none)."""
from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
