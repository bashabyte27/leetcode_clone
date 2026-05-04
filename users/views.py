import random, time
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from .forms import LoginForm, RegisterForm, ForgotPasswordForm
from .models import Users, UserProfile, UserStats
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required


def get_otp():
    return str(random.randint(100000, 999999))


def verify_otp(entered_otp, stored_otp, expires_at, attempts):
    """Pure utility — always returns (bool, str). No rendering, no request."""
    if time.time() > expires_at:
        return False, 'OTP expired. Please try again.'
    if attempts >= 3:
        return False, 'Too many wrong attempts. Please try again.'
    if entered_otp == stored_otp:
        return True, 'OTP verified.'
    return False, 'Wrong OTP.'


def user_list(request):
    all_users = Users.objects.all()
    return render(request, 'users/users_list.html', {'users': all_users})


def register_view(request):
    form = RegisterForm()

    if request.method == 'POST':
        if 'send-otp' in request.POST:
            form = RegisterForm(request.POST)
            if form.is_valid():
                otp = get_otp()
                request.session['otp'] = otp
                request.session['otp_expires_at'] = time.time() + 300
                request.session['otp_attempts'] = 0
                request.session['pending_user'] = {
                    'email':     form.cleaned_data['email'],
                    'user_name': form.cleaned_data['user_name'],
                    'password':  make_password(form.cleaned_data['password1']),
                    'mobile_no': form.cleaned_data.get('mobile_no', ''),
                }
                send_mail(
                    'Your OTP for Registration',
                    f'Your OTP is: {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [form.cleaned_data['email']],
                )
                return render(request, 'users/otp_form.html', {
                    'email': form.cleaned_data['email'],
                })

        elif 'verify-otp' in request.POST:
            entered_otp  = request.POST.get('otp', '').strip()
            pending_user = request.session.get('pending_user')

            status, msg = verify_otp(
                entered_otp=entered_otp,
                stored_otp=request.session.get('otp'),
                expires_at=request.session.get('otp_expires_at', 0),
                attempts=request.session.get('otp_attempts', 0),
            )

            if status:
                user = Users(
                    email=pending_user['email'],
                    user_name=pending_user['user_name'],
                    password=pending_user['password'],
                    mobile_no=pending_user['mobile_no'],
                    is_verified=True,
                )
                user.save()
                request.session.flush()
                return redirect('users:login')
            else:
                request.session['otp_attempts'] = request.session.get('otp_attempts', 0) + 1
                return render(request, 'users/otp_form.html', {
                    'email': pending_user['email'] if pending_user else '',
                    'error': msg,
                })

    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request,data=request.POST)
        if form.is_valid():
            login(request, form.user_cache)
            return redirect('problems:problem_list')  # fixed name
        else:
            return render(request,'users/login.html',{'form':form})
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    from django.contrib.auth import logout
    logout(request)
    return redirect('users:login')


def reset_password(request):
    form = ForgotPasswordForm()

    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)

        if 'send-otp' in request.POST and form.is_valid():
            email = form.cleaned_data['email']
            if not Users.objects.filter(email=email).exists():
                form.add_error('email', 'No account found with this email.')
            else:
                otp = get_otp()
                request.session['reset_otp'] = otp
                request.session['reset_expires_at'] = time.time() + 300
                request.session['reset_attempts'] = 0
                # Store everything needed for step 2 in the session
                request.session['pending_reset'] = {
                    'email':    email,
                    'password': make_password(form.cleaned_data['new_password1']),
                }
                send_mail(
                    'Your OTP for Password Reset',
                    f'Your OTP is: {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                )
                return render(request, 'users/otp_form.html', {
                    'email': email,
                    'form_action': 'reset-password',  # optional, for template routing
                })

        elif 'verify-otp' in request.POST:  # no form.is_valid() needed here
            entered_otp   = request.POST.get('otp', '').strip()
            pending_reset = request.session.get('pending_reset')

            if not pending_reset:
                return redirect('users:reset_password')

            status, msg = verify_otp(
                entered_otp=entered_otp,
                stored_otp=request.session.get('reset_otp'),
                expires_at=request.session.get('reset_expires_at', 0),
                attempts=request.session.get('reset_attempts', 0),
            )

            if status:
                user = Users.objects.filter(email=pending_reset['email']).first()
                if user:
                    user.password = pending_reset['password']  # already hashed
                    user.save()
                request.session.flush()
                return redirect('users:login')
            else:
                request.session['reset_attempts'] = request.session.get('reset_attempts', 0) + 1
                return render(request, 'users/otp_form.html', {
                    'email': pending_reset['email'],
                    'error': msg,
                })

    return render(request, 'users/forgot_password.html', {'form': form})

@login_required
def profile_view(request,username):
    from_user = request.user
    to_user = get_object_or_404(Users,user_name=username)
    if from_user.user_name==to_user.user_name:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        stats, is_created = UserStats.objects.get_or_create(user=request.user)
        context = {
            'profile':profile,
            'stats':stats,
            'editable':True
        }
        return render(request,"users/profile.html",context)
    else:
        to_user_profile, created = UserProfile.objects.get_or_create(user=to_user)
        stats, is_created = UserStats.objects.get_or_create(user=to_user)
        context = {
            'profile':to_user_profile,
            'stats':stats,
            'editable':False
        }

        return render(request,'users/profile.html',context)

