from django.contrib import admin
from django.urls import include, path

from accounts import views as account_views

admin.site.site_header = "WorkLink administration"
admin.site.site_title = "WorkLink admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", account_views.home, name="home"),
    path("accounts/", include("accounts.urls")),
    path("jobs/", include("jobs.urls")),
    path("applications/", include("applications.urls")),
    path("notifications/", include("notifications.urls")),
    path("trust/", include("trust.urls")),
    path("ai/", include("ai_assist.urls")),
]
