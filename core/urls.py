"""URL routes for the core application."""

from django.urls import path

from core.views import (
    BillingPageView,
    HomePageView,
    MergesetCreateView,
    MergesetDeleteView,
    MergesetDetailView,
    MergesetFileDeleteView,
    MergesetFileUploadView,
    MergesetListView,
    SupportPageView,
)

app_name = "core"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("mergesets/", MergesetListView.as_view(), name="mergeset_list"),
    path("mergesets/new/", MergesetCreateView.as_view(), name="mergeset_create"),
    path("mergesets/<int:pk>/", MergesetDetailView.as_view(), name="mergeset_detail"),
    path(
        "mergesets/<int:pk>/delete/",
        MergesetDeleteView.as_view(),
        name="mergeset_delete",
    ),
    path(
        "mergesets/<int:pk>/files/",
        MergesetFileUploadView.as_view(),
        name="mergeset_file_upload",
    ),
    path(
        "mergesets/<int:pk>/files/<int:file_pk>/delete/",
        MergesetFileDeleteView.as_view(),
        name="mergeset_file_delete",
    ),
    path("billing/", BillingPageView.as_view(), name="billing"),
    path("support/", SupportPageView.as_view(), name="support"),
]
