from django.urls import path

from . import views

urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("<int:pk>/open/", views.notification_open, name="notification_open"),
    path("read-all/", views.notification_read_all, name="notification_read_all"),
]
