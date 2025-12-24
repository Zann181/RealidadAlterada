from django.conf import settings
from django.contrib.auth.views import LoginView
from django.urls import reverse

from core.roles import ROLE_CLIENTE, ROLE_VENDEDOR, user_has_role


class AdminLoginView(LoginView):
    """Login con redireccion por rol."""

    template_name = "registration/login.html"

    def get_success_url(self):
        user = self.request.user
        redirect_to = self.get_redirect_url()
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            if redirect_to and redirect_to.startswith("/admin/"):
                return redirect_to
            return reverse("admin:index")
        if user_has_role(user, ROLE_VENDEDOR):
            return reverse("core:dashboard")
        if user_has_role(user, ROLE_CLIENTE):
            return reverse("core:cliente_dashboard")
        if redirect_to:
            return redirect_to
        return settings.LOGIN_REDIRECT_URL
