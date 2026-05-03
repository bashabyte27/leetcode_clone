import email

from django.shortcuts import render, redirect
from .forms import LoginForm, RegisterForm, ForgotPasswordForm
from .models import Users
# Create your views here.
def user_list(request):
    all_users = Users.objects.all()

    return render(request, 'users/users_list.html', {'users': all_users})
    
def register_view(request):
    form = RegisterForm()
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users:login')
    
    return render(request, 'users/register.html', {'form':form})

def login_view(request):
    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            # Perform login logic here
            return redirect('users:user_list')
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    # Perform logout logic here
    return redirect('users:login')

def forgot_password_view(request):
    form = ForgotPasswordForm()
    if request.method == 'POST':
        form = ForgotPasswordForm(request)
        instance = Users.objects.filter(email=email).first()
        if instance:
            instance.password = 'new_password'  # Set a new password or generate one
            instance.save()
            # Send an email to the user with the new password or a password reset link
    
    # Implement forgot password logic here
    return render(request, 'users/forgot_password.html')
