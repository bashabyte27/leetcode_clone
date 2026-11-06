from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Assessment, Attempt, Participant

User = get_user_model()


class SignupDrilldownTests(TestCase):
    """Clicking a name on the Signups tab opens the same panel as the leaderboard."""

    def setUp(self):
        self.faculty = User.objects.create_user(
            email="fac@example.com", user_name="fac", password="x", is_faculty=True
        )
        self.student = User.objects.create_user(
            email="stu@example.com", user_name="stu", password="x"
        )
        self.assessment = Assessment.objects.create(
            created_by=self.faculty, name="Drill assessment", slug="drill-assessment",
            duration_minutes=30, max_attempts=1,
        )
        self.participant = Participant.objects.create(assessment=self.assessment, user=self.student)
        self.client.force_login(self.faculty)
        self.url = reverse("assessment:assessment_detail", args=[self.assessment.pk])

    def test_signup_names_link_to_the_student_panel(self):
        response = self.client.get(self.url, {"tab": "participants"})
        self.assertContains(response, f"user={self.student.pk}#participant-details")
        self.assertNotContains(response, 'id="participant-details"')

    def test_unstarted_signup_shows_panel_without_result(self):
        response = self.client.get(self.url, {"tab": "participants", "user": str(self.student.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="participant-details"')
        self.assertContains(response, "Results for Drill assessment only")
        self.assertContains(response, "No finalized result yet")
        self.assertContains(response, "This student has not started an attempt.")
        self.assertContains(response, "Unranked")
        self.assertIsNone(response.context["selected_participant"]["result"])
        self.assertEqual(response.context["participant_history"], [])

    def test_in_progress_signup_shows_latest_attempt_and_both_subtabs(self):
        Attempt.objects.create(participant=self.participant, attempt_number=1)
        summary = self.client.get(self.url, {"tab": "participants", "user": str(self.student.pk)})
        self.assertContains(summary, "Latest attempt: In Progress")
        submissions = self.client.get(
            self.url,
            {"tab": "participants", "user": str(self.student.pk), "participant_tab": "submissions"},
        )
        self.assertEqual(submissions.status_code, 200)
        self.assertContains(submissions, "No submissions were made in this attempt.")
        # Sub-tab links stay on the Signups tab
        self.assertContains(submissions, f"?tab=participants&amp;user={self.student.pk}")

    def test_unknown_user_is_ignored(self):
        response = self.client.get(self.url, {"tab": "participants", "user": "not-a-user"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="participant-details"')
