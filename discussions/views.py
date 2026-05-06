from django.shortcuts import render
from .models import Discussion, Comment
from problems.models import Problem
from .forms import CommentForm
from django.http import HttpResponse
# Create your views here.
def discussion_list(request):
    all_discussions = Discussion.objects.all()


    return render(request,'/discussion/dicussion_list.html',{'all_discussions':all_discussions})

def comment(request,problem_comment):
    form = CommentForm()

    if request.method=='POST':
        form = CommentForm(request)
        if form.is_valid():
            user = request.user
            problem = Problem.objects.get(slug=problem_comment)
            discussion = Discussion.objects.create(
                problem=problem,
                user=request.user,
                language=request.language,


                )
            
            Comment.objects.create(
                discussion=discussion,
                user=user,

            )
    return HttpResponse('Under development')