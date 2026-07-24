"""CMS (Studio) URL config — mounted at ^api/mcp/cms/ by MCPCmsConfig.
Only the authoring tools live here; they need the modulestore (CMS-writable)."""
from django.urls import path

from . import authoring_views as av

app_name = "openedx_mcp_cms"

COURSE_ID = "<path:course_id>"

urlpatterns = [
    path(f"courses/{COURSE_ID}/outline/", av.CourseOutlineView.as_view(), name="outline"),
    path("courses/settings/", av.UpdateCourseSettingsView.as_view(), name="course-settings"),

    path("blocks/create/", av.CreateBlockView.as_view(), name="create-block"),
    path("blocks/create-tree/", av.CreateBlockTreeView.as_view(), name="create-block-tree"),
    path("blocks/update/", av.UpdateBlockView.as_view(), name="update-block"),
    path("blocks/publish/", av.PublishBlockView.as_view(), name="publish-block"),
    path("blocks/delete/", av.DeleteBlockView.as_view(), name="delete-block"),
]
