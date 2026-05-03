from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def discussion_list(request):
    return HttpResponse("List of Discussions")
    