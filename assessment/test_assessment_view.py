import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assessment.models import (
    Assessment,
    AssessmentQuestionSnapshot,
    AssessmentSectionSnapshot,
    AssessmentVersion,
    Attempt,
    AttemptAuthorization,
    AttemptEvent,
    AttemptQuestionState,
    CodingQuestion,
    CodingQuestionLanguageSnapshot,
    CodingQuestionSnapshot,
    CodingTestCaseSnapshot,
    Participant,
    ProgrammingLanguage,
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
        self.language = ProgrammingLanguage.objects.create(
            name="Python",
            slug="assessment-test-python",
            is_active=True,
            is_judge0_executable=True,
            judge0_language_id=71,
        )
        CodingQuestionLanguageSnapshot.objects.create(
            question=coding_snapshot,
            language=self.language,
            language_name="Python",
            language_slug="python",
            starter_code="",
        )
        CodingTestCaseSnapshot.objects.create(
            question=coding_snapshot,
            input_data="2",
            expected_output="even",
            is_sample=True,
            position=1,
        )
        CodingTestCaseSnapshot.objects.create(
            question=coding_snapshot,
            input_data="7",
            expected_output="odd",
            is_sample=False,
            position=2,
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
        self.session_id = str(uuid.uuid4())

    def _login(self):
        self.client.force_login(self.student)

    def _start_attempt(self):
        response = self.client.post(
            self.start_url,
            data=json.dumps({"session_id": self.session_id}),
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
                    "session_id": self.session_id,
                    "event_id": str(event_id or uuid.uuid4()),
                    "event_type": "tab_hidden",
                    "timestamp": timezone.now().isoformat(),
                    "details": {"visibility": "hidden"},
                }
            ),
            content_type="application/json",
        )

    def _exam_request_payload(self, attempt, **extra):
        return {
            "attempt_id": attempt["id"],
            "session_id": self.session_id,
            **extra,
        }

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

    def test_landing_page_auto_enrolls_signed_in_users_with_the_hosted_link(self):
        self._login()
        self.participant.delete()

        response = self.client.get(self.landing_url)
        self.assertEqual(response.status_code, 200)
        participant = Participant.objects.get(
            assessment=self.assessment,
            user=self.student,
        )
        self.assertEqual(participant.status, Participant.Status.REGISTERED)

        start_response = self.client.post(
            self.start_url,
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 200)
        self.assertEqual(start_response.json()["attempt"]["status"], Attempt.Status.IN_PROGRESS)

    def test_blocked_and_removed_users_cannot_access_hosted_assessment_or_api(self):
        self._login()
        for status in (
            Participant.Status.DISQUALIFIED,
            Participant.Status.REMOVED,
        ):
            with self.subTest(status=status):
                self.participant.status = status
                self.participant.save(update_fields=["status"])
                response = self.client.get(self.landing_url)
                self.assertEqual(response.status_code, 403)
                self.assertContains(response, "blocked or removed", status_code=403)
                api_response = self.client.get(self.status_url)
                self.assertEqual(api_response.status_code, 403)

    def test_unpublished_assessment_without_registration_explains_it_is_not_live(self):
        self._login()
        self.participant.delete()
        self.assessment.status = Assessment.Status.DRAFT
        self.assessment.save(update_fields=["status"])

        response = self.client.get(self.landing_url)

        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response,
            "has not been published",
            status_code=403,
        )

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
            data=json.dumps({"session_id": self.session_id}),
            content_type="application/json",
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.json()["resumed"])
        self.assertEqual(second_response.json()["attempt"]["id"], first["id"])
        self.assertEqual(Attempt.objects.filter(participant=self.participant).count(), 1)
        self.assertEqual(
            self.client.get(
                self.status_url,
                {"session_id": self.session_id},
            ).json()["attempt"]["id"],
            first["id"],
        )
        self.assertEqual(
            self.client.get(
                self.status_url,
                {"session_id": self.session_id},
            ).json()["warnings_remaining"],
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
        attempt.expires_at = timezone.now() - timedelta(seconds=10)
        attempt.save(update_fields=["expires_at"])

        response = self.client.get(
            self.status_url,
            {"session_id": self.session_id},
        )

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
                    "session_id": self.session_id,
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
                    "session_id": self.session_id,
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

    def test_submitted_attempt_with_extra_attempts_can_start_again(self):
        self._login()
        Attempt.objects.create(
            participant=self.participant,
            assessment_version=self.version,
            attempt_number=1,
            status=Attempt.Status.SUBMITTED,
        )
        AttemptAuthorization.objects.create(
            participant=self.participant,
            authorized_by=self.faculty,
            extra_attempts=1,
            reason="Additional attempt approved",
        )

        landing = self.client.get(self.landing_url)

        self.assertEqual(landing.context["assessment_state"], "ready")
        self.assertTrue(landing.context["new_attempt_available"])
        self.assertContains(landing, "Another attempt is available")
        self.assertContains(landing, 'id="start-exam"')
        self.assertContains(landing, "1 of 2 total attempts remain")

        response = self.client.post(
            self.start_url,
            data=json.dumps({"session_id": str(uuid.uuid4())}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            Attempt.objects.filter(participant=self.participant).count(),
            2,
        )

    def test_submit_and_exit_finishes_attempt_without_a_navigation_endpoint(self):
        self._login()
        attempt = self._start_attempt()
        response = self.client.post(
            self.violation_url,
            data=json.dumps(
                {
                    "attempt_id": attempt["id"],
                    "session_id": self.session_id,
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

    def test_exam_state_and_question_restore_without_exposing_hidden_cases(self):
        self._login()
        attempt = self._start_attempt()
        state_url = reverse("assessment:get_exam_state", args=[self.assessment.slug])
        question_url = reverse("assessment:get_exam_question", args=[self.assessment.slug])

        state_response = self.client.get(
            state_url,
            {
                "attempt_id": attempt["id"],
                "session_id": self.session_id,
            },
        )
        self.assertEqual(state_response.status_code, 200, state_response.content)
        self.assertEqual(
            state_response.json()["current_question_id"],
            self.question.pk,
        )

        question_response = self.client.get(
            question_url,
            {
                "attempt_id": attempt["id"],
                "question_id": self.question.pk,
                "session_id": self.session_id,
            },
        )
        self.assertEqual(question_response.status_code, 200, question_response.content)
        question_data = question_response.json()
        self.assertEqual(len(question_data["samples"]), 1)
        self.assertEqual(question_data["samples"][0]["input"], "2")
        serialized = json.dumps(question_data)
        self.assertNotIn('"input_data": "7"', serialized)
        self.assertNotIn('"expected_output": "odd"', serialized)
        self.assertNotIn("is_correct", serialized)
        self.assertNotIn("Editorial", question_data["html"])
        self.assertNotIn("Discussion", question_data["html"])

    def test_editorial_and_discussion_endpoints_are_blocked_during_attempt(self):
        self._login()
        self._start_attempt()

        editorial = self.client.get(
            reverse("problems:editorial", args=["unrelated-problem"])
        )
        discussion = self.client.get(
            reverse("discussions:discussion_tab", args=["unrelated-problem"])
        )

        self.assertEqual(editorial.status_code, 403)
        self.assertEqual(discussion.status_code, 403)

    def test_code_draft_restores_for_its_question_and_language(self):
        self._login()
        attempt = self._start_attempt()
        draft_url = reverse("assessment:save_code_draft", args=[self.assessment.slug])
        question_url = reverse("assessment:get_exam_question", args=[self.assessment.slug])
        payload = self._exam_request_payload(
            attempt,
            question_id=self.question.pk,
            language_id=self.language.pk,
            source_code="print('saved')",
        )

        response = self.client.post(
            draft_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)

        restored = self.client.get(
            question_url,
            {
                "attempt_id": attempt["id"],
                "question_id": self.question.pk,
                "session_id": self.session_id,
            },
        )
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertEqual(restored.json()["languages"][0]["draft"], "print('saved')")

    def test_code_submission_judges_hidden_cases_without_returning_their_data(self):
        self._login()
        attempt = self._start_attempt()
        submit_url = reverse(
            "assessment:submit_assessment_code",
            args=[self.assessment.slug],
        )
        payload = self._exam_request_payload(
            attempt,
            question_id=self.question.pk,
            language_id=self.language.pk,
            source_code="print(input())",
        )
        results = [
            ("even", Decimal("1"), "", "accepted"),
            ("odd", Decimal("1"), "", "accepted"),
        ]

        with (
            patch("assessment.views.is_code_safe", return_value=(True, "")),
            patch("assessment.views.execute_code", side_effect=results) as execute,
        ):
            response = self.client.post(
                submit_url,
                data=json.dumps(payload),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["passed"], 2)
        self.assertEqual(execute.call_count, 2)
        self.assertNotIn("odd", response.content.decode())
        self.assertNotIn("results", response.json())

    def test_run_code_and_mark_for_review_apis_update_the_attempt(self):
        self._login()
        attempt = self._start_attempt()
        run_url = reverse(
            "assessment:run_assessment_code",
            args=[self.assessment.slug],
        )
        run_payload = self._exam_request_payload(
            attempt,
            question_id=self.question.pk,
            language_id=self.language.pk,
            source_code="print(input())",
        )
        with (
            patch("assessment.views.is_code_safe", return_value=(True, "")),
            patch(
                "submissions.judge0.execute_single",
                return_value={
                    "status": {"id": 3},
                    "stdout": "even",
                    "stderr": "",
                    "compile_output": "",
                    "time": "0.001",
                },
            ) as execute,
        ):
            run_response = self.client.post(
                run_url,
                data=json.dumps(run_payload),
                content_type="application/json",
            )

        self.assertEqual(run_response.status_code, 200, run_response.content)
        self.assertEqual(run_response.json()["results"][0]["status"], "accepted")
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0], self.language.judge0_language_id)

        submit_url = reverse(
            "assessment:submit_assessment_code",
            args=[self.assessment.slug],
        )
        with (
            patch("assessment.views.is_code_safe", return_value=(True, "")),
            patch(
                "submissions.judge0.execute_single",
                side_effect=[
                    {
                        "status": {"id": 3},
                        "stdout": "even",
                        "stderr": "",
                        "compile_output": "",
                        "time": "0.001",
                    },
                    {
                        "status": {"id": 3},
                        "stdout": "odd",
                        "stderr": "",
                        "compile_output": "",
                        "time": "0.001",
                    },
                ],
            ) as execute,
        ):
            submit_response = self.client.post(
                submit_url,
                data=json.dumps(run_payload),
                content_type="application/json",
            )
        self.assertEqual(submit_response.status_code, 200, submit_response.content)
        self.assertEqual(submit_response.json()["status"], "accepted")
        self.assertEqual(execute.call_count, 2)

        review_url = reverse(
            "assessment:update_exam_question_state",
            args=[self.assessment.slug],
        )
        review_response = self.client.post(
            review_url,
            data=json.dumps(
                self._exam_request_payload(
                    attempt,
                    question_id=self.question.pk,
                    action="mark_for_review",
                    marked=True,
                )
            ),
            content_type="application/json",
        )

        self.assertEqual(review_response.status_code, 200, review_response.content)
        self.assertTrue(
            AttemptQuestionState.objects.get(
                attempt_id=attempt["id"],
                question=self.question,
            ).marked_for_review
        )

    def test_exam_apis_reject_foreign_attempt_and_late_draft(self):
        self._login()
        attempt = self._start_attempt()
        state_url = reverse("assessment:get_exam_state", args=[self.assessment.slug])
        draft_url = reverse("assessment:save_code_draft", args=[self.assessment.slug])

        another_student = Users.objects.create_user(
            email="other-exam-student@example.com",
            user_name="other_exam_student",
            password="test-password",
        )
        self.client.force_login(another_student)
        foreign_response = self.client.get(
            state_url,
            {
                "attempt_id": attempt["id"],
                "session_id": self.session_id,
            },
        )
        self.assertEqual(foreign_response.status_code, 404)

        self.client.force_login(self.student)
        attempt_record = Attempt.objects.get(pk=attempt["id"])
        attempt_record.expires_at = timezone.now() - timedelta(seconds=10)
        attempt_record.save(update_fields=["expires_at"])
        late_response = self.client.post(
            draft_url,
            data=json.dumps(
                self._exam_request_payload(
                    attempt,
                    question_id=self.question.pk,
                    language_id=self.language.pk,
                    source_code="print('late')",
                )
            ),
            content_type="application/json",
        )
        self.assertEqual(late_response.status_code, 409)
        self.assertFalse(
            Attempt.objects.get(pk=attempt["id"]).code_drafts.exists()
        )

    def test_latest_exam_session_invalidates_the_previous_tab(self):
        self._login()
        attempt = self._start_attempt()
        state_url = reverse("assessment:get_exam_state", args=[self.assessment.slug])
        question_url = reverse("assessment:get_exam_question", args=[self.assessment.slug])
        new_session_id = str(uuid.uuid4())

        claimed = self.client.get(
            state_url,
            {
                "attempt_id": attempt["id"],
                "session_id": new_session_id,
            },
        )
        stale = self.client.get(
            question_url,
            {
                "attempt_id": attempt["id"],
                "question_id": self.question.pk,
                "session_id": self.session_id,
            },
        )

        self.assertEqual(claimed.status_code, 200, claimed.content)
        self.assertEqual(stale.status_code, 409)

    def test_exam_submission_is_idempotent(self):
        self._login()
        attempt = self._start_attempt()
        submit_url = reverse("assessment:submit_exam", args=[self.assessment.slug])
        payload = self._exam_request_payload(attempt)

        first = self.client.post(
            submit_url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        second = self.client.post(
            submit_url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(
            Attempt.objects.get(pk=attempt["id"]).status,
            Attempt.Status.SUBMITTED,
        )
