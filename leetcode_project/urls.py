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
from django.conf.urls.static import static
from django.conf import settings
from . import views as site_views
# from courses import views as course_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', site_views.home, name='home'),
    path('users/', include('users.urls')),
    path('problems/', include('problems.urls')),
    path('submissions/', include('submissions.urls')),
    path('discussions/', include('discussions.urls')),
    path('leaderboard/', include('leaderboard.urls')),
    path('courses/', include('courses.urls')),
    path('staff/courses/', include('courses.staff_urls')),
    path('staff/', include('staff.urls')),
    path('assessments/', include('assessment.urls')),
] + static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
