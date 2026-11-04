from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from assessment.models import (
    Assessment,
    AssessmentModerator,
    AssessmentQuestion,
    AssessmentSection,
    CodingQuestion,
    McqQuestion,
)
from users.models import Users


class AssessmentAdminFlowTests(TestCase):
    def setUp(self):
        self.owner = Users.objects.create_user(
            email="assessment-owner@example.com",
            user_name="assessment_owner",
            password="TestPassword123!",
            is_faculty=True,
        )
        self.moderator = Users.objects.create_user(
            email="assessment-moderator@example.com",
            user_name="assessment_mod",
            password="TestPassword123!",
        )
        self.assessment = Assessment.objects.create(
            created_by=self.owner,
            name="Interview assessment",
            slug="interview-assessment",
            duration_minutes=45,
        )
        self.section = AssessmentSection.objects.create(
            assessment=self.assessment,
            title="Questions",
            position=1,
        )
        self.question = CodingQuestion.objects.create(
            owner=self.owner,
            title="Reverse a string",
            slug="reverse-a-string",
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic="Strings",
            subtopic="Basics",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="Reverse the supplied string.",
        )
        self.other_question = CodingQuestion.objects.create(
            owner=self.owner,
            title="Reverse a sentence",
            slug="reverse-a-sentence",
            coding_mode=CodingQuestion.CodingMode.COMPLETE,
            topic="Strings",
            subtopic="Basics",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="Reverse the supplied sentence.",
        )
        self.mcq_question = McqQuestion.objects.create(
            owner=self.owner,
            title="Python author",
            slug="python-author",
            question_type=McqQuestion.QuestionType.REGULAR,
            category=McqQuestion.Category.PROGRAMMING,
            topic="History of Python",
            sub_topic="Author of Python",
            difficulty=McqQuestion.Difficulty.EASY,
            statement="Who is the author of Python?",
        )
        self.other_owner = Users.objects.create_user(
            email="another-assessment-owner@example.com",
            user_name="another_owner",
            password="TestPassword123!",
            is_faculty=True,
        )
        self.other_owners_question = CodingQuestion.objects.create(
            owner=self.other_owner,
            title="Another owner's question",
            slug="another-owners-question",
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic="Other topic",
            subtopic="Other subtopic",
            difficulty=CodingQuestion.Difficulty.EASY,
            statement="A question owned by another user.",
        )

    def test_dashboard_has_assessment_and_question_management_tabs(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse("assessment:dashboard"))
        self.assertContains(response, "Manage Assessments")
        self.assertContains(response, "Manage Questions")
        self.assertContains(response, self.assessment.name)
        self.assertNotContains(response, "Manage Contests")

        response = self.client.get(
            reverse("assessment:dashboard"),
            {"tab": "questions"},
        )
        self.assertContains(response, "Coding questions")
        self.assertContains(response, "Programming MCQ")
        self.assertContains(response, "Aptitude")
        self.assertContains(response, "Quant")
        self.assertContains(response, "Reasoning")
        self.assertContains(response, "Other")
        self.assertContains(response, "Add question")
        self.assertContains(response, "Create question")
        self.assertContains(response, self.question.title)
        self.assertContains(response, self.question.topic)
        self.assertContains(response, self.question.subtopic)
        self.assertNotContains(response, self.other_owners_question.title)
        self.assertContains(response, "<th>Question</th>", html=True)
        self.assertContains(response, "<th>Topic</th>", html=True)
        self.assertContains(response, "<th>Subtopic</th>", html=True)
        self.assertNotContains(response, self.mcq_question.title)

        response = self.client.get(
            reverse("assessment:dashboard"),
            {"tab": "questions", "question_group": "programming_mcq"},
        )
        self.assertContains(response, self.mcq_question.title)
        self.assertContains(response, self.mcq_question.topic)
        self.assertContains(response, self.mcq_question.sub_topic)
        self.assertNotContains(response, self.question.title)
        self.assertNotContains(response, "<th>Mode</th>", html=True)

    def test_question_bank_search_filters_live_and_keeps_owner_scope(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("assessment:question_bank_search"),
            {
                "group": "coding",
                "q": "sentence",
                "topic": "Strings",
                "subtopic": "Basics",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["title"], self.other_question.title)

        response = self.client.get(
            reverse("assessment:question_bank_search"),
            {"group": "programming_mcq"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["title"] for row in response.json()["results"]],
            [self.mcq_question.title],
        )

        response = self.client.get(
            reverse("assessment:question_bank_search"),
            {"group": "not-a-category"},
        )
        self.assertEqual(response.status_code, 400)

    def test_question_add_and_create_buttons_open_their_flows(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("assessment:question_add"))
        self.assertContains(response, "Add question to an assessment")
        response = self.client.post(
            reverse("assessment:question_add"),
            {"assessment_id": self.assessment.pk},
        )
        self.assertRedirects(
            response,
            reverse(
                "assessment:section_question_add",
                args=[self.assessment.pk, self.section.pk],
            ),
        )

        response = self.client.get(reverse("assessment:question_create"))
        self.assertContains(response, "Create MCQ question")
        self.assertContains(response, "Create coding question")

    def test_details_tab_updates_name_url_schedule_and_duration(self):
        self.client.force_login(self.owner)
        details_response = self.client.get(
            reverse("assessment:assessment_detail", args=[self.assessment.pk])
        )
        for label in ("Details", "Questions", "Moderators", "Leaderboard", "Submissions", "Reports"):
            self.assertContains(details_response, label)
        for label in ("Assessment URL", "Start time", "End time", "Duration minutes"):
            self.assertContains(details_response, label)

        start_time = timezone.now() + timedelta(days=1)
        end_time = start_time + timedelta(hours=2)
        response = self.client.post(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {
                "action": "save_details",
                "name": "Updated assessment",
                "slug": "updated-assessment",
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M"),
                "end_time": end_time.strftime("%Y-%m-%dT%H:%M"),
                "duration_minutes": "75",
            },
        )
        self.assertRedirects(
            response,
            f"{reverse('assessment:assessment_detail', args=[self.assessment.pk])}?tab=details",
        )
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.name, "Updated assessment")
        self.assertEqual(self.assessment.slug, "updated-assessment")
        self.assertEqual(self.assessment.duration_minutes, 75)
        self.assertEqual(
            self.client.get(
                reverse(
                    "assessment:assessment_detail_by_slug",
                    args=[self.assessment.slug],
                )
            ).status_code,
            200,
        )

    def test_section_question_picker_suggests_matches_and_adds_question(self):
        self.client.force_login(self.owner)
        add_tab_url = reverse("assessment:assessment_detail", args=[self.assessment.pk])
        response = self.client.get(
            reverse(
                "assessment:section_question_add",
                args=[self.assessment.pk, self.section.pk],
            )
        )
        self.assertContains(response, "Question category")
        self.assertContains(response, "data-section-question-checkbox")
        search_url = reverse(
            "assessment:section_question_search",
            args=[self.assessment.pk, self.section.pk],
        )
        response = self.client.get(
            search_url,
            {"q": "Reverse a", "type": "coding"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [question["title"] for question in response.json()["results"]],
            ["Reverse a sentence", "Reverse a string"],
        )

        response = self.client.post(
            reverse(
                "assessment:section_question_add",
                args=[self.assessment.pk, self.section.pk],
            ),
            {
                "question_type": "coding",
                "question_id": self.question.pk,
                "max_score": "5",
                "negative_marks": "0",
            },
        )
        self.assertRedirects(
            response,
            f"{add_tab_url}?tab=questions#section-{self.section.pk}",
        )
        assignment = AssessmentQuestion.objects.get(
            assessment=self.assessment,
            coding_question=self.question,
        )
        self.assertEqual(assignment.section, self.section)
        detail_response = self.client.get(add_tab_url, {"tab": "questions"})
        self.assertEqual(detail_response.context["question_count"], 1)
        self.assertContains(detail_response, "Questions")
        self.assertContains(detail_response, "assessment-question-count")
        self.assertContains(
            detail_response,
            reverse(
                "assessment:section_question_add",
                args=[self.assessment.pk, self.section.pk],
            ),
        )
        self.assertContains(detail_response, "Add question")
        self.assertContains(detail_response, self.question.title)
        self.assertContains(detail_response, "assessment-section-collapse")
        self.assertNotContains(detail_response, "Import in bulk")
        self.assertContains(detail_response, "Preview")
        self.assertContains(detail_response, "Remove")
        unavailable = self.client.get(
            search_url,
            {"q": self.question.title, "type": "coding"},
        )
        self.assertEqual(unavailable.json()["results"], [])

    def test_question_add_creates_default_section_when_needed(self):
        assessment = Assessment.objects.create(
            created_by=self.owner,
            name="No sections yet",
            slug="no-sections-yet",
            duration_minutes=30,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("assessment:assessment_question_add", args=[assessment.pk]),
            {
                "question_type": "coding",
                "question_id": self.question.pk,
                "max_score": "1",
                "negative_marks": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            AssessmentSection.objects.get(assessment=assessment).title,
            "Questions",
        )
        self.assertTrue(
            AssessmentQuestion.objects.filter(
                assessment=assessment,
                coding_question=self.question,
            ).exists()
        )

    def test_owner_can_assign_and_moderator_can_manage_assessment(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("assessment:moderator_search", args=[self.assessment.pk]),
            {"q": "assessment_mod"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["user_name"], "assessment_mod")

        response = self.client.post(
            reverse("assessment:moderator_add", args=[self.assessment.pk]),
            {"user_id": self.moderator.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AssessmentModerator.objects.filter(
                assessment=self.assessment,
                user=self.moderator,
            ).exists()
        )

        self.client.force_login(self.moderator)
        self.assertEqual(
            self.client.get(
                reverse("assessment:assessment_detail", args=[self.assessment.pk])
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse("assessment:assessment_detail", args=[self.assessment.pk]),
            {
                "action": "save_details",
                "name": "Edited by moderator",
                "slug": self.assessment.slug,
                "start_time": "",
                "end_time": "",
                "duration_minutes": "50",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assessment.refresh_from_db()
        self.assertEqual(self.assessment.name, "Edited by moderator")
        create_options = self.client.get(
            reverse("assessment:question_create_options", args=[self.assessment.pk])
        )
        self.assertEqual(create_options.status_code, 200)
        self.assertContains(create_options, "Create MCQ")
        self.assertContains(create_options, "Create coding question")
