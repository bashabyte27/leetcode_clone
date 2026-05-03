from django.urls import path
from . import views
app_name = 'premium'
urlpatterns = [
    path('', views.premium_content, name='premium_content'),
]