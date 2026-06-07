"""URL routes for the core application."""

from django.urls import path

from core.views import HomePageView

app_name = "core"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
]
