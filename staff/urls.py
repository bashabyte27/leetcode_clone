from django.urls import path

from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/import/', views.user_import, name='user_import'),
    path('users/<uuid:user_id>/', views.user_detail, name='user_detail'),
    path('users/<uuid:user_id>/update/', views.user_update, name='user_update'),
    path('users/<uuid:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<uuid:user_id>/delete/', views.user_delete, name='user_delete'),
    path('users/<uuid:user_id>/export/xlsx/', views.user_export_xlsx, name='user_export_xlsx'),
    path('users/<uuid:user_id>/export/pdf/', views.user_export_pdf, name='user_export_pdf'),
    path('problems/', views.problem_list, name='problem_list'),
    path('problems/create/', views.problem_create, name='problem_create'),
    path('problems/<int:problem_id>/', views.problem_detail, name='problem_detail'),
    path('problems/<int:problem_id>/delete/', views.problem_delete, name='problem_delete'),
    path('problems/<int:problem_id>/test-cases/add/', views.test_case_create, name='test_case_create'),
    path('problems/<int:problem_id>/test-cases/<int:test_case_id>/delete/', views.test_case_delete, name='test_case_delete'),
    path('problems/import/', views.problem_import, name='problem_import'),
]
