from tkinter import CASCADE

from django.db import models
from django.contrib.auth.hashers import make_password
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from jsonschema import ValidationError
# Create your models here.
class Users(models.Model):
    user_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile_no = models.CharField(max_length=15,unique=True)
    password = models.CharField(max_length=255)
    avatar_url = models.URLField(blank=True, null=True)
    role = models.CharField(max_length=50, default='user')
    is_verified = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
    # hash only if not already hashed
        if not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_name} | {self.email} | {self.mobile_no}"

class UserProfiles(models.Model):
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, null=True)
    location = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    company = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"User_Profile: {self.user.id} | {self.user.user_name} | {self.user.email} | {self.user.mobile_no}"

class UserStats(models.Model):
    user = models.OneToOneField(Users,on_delete=models.CASCADE, related_name='stats')
    easy_solved = models.IntegerField(default=0)
    medium_solved = models.IntegerField(default=0)
    hard_solved = models.IntegerField(default=0)
    acceptance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    global_rank = models.IntegerField(default=0)
    streak_days = models.IntegerField(default=0)
    total_submissions = models.IntegerField(default=0)
    reputation_points = models.IntegerField(default=0)
    last_active = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return f"User_Stats: {self.user.user_name} | {self.user.email} | {self.user.mobile_no}"
    

class Sessions(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='sessions')
    token_hash = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token_hash.startswith('pbkdf2_'):
            self.token_hash = make_password(self.token_hash)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Session: {self.user.user_name} | {self.user.email} | {self.user.mobile_no} | IP: {self.ip_address}"
    
class OauthProviders(models.Model):
    user = models.ForeignKey(Users,on_delete=models.CASCADE, related_name='oauth_providers')
    provider_name = models.CharField(max_length=100)
    provider_user_id = models.CharField(max_length=255, unique=True)
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OauthProvider: {self.user.user_name} | {self.provider_name}"
    
class Problems(models.Model):
    title = models.CharField(max_length=255)
    slug=models.SlugField(unique=True)
    description = models.TextField()
    difficulty = models.CharField(max_length=50)
    acceptance_rate = models.DecimalField(max_digits=5, decimal_places=2)
    tags = models.CharField(max_length=255)
    likes = models.IntegerField(default=0)
    dislikes = models.IntegerField(default=0)
    is_premium = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Problem: {self.title} | Difficulty: {self.difficulty} | Acceptance Rate: {self.acceptance_rate}%"
    

class tags(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)


    def __str__(self):
        return f"Tag: {self.name}"
    
class ProblemTags(models.Model):
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='problem_tags')
    tag = models.ForeignKey(tags, on_delete=models.CASCADE, related_name='tag_problems')

    def __str__(self):
        return f"ProblemTag: {self.problem.title} | Tag: {self.tag.name}"
    
class companies(models.Model):
    name = models.CharField(max_length=100,unique=True)
    slug = models.SlugField(unique=True)
    logo_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"Company: {self.name}"
    
class ProblemCompanies(models.Model):
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='problem_companies')
    company = models.ForeignKey(companies, on_delete=models.CASCADE, related_name='company_problems')

    def __str__(self):
        return f"ProblemCompany: {self.problem.title} | Company: {self.company.name}"

class TestCases(models.Model):
    problem = models.ForeignKey(Problems,on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField()
    expected_output = models.TextField()
    is_sample = models.BooleanField(default=False)
    explanation = models.TextField()
    order_num = models.IntegerField(unique=True)

    def __str__(self):
        return f"{self.id} | {self.problem.title}"
    
class ProblemHints(models.Model):
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name = 'hintsmodels.')
    hint_text = models.TextField()
    order_num = models.IntegerField(unique=True)

class CodeTemplates(models.Model):
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='code_templates')
    language = models.CharField(max_length=50)
    template_code = models.TextField()
    solution_code = models.TextField(blank=True, null=True)


    def __str__(self):
        return f"CodeTemplate: {self.problem.title} | Language: {self.language}"
    
class Submissions(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='submissions')
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='submissions')
    language = models.CharField(max_length=50)
    code = models.TextField()
    status = models.CharField(max_length=50)
    runtime = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    memory_usage = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Submission: {self.user.user_name} | {self.problem.title} | Status: {self.status}"
    
class SubmissionResults(models.Model):
    submission = models.ForeignKey(Submissions, on_delete=models.CASCADE, related_name = 'submission_result')
    test_case = models.ForeignKey(TestCases, on_delete=models.CASCADE, related_name = 'test_case_results')
    status = models.CharField(max_length=50)
    actual_output = models.TextField()
    runtime_ms = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    memory_usage_kb = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

class Discussions(models.Model):
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE,related_name = "discussions")
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='discussions')
    title = models.CharField(max_length=255)
    content = models.CharField(max_length=255)
    views = models.IntegerField(default=0)
    vote_count = models.IntegerField(default=0)
    is_pinned = models.BooleanField()


class Comments(models.Model):
    discussion = models.ForeignKey(Discussions, on_delete=models.CASCADE, related_name = 'comments')
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    vote_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Discussion: {self.user.user_name} | {self.content}"



class Vote(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)

    # Generic relation
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Vote value
    value = models.SmallIntegerField()  # +1 or -1

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')  # 🔥 one vote per user per object

    def __str__(self):
        return f"{self.user.user_name} voted {self.value}"

class Notifications(models.Model):
    user = models.ForeignKey(Users, on_delete = models.CASCADE, related_name = "notifications")
    type = models.CharField(max_length=255)
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.user_name} | {self.type} | {self.title} | Read: {self.is_read}"
    

class Contests(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    contest_type = models.CharField(max_length=50)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_virtual = models.BooleanField(default=False)

    def __str__(self):
        return f"Contest: {self.title} | Type: {self.contest_type} | Start: {self.start_time} | End: {self.end_time}"
    
    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
    
    class Meta:
        ordering = ['-start_time']  #  latest contests first

class ContestProblems(models.Model):
    contest = models.ForeignKey(Contests, on_delete=models.CASCADE, related_name='contest_problems')
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='problem_contests')
    order_num = models.IntegerField(unique=True)
    ponits = models.PositiveIntegerField(default=100)


    def __str__(self):
        return f"ContestProblem: {self.contest.title} | Problem: {self.problem.title}"



class ContestParticipant(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='contest_participations')
    contest = models.ForeignKey(Contests, on_delete=models.CASCADE, related_name='participants')
    
    rank = models.IntegerField(null=True, blank=True)
    score = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    penalty_minutes = models.IntegerField(default=0)
    
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'contest')
        ordering = ['rank']

    def __str__(self):
        return f"{self.user.user_name} | {self.contest.title} | Rank: {self.rank}"
    

class ContestSubmissions(models.Model):
    participant = models.ForeignKey(ContestParticipant, on_delete=models.CASCADE, related_name='contest_submissions')
    contest_problem = models.ForeignKey(ContestProblems, on_delete=models.CASCADE, related_name='contest_submissions')
    submission = models.ForeignKey(Submissions, on_delete=models.CASCADE, related_name='contest_submissions')
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='contest_submissions')
    score_gained = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_accepted = models.BooleanField(default=False)

    def __str__(self):
        return f"ContestSubmission: {self.participant.user.user_name} | {self.contest_problem.problem.title} | Status: {self.status}"
    

class StudyPlans(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    total_days = models.IntegerField(default=30)
    difficulty = models.CharField(max_length=50)
    is_premium = models.BooleanField(default=True)


    def __str__(self):
        return f"StudyPlan: {self.title} | Difficulty: {self.difficulty} | Premium: {self.is_premium}"
class StudyPlanItems(models.Model):
    study_plan = models.ForeignKey(StudyPlans, on_delete=models.CASCADE, related_name='items')
    day_num = models.IntegerField()
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='study_plan_items')
    order_num = models.IntegerField(unique=True)

    class Meta:
        unique_together = ('study_plan', 'day_num')

    def __str__(self):
        return f"StudyPlanItem: {self.study_plan.title} | Day: {self.day_num} | Problem: {self.problem.title}"
    
class UserStudyPlan(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='study_plan_progress')
    study_plan = models.ForeignKey(StudyPlans, on_delete=models.CASCADE, related_name='user_progress')
    day_num = models.IntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ('user', 'study_plan', 'day_num')

    def __str__(self):
        return f"UserStudyPlanProgress: {self.user.user_name} | {self.study_plan.title} | Day: {self.day_num} | Completed: {self.is_completed}"
    

class ProblemLists(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='problem_lists')
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ProblemList: {self.title}"
    
class ProblemListItems(models.Model):  
    problem_list = models.ForeignKey(ProblemLists, on_delete=models.CASCADE, related_name='items')
    problem = models.ForeignKey(Problems, on_delete=models.CASCADE, related_name='problem_list_items')
    notes = models.TextField(blank=True, null=True)
    added_at = models.DateTimeField(auto_now_add=True)
    order_num = models.IntegerField(unique=True)

    def __str__(self):
        return f"ProblemListItem: {self.problem_list.title} | Problem: {self.problem.title}"

class SubscriptionPlan(models.Model):
    plan_name = models.CharField(max_length=100)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=list)  # List of features included in the plan
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"SubscriptionPlan: {self.plan_name} | Monthly: {self.price_monthly} | Yearly: {self.price_yearly} | Active: {self.is_active}"

class Subscriptions(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='subscriptions')
    status = models.CharField(max_length=50)  # e.g., active, cancelled, expired
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Subscription: {self.user.user_name} | Plan: {self.plan.plan_name} | Active: {self.is_active}"
    
class PaymentTransactions(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='payment_transactions')
    subscription = models.ForeignKey(Subscriptions, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    transaction_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50)  # e.g., succeeded, failed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PaymentTransaction: {self.user.user_name} | Amount: {self.amount} {self.currency} | Status: {self.status}"
    
