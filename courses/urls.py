"""Student-facing course URLs, mounted at /courses/."""

from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.catalog_view, name="catalog"),
    path("my-learning/", views.my_learning, name="my_learning"),
    path("<slug:slug>/", views.course_detail, name="course"),
    path("<slug:slug>/enroll/", views.enroll, name="enroll"),
    path("<slug:slug>/preview/<slug:module_slug>/<slug:lesson_slug>/", views.preview_lesson, name="preview"),
]
