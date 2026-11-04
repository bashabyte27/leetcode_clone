from django.test import TestCase
from django.urls import reverse

from .models import Problem


class ProblemDetailPracticeModeTests(TestCase):
    def test_practice_editor_retains_its_dom_contract(self):
        problem = Problem.objects.create(
            order_num=1,
            title="Practice editor test",
            slug="practice-editor-test",
            description="Return the input.",
            difficulty="easy",
        )

        response = self.client.get(
            reverse("problems:problem", args=[problem.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["coding_mode"], "practice")
        self.assertContains(response, 'id="monaco-editor-container"')
        self.assertContains(response, 'data-tab="editorial"')
        self.assertContains(response, 'data-tab="discussion"')
