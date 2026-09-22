from django.urls import path

from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/import/', views.user_import, name='user_import'),
    path('users/<uuid:user_id>/', views.user_detail, name='user_detail'),
    path('users/<uuid:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<uuid:user_id>/export/xlsx/', views.user_export_xlsx, name='user_export_xlsx'),
    path('users/<uuid:user_id>/export/pdf/', views.user_export_pdf, name='user_export_pdf'),
    path('problems/', views.problem_list, name='problem_list'),
    path('problems/create/', views.problem_create, name='problem_create'),
    path('problems/import/', views.problem_import, name='problem_import'),
]
