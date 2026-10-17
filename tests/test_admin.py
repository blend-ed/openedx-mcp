"""Admin connect page: the raw key is shown once on save, and the standalone
connect page renders without one (the token is pasted client-side)."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from openedx_mcp.models import MCPKey

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client, settings):
    settings.ROOT_URLCONF = "tests.admin_urls"
    settings.OPENEDX_MCP_PUBLIC_URL = "https://mcp.example.com/mcp"
    user = get_user_model().objects.create_superuser("root", "root@example.com", "pw")
    client.force_login(user)
    client.user = user
    return client


def test_add_renders_connect_page_with_raw_key(admin_client):
    resp = admin_client.post(reverse("admin:openedx_mcp_mcpkey_add"), {
        "user": admin_client.user.pk, "name": "laptop", "scopes": ["read"],
    })
    assert resp.status_code == 200
    assert resp.templates[0].name == "admin/openedx_mcp/mcpkey/connect.html"
    raw = resp.context["raw_key"]
    key = MCPKey.objects.get(name="laptop")
    assert raw.startswith(key.key_prefix)
    assert raw.encode() in resp.content
    assert b"https://mcp.example.com/mcp" in resp.content
    assert "no-store" in resp["Cache-Control"]


def test_connect_page_without_key(admin_client):
    resp = admin_client.get(reverse("admin:openedx_mcp_mcpkey_connect"))
    assert resp.status_code == 200
    assert resp.context["raw_key"] is None
    assert b"mcpk_" not in resp.content.replace(b'placeholder="mcpk_', b"")


def test_changelist_links_to_connect(admin_client):
    resp = admin_client.get(reverse("admin:openedx_mcp_mcpkey_changelist"))
    assert reverse("admin:openedx_mcp_mcpkey_connect").encode() in resp.content


def test_connect_requires_staff(client, settings):
    settings.ROOT_URLCONF = "tests.admin_urls"
    resp = client.get(reverse("admin:openedx_mcp_mcpkey_connect"))
    assert resp.status_code == 302  # to admin login
