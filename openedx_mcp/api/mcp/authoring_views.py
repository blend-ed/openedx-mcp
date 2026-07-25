"""CMS course-authoring tool endpoints. Loaded only in the Studio process
(/api/mcp/cms/). Reads need read; writes need write:courses; delete adds
destructive. Draft edits apply immediately; delete/publish use confirm handshake."""
from rest_framework.response import Response

from ...models import Scope
from ...native import authoring as nau
from .base import MCPView
from .guards import audited_write


class CourseOutlineView(MCPView):
    def get(self, request, course_id):
        outline = nau.read_outline(request.user, course_id)
        if outline is None:
            return Response({"error": "No such course."}, status=404)
        return Response(outline)


class CreateBlockView(MCPView):
    @audited_write("create_xblock", scope=Scope.WRITE_COURSES, require_confirm=False)
    def post(self, request, confirmed=True):
        d = request.data
        return Response(nau.create_block(request.user, d["parent_locator"], d["category"],
                                         d.get("display_name"), d.get("boilerplate"))), 1


class CreateBlockTreeView(MCPView):
    """Create a whole subtree (sections→subsections→units→components) in one call."""
    @audited_write("create_xblock", scope=Scope.WRITE_COURSES, require_confirm=False)
    def post(self, request, confirmed=True):
        d = request.data
        result = nau.create_block_tree(request.user, d["parent_locator"], d["nodes"])
        # affected = count of blocks created across the tree
        def _count(nodes):
            return sum(1 + _count(n.get("children", [])) for n in nodes)
        return Response(result), _count(result.get("created", []))


class UpdateBlockView(MCPView):
    @audited_write("update_xblock", scope=Scope.WRITE_COURSES, require_confirm=False)
    def post(self, request, confirmed=True):
        d = request.data
        return Response(nau.update_block(request.user, d["locator"], data=d.get("data"),
                                         metadata=d.get("metadata"), fields=d.get("fields"),
                                         publish=d.get("publish"))), 1


class PublishBlockView(MCPView):
    @audited_write("publish_xblock", scope=Scope.WRITE_COURSES, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        if not confirmed:
            return Response({"would_publish": d["locator"]})
        return Response(nau.publish_block(request.user, d["locator"])), 1


class DeleteBlockView(MCPView):
    @audited_write("delete_xblock", scope=Scope.WRITE_COURSES, destructive=True, require_confirm=True)
    def post(self, request, confirmed=True):
        d = request.data
        if not confirmed:
            return Response({"would_delete": d["locator"]})
        return Response(nau.delete_block(request.user, d["locator"])), 1


class UpdateCourseSettingsView(MCPView):
    @audited_write("update_course_settings", scope=Scope.WRITE_COURSES, require_confirm=False)
    def post(self, request, confirmed=True):
        d = request.data
        return Response(nau.update_course_settings(
            request.user, d["course_id"], details=d.get("details"),
            grading=d.get("grading"), advanced=d.get("advanced"))), 1
