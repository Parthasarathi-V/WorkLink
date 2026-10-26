from django.urls import path

from . import views

urlpatterns = [
    path("complaints/", views.complaint_list, name="complaint_list"),
    path("complaints/new/<int:application_id>/", views.complaint_create, name="complaint_create"),
    path("complaints/<int:pk>/", views.complaint_detail, name="complaint_detail"),
    path("complaints/<int:pk>/respond/", views.complaint_respond, name="complaint_respond"),
    path("reviews/new/<int:placement_id>/", views.review_create, name="review_create"),
]
