"""URL routing + native-wrapper tests. edx-platform modules are stubbed via
sys.modules, so these run without the platform."""
import json
import sys
from types import ModuleType, SimpleNamespace

from django.urls import resolve
from opaque_keys.edx.keys import CourseKey

from openedx_mcp.api.mcp import cms_urls, urls
from openedx_mcp.native import authoring, roles

COURSE = "course-v1:Org+Num+Run"


def _stub(monkeypatch, dotted, **attrs):
    mod = ModuleType(dotted)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, dotted, mod)


# --- routing ---

def test_course_team_route_not_shadowed_by_course_detail():
    match = resolve(f"/courses/{COURSE}/team/", urlconf=urls)
    assert match.url_name == "course-team"
    assert match.kwargs == {"course_id": COURSE}


def test_course_detail_route():
    match = resolve(f"/courses/{COURSE}/", urlconf=urls)
    assert match.url_name == "course-detail"
    assert match.kwargs == {"course_id": COURSE}


def test_user_certificate_routes():
    assert resolve("/certificates/user/bob/", urlconf=urls).url_name == "user-certificates"
    match = resolve(f"/certificates/user/bob/{COURSE}/", urlconf=urls)
    assert match.url_name == "user-certificate"
    assert match.kwargs == {"username": "bob", "course_id": COURSE}


def test_cms_outline_route():
    match = resolve(f"/courses/{COURSE}/outline/", urlconf=cms_urls)
    assert match.url_name == "outline"
    assert match.kwargs == {"course_id": COURSE}
    assert resolve("/courses/settings/", urlconf=cms_urls).url_name == "course-settings"


# --- roles ---

def test_list_user_roles_is_json_serializable(monkeypatch, django_user_model, db):
    user = django_user_model.objects.create(username="alice")
    rows = [{"role": "staff", "org": "Org", "course_id": CourseKey.from_string(COURSE)},
            {"role": "org_staff", "org": "Org", "course_id": None}]
    manager = SimpleNamespace(filter=lambda **kw: SimpleNamespace(values=lambda *a: rows))
    _stub(monkeypatch, "common.djangoapps.student.models",
          CourseAccessRole=SimpleNamespace(objects=manager))

    result = roles.list_user_roles(user.username)

    json.dumps(result)  # must not raise on CourseLocator
    assert result["roles"][0]["course_id"] == COURSE
    assert result["roles"][1]["course_id"] is None


# --- outline ---

def test_read_outline_includes_full_tree_compactly(monkeypatch):
    calls = {}
    always = object()

    def create_xblock_info(xblock, **kw):
        calls.update(kw)
        return {"id": "root", "display_name": "Course", "category": "course",
                "user_partitions": [1, 2], "actions": {}, "visibility_state": None,
                "child_info": {"category": "chapter", "children": [
                    {"id": "ch", "display_name": "Ch", "category": "chapter",
                     "published": False, "lms_url": "x", "child_info": {}}]}}

    _stub(monkeypatch, "cms.djangoapps.contentstore.xblock_storage_handlers.view_handlers",
          ALWAYS=always, create_xblock_info=create_xblock_info)
    course = object()
    store = SimpleNamespace(get_course=lambda key, depth=None: course)
    _stub(monkeypatch, "xmodule.modulestore.django", modulestore=lambda: store)

    out = authoring.read_outline(SimpleNamespace(), COURSE)

    assert calls["include_children_predicate"] is always
    assert out == {"id": "root", "display_name": "Course", "category": "course",
                   "children": [{"id": "ch", "display_name": "Ch", "category": "chapter",
                                 "published": False}]}
