from django.test import TestCase

from django.urls import reverse

from .models import Users


class LoginTests(TestCase):
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
