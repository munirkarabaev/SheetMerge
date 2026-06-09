"""URL routes for authenticated user pages."""

from django.urls import path

from users.views import DashboardPageView

app_name = "users"

urlpatterns = [
    path("", DashboardPageView.as_view(), name="dashboard"),
]
