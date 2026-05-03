from django.urls import path
from . import views
app_name = 'problems'

urlpatterns = [
    path('', views.problem_list, name='problem_list'),
]