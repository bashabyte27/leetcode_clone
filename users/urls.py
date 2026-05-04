from django.urls import path
from . import views
app_name = 'users'

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('reset-password/',views.reset_password, name='reset_password'),
    path('profile/',views.profile_view,name='profile'),
    path('logout/', views.logout_view, name='logout'),

]
