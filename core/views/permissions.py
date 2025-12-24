from django.conf import settings
from django.contrib.auth.decorators import user_passes_test

from core.roles import ROLE_CLIENTE, ROLE_VENDEDOR, user_has_role


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def is_vendor(user):
    return user_has_role(user, ROLE_VENDEDOR)


def is_client(user):
    return user_has_role(user, ROLE_CLIENTE)


def is_panel_user(user):
    return user.is_authenticated and (is_admin(user) or is_vendor(user))


def admin_required(view_func):
    return user_passes_test(is_admin, login_url=settings.LOGIN_URL)(view_func)


def panel_required(view_func):
    return user_passes_test(is_panel_user, login_url=settings.LOGIN_URL)(view_func)


def client_required(view_func):
    return user_passes_test(is_client, login_url=settings.LOGIN_URL)(view_func)
