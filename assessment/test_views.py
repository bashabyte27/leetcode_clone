import json
import uuid
from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from assessment.forms import AssessmentQuestionForm
from assessment.models import (
    Assessment,
    AssessmentModerator,
    AssessmentQuestion,
    AssessmentQuestionSnapshot,
    AssessmentResult,
    AssessmentSection,
    AssessmentSectionSnapshot,
    AssessmentSubmission,
    AssessmentVersion,
    Attempt,
    AttemptAnswer,
    AttemptAuthorization,
    AttemptEvent,
    CodingQuestion,
    CodingQuestionLanguage,
    CodingQuestionLanguageSnapshot,
    CodingQuestionSnapshot,
    CodingTestCase,
    CodingTestCaseSnapshot,
    McqOption,
    McqQuestion,
    McqQuestionSnapshot,
    Participant,
    ProgrammingLanguage,
)
from users.models import Users


class AssessmentManagementViewTests(TestCase):
    def setUp(self):
        self.faculty = Users.objects.create_user(
            email="owner@example.com",
            user_name="owner",
            password="StrongPass123!",
            is_faculty=True,
        )
        self.other_faculty = Users.objects.create_user(
            email="other@example.com",
            user_name="other",
            password="StrongPass123!",
            is_faculty=True,
        )
        self.student = Users.objects.create_user(
            email="student@example.com",
            user_name="student",
            password="StrongPass123!",
        )
        self.staff = Users.objects.create_user(
            email="staff@example.com",
            user_name="staff",
            password="StrongPass123!",
            is_staff=True,
        )
        self.language = ProgrammingLanguage.objects.create(
            name="Python",
            slug="python",
            is_active=True,
            is_judge0_executable=True,
            judge0_language_id=71,
        )
        self.assessment = Assessment.objects.create(
            created_by=self.faculty,
            name="Owner assessment",
            slug="owner-assessment",
            duration_minutes=45,
            max_attempts=1,
        )
        self.section = AssessmentSection.objects.create(
            assessment=self.assessment,
            title="Section A",
            position=1,
        )
        self.other_assessment = Assessment.objects.create(
            created_by=self.other_faculty,
            name="Other assessment",
            slug="other-assessment",
            duration_minutes=30,
            max_attempts=1,
        )
        self.other_section = AssessmentSection.objects.create(
            assessment=self.other_assessment,
            title="Other section",
            position=1,
        )
        self.mcq = McqQuestion.objects.create(
            owner=self.faculty,
            title="Owned MCQ",
            slug="owned-mcq",
            question_type=McqQuestion.QuestionType.REGULAR,
            category=McqQuestion.Category.QUANT,
            topic="Arithmetic",
            difficulty=McqQuestion.Difficulty.EASY,
            statement="What is 2 + 2?",
        )
        self.other_mcq = McqQuestion.objects.create(
            owner=self.other_faculty,
            title="Other MCQ",
            slug="other-mcq",
            question_type=McqQuestion.QuestionType.REGULAR,
            category=McqQuestion.Category.QUANT,
            topic="Arithmetic",
            difficulty=McqQuestion.Difficulty.EASY,
            statement="What is 3 + 3?",
        )
        self.coding = CodingQuestion.objects.create(
            owner=self.faculty,
            title="Owned coding question",
            slug="owned-coding-question",
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic="Strings",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="Reverse text.",
        )

    def _login(self, user=None):
        self.client.force_login(user or self.faculty)

    def _assessment_payload(self, **overrides):
        now = timezone.now()
        payload = {
            "name": "New assessment",
            "slug": "",
            "description": "Assessment description",
            "start_time": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
            "end_time": (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_minutes": "60",
            "passing_marks": "0",
            "status": Assessment.Status.DRAFT,
            "max_attempts": "1",
            "result_release_policy": Assessment.ResultReleasePolicy.AFTER_END,
            "results_release_at": "",
        }
        payload.update(overrides)
        return payload

    def _mcq_payload(self, **overrides):
        payload = {
            "title": "New MCQ",
            "slug": "",
            "question_type": McqQuestion.QuestionType.REGULAR,
            "category": McqQuestion.Category.QUANT,
            "topic": "Arithmetic",
            "sub_topic": "Addition",
            "difficulty": McqQuestion.Difficulty.EASY,
            "statement": "What is 1 + 1?",
            "programming_language": "",
            "explanation": "Add the numbers.",
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        }
        for index in range(2):
            payload[f"form-{index}-text"] = f"Option {index + 1}"
            payload[f"form-{index}-is_correct"] = "on" if index == 0 else ""
        payload.update(overrides)
        return payload

    def _coding_payload(self, **overrides):
        payload = {
            "title": "New coding question",
            "slug": "",
            "coding_mode": CodingQuestion.CodingMode.SCRATCH,
            "topic": "Strings",
            "subtopic": "Basics",
            "difficulty": CodingQuestion.Difficulty.EASY,
            "statement": "Reverse a string.",
            "input_format": "A string",
            "output_format": "The reversed string",
            "constraints_text": "",
            "explanation": "",
            "time_limit_seconds": "2",
            "memory_limit_kb": "262144",
            "is_active": "on",
            "languages-TOTAL_FORMS": "1",
            "languages-INITIAL_FORMS": "0",
            "languages-MIN_NUM_FORMS": "0",
            "languages-MAX_NUM_FORMS": "1000",
            "languages-0-language": str(self.language.pk),
            "languages-0-starter_code": "",
            "languages-0-buggy_code": "",
            "test-cases-TOTAL_FORMS": "1",
            "test-cases-INITIAL_FORMS": "0",
            "test-cases-MIN_NUM_FORMS": "0",
            "test-cases-MAX_NUM_FORMS": "1000",
            "test-cases-0-input_data": "abc",
            "test-cases-0-expected_output": "cba",
            "test-cases-0-is_sample": "on",
            "test-cases-0-weight": "1",
            "test-cases-0-position": "1",
            "test-cases-0-explanation": "Simple sample",
        }
        payload.update(overrides)
        return payload

    def test_coding_question_form_starts_with_supported_languages_and_test_case(self):
        self._login()
        response = self.client.get(reverse("assessment:coding_question_create"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context["language_formset"].forms),
            ProgrammingLanguage.objects.filter(
                is_active=True,
                is_judge0_executable=True,
            ).count(),
        )
        self.assertEqual(len(response.context["test_case_formset"].forms), 1)
        self.assertContains(response, "Add other language")
        self.assertContains(response, "Add test case")
        self.assertContains(response, "Write From Scratch")
        self.assertContains(response, "Use Starter Code")
        self.assertContains(response, "Fix the Bug")
        self.assertContains(response, "Python")
        self.assertIn("coding_mode", [field.name for field in response.context["form"].visible_fields()])
        self.assertEqual(
            [form["language"].value() for form in response.context["language_formset"].forms],
            list(
                ProgrammingLanguage.objects.filter(
                    is_active=True,
                    is_judge0_executable=True,
                ).order_by("name").values_list("pk", flat=True)
            ),
        )
        self.assertNotIn("DELETE", response.context["language_formset"].forms[0].fields)
        self.assertNotIn("DELETE", response.context["test_case_formset"].forms[0].fields)

    def test_mcq_create_form_shows_requested_fields_and_two_options(self):
        self._login()
        response = self.client.get(reverse("assessment:mcq_question_create"))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(
            [field.name for field in form.visible_fields()],
            [
                "title",
                "question_type",
                "category",
                "topic",
                "sub_topic",
                "difficulty",
                "statement",
                "programming_language",
                "explanation",
                "allow_multiple",
            ],
        )
        self.assertEqual([field.name for field in form.hidden_fields()], ["slug"])
        self.assertTrue(form.fields["sub_topic"].required)
        self.assertFalse(form.fields["programming_language"].required)
        self.assertIn(
            "Required only for Programming MCQs.",
            form.fields["programming_language"].help_text,
        )
        self.assertEqual(form["difficulty"].value(), McqQuestion.Difficulty.EASY)
        option_formset = response.context["option_formset"]
        self.assertEqual(len(option_formset.forms), 2)
        self.assertNotIn("position", option_formset.forms[0].fields)
        self.assertNotIn("DELETE", option_formset.forms[0].fields)
        self.assertContains(response, "Add option")
        self.assertContains(response, "data-mcq-programming-language")

    def test_multi_answer_mcq_allows_multiple_correct_options(self):
        self._login()
        payload = self._mcq_payload(allow_multiple="on")
        payload["form-1-is_correct"] = "on"
        response = self.client.post(
            reverse("assessment:mcq_question_create"),
            payload,
        )

        self.assertRedirects(response, reverse("assessment:question_bank"))
        question = McqQuestion.objects.get(slug="new-mcq")
        self.assertTrue(question.allow_multiple)
        self.assertEqual(question.options.filter(is_correct=True).count(), 2)

    def test_assessment_leaderboard_uses_best_finalized_attempt_and_shows_details(self):
        self._login()
        owner_participant = Participant.objects.create(
            assessment=self.assessment,
            user=self.faculty,
        )
        student_participant = Participant.objects.create(
            assessment=self.assessment,
            user=self.student,
        )

        def create_result(participant, number, score, correct_count, elapsed, status):
            attempt = Attempt.objects.create(
                participant=participant,
                attempt_number=number,
                status=status,
            )
            submitted_at = timezone.now()
            Attempt.objects.filter(pk=attempt.pk).update(
                started_at=submitted_at - timedelta(seconds=elapsed),
                submitted_at=submitted_at,
            )
            attempt.refresh_from_db()
            if status == Attempt.Status.SUBMITTED:
                return AssessmentResult.objects.create(
                    attempt=attempt,
                    assessment=self.assessment,
                    total_score=score,
                    max_score=10,
                    correct_count=correct_count,
                    evaluation_status=AssessmentResult.EvaluationStatus.FINALIZED,
                )
            return None

        create_result(
            owner_participant,
            1,
            8,
            3,
            90,
            Attempt.Status.SUBMITTED,
        )
        best_owner_result = create_result(
            owner_participant,
            2,
            9,
            4,
            240,
            Attempt.Status.SUBMITTED,
        )
        version = AssessmentVersion.objects.create(
            assessment=self.assessment,
            version_number=1,
            name=self.assessment.name,
            duration_minutes=45,
            max_attempts=1,
            result_release_policy=AssessmentVersion.ResultReleasePolicy.AFTER_END,
        )
        section_snapshot = AssessmentSectionSnapshot.objects.create(
            version=version,
            title="Section A",
            position=1,
        )
        coding_snapshot = CodingQuestionSnapshot.objects.create(
            version=version,
            title="Snapshot coding question",
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic="Strings",
            subtopic="Basics",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="Reverse a string.",
            time_limit_seconds=2,
            memory_limit_kb=262144,
        )
        question_snapshot = AssessmentQuestionSnapshot.objects.create(
            section=section_snapshot,
            coding_snapshot=coding_snapshot,
            position=1,
            max_score=10,
        )
        AssessmentSubmission.objects.create(
            attempt=best_owner_result.attempt,
            assessment_question_snapshot=question_snapshot,
            language=self.language,
            source_code="print('test')",
            status=AssessmentSubmission.Status.ACCEPTED,
            score=10,
        )
        create_result(
            student_participant,
            1,
            9,
            3,
            180,
            Attempt.Status.SUBMITTED,
        )
        create_result(
            student_participant,
            2,
            10,
            5,
            20,
            Attempt.Status.IN_PROGRESS,
        )

        response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {"tab": "leaderboard"},
        )
        self.assertEqual(response.status_code, 200)
        leaderboard = response.context["leaderboard"]
        self.assertEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0]["user"], self.student)
        self.assertEqual(leaderboard[0]["rank"], 1)
        self.assertEqual(leaderboard[1]["result"], best_owner_result)
        self.assertEqual(leaderboard[1]["rank"], 2)
        self.assertEqual(
            leaderboard[1]["profile_url"],
            reverse("users:profile", args=[self.faculty.user_name]),
        )

        detail_response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {
                "tab": "leaderboard",
                "user": str(self.faculty.pk),
            },
        )
        self.assertEqual(
            detail_response.context["selected_participant"]["rank"],
            2,
        )
        self.assertContains(detail_response, "Results for Owner assessment only")
        self.assertContains(detail_response, "Submissions")
        self.assertContains(detail_response, "4")

        submissions_response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {
                "tab": "leaderboard",
                "user": str(self.faculty.pk),
                "participant_tab": "submissions",
            },
        )
        self.assertContains(
            submissions_response,
            "Snapshot coding question",
        )

    def test_submissions_tab_lists_coding_and_mcq_and_shows_question_history(self):
        self._login()
        participant = Participant.objects.create(
            assessment=self.assessment,
            user=self.student,
        )
        version = AssessmentVersion.objects.create(
            assessment=self.assessment,
            version_number=1,
            name=self.assessment.name,
            duration_minutes=45,
            max_attempts=1,
            result_release_policy=AssessmentVersion.ResultReleasePolicy.AFTER_END,
        )
        section_snapshot = AssessmentSectionSnapshot.objects.create(
            version=version,
            title="Section A",
            position=1,
        )
        coding_snapshot = CodingQuestionSnapshot.objects.create(
            version=version,
            title="Even or odd",
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic="Basics",
            subtopic="",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="Determine whether a number is even or odd.",
            time_limit_seconds=2,
            memory_limit_kb=262144,
        )
        coding_question_snapshot = AssessmentQuestionSnapshot.objects.create(
            section=section_snapshot,
            coding_snapshot=coding_snapshot,
            position=1,
            max_score=10,
        )
        mcq_snapshot = McqQuestionSnapshot.objects.create(
            version=version,
            title="Who is the author?",
            question_type=McqQuestion.QuestionType.REGULAR,
            category=McqQuestion.Category.VERBAL,
            topic="Literature",
            difficulty=McqQuestion.Difficulty.EASY,
            statement="Choose the author.",
        )
        mcq_question_snapshot = AssessmentQuestionSnapshot.objects.create(
            section=section_snapshot,
            mcq_snapshot=mcq_snapshot,
            position=2,
            max_score=5,
        )
        first_attempt = Attempt.objects.create(
            participant=participant,
            attempt_number=1,
            status=Attempt.Status.SUBMITTED,
        )
        second_attempt = Attempt.objects.create(
            participant=participant,
            attempt_number=2,
            status=Attempt.Status.SUBMITTED,
        )
        first_coding_submission = AssessmentSubmission.objects.create(
            attempt=first_attempt,
            assessment_question_snapshot=coding_question_snapshot,
            language=self.language,
            source_code="print('first try')",
            status=AssessmentSubmission.Status.WRONG_ANSWER,
        )
        AssessmentSubmission.objects.create(
            attempt=second_attempt,
            assessment_question_snapshot=coding_question_snapshot,
            language=self.language,
            source_code="print('second try')",
            status=AssessmentSubmission.Status.ACCEPTED,
        )
        mcq_answer = AttemptAnswer.objects.create(
            attempt=second_attempt,
            assessment_question_snapshot=mcq_question_snapshot,
            text_answer="William Shakespeare",
            is_correct=False,
        )

        response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {"tab": "submissions"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["submission_rows"]), 3)
        self.assertContains(response, "Even or odd")
        self.assertContains(response, "Who is the author?")
        self.assertContains(response, "Wrong Answer")

        coding_detail = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {
                "tab": "submissions",
                "submission": f"coding-{first_coding_submission.pk}",
            },
        )
        self.assertContains(coding_detail, "print(&#x27;first try&#x27;)")
        self.assertEqual(len(coding_detail.context["submission_history"]), 2)

        mcq_detail = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {"tab": "submissions", "submission": f"answer-{mcq_answer.pk}"},
        )
        self.assertContains(mcq_detail, "William Shakespeare")

    def test_management_endpoints_require_login_and_authorized_role(self):
        protected_urls = [
            reverse("assessment:dashboard"),
            reverse("assessment:assessment_create"),
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            reverse("assessment:assessment_edit", args=[self.assessment.pk]),
            reverse("assessment:section_create", args=[self.assessment.pk]),
            reverse(
                "assessment:section_edit",
                args=[self.assessment.pk, self.section.pk],
            ),
            reverse(
                "assessment:section_question_add",
                args=[self.assessment.pk, self.section.pk],
            ),
            reverse("assessment:question_bank"),
            reverse("assessment:mcq_question_create"),
            reverse("assessment:mcq_question_edit", args=[self.mcq.pk]),
            reverse("assessment:coding_question_create"),
            reverse("assessment:coding_question_edit", args=[self.coding.pk]),
        ]
        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith("/accounts/login/?next="))

        self._login(self.student)
        role_only_urls = {
            reverse("assessment:dashboard"),
            reverse("assessment:assessment_create"),
            reverse("assessment:question_bank"),
            reverse("assessment:mcq_question_create"),
            reverse("assessment:coding_question_create"),
        }
        for url in protected_urls:
            with self.subTest(url=url):
                expected = 403 if url in role_only_urls else 404
                self.assertEqual(self.client.get(url).status_code, expected)

        post_only_urls = [
            reverse("assessment:assessment_delete", args=[self.assessment.pk]),
            reverse(
                "assessment:section_delete",
                args=[self.assessment.pk, self.section.pk],
            ),
            reverse(
                "assessment:section_question_remove",
                args=[self.assessment.pk, self.section.pk, 999999],
            ),
        ]
        for url in post_only_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 404)

    def test_owner_and_assessment_moderator_can_manage_assessment(self):
        self._login()
        urls = [
            reverse("assessment:dashboard"),
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            reverse("assessment:assessment_edit", args=[self.assessment.pk]),
            reverse("assessment:section_create", args=[self.assessment.pk]),
            reverse(
                "assessment:section_edit",
                args=[self.assessment.pk, self.section.pk],
            ),
            reverse(
                "assessment:section_question_add",
                args=[self.assessment.pk, self.section.pk],
            ),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

        AssessmentModerator.objects.create(
            assessment=self.assessment,
            user=self.student,
        )
        self._login(self.student)
        self.assertEqual(self.client.get(reverse("assessment:dashboard")).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("assessment:assessment_detail", args=[self.assessment.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("assessment:section_edit", args=[self.assessment.pk, self.section.pk])
            ).status_code,
            200,
        )

    def test_staff_can_manage_other_users_assessments_and_questions(self):
        self._login(self.staff)
        self.assertEqual(
            self.client.get(
                reverse("assessment:assessment_detail", args=[self.assessment.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("assessment:mcq_question_edit", args=[self.mcq.pk])
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("assessment:question_bank")).status_code, 200)

    def test_foreign_assessments_and_sections_are_not_accessible(self):
        self._login()
        for url in (
            reverse("assessment:assessment_detail", args=[self.other_assessment.pk]),
            reverse("assessment:assessment_edit", args=[self.other_assessment.pk]),
            reverse(
                "assessment:section_edit",
                args=[self.other_assessment.pk, self.other_section.pk],
            ),
            reverse(
                "assessment:section_edit",
                args=[self.assessment.pk, self.other_section.pk],
            ),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_owner_can_block_remove_and_restore_assessment_participants(self):
        self._login()
        participant = Participant.objects.create(
            assessment=self.assessment,
            user=self.student,
        )
        detail_response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {"tab": "participants"},
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Signups")
        self.assertContains(detail_response, "student")

        for action, expected_status in (
            ("block", Participant.Status.DISQUALIFIED),
            ("restore", Participant.Status.REGISTERED),
            ("remove", Participant.Status.REMOVED),
        ):
            response = self.client.post(
                reverse(
                    "assessment:assessment_participant_action",
                    args=[self.assessment.pk, participant.pk, action],
                )
            )
            self.assertRedirects(
                response,
                f"{reverse('assessment:assessment_detail', args=[self.assessment.pk])}?tab=participants",
            )
            participant.refresh_from_db()
            self.assertEqual(participant.status, expected_status)

    def test_faculty_can_grant_attempts_and_student_can_use_them(self):
        participant = Participant.objects.create(
            assessment=self.assessment,
            user=self.student,
        )
        self.assessment.status = Assessment.Status.PUBLISHED
        self.assessment.save(update_fields=["status"])
        version = AssessmentVersion.objects.create(
            assessment=self.assessment,
            version_number=1,
            status=AssessmentVersion.Status.PUBLISHED,
            is_current=True,
            name=self.assessment.name,
            duration_minutes=45,
            max_attempts=1,
            result_release_policy=AssessmentVersion.ResultReleasePolicy.IMMEDIATE,
        )
        self._login()
        self.assertEqual(
            self.client.post(
                reverse(
                    "assessment:assessment_participant_action",
                    args=[self.assessment.pk, participant.pk, "grant_attempts"],
                ),
                {"extra_attempts": "1", "reason": "Approved by faculty"},
            ).status_code,
            302,
        )
        authorization = AttemptAuthorization.objects.get(participant=participant)
        self.assertEqual(authorization.authorized_by, self.faculty)
        self.assertEqual(authorization.extra_attempts, 1)
        signup_response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {"tab": "participants", "q": "student"},
        )
        self.assertContains(signup_response, "student@example.com")
        self.assertContains(signup_response, "0 / 2")

        self.client.force_login(self.student)
        start_url = reverse(
            "assessment:start_attempt",
            args=[self.assessment.slug],
        )
        first_session = uuid.uuid4()
        response = self.client.post(
            start_url,
            data=json.dumps({"session_id": str(first_session)}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        first_attempt = Attempt.objects.get(participant=participant)
        first_attempt.status = Attempt.Status.SUBMITTED
        first_attempt.save(update_fields=["status"])

        duplicate_response = self.client.post(
            start_url,
            data=json.dumps({"session_id": str(first_session)}),
            content_type="application/json",
        )
        self.assertEqual(duplicate_response.status_code, 409)

        second_response = self.client.post(
            start_url,
            data=json.dumps({"session_id": str(uuid.uuid4())}),
            content_type="application/json",
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            Attempt.objects.filter(participant=participant).count(),
            2,
        )
        self.assertEqual(version.status, AssessmentVersion.Status.PUBLISHED)

    def test_faculty_restart_preserves_and_cancels_active_attempt(self):
        participant = Participant.objects.create(
            assessment=self.assessment,
            user=self.student,
        )
        attempt = Attempt.objects.create(
            participant=participant,
            attempt_number=1,
            status=Attempt.Status.IN_PROGRESS,
        )
        previous_session_id = attempt.active_session_id
        self._login()

        response = self.client.post(
            reverse(
                "assessment:assessment_participant_action",
                args=[self.assessment.pk, participant.pk, "restart"],
            ),
            {"reason": "Connectivity issue"},
        )

        self.assertEqual(response.status_code, 302)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, Attempt.Status.CANCELLED)
        self.assertNotEqual(attempt.active_session_id, previous_session_id)
        self.assertEqual(Attempt.objects.filter(participant=participant).count(), 1)
        self.assertEqual(
            AttemptAuthorization.objects.get(participant=participant).extra_attempts,
            1,
        )
        self.assertTrue(
            AttemptEvent.objects.filter(
                attempt=attempt,
                event_type=AttemptEvent.EventType.RESTARTED,
            ).exists()
        )

    def test_assessment_create_edit_and_invalid_form(self):
        self._login()
        create_response = self.client.post(
            reverse("assessment:assessment_create"),
            self._assessment_payload(status=Assessment.Status.PUBLISHED),
        )
        created = Assessment.objects.get(slug="new-assessment")
        self.assertRedirects(
            create_response,
            reverse("assessment:assessment_detail", args=[created.pk]),
        )
        self.assertEqual(created.created_by, self.faculty)
        self.assertEqual(created.status, Assessment.Status.DRAFT)
        self.assertTrue(any(get_messages(create_response.wsgi_request)))

        detail_response = self.client.get(
            reverse("assessment:assessment_detail", args=[created.pk]),
        )
        self.assertContains(detail_response, "Hosted assessment:")
        self.assertContains(detail_response, "Publish assessment")
        self.assertContains(detail_response, "/assessments/new-assessment/view/")

        invalid = self.client.post(
            reverse("assessment:assessment_create"),
            self._assessment_payload(duration_minutes="0"),
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, "Duration must be at least 1 minute.")
        self.assertEqual(Assessment.objects.filter(name="New assessment").count(), 1)

        edit_response = self.client.post(
            reverse("assessment:assessment_edit", args=[created.pk]),
            self._assessment_payload(name="Updated name", slug=created.slug),
        )
        self.assertRedirects(
            edit_response,
            reverse("assessment:assessment_detail", args=[created.pk]),
        )
        created.refresh_from_db()
        self.assertEqual(created.name, "Updated name")

    def test_assessment_status_cannot_be_published_through_settings_form(self):
        self._login()
        response = self.client.post(
            reverse("assessment:assessment_edit", args=[self.assessment.pk]),
            self._assessment_payload(
                name=self.assessment.name,
                slug=self.assessment.slug,
                status=Assessment.Status.PUBLISHED,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Use the Publish assessment action")
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, Assessment.Status.DRAFT)

    def test_publish_creates_current_immutable_assessment_version(self):
        self._login()
        McqOption.objects.create(
            question=self.mcq,
            text="Four",
            is_correct=True,
            position=1,
        )
        McqOption.objects.create(
            question=self.mcq,
            text="Five",
            is_correct=False,
            position=2,
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            section=self.section,
            mcq_question=self.mcq,
            position=1,
            max_score=10,
        )
        CodingQuestionLanguage.objects.create(
            question=self.coding,
            language=self.language,
            starter_code="print('ready')",
        )
        CodingTestCase.objects.create(
            question=self.coding,
            input_data="",
            expected_output="ready",
            is_sample=True,
            position=1,
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            section=self.section,
            coding_question=self.coding,
            position=2,
            max_score=5,
        )

        response = self.client.post(
            reverse("assessment:assessment_publish", args=[self.assessment.pk]),
        )

        self.assertRedirects(
            response,
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
        )
        version = AssessmentVersion.objects.get(assessment=self.assessment)
        self.assertEqual(version.status, AssessmentVersion.Status.PUBLISHED)
        self.assertTrue(version.is_current)
        self.assertEqual(version.published_by, self.faculty)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, Assessment.Status.PUBLISHED)
        section_snapshot = AssessmentSectionSnapshot.objects.get(version=version)
        question_snapshot = AssessmentQuestionSnapshot.objects.get(
            section=section_snapshot,
            mcq_snapshot__isnull=False,
        )
        self.assertEqual(question_snapshot.mcq_snapshot.title, self.mcq.title)
        self.assertEqual(question_snapshot.mcq_snapshot.options.count(), 2)
        coding_snapshot = CodingQuestionSnapshot.objects.get(version=version)
        language_snapshot = CodingQuestionLanguageSnapshot.objects.get(
            question=coding_snapshot
        )
        test_case_snapshot = CodingTestCaseSnapshot.objects.get(
            question=coding_snapshot
        )
        self.assertEqual(language_snapshot.language_slug, self.language.slug)
        self.assertEqual(language_snapshot.starter_code, "print('ready')")
        self.assertEqual(test_case_snapshot.expected_output, "ready")

    def test_publish_requires_a_question_in_every_section(self):
        self._login()
        response = self.client.post(
            reverse("assessment:assessment_publish", args=[self.assessment.pk]),
        )

        self.assertRedirects(
            response,
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
        )
        self.assertEqual(
            AssessmentVersion.objects.filter(assessment=self.assessment).count(),
            0,
        )
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.status, Assessment.Status.DRAFT)
        self.assertTrue(any(get_messages(response.wsgi_request)))

    def test_section_create_edit_delete_and_post_only_delete(self):
        self._login()
        create_url = reverse("assessment:section_create", args=[self.assessment.pk])
        response = self.client.post(
            create_url,
            {"title": "Section B", "instructions": "Instructions", "position": "2", "time_limit_minutes": ""},
        )
        self.assertRedirects(
            response,
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
        )
        section = AssessmentSection.objects.get(assessment=self.assessment, title="Section B")

        edit_url = reverse("assessment:section_edit", args=[self.assessment.pk, section.pk])
        response = self.client.post(
            edit_url,
            {"title": "Renamed section", "instructions": "", "position": "2", "time_limit_minutes": "15"},
        )
        self.assertRedirects(response, reverse("assessment:assessment_detail", args=[self.assessment.pk]))
        section.refresh_from_db()
        self.assertEqual(section.title, "Renamed section")

        delete_url = reverse("assessment:section_delete", args=[self.assessment.pk, section.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 405)
        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse("assessment:assessment_detail", args=[self.assessment.pk]))
        self.assertFalse(AssessmentSection.objects.filter(pk=section.pk).exists())

    def test_assessment_delete_is_post_only_and_requires_access(self):
        self._login()
        url = reverse("assessment:assessment_delete", args=[self.assessment.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("assessment:dashboard"))

        self._login(self.other_faculty)
        self.assertEqual(
            self.client.post(
                reverse("assessment:assessment_delete", args=[self.assessment.pk])
            ).status_code,
            404,
        )

    def test_question_bank_is_owner_scoped_and_edit_is_owner_scoped(self):
        self._login()
        response = self.client.get(reverse("assessment:question_bank"))
        self.assertContains(response, self.mcq.title)
        self.assertNotContains(response, self.other_mcq.title)
        self.assertEqual(
            self.client.get(
                reverse("assessment:mcq_question_edit", args=[self.other_mcq.pk])
            ).status_code,
            404,
        )

        assignment_form = AssessmentQuestionForm(
            assessment=self.assessment,
            section=self.section,
            user=self.faculty,
        )
        self.assertIn(self.mcq, assignment_form.fields["mcq_question"].queryset)
        self.assertNotIn(self.other_mcq, assignment_form.fields["mcq_question"].queryset)

    def test_mcq_create_and_edit_save_options_and_reject_invalid_formsets(self):
        self._login()
        response = self.client.post(
            reverse("assessment:mcq_question_create"),
            self._mcq_payload(),
        )
        question = McqQuestion.objects.get(slug="new-mcq")
        self.assertRedirects(response, reverse("assessment:question_bank"))
        self.assertEqual(question.owner, self.faculty)
        self.assertEqual(question.options.count(), 2)
        self.assertEqual(question.options.filter(is_correct=True).count(), 1)

        edit_payload = self._mcq_payload(title=question.title, slug=question.slug)
        existing_options = list(question.options.order_by("position"))
        edit_payload["form-INITIAL_FORMS"] = "2"
        edit_payload["form-0-id"] = str(existing_options[0].pk)
        edit_payload["form-1-id"] = str(existing_options[1].pk)
        response = self.client.post(
            reverse("assessment:mcq_question_edit", args=[question.pk]),
            edit_payload,
        )
        self.assertRedirects(response, reverse("assessment:question_bank"))

        invalid_payload = self._mcq_payload()
        for index in range(4):
            invalid_payload[f"form-{index}-text"] = ""
            invalid_payload[f"form-{index}-is_correct"] = ""
        response = self.client.post(
            reverse("assessment:mcq_question_create"),
            invalid_payload,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "At least two non-empty options are required.")
        self.assertEqual(McqQuestion.objects.filter(title="New MCQ").count(), 1)

    def test_coding_question_create_and_edit_save_nested_records(self):
        self._login()
        response = self.client.post(
            reverse("assessment:coding_question_create"),
            self._coding_payload(),
        )
        self.assertEqual(
            response.status_code,
            302,
            (
                f"form={response.context['form'].errors}; "
                f"languages={response.context['language_formset'].errors}; "
                f"language non-form={response.context['language_formset'].non_form_errors()}; "
                f"cases={response.context['test_case_formset'].errors}; "
                f"case non-form={response.context['test_case_formset'].non_form_errors()}"
            )
            if response.status_code == 200
            else response.url,
        )
        self.assertRedirects(response, reverse("assessment:question_bank"))
        question = CodingQuestion.objects.get(slug="new-coding-question")
        self.assertEqual(question.owner, self.faculty)
        self.assertEqual(question.supported_languages.count(), 1)
        self.assertEqual(question.test_cases.count(), 1)

        edit_payload = self._coding_payload(title=question.title, slug=question.slug)
        language = question.supported_languages.get()
        case = question.test_cases.get()
        edit_payload.update(
            {
                "languages-TOTAL_FORMS": "1",
                "languages-INITIAL_FORMS": "1",
                "languages-0-id": str(language.pk),
                "languages-0-language": str(language.language_id),
                "languages-0-starter_code": "def solve():\n    return None",
                "languages-0-buggy_code": "",
                "test-cases-TOTAL_FORMS": "1",
                "test-cases-INITIAL_FORMS": "1",
                "test-cases-0-id": str(case.pk),
                "test-cases-0-input_data": "abc",
                "test-cases-0-expected_output": "cba",
                "test-cases-0-is_sample": "on",
                "test-cases-0-weight": "1",
                "test-cases-0-position": "1",
                "test-cases-0-explanation": "Updated explanation",
            }
        )
        response = self.client.post(
            reverse("assessment:coding_question_edit", args=[question.pk]),
            edit_payload,
        )
        self.assertRedirects(response, reverse("assessment:question_bank"))
        self.assertEqual(question.test_cases.count(), 1)
        self.assertEqual(question.test_cases.get().explanation, "Updated explanation")

    def test_coding_question_invalid_formset_does_not_create_question(self):
        self._login()
        payload = self._coding_payload()
        payload["languages-0-language"] = ""
        response = self.client.post(reverse("assessment:coding_question_create"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "At least one supported language is required.")
        self.assertFalse(CodingQuestion.objects.filter(title="New coding question").exists())

    def test_add_question_scopes_choices_and_removal_checks_nested_ids(self):
        self._login()
        add_url = reverse(
            "assessment:section_question_add",
            args=[self.assessment.pk, self.section.pk],
        )
        response = self.client.get(add_url)
        self.assertContains(response, "Question category")
        self.assertContains(response, "data-section-question-checkbox")
        self.assertContains(response, ">Save changes</button>")
        self.assertNotContains(response, ">Add questions</button>")
        search_url = reverse(
            "assessment:section_question_search",
            args=[self.assessment.pk, self.section.pk],
        )
        suggestions = self.client.get(
            search_url,
            {"q": "Owned", "type": "mcq"},
        )
        self.assertEqual(suggestions.status_code, 200)
        self.assertEqual(
            [question["title"] for question in suggestions.json()["results"]],
            ["Owned MCQ"],
        )
        response = self.client.post(
            add_url,
            {
                "question_type": "mcq",
                "question_id": str(self.mcq.pk),
                "max_score": "5",
                "negative_marks": "0",
            },
        )
        assignment = AssessmentQuestion.objects.get(
            assessment=self.assessment,
            section=self.section,
            mcq_question=self.mcq,
        )
        self.assertRedirects(
            response,
            f"{reverse('assessment:assessment_detail', args=[self.assessment.pk])}"
            f"?tab=questions#section-{self.section.pk}",
        )

        self.assertEqual(
            self.client.post(
                reverse(
                    "assessment:section_question_remove",
                    args=[self.assessment.pk, self.section.pk, assignment.pk],
                )
            ).status_code,
            302,
        )
        self.assertFalse(AssessmentQuestion.objects.filter(pk=assignment.pk).exists())
        self.assertTrue(McqQuestion.objects.filter(pk=self.mcq.pk).exists())

    def test_section_question_bulk_add_filters_mcq_category_and_adds_all_selected(self):
        aptitude_questions = [
            McqQuestion.objects.create(
                owner=self.faculty,
                title=f"Aptitude question {index}",
                slug=f"aptitude-question-{index}",
                question_type=McqQuestion.QuestionType.REGULAR,
                category=McqQuestion.Category.APTITUDE,
                topic="Logic",
                sub_topic="Patterns",
                difficulty=McqQuestion.Difficulty.EASY,
                statement=f"Choose the right answer {index}.",
            )
            for index in range(2)
        ]
        self._login()
        add_url = reverse(
            "assessment:section_question_add",
            args=[self.assessment.pk, self.section.pk],
        )
        response = self.client.get(
            add_url,
            {"question_type": "mcq", "category": "aptitude"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["title"] for row in response.context["question_rows"]],
            ["Aptitude question 0", "Aptitude question 1"],
        )
        self.assertNotContains(response, self.mcq.title)

        response = self.client.post(
            add_url,
            {
                "bulk_add": "1",
                "question_type": "mcq",
                "category": "aptitude",
                "selected_questions": [str(question.pk) for question in aptitude_questions],
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('assessment:assessment_detail', args=[self.assessment.pk])}"
            f"?tab=questions#section-{self.section.pk}",
        )
        self.assertEqual(
            AssessmentQuestion.objects.filter(
                assessment=self.assessment,
                section=self.section,
                mcq_question__in=aptitude_questions,
            ).count(),
            2,
        )

        other_assignment = AssessmentQuestion.objects.create(
            assessment=self.other_assessment,
            section=self.other_section,
            mcq_question=self.other_mcq,
            position=1,
            max_score=5,
        )
        tampered = reverse(
            "assessment:section_question_remove",
            args=[self.assessment.pk, self.section.pk, other_assignment.pk],
        )
        self.assertEqual(self.client.get(tampered).status_code, 405)
        self.assertEqual(self.client.post(tampered).status_code, 404)
        self.assertTrue(AssessmentQuestion.objects.filter(pk=other_assignment.pk).exists())

    def test_question_assignment_rejects_unowned_question_ids_and_invalid_values(self):
        self._login()
        response = self.client.post(
            reverse(
                "assessment:section_question_add",
                args=[self.assessment.pk, self.section.pk],
            ),
            {
                "question_type": "mcq",
                "question_id": str(self.other_mcq.pk),
                "max_score": "5",
                "negative_marks": "0",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AssessmentQuestion.objects.filter(assessment=self.assessment).exists())

    def test_moderator_can_manage_assessment_but_cannot_edit_foreign_question(self):
        AssessmentModerator.objects.create(
            assessment=self.assessment,
            user=self.student,
        )
        self._login(self.student)
        self.assertEqual(
            self.client.get(
                reverse("assessment:assessment_detail", args=[self.assessment.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("assessment:mcq_question_edit", args=[self.mcq.pk])
            ).status_code,
            404,
        )

    def test_management_detail_does_not_render_coding_hidden_test_data(self):
        coding = CodingQuestion.objects.create(
            owner=self.faculty,
            title="Secret case coding question",
            slug="secret-case-coding-question",
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic="Testing",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="A coding prompt.",
        )
        CodingTestCase.objects.create(
            question=coding,
            input_data="hidden-input-value",
            expected_output="hidden-expected-value",
            position=1,
            explanation="hidden-explanation-value",
        )
        AssessmentQuestion.objects.create(
            assessment=self.assessment,
            section=self.section,
            coding_question=coding,
            position=1,
            max_score=10,
        )
        self._login()
        response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {"tab": "questions"},
        )
        self.assertContains(response, coding.title)
        self.assertNotContains(response, "hidden-input-value")
        self.assertNotContains(response, "hidden-expected-value")
        self.assertNotContains(response, "hidden-explanation-value")
