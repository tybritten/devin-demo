"""Read-only JSON API for services. Authenticate with `Authorization: Bearer <token>`."""

from functools import wraps

from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from . import services
from .models import ApiClient, FeatureFlag


def api_client_required(view):
    # Token-authenticated and read-only, so no session or CSRF cookie is involved.
    @csrf_exempt
    @login_not_required
    @require_GET
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not ApiClient.authenticate(token.strip()):
            return JsonResponse({"error": "invalid or missing API token"}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


@api_client_required
def flag_list(request):
    flags = FeatureFlag.objects.filter(is_archived=False)
    return JsonResponse(
        {
            "flags": [services.flag_payload(f) for f in flags],
            "bucketing": "int(sha256(f'{key}:{target}').hexdigest()[:8], 16) % 100",
        }
    )


@api_client_required
def flag_evaluate(request, key):
    flag = FeatureFlag.objects.filter(key=key, is_archived=False).first()
    if flag is None:
        return JsonResponse({"error": f"unknown flag {key!r}"}, status=404)
    target = request.GET.get("target")
    return JsonResponse({"key": flag.key, "target": target, "enabled": flag.is_enabled_for(target)})
