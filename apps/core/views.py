from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from apps.flags.launcher import tile as flags_tile
from apps.kyc.launcher import tile as kyc_tile
from apps.refunds.launcher import tile as refunds_tile

# Each app exposes `launcher.tile(user)`, returning a tile dict or None if the user lacks access.
TILE_PROVIDERS = [kyc_tile, refunds_tile, flags_tile]


def home(request):
    tiles = [t for provider in TILE_PROVIDERS if (t := provider(request.user))]
    return render(request, "core/home.html", {"tiles": tiles})


@login_not_required
def healthz(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})
