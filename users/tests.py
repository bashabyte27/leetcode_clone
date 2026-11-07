from django.test import TestCase
from django.urls import reverse

from .models import Users


class LoginTests(TestCase):
	def test_login_returns_to_safe_next_url(self):
		user = Users.objects.create_user('student@example.com', 'student_user', 'Password123!')
		response = self.client.post(reverse('users:login'), {
			'username_or_email': user.user_name,
			'password': 'Password123!',
			'next': '/assessments/sample_assessment_1/view/',
		})
		self.assertRedirects(
			response,
			'/assessments/sample_assessment_1/view/',
			fetch_redirect_response=False,
		)

	def test_login_rejects_external_next_url(self):
		user = Users.objects.create_user('student@example.com', 'student_user', 'Password123!')
		response = self.client.post(reverse('users:login'), {
			'username_or_email': user.user_name,
			'password': 'Password123!',
			'next': 'https://example.com/attacker',
		})
		self.assertRedirects(
			response,
			reverse('problems:problem_list'),
			fetch_redirect_response=False,
		)

	def test_blocked_user_sees_acknowledgement_and_stays_logged_out(self):
		user = Users.objects.create_user('blocked@example.com', 'blocked_user', 'Password123!', is_active=False)
		response = self.client.post(reverse('users:login'), {
			'username_or_email': user.user_name,
			'password': 'Password123!',
		})
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Your account has been blocked. Please contact the higher authority.')
		self.assertNotIn('_auth_user_id', self.client.session)

# Create your tests here.


class AdminUserCreationTests(TestCase):
	def setUp(self):
		self.admin = Users.objects.create_superuser('admin@example.com', 'site_admin', 'AdminPass123!')
		self.client.force_login(self.admin)

	def test_admin_created_user_has_hashed_password_and_can_log_in(self):
		response = self.client.post(reverse('admin:users_users_add'), {
			'email': 'newbie@example.com',
			'user_name': 'newbie',
			'password1': 'Str0ngPass!42',
			'password2': 'Str0ngPass!42',
			'role': 'user',
			'is_active': 'on',
		})
		self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['adminform'].form.errors)
		user = Users.objects.get(email='newbie@example.com')
		self.assertNotEqual(user.password, 'Str0ngPass!42')
		self.assertTrue(user.check_password('Str0ngPass!42'))

		self.client.logout()
		response = self.client.post(reverse('users:login'), {
			'username_or_email': 'newbie',
			'password': 'Str0ngPass!42',
		})
		self.assertEqual(response.status_code, 302)
		self.assertEqual(str(self.client.session['_auth_user_id']), str(user.pk))

	def test_admin_change_page_does_not_expose_editable_password(self):
		response = self.client.get(reverse('admin:users_users_change', args=[self.admin.pk]))
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'name="password"')


class RemovedPublicRoutesTests(TestCase):
	"""Routes that exposed data or were dead placeholders must stay gone."""

	def test_removed_urls_return_404(self):
		Users.objects.create_user('a@example.com', 'someone', 'Password123!')
		for url in ('/users/', '/users/someone/', '/problems/problems',
					'/problems/two-sum/submissions', '/contests/', '/premium/', '/study-plans/'):
			with self.subTest(url=url):
				self.assertEqual(self.client.get(url).status_code, 404)
