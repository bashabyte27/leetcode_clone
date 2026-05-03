from django.urls import path
from . import views
app_name = 'study_plans'

urlpatterns = [
    path('', views.study_plan_list, name='study_plan_list'),
]