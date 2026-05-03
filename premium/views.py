from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.
def premium_content(request):

    return HttpResponse("Premium Content")