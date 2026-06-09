"""URL routes for the core application."""

from django.urls import path

from core.views import HomePageView, ProjectCreateView, ProjectDetailView, ProjectListView

app_name = "core"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("projects/", ProjectListView.as_view(), name="project_list"),
    path("projects/new/", ProjectCreateView.as_view(), name="project_create"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project_detail"),
]
