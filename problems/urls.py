from django.urls import path
from . import views
app_name = 'problems'

urlpatterns = [
    path('', views.problem_list, name='problem_list'),
    path('shuffle/', views.shuffle_problem, name='shuffle_problem'),
    path('<slug:problemname>',views.problem_detail,name='problem'),
    path('problems-panel/',views.problem_get_list,name='problem_list_panel'),
    path('<slug:problemname>/editorial',views.editorial,name='editorial'),
    path('<slug:problemname>/submissions',views.submission_history,name='submission_history'),
    path('problems',views.problem_page,name='problem_page')
]