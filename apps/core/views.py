from django.contrib.auth.decorators import login_not_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from apps.kyc.models import ReviewCase


def home(request):
    tiles = []
    if request.user.has_perm("kyc.view_reviewcase"):
        open_cases = ReviewCase.objects.open()
        tiles.append(
            {
                "title": "KYC Review Queue",
                "description": "Review and decide customer KYC cases.",
                "url_name": "kyc:queue",
                "stats": [
                    ("Assigned to me", open_cases.filter(assigned_to=request.user).count()),
                    ("Unassigned", open_cases.filter(assigned_to__isnull=True).count()),
                    ("Overdue", open_cases.overdue().count()),
                ],
            }
        )
    return render(request, "core/home.html", {"tiles": tiles})


@login_not_required
def healthz(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})
