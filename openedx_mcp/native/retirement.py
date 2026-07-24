"""
Account retirement pipeline (LMS).

Two levels:
  * request_retirement(full=True)  -> create_retirement_request_and_deactivate_account:
    the real thing — queue row + hash username/email + unusable password + drop
    social-auth/OAuth/activation keys + retire recovery email. Downstream async
    jobs clear PII. Irreversible.
  * request_retirement(full=False) -> UserRetirementStatus.create_retirement:
    queue row only (no credential changes). Rarely what you want.

Distinct from simple deactivation (User.is_active=False), which is reversible and
touches no PII. Requires the acting user to hold the retirement Django perm.
"""


def _user(username_or_email):
    from django.contrib.auth import get_user_model
    U = get_user_model()
    u = U.objects.filter(username=username_or_email).first()
    if u is None and "@" in username_or_email:
        u = U.objects.filter(email__iexact=username_or_email).first()
    if u is None:
        raise ValueError(f"No such user: {username_or_email}")
    return u


def request_retirement(username_or_email, full=True):
    user = _user(username_or_email)
    if full:
        from openedx.core.djangoapps.user_api.accounts.utils import (
            create_retirement_request_and_deactivate_account,
        )
        create_retirement_request_and_deactivate_account(user)
        mode = "full (deactivated + queued + PII scheduled)"
    else:
        from openedx.core.djangoapps.user_api.models import UserRetirementStatus
        UserRetirementStatus.create_retirement(user)
        mode = "queue-only"
    return {"retirement_requested": username_or_email, "mode": mode}


def retirement_status(username_or_email):
    from openedx.core.djangoapps.user_api.models import UserRetirementStatus
    user = _user(username_or_email)
    row = UserRetirementStatus.objects.filter(user=user).select_related("current_state").first()
    if row is None:
        return {"user": user.username, "retirement": None}
    return {"user": user.username, "retirement": {
        "current_state": row.current_state.state_name if row.current_state else None,
        "retired_username": row.retired_username,
        "created": row.created.isoformat() if row.created else None,
        "modified": row.modified.isoformat() if row.modified else None,
    }}
