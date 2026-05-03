from django.urls import path
from . import views
app_name = 'users'

urlpatterns = [
    path('', views.user_list, name='user_list'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    # path('logout/', views.logout_view, name='logout'),
    path('test-email/', views.test_email, name='test_email'),

]
