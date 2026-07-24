"""
Open edX plugin configuration for openedx-mcp.

One Django app, two AppConfigs — one per Open edX process:

  * MCPLmsConfig  (lms.djangoapp)  mounts ^api/mcp/       — people, access,
    enrollment, analytics, key-management. Runs in the LMS.
  * MCPCmsConfig  (cms.djangoapp)  mounts ^api/mcp/cms/   — course authoring
    (create/clone/delete course, xblock CRUD, publish, settings). Runs in the
    CMS because these APIs touch the modulestore, which is only writable there.

Both share the same models (the MCPKey table lives in one app label, migrated
once and read from both processes against the same DB).

See edx-django-utils plugin docs:
https://github.com/openedx/edx-django-utils/tree/master/edx_django_utils/plugins
"""
import logging

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType

log = logging.getLogger(__name__)


class MCPLmsConfig(AppConfig):
    name = "openedx_mcp"
    label = "openedx_mcp"
    verbose_name = "Open edX Admin MCP"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "openedx_mcp",
                PluginURLs.REGEX: r"^api/mcp/",
                PluginURLs.RELATIVE_PATH: "api.mcp.urls",
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
                SettingsType.PRODUCTION: {PluginSettings.RELATIVE_PATH: "settings.production"},
                SettingsType.DEVSTACK: {PluginSettings.RELATIVE_PATH: "settings.development"},
            }
        },
    }

    def ready(self):
        log.info("openedx-mcp (LMS) %s ready", __import__("openedx_mcp").__version__)


class MCPCmsConfig(AppConfig):
    name = "openedx_mcp"
    label = "openedx_mcp"
    verbose_name = "Open edX Admin MCP (Studio)"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.CMS: {
                PluginURLs.NAMESPACE: "openedx_mcp_cms",
                PluginURLs.REGEX: r"^api/mcp/cms/",
                PluginURLs.RELATIVE_PATH: "api.mcp.cms_urls",
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
                SettingsType.PRODUCTION: {PluginSettings.RELATIVE_PATH: "settings.production"},
                SettingsType.DEVSTACK: {PluginSettings.RELATIVE_PATH: "settings.development"},
            }
        },
    }

    def ready(self):
        log.info("openedx-mcp (CMS) ready")
