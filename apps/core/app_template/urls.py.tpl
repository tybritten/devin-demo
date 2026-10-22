from django.urls import path

from . import views

app_name = "__app__"

urlpatterns = [
    path("", views.RecordListView.as_view(), name="list"),
    path("new/", views.record_create, name="create"),
    path("<int:pk>/", views.RecordDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.record_edit, name="edit"),
    path("<int:pk>/transition/", views.record_transition, name="transition"),
    path("<int:pk>/comment/", views.record_comment, name="comment"),
]
