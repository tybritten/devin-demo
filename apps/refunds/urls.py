from django.urls import path

from . import views

app_name = "refunds"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("all/", views.RefundListView.as_view(), name="refund_list"),
    path("new/", views.refund_create, name="refund_create"),
    path("<int:pk>/", views.RefundDetailView.as_view(), name="refund_detail"),
    path("<int:pk>/transition/", views.refund_transition, name="refund_transition"),
    path("<int:pk>/comment/", views.refund_comment, name="refund_comment"),
]
