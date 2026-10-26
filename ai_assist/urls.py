from django.urls import path

from . import views

urlpatterns = [
    path("job-draft/", views.job_draft, name="ai_job_draft"),
    path("cover-note/<int:job_id>/", views.cover_note, name="ai_cover_note"),
]
