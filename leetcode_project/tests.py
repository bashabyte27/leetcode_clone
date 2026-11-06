from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from problems.models import Problem


class HomePageTests(TestCase):
    def test_anonymous_sees_live_problems_and_signup(self):
        Problem.objects.create(title="Reverse Words", slug="reverse-words", description="x", difficulty="easy", order_num=7)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reverse Words")
        self.assertContains(response, reverse("problems:problem", args=["reverse-words"]))
        self.assertContains(response, reverse("users:register"))
        self.assertEqual(response.context["problem_stats"]["easy"], 1)

    def test_faculty_gets_assessment_dashboard_link(self):
        user = get_user_model().objects.create_user(
            user_name="prof", email="prof@example.com", password="pw-123456", is_faculty=True
        )
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("assessment:dashboard"))
        self.assertContains(response, "Continue practicing")
        self.assertNotContains(response, "Start coding free")
