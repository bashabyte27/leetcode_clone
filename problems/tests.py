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


from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse

from problems.models import Problem
from problems.stats import _streaks, practice_calendar
from submissions.models import Submission, SubmissionStatusChoices


class ProblemListPageTests(TestCase):
    def setUp(self):
        self.problem = Problem.objects.create(
            title="Even or Odd", slug="even-or-odd", description="x", difficulty="easy", order_num=1
        )
        self.user = get_user_model().objects.create_user(
            user_name="learner", email="learner@example.com", password="pw-123456"
        )

    def _submit(self, status):
        return Submission.objects.create(user=self.user, problem=self.problem, code="x", status=status)

    def test_anonymous_visitor_gets_the_page(self):
        response = self.client.get(reverse("problems:problem_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Even or Odd")
        self.assertNotIn("calendar", response.context)

    def test_acceptance_is_computed_from_judged_submissions(self):
        self._submit(SubmissionStatusChoices.ACCEPTED)
        self._submit(SubmissionStatusChoices.WRONG_ANSWER)
        self._submit(SubmissionStatusChoices.WRONG_ANSWER)
        self._submit(SubmissionStatusChoices.WRONG_ANSWER)
        self._submit(SubmissionStatusChoices.PENDING)  # no verdict yet: ignored
        response = self.client.get(reverse("problems:problem_list"))
        self.assertEqual(response.context["problems"][0].acceptance, 25.0)
        self.assertContains(response, "25%")

    def test_unsubmitted_problem_shows_new_instead_of_zero(self):
        response = self.client.get(reverse("problems:problem_list"))
        self.assertIsNone(response.context["problems"][0].acceptance)

    def test_logged_in_user_gets_calendar_progress_and_totals(self):
        self._submit(SubmissionStatusChoices.ACCEPTED)
        self.client.force_login(self.user)
        response = self.client.get(reverse("problems:problem_list"))
        self.assertEqual(response.context["solved_total"], 1)
        self.assertEqual(response.context["progress"], 100)
        self.assertEqual(response.context["calendar"]["active_days"], 1)
        self.assertEqual(response.context["calendar"]["current_streak"], 1)
        self.assertEqual(response.context["user_totals"]["rate"], 100.0)


class PracticeStatsTests(TestCase):
    def test_streak_survives_until_end_of_today(self):
        today = date(2026, 11, 6)
        days = {today - timedelta(days=1), today - timedelta(days=2), today - timedelta(days=5)}
        self.assertEqual(_streaks(days, today), (2, 2))

    def test_streak_breaks_after_a_missed_day(self):
        today = date(2026, 11, 6)
        self.assertEqual(_streaks({today - timedelta(days=2)}, today), (0, 1))

    def test_calendar_is_whole_weeks_ending_today(self):
        user = get_user_model().objects.create_user(user_name="cal", email="cal@example.com", password="pw-123456")
        cal = practice_calendar(user, today=date(2026, 11, 6))
        self.assertTrue(all(len(week) == 7 for week in cal["weeks"]))
        self.assertEqual(cal["weeks"][0][0]["date"].weekday(), 6)  # starts on a Sunday
        self.assertEqual(cal["weeks"][-1][5]["date"], date(2026, 11, 6))
        self.assertIsNone(cal["weeks"][-1][6])  # tomorrow is blank
