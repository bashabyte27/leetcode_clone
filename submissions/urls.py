from django.urls import path
from .import views
app_name = 'submissions'

urlpatterns = [
    path('', views.submission_list, name='submission_list'), 
]