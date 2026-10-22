"""
Shared DRF base for every MCP facade view.

Authentication accepts, in order: the MCP key, an Open edX JWT bearer (carries
is_staff/is_superuser), or a session. Authorization is the single live
IsStaffOrSuperuser gate. These platform auth classes only import inside a running
LMS/CMS, which is the only place these URL configs are loaded.

Errors always come back as JSON. A bad id, a missing field or an unknown user is
the caller's mistake (4xx), so the model can correct itself; anything else is a
JSON 500 rather than the LMS's HTML error page.
"""
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from opaque_keys import InvalidKeyError
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import IsStaffOrSuperuser, MCPKeyAuthentication

log = logging.getLogger(__name__)


def _platform_auth_classes():
    from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
    from rest_framework.authentication import SessionAuthentication
    return [MCPKeyAuthentication, JwtAuthentication, SessionAuthentication]


def error_response(exc):
    """JSON Response for an exception a view raised, or None when DRF's own
    handler already turns it into one (APIException: 400/403/404/429...)."""
    if isinstance(exc, drf_exceptions.APIException):
        return None
    if isinstance(exc, InvalidKeyError):
        return Response({"error": f"Not a valid course or block id: {exc}"}, status=404)
    if isinstance(exc, ObjectDoesNotExist):
        return Response({"error": str(exc) or "Not found."}, status=404)
    if isinstance(exc, KeyError):
        return Response({"error": f"Missing required field: {exc.args[0]}"}, status=400)
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        return Response({"error": "Validation failed.", "detail": detail}, status=400)
    if isinstance(exc, ValueError):
        return Response({"error": str(exc)}, status=400)
    if isinstance(exc, DjangoPermissionDenied):
        return Response({"error": str(exc) or "Not permitted on this platform."}, status=403)
    log.exception("openedx-mcp: unhandled error in %s", type(exc).__name__)
    return Response({"error": f"Internal error ({type(exc).__name__}); see the LMS/CMS logs."},
                    status=500)


def int_param(request, name, default):
    """Integer query param; a non-numeric value is a 400, not a 500."""
    raw = request.query_params.get(name)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError:
        raise drf_exceptions.ValidationError({name: "Must be an integer."}) from None


class MCPView(APIView):
    permission_classes = [IsStaffOrSuperuser]

    def get_authenticators(self):
        return [cls() for cls in _platform_auth_classes()]

    def handle_exception(self, exc):
        resp = error_response(exc)
        return resp if resp is not None else super().handle_exception(exc)
