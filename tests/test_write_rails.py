"""Write-rail and error-mapping tests: failed writes keep their audit row and
roll back their own changes, errors are JSON with the right status, and the
Ulmo account-creation path is the one called. Platform modules are stubbed."""
import sys
from types import ModuleType, SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve
from opaque_keys import InvalidKeyError
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from openedx_mcp.api.mcp import base, cms_urls, urls
from openedx_mcp.api.mcp import views as mcp_views
from openedx_mcp.api.mcp.guards import audited_write
from openedx_mcp.models import MCPAuditLog
from openedx_mcp.native import enrollment, users

User = get_user_model()
factory = APIRequestFactory()
COURSE = "course-v1:Org+Num+Run"


def _stub(monkeypatch, dotted, **attrs):
    mod = ModuleType(dotted)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, dotted, mod)


def _call(view_cls, user, data):
    request = factory.post("/", data, format="json")
    force_authenticate(request, user=user)
    return view_cls.as_view()(request)


class _FailingWrite(APIView):
    """Writes a user, then blows up — the user must not survive."""
    permission_classes = []

    @audited_write("t_fail", require_confirm=False)
    def post(self, request, confirmed=True):
        User.objects.create(username="half-written")
        raise RuntimeError("boom")


class _BadInputWrite(APIView):
    permission_classes = []

    @audited_write("t_input", require_confirm=True)
    def post(self, request, confirmed=True):
        return Response({"would": request.data["missing"]})


# --- guard: savepoint + audit ---

@pytest.mark.django_db
def test_failed_write_rolls_back_its_changes_but_keeps_the_error_audit():
    admin = User.objects.create(username="admin", is_staff=True)
    resp = _call(_FailingWrite, admin, {"x": 1})

    assert resp.status_code == 500
    assert "RuntimeError" in resp.data["error"]
    assert not User.objects.filter(username="half-written").exists()
    outcomes = list(MCPAuditLog.objects.filter(tool="t_fail")
                    .order_by("id").values_list("outcome", flat=True))
    assert outcomes == ["attempt", "error"]
    assert "boom" in MCPAuditLog.objects.get(tool="t_fail", outcome="error").error


@pytest.mark.django_db
def test_dry_run_with_missing_field_is_a_json_400():
    admin = User.objects.create(username="admin", is_staff=True)
    resp = _call(_BadInputWrite, admin, {})
    assert resp.status_code == 400
    assert resp.data == {"error": "Missing required field: missing"}
    assert "confirm_token" not in resp.data


# --- error mapping / params ---

def test_invalid_key_maps_to_404():
    # e.g. courses/<id>/foo/ swallowed by the greedy course-detail route
    resp = base.error_response(InvalidKeyError("CourseKey", f"{COURSE}/foo"))
    assert resp.status_code == 404


def test_unknown_exception_maps_to_json_500():
    resp = base.error_response(RuntimeError("x"))
    assert resp.status_code == 500 and "RuntimeError" in resp.data["error"]


def test_int_param_rejects_non_numeric_with_400():
    from rest_framework.exceptions import ValidationError
    from rest_framework.request import Request
    request = Request(factory.get("/", {"limit": "ten"}))
    with pytest.raises(ValidationError):
        base.int_param(request, "limit", 50)
    assert base.int_param(Request(factory.get("/")), "limit", 50) == 50


# --- routes ---

def test_new_routes_resolve():
    assert resolve("/audit/", urlconf=urls).url_name == "audit-log"
    match = resolve(f"/courses/{COURSE}/settings/", urlconf=cms_urls)
    assert match.url_name == "course-settings-read"
    assert match.kwargs == {"course_id": COURSE}
    assert resolve("/courses/settings/", urlconf=cms_urls).url_name == "course-settings"


# --- audit log read ---

@pytest.mark.django_db
def test_audit_log_staff_see_only_their_own_rows(monkeypatch):
    monkeypatch.setattr(base, "_platform_auth_classes", lambda: [])
    staff = User.objects.create(username="staff", is_staff=True)
    other = User.objects.create(username="other", is_staff=True)
    root = User.objects.create(username="root", is_staff=True, is_superuser=True)
    MCPAuditLog.objects.create(user=staff, tool="enroll_user", outcome="success")
    MCPAuditLog.objects.create(user=other, tool="enroll_user", outcome="error")

    def get(user, **params):
        request = factory.get("/", params)
        force_authenticate(request, user=user)
        return mcp_views.AuditLogView.as_view()(request)

    assert [r["user"] for r in get(staff).data["rows"]] == ["staff"]
    assert get(root).data["total"] == 2
    assert [r["user"] for r in get(root, outcome="error").data["rows"]] == ["other"]
    assert get(root, limit="x").status_code == 400


# --- create_user ---

def test_create_user_uses_ulmo_form_and_sends_activation(monkeypatch, django_user_model, db):
    sent = []
    form_kwargs = {}

    class Form:
        def __init__(self, data=None, tos_required=True):
            form_kwargs.update(data=data, tos_required=tos_required)

    def do_create_account(form):
        user = django_user_model.objects.create(username="new", email="n@x.org", is_active=False)
        return user, SimpleNamespace(name="New"), SimpleNamespace()

    _stub(monkeypatch, "openedx.core.djangoapps.user_authn.views.registration_form",
          AccountCreationForm=Form)
    _stub(monkeypatch, "common.djangoapps.student.helpers", do_create_account=do_create_account)
    _stub(monkeypatch, "common.djangoapps.student.views.management",
          compose_and_send_activation_email=lambda u, p, r: sent.append(u.username))

    out = users.create_user("n@x.org", "new", name="New", send_activation_email=True)

    assert form_kwargs["tos_required"] is False
    assert form_kwargs["data"]["name"] == "New"
    assert sent == ["new"]
    assert out["is_active"] is False and out["activation_email_queued"] is True


@pytest.mark.django_db
def test_account_conflicts():
    User.objects.create(username="taken", email="Taken@x.org")
    assert users.account_conflicts("taken@x.org", "taken") == ["username", "email"]
    assert users.account_conflicts("free@x.org", "free") == []


# --- bulk enroll preview ---

def test_bulk_preview_splits_enroll_now_from_pending(monkeypatch):
    groups = {"enrolled": ["a@x"], "pending": ["p@x"],
              "account_not_enrolled": ["b@x"], "no_account": ["c@x", "d@x"]}
    monkeypatch.setattr(enrollment, "_classify", lambda key, entries: (["a@x"] * 5, groups))

    enroll = enrollment.preview_bulk_enroll(COURSE, [], action="enroll")
    assert (enroll["already_enrolled"], enroll["will_enroll"], enroll["will_be_pending"]) == (1, 1, 3)

    unenroll = enrollment.preview_bulk_enroll(COURSE, [], action="unenroll")
    assert (unenroll["will_unenroll"], unenroll["will_revoke_pending"],
            unenroll["not_enrolled"]) == (1, 1, 3)
