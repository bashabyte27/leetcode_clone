import io

from openpyxl import load_workbook
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from problems.models import Problem, TestCase as ProblemTestCase
from submissions.models import Submission, SubmissionStatusChoices
from users.models import Users

from .services import import_users


class StaffAccessTests(TestCase):
    def setUp(self):
        self.user = Users.objects.create_user('user@example.com', 'regular_user', 'Password123!')
        self.staff = Users.objects.create_user('staff@example.com', 'staff_user', 'Password123!', is_staff=True)

    def test_staff_area_requires_staff(self):
        response = self.client.get(reverse('staff:dashboard'))
        self.assertRedirects(response, f'{reverse("users:login")}?next={reverse("staff:dashboard")}')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('staff:dashboard')).status_code, 302)

    def test_staff_can_view_dashboard_and_problem_list(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('staff:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('staff:problem_list')).status_code, 200)

    def test_block_action_requires_post(self):
        self.client.force_login(self.staff)
        target = Users.objects.create_user('other@example.com', 'other_user', 'Password123!')
        response = self.client.get(reverse('staff:user_toggle_active', args=[target.id]))
        target.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(target.is_active)

    def test_user_import_reports_duplicate_rows(self):
        upload = SimpleUploadedFile(
            'users.csv', b'email,user_name,password\nnew@example.com,new_user,StrongPassword123!\nuser@example.com,duplicate,StrongPassword123!\n',
            content_type='text/csv',
        )
        result = import_users(upload)
        self.assertEqual(result['created'], 1)
        self.assertEqual(len(result['errors']), 1)

    def test_progress_export_is_xlsx(self):
        self.client.force_login(self.staff)
        target = Users.objects.create_user('export@example.com', 'export_user', 'Password123!')
        problem = Problem.objects.create(title='Export problem', description='A problem', difficulty='easy')
        Submission.objects.create(user=target, problem=problem, code='print(1)', status=SubmissionStatusChoices.ACCEPTED)
        response = self.client.get(reverse('staff:user_export_xlsx', args=[target.id]))
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(io.BytesIO(response.content))
        self.assertEqual(workbook.sheetnames, ['Summary', 'Solved problems', 'Submission history'])

    def test_problem_create_generates_slug_and_testcases(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('staff:problem_create'), {
            'title': 'Two Sum Practice',
            'description': 'Return the matching pair.',
            'difficulty': 'easy',
            'test_cases': '[{"input_data":"[2,7]","expected_output":"9","is_sample":true}]',
        })
        problem = Problem.objects.get(title='Two Sum Practice')
        self.assertRedirects(response, reverse('staff:problem_list'))
        self.assertEqual(problem.slug, 'two-sum-practice')
        self.assertEqual(ProblemTestCase.objects.filter(problem=problem).count(), 1)

    def test_invalid_testcases_do_not_create_problem(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse('staff:problem_create'), {
            'title': 'Broken Testcase Problem',
            'description': 'This should fail.',
            'difficulty': 'medium',
            'test_cases': '[{"input_data":"only input"}]',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Problem.objects.filter(title='Broken Testcase Problem').exists())
