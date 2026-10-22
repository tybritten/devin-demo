from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from .registry import ops_apps


def home(request):
    tiles = [t for app in ops_apps() if (t := app.tile(request.user))]
    return render(request, "core/home.html", {"tiles": tiles})


@login_not_required
def healthz(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})
