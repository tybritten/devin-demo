from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("", views.SystemListView.as_view(), name="system_list"),
    path("<slug:slug>/", views.SystemDetailView.as_view(), name="system_detail"),
]
