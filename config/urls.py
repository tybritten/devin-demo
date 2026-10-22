from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.audit.lockout import LockoutAuthenticationForm
from apps.core.registry import ops_urlpatterns

urlpatterns = [
    path("", include("apps.core.urls")),
    *ops_urlpatterns(),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(authentication_form=LockoutAuthenticationForm),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
