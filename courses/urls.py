from django.urls import path

from courses import views

urlpatterns = [
    path('', views.course_list, name='course_list'),
]