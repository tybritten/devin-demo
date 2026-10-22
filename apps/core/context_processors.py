from .registry import ops_apps


def ops_nav(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"ops_nav": []}
    return {"ops_nav": [app for app in ops_apps() if app.user_has_access(user)]}
