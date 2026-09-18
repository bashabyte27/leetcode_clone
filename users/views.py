import os
import random, time

import resend
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q

from .forms import LoginForm, RegisterForm, ForgotPasswordForm
from .models import Users, UserProfile, UserFollow
from problems.models import Problem, DifficultyChoices
from submissions.models import Submission, SubmissionStatusChoices


resend.api_key = os.getenv("RESEND_API_KEY")


def send_otp_email(subject, email, otp):
    if not resend.api_key:
        return False

    try:
        response = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [email],
            "subject": subject,
            "text": f"Your OTP is: {otp}",
        })
    except Exception:
        return False

    if not response:
        return False
    if isinstance(response, dict) and response.get("error"):
        return False
    return not getattr(response, "error", None)


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
                print(otp)
                request.session['otp'] = otp
                request.session['otp_expires_at'] = time.time() + 300
                request.session['otp_attempts'] = 0
                request.session['pending_user'] = {
                    'email':     form.cleaned_data['email'],
                    'user_name': form.cleaned_data['user_name'],
                    'password':  make_password(form.cleaned_data['password1']),
                    'mobile_no': form.cleaned_data.get('mobile_no') or None,
                }
                if send_otp_email(
                    'Your OTP for Registration',
                    form.cleaned_data['email'],
                    otp,
                ):
                    return render(request, 'users/otp_form.html', {
                        'email': form.cleaned_data['email'],
                    })
                form.add_error(None, 'Unable to send OTP email. Please try again.')

        elif 'verify-otp' in request.POST:
            entered_otp  = request.POST.get('otp_code', '').strip()
            pending_user = request.session.get('pending_user')
            print(entered_otp)

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
    logout(request)
    return redirect('home')


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
                if send_otp_email(
                    'Your OTP for Password Reset',
                    email,
                    otp,
                ):
                    return render(request, 'users/otp_form.html', {
                        'email': email,
                        'form_action': 'reset-password',  # optional, for template routing
                    })
                form.add_error(None, 'Unable to send OTP email. Please try again.')

        elif 'verify-otp' in request.POST:  # no form.is_valid() needed here
            entered_otp   = request.POST.get('otp_code', '').strip()
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
def profile_view(request, username):
    to_user = get_object_or_404(Users, user_name=username)
    editable = request.user.is_authenticated and (request.user.id == to_user.id or request.user.user_name == to_user.user_name)

    profile, _ = UserProfile.objects.get_or_create(user=to_user)

    # ── User's Submissions & Real Solved Data ──
    user_submissions = Submission.objects.filter(user=to_user)
    total_submissions = user_submissions.count()
    accepted_submissions = user_submissions.filter(status=SubmissionStatusChoices.ACCEPTED).count()

    # Solved unique problems
    accepted_subs = user_submissions.filter(status=SubmissionStatusChoices.ACCEPTED)
    total_solved = accepted_subs.values('problem_id').distinct().count()
    easy_solved = accepted_subs.filter(problem__difficulty=DifficultyChoices.EASY).values('problem_id').distinct().count()
    medium_solved = accepted_subs.filter(problem__difficulty=DifficultyChoices.MEDIUM).values('problem_id').distinct().count()
    hard_solved = accepted_subs.filter(problem__difficulty=DifficultyChoices.HARD).values('problem_id').distinct().count()

    # Total active problems in DB
    total_problems = Problem.objects.filter(is_active=True).count()
    total_easy = Problem.objects.filter(is_active=True, difficulty=DifficultyChoices.EASY).count()
    total_medium = Problem.objects.filter(is_active=True, difficulty=DifficultyChoices.MEDIUM).count()
    total_hard = Problem.objects.filter(is_active=True, difficulty=DifficultyChoices.HARD).count()

    # Submission Rate = accepted submissions / total submissions * 100
    if total_submissions > 0:
        submission_rate = round((accepted_submissions / total_submissions) * 100, 1)
    else:
        submission_rate = 0.0

    # ── Dynamic Rank against ALL users based on submissions ──
    user_rankings = Users.objects.annotate(
        solved_count=Count('submissions__problem', filter=Q(submissions__status=SubmissionStatusChoices.ACCEPTED), distinct=True),
        accepted_count=Count('submissions', filter=Q(submissions__status=SubmissionStatusChoices.ACCEPTED)),
    ).order_by('-solved_count', '-accepted_count', 'created_at')

    user_ids_ordered = list(user_rankings.values_list('id', flat=True))
    try:
        rank = user_ids_ordered.index(to_user.id) + 1
    except ValueError:
        rank = len(user_ids_ordered)

    # ── Social Counts ──
    followers_count = UserFollow.objects.filter(following=to_user).count()
    following_count = UserFollow.objects.filter(follower=to_user).count()

    # ── Backend Paginated Submissions History (20 per page) ──
    submissions_qs = user_submissions.select_related(
        'problem', 'language'
    ).order_by('-submitted_at')
    paginator = Paginator(submissions_qs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Elided page range for clean navigation
    elided_page_range = paginator.get_elided_page_range(
        number=page_obj.number, on_each_side=2, on_ends=1
    )

    context = {
        'to_user': to_user,
        'profile': profile,
        'editable': editable,
        'rank': rank,
        'total_users': len(user_ids_ordered),
        'total_solved': total_solved,
        'easy_solved': easy_solved,
        'medium_solved': medium_solved,
        'hard_solved': hard_solved,
        'total_problems': total_problems,
        'total_easy': total_easy,
        'total_medium': total_medium,
        'total_hard': total_hard,
        'total_submissions': total_submissions,
        'accepted_submissions': accepted_submissions,
        'submission_rate': submission_rate,
        'followers_count': followers_count,
        'following_count': following_count,
        'page_obj': page_obj,
        'paginator': paginator,
        'elided_page_range': elided_page_range,
    }
    return render(request, 'users/profile.html', context)

