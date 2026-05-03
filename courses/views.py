from django.shortcuts import render
from .models import Courses

# Create your views here.
app_name = 'courses'

def course_list(request):
    courses = Courses.objects.all()
    return render(request, 'courses/course_list.html',{'courses':courses})