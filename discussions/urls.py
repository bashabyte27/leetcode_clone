from django.urls import path
from . import views
app_name = 'discussions'

urlpatterns = [
    path('', views.discussion_list, name='discussion_list'),
    path('/comment/<slug:problem_comment>',views.comment,name="post_comment"),

]