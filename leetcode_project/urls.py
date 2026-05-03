"""
URL configuration for postgres_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin

from django.urls import path, include
from users import views as user_views

urlpatterns = [
    path('users/', include('users.urls')),
    path('problems/', include('problems.urls')),
    path('contests/', include('contests.urls')),
    path('submissions/', include('submissions.urls')),
    path('discussions/', include('discussions.urls')),
    path('premium/', include('premium.urls')),
    path('study-plans/', include('study_plans.urls')),
]
