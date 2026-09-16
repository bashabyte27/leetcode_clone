# submissions/urls.py

from django.urls import path
from . import views

app_name = 'submissions'

urlpatterns = [
    # path('', views.submission_list, name='submission_list'),
    path('submit/<slug:problem_slug>/', views.submit_code, name='submit_code'),
    path('run/<slug:problem_slug>/', views.run_code, name='run_code'),
    path('<slug:problem_slug>/', views.submission_list, name='submission_list'),
    path('detail/<int:submission_id>/', views.submission_detail, name='submission_detail'),
]