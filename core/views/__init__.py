"""View exports for the core application."""

from core.views.home import HomePageView
from core.views.projects import ProjectCreateView, ProjectDetailView, ProjectListView

__all__ = [
    "HomePageView",
    "ProjectCreateView",
    "ProjectDetailView",
    "ProjectListView",
]
