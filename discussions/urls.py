from django.urls import path
from . import views

app_name = 'discussions'

urlpatterns = [
    path('problems/<slug:problem_slug>/', views.discussion_tab, name='discussion_tab'),
    path('problems/<slug:problem_slug>/comment/', views.post_comment, name='post_comment'),
    path('comments/<int:comment_id>/vote/', views.vote_comment, name='vote_comment'),
]