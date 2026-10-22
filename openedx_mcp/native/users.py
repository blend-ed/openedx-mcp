"""
User management — thin wrappers over native Open edX user APIs (LMS).
"""
from django.contrib.auth import get_user_model

User = get_user_model()


def get_user(username_or_email):
    q = User.objects.filter(username=username_or_email).first()
    if q is None and "@" in username_or_email:
        q = User.objects.filter(email__iexact=username_or_email).first()
    return q


def list_users(query="", is_staff=None, limit=50, offset=0):
    qs = User.objects.all().order_by("id")
    if query:
        from django.db.models import Q
        qs = qs.filter(Q(username__icontains=query) | Q(email__icontains=query))
    if is_staff is not None:
        qs = qs.filter(is_staff=is_staff)
    total = qs.count()
    rows = [_user_dict(u) for u in qs[offset:offset + limit]]
    return {"total": total, "limit": limit, "offset": offset, "users": rows}


def _user_dict(u):
    return {"id": u.id, "username": u.username, "email": u.email,
            "is_active": u.is_active, "is_staff": u.is_staff, "is_superuser": u.is_superuser,
            "date_joined": u.date_joined.isoformat() if u.date_joined else None}


def get_account(request, username):
    """Full account settings. Native: user_api.accounts.api.get_account_settings
    (needs a request for permission scoping)."""
    from openedx.core.djangoapps.user_api.accounts.api import get_account_settings
    return get_account_settings(request, [username])


def create_user(email, username, name="", password=None, send_activation_email=False):
    """Create an account WITHOUT logging anyone in. Native path:
    student.helpers.do_create_account(form) → (user, profile, registration),
    user.is_active=False. Prefer this over create_account_with_params, which
    authenticates the caller into the session as a side effect.

    Raises django ValidationError for a taken/invalid username or email, and
    PermissionDenied when the platform has ALLOW_PUBLIC_ACCOUNT_CREATION off."""
    import uuid

    from common.djangoapps.student.helpers import do_create_account
    from common.djangoapps.student.views.management import compose_and_send_activation_email

    # Ulmo moved the form out of student.forms.
    from openedx.core.djangoapps.user_authn.views.registration_form import AccountCreationForm

    form = AccountCreationForm(
        data={
            "username": username,
            "email": email,
            "password": password or uuid.uuid4().hex,
            "name": name or username,
        },
        tos_required=False,
    )
    user, profile, registration = do_create_account(form)
    if send_activation_email:
        # Queues the platform's activation email (celery); failures are logged
        # by the platform, not raised.
        compose_and_send_activation_email(user, profile, registration)
    return {**_user_dict(user), "activation_email_queued": bool(send_activation_email)}


def account_conflicts(email, username):
    """Which of email/username already belong to an account (for previews)."""
    conflicts = []
    if username and User.objects.filter(username=username).exists():
        conflicts.append("username")
    if email and User.objects.filter(email__iexact=email).exists():
        conflicts.append("email")
    return conflicts


def set_global_staff(username_or_email, value):
    """Toggle is_staff. Native: student.roles.GlobalStaff().add_users/remove_users."""
    from common.djangoapps.student.roles import GlobalStaff
    user = get_user(username_or_email)
    if user is None:
        raise ValueError(f"No such user: {username_or_email}")
    if value:
        GlobalStaff().add_users(user)
    else:
        GlobalStaff().remove_users(user)
    user.refresh_from_db()
    return _user_dict(user)


def set_superuser(username_or_email, value):
    """Toggle is_superuser directly (no native role helper exists)."""
    user = get_user(username_or_email)
    if user is None:
        raise ValueError(f"No such user: {username_or_email}")
    user.is_superuser = value
    user.save(update_fields=["is_superuser"])
    return _user_dict(user)
