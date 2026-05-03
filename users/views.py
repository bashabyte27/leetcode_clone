import email
import random, time
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect
from .forms import LoginForm, RegisterForm, ForgotPasswordForm
from .models import Users
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
# Create your views here.
def user_list(request):
    all_users = Users.objects.all()

    return render(request, 'users/users_list.html', {'users': all_users})


def register_view(request):
    form = RegisterForm()

    if request.method == 'POST':
        # ── Step 1: User submits registration form ──
        if 'send-otp' in request.POST:
            form = RegisterForm(request.POST)
            if form.is_valid():
                otp = str(random.randint(100000, 999999))
                request.session['otp'] = otp
                request.session['otp_expires_at'] = time.time() + 300  # 5 minutes
                request.session['otp_attempts'] = 0
                request.session['pending_user'] = {
                    'email':     form.cleaned_data['email'],
                    'user_name': form.cleaned_data['user_name'],
                    'password':  make_password(form.cleaned_data['password1']),  # hashed ✓
                    'mobile_no': form.cleaned_data.get('mobile_no', ''),
                }
                send_mail(
                    'Your OTP for Registration',
                    f'Your OTP is: {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [form.cleaned_data['email']],
                )
                return render(request, 'users/register.html', {
                    'otp_sent': True,
                    'email': form.cleaned_data['email'],
                })

        # ── Step 2: User submits OTP ──
        elif 'verify-otp' in request.POST:
            entered_otp   = request.POST.get('otp', '').strip()
            stored_otp    = request.session.get('otp')
            expires_at    = request.session.get('otp_expires_at', 0)
            attempts      = request.session.get('otp_attempts', 0)
            pending_user  = request.session.get('pending_user')

            # Expiry check
            if time.time() > expires_at:
                request.session.flush()
                return render(request, 'users/register.html', {
                    'otp_sent': True,
                    'error': 'OTP expired. Please register again.',
                })

            # Attempt limit
            if attempts >= 3:
                request.session.flush()
                return render(request, 'users/register.html', {
                    'form': RegisterForm(),
                    'error': 'Too many wrong attempts. Please register again.',
                })

            if entered_otp == stored_otp:
                # Create user with the already-hashed password
                user = Users(
                    email=pending_user['email'],
                    user_name=pending_user['user_name'],
                    password=pending_user['password'],   # already hashed, skip set_password
                    mobile_no=pending_user['mobile_no'],
                    is_verified=True,
                )
                user.save()
                request.session.flush()
                return redirect('users:login')

            else:
                request.session['otp_attempts'] = attempts + 1
                return render(request, 'users/register.html', {
                    'otp_sent': True,
                    'error': f'Wrong OTP. {2 - attempts} attempt(s) left.',
                    'email': pending_user['email'],
                })

    return render(request, 'users/register.html', {'form': form})

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

def test_email(request):
    send_mail(
        'Test Email',
        'This is a test email from Django',
        settings.DEFAULT_FROM_EMAIL,
        ['bashabyte@gmail.com'],  # put your own email here
    )
    return HttpResponse("Email sent! Check console")
