from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("attandance_app.urls")),  # Routes root to your attendance app.
]
