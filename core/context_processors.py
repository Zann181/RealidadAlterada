from django.conf import settings

from core.roles import ROLE_CLIENTE, ROLE_VENDEDOR, user_has_role


def site_name(request):
    user = getattr(request, "user", None)
    is_admin = bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
    is_vendor = user_has_role(user, ROLE_VENDEDOR)
    is_client = user_has_role(user, ROLE_CLIENTE)
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "Sistema"),
        "WHATSAPP_NUMBER": getattr(settings, "WHATSAPP_NUMBER", ""),
        "IS_ADMIN": is_admin,
        "IS_VENDEDOR": is_vendor,
        "IS_CLIENTE": is_client,
    }
