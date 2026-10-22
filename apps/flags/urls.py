from django.urls import path

from . import api, views

app_name = "flags"

urlpatterns = [
    path("", views.FlagListView.as_view(), name="flag_list"),
    path("new/", views.flag_create, name="flag_create"),
    path("<int:pk>/", views.flag_detail, name="flag_detail"),
    path("<int:pk>/toggle/", views.flag_toggle, name="flag_toggle"),
    path("<int:pk>/archive/", views.flag_archive, name="flag_archive"),
    path("api/v1/flags/", api.flag_list, name="api_flag_list"),
    path("api/v1/flags/<str:key>/", api.flag_evaluate, name="api_flag_evaluate"),
]
