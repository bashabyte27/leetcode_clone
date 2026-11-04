import json
import uuid
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assessment.models import (
    Assessment,
    AssessmentQuestionSnapshot,
    AssessmentSectionSnapshot,
    AssessmentVersion,
    Attempt,
    AttemptEvent,
    CodingQuestion,
    CodingQuestionSnapshot,
    Participant,
    ViolationLog,
)
from users.models import Users


class HostedAssessmentViewTests(TestCase):
    def setUp(self):
        self.faculty = Users.objects.create_user(
            email="hosted-faculty@example.com",
            user_name="hosted_faculty",
            password="StrongPass123!",
            is_faculty=True,
        )
        self.student = Users.objects.create_user(
            email="hosted-student@example.com",
            user_name="hosted_student",
            password="StrongPass123!",
        )
        self.assessment = Assessment.objects.create(
            created_by=self.faculty,
            name="Hosted assessment",
            slug="hosted-assessment",
            duration_minutes=30,
            passing_marks=5,
            status=Assessment.Status.PUBLISHED,
        )
        self.version = AssessmentVersion.objects.create(
            assessment=self.assessment,
            version_number=1,
            is_current=True,
            status=AssessmentVersion.Status.PUBLISHED,
            name=self.assessment.name,
            duration_minutes=30,
            passing_marks=5,
            max_attempts=1,
            result_release_policy=AssessmentVersion.ResultReleasePolicy.AFTER_END,
        )
        self.section = AssessmentSectionSnapshot.objects.create(
            version=self.version,
            title="Programming",
            position=1,
            time_limit_minutes=20,
        )
        coding_snapshot = CodingQuestionSnapshot.objects.create(
            version=self.version,
            title="Even or odd",
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic="Basics",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="Write a program to identify even numbers.",
            time_limit_seconds=2,
            memory_limit_kb=262144,
        )
        self.question = AssessmentQuestionSnapshot.objects.create(
            section=self.section,
            coding_snapshot=coding_snapshot,
            position=1,
            max_score=10,
            negative_marks=2,
        )
        self.participant = Participant.objects.create(
            assessment=self.assessment,
            user=self.student,
        )
        self.landing_url = reverse(
            "assessment:assessment_view",
            args=[self.assessment.slug],
        )
        self.start_url = reverse(
            "assessment:start_attempt",
            args=[self.assessment.slug],
        )
        self.status_url = reverse(
            "assessment:get_attempt_status",
            args=[self.assessment.slug],
        )
        self.violation_url = reverse(
            "assessment:log_violation",
            args=[self.assessment.slug],
        )

    def _login(self):
        self.client.force_login(self.student)

    def _start_attempt(self):
        response = self.client.post(
            self.start_url,
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["attempt"]

    def _log_violation(self, attempt_id, event_id=None):
        return self.client.post(
            self.violation_url,
            data=json.dumps(
                {
                    "attempt_id": attempt_id,
                    "event_id": str(event_id or uuid.uuid4()),
                    "event_type": "tab_hidden",
                    "timestamp": timezone.now().isoformat(),
                    "details": {"visibility": "hidden"},
                }
            ),
            content_type="application/json",
        )

    def test_landing_page_shows_candidate_assessment_and_section_summary(self):
        self._login()

        response = self.client.get(self.landing_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hosted assessment")
        self.assertContains(response, "Programming")
        self.assertContains(response, "10")
        self.assertContains(response, "negative marks up to 2.00 in total")
        self.assertContains(response, "section-container")
        self.assertContains(response, "I have read and agree")
        self.assertEqual(response.context["assessment_state"], "ready")

    def test_landing_page_requires_participant_access(self):
        self._login()
        self.participant.delete()

        self.assertEqual(self.client.get(self.landing_url).status_code, 404)
        self.assertEqual(self.client.post(self.start_url).status_code, 403)

    def test_anonymous_landing_request_redirects_to_project_login_with_next(self):
        response = self.client.get(self.landing_url)

        self.assertRedirects(
            response,
            f"{reverse('users:login')}?next={self.landing_url}",
            fetch_redirect_response=False,
        )

    def test_start_attempt_is_idempotent_and_status_restores_timer(self):
        self._login()

        first = self._start_attempt()
        second_response = self.client.post(
            self.start_url,
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.json()["resumed"])
        self.assertEqual(second_response.json()["attempt"]["id"], first["id"])
        self.assertEqual(Attempt.objects.filter(participant=self.participant).count(), 1)
        self.assertEqual(
            self.client.get(self.status_url).json()["attempt"]["id"],
            first["id"],
        )
        self.assertEqual(
            self.client.get(self.status_url).json()["warnings_remaining"],
            3,
        )
        self.assertEqual(
            Participant.objects.get(pk=self.participant.pk).status,
            Participant.Status.STARTED,
        )
        self.assertTrue(AttemptEvent.objects.filter(
            attempt_id=first["id"],
            event_type=AttemptEvent.EventType.STARTED,
        ).exists())

    def test_upcoming_landing_page_shows_start_countdown(self):
        self._login()
        self.version.start_time = timezone.now() + timedelta(minutes=10)
        self.version.save(update_fields=["start_time"])

        response = self.client.get(self.landing_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["assessment_state"], "upcoming")
        self.assertContains(response, "start-countdown")
        self.assertContains(response, "Start exam")

    def test_unpublished_assessment_shows_scheduled_countdown_without_start_button(self):
        self._login()
        self.assessment.status = Assessment.Status.DRAFT
        self.assessment.save(update_fields=["status"])
        self.version.start_time = timezone.now() + timedelta(minutes=10)
        self.version.save(update_fields=["start_time"])

        response = self.client.get(self.landing_url)

        self.assertEqual(response.context["assessment_state"], "not_live")
        self.assertContains(response, "start-countdown")
        self.assertNotContains(response, 'id="start-exam"')

    def test_start_attempt_rejects_not_live_and_expired_assessments(self):
        self._login()
        self.version.start_time = timezone.now() + timedelta(hours=1)
        self.version.save(update_fields=["start_time"])

        response = self.client.post(
            self.start_url,
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("not started yet", response.json()["error"])
        self.assertFalse(Attempt.objects.filter(participant=self.participant).exists())

    @override_settings(ASSESSMENT_PROCTOR_WARNING_LIMIT=1, ASSESSMENT_PROCTOR_AUTO_SUBMIT=True)
    def test_violation_logs_are_idempotent_and_auto_submit_after_warning_limit(self):
        self._login()
        attempt = self._start_attempt()
        event_id = uuid.uuid4()

        first = self._log_violation(attempt["id"], event_id)
        duplicate = self._log_violation(attempt["id"], event_id)
        second = self._log_violation(attempt["id"])

        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.json()["violation_count"], 1)
        self.assertEqual(first.json()["warnings_remaining"], 0)
        self.assertEqual(second.json()["violation_count"], 2)
        self.assertTrue(second.json()["auto_submitted"])
        self.assertEqual(ViolationLog.objects.filter(attempt_id=attempt["id"]).count(), 2)
        self.assertEqual(
            Attempt.objects.get(pk=attempt["id"]).status,
            Attempt.Status.SUBMITTED,
        )

    def test_status_endpoint_marks_server_deadline_expired(self):
        self._login()
        attempt_payload = self._start_attempt()
        attempt = Attempt.objects.get(pk=attempt_payload["id"])
        attempt.expires_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=["expires_at"])

        response = self.client.get(self.status_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["attempt"]["status"], Attempt.Status.TIMED_OUT)
        self.assertEqual(
            Participant.objects.get(pk=self.participant.pk).status,
            Participant.Status.COMPLETED,
        )

    @override_settings(ASSESSMENT_INVIGILATOR_PIN="2718")
    def test_submit_and_exit_and_invigilator_pin_finish_attempt(self):
        self._login()
        attempt = self._start_attempt()
        wrong_pin = self.client.post(
            self.violation_url,
            data=json.dumps(
                {
                    "attempt_id": attempt["id"],
                    "event_type": "invigilator_exit",
                    "pin": "0000",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(wrong_pin.status_code, 403)

        authorized = self.client.post(
            self.violation_url,
            data=json.dumps(
                {
                    "attempt_id": attempt["id"],
                    "event_type": "invigilator_exit",
                    "pin": "2718",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(authorized.status_code, 200)
        self.assertTrue(authorized.json()["submitted"])
        self.assertEqual(
            Participant.objects.get(pk=self.participant.pk).status,
            Participant.Status.COMPLETED,
        )

        response = self.client.get(self.landing_url)
        self.assertEqual(response.context["assessment_state"], "submitted")
        self.assertNotContains(response, 'id="start-exam"')

    def test_submit_and_exit_finishes_attempt_without_a_navigation_endpoint(self):
        self._login()
        attempt = self._start_attempt()
        response = self.client.post(
            self.violation_url,
            data=json.dumps(
                {
                    "attempt_id": attempt["id"],
                    "event_type": "submit_and_exit",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["submitted"])
        self.assertEqual(
            Attempt.objects.get(pk=attempt["id"]).status,
            Attempt.Status.SUBMITTED,
        )
