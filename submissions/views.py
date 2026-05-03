from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.
def submission_list(request):
    return HttpResponse("This is submissions app")