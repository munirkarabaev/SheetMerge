"""URL configuration for the SheetMerge project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('core.urls')),
    path('accounts/', include('allauth.urls')),
    path('app/', include('users.urls')),
    path('admin/', admin.site.urls),
]
