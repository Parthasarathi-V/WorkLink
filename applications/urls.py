from django.urls import path

from . import views

urlpatterns = [
    path("mine/", views.my_applications, name="my_applications"),
    path("job/<int:job_id>/apply/", views.apply, name="apply"),
    path("job/<int:job_id>/applicants/", views.job_applicants, name="job_applicants"),
    path("<int:pk>/", views.application_detail, name="application_detail"),
    path("<int:pk>/status/", views.application_status, name="application_status"),
    path("<int:pk>/joined/", views.application_joined, name="application_joined"),
    path("<int:pk>/dispute/", views.application_dispute, name="application_dispute"),
    path("<int:pk>/protection/", views.application_protection, name="application_protection"),
    path("<int:pk>/message/", views.application_message, name="application_message"),
]
