"""
Shared DRF base for every MCP facade view.

Authentication accepts, in order: the MCP key, an Open edX JWT bearer (carries
is_staff/is_superuser), or a session. Authorization is the single live
IsStaffOrSuperuser gate. These platform auth classes only import inside a running
LMS/CMS, which is the only place these URL configs are loaded.
"""
from rest_framework.views import APIView

from .auth import IsStaffOrSuperuser, MCPKeyAuthentication


def _platform_auth_classes():
    from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
    from rest_framework.authentication import SessionAuthentication
    return [MCPKeyAuthentication, JwtAuthentication, SessionAuthentication]


class MCPView(APIView):
    permission_classes = [IsStaffOrSuperuser]

    def get_authenticators(self):
        return [cls() for cls in _platform_auth_classes()]
