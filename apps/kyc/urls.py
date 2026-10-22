from django.urls import path

from . import views

app_name = "kyc"

urlpatterns = [
    path("", views.QueueView.as_view(), name="queue"),
    path("cases/new/", views.case_create, name="case_create"),
    path("cases/<int:pk>/", views.CaseDetailView.as_view(), name="case_detail"),
    path("cases/<int:pk>/claim/", views.case_claim, name="case_claim"),
    path("cases/<int:pk>/assign/", views.case_assign, name="case_assign"),
    path("cases/<int:pk>/transition/", views.case_transition, name="case_transition"),
    path("cases/<int:pk>/comment/", views.case_comment, name="case_comment"),
    path("cases/<int:pk>/documents/", views.document_upload, name="document_upload"),
    path("documents/<int:pk>/download/", views.document_download, name="document_download"),
]
