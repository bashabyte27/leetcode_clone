from django.urls import path
from . import views
app_name = 'contests'
urlpatterns = [
    path('', views.contest_list, name='contest_list'), 
]