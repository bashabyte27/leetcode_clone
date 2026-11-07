from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from problems.curriculum import CURRICULUM, build_cases
from problems.models import Editorial, Problem, ProblemHint, TestCase as ProblemTestCase
from submissions.models import Submission, SubmissionResult
from users.models import Users


class CurriculumDataTests(TestCase):
    def test_hundred_unique_problems_with_valid_cases(self):
        self.assertEqual(len(CURRICULUM), 100)
        self.assertEqual(len({s.slug for s in CURRICULUM}), 100)
        for index, spec in enumerate(CURRICULUM):
            cases = build_cases(spec, index)
            samples = [c for c in cases if c["is_sample"]]
            self.assertTrue(15 <= len(cases) <= 20, spec.slug)
            self.assertTrue(3 <= len(samples) <= 5, spec.slug)
            self.assertTrue(all(c["explanation"] for c in samples), spec.slug)
            self.assertEqual(len({c["input_data"] for c in cases}), len(cases), spec.slug)


class SeedCurriculumCommandTests(TestCase):
    def test_seed_is_idempotent_and_keeps_submission_history(self):
        call_command("seed_curriculum", verbosity=0)
        self.assertEqual(Problem.objects.filter(order_num__gte=15, order_num__lte=114).count(), 100)
        first = Problem.objects.get(order_num=15)
        self.assertEqual(first.slug, "namaste-coder")
        self.assertEqual(first.test_cases.filter(is_sample=True).count(), 3)
        self.assertTrue(Editorial.objects.get(problem=first).is_published)
        self.assertGreaterEqual(first.hints.count(), 2)
        self.assertTrue(first.tags.exists())

        user = Users.objects.create_user("s@example.com", "learner", "Password123!")
        submission = Submission.objects.create(user=user, problem=first, code="print()")
        case = first.test_cases.first()
        SubmissionResult.objects.create(submission=submission, test_case=case, status="accepted")

        cases_before = ProblemTestCase.objects.count()
        call_command("seed_curriculum", verbosity=0)
        self.assertEqual(ProblemTestCase.objects.count(), cases_before)
        self.assertTrue(SubmissionResult.objects.filter(test_case=case).exists())
        self.assertEqual(ProblemHint.objects.filter(problem=first).count(), len(CURRICULUM[0].hints))

    def test_order_conflict_aborts_without_writing(self):
        Problem.objects.create(order_num=20, title="Someone else", slug="someone-else", description="x", difficulty="easy")
        with self.assertRaises(Exception):
            call_command("seed_curriculum", verbosity=0)
        self.assertFalse(Problem.objects.filter(slug="namaste-coder").exists())

    def test_problem_page_shows_hints_and_samples(self):
        call_command("seed_curriculum", verbosity=0)
        response = self.client.get(reverse("problems:problem", args=["valid-brackets"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hint (2)")
        self.assertContains(response, "Example 1")
