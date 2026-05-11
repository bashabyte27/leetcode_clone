from django.urls import path
from . import views
app_name = 'problems'

urlpatterns = [
    path('', views.problem_list, name='problem_list'),
    path('<slug:problemname>',views.problem_detail,name='problem'),
    path('<slug:problemname>/solutions', views.get_solution, name='get_solutions'),
    path('/problems-panel/',views.problem_get_list,name='problem_list_panel'),
    path('<slug:problemname>/editorial',views.editorial,name='editorial'),
    path('<slug:problemname>/submissions',views.submission_history,name='submission_history'),
    path('problems',views.problem_page,name='problem_page')
]