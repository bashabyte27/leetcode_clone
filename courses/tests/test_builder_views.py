import json

from django.test import TestCase
from django.urls import reverse

from courses.models import Course, LessonStep, Module, StepHint, StepQuestion

from .factories import (
    make_coding_question, make_course, make_lesson, make_mcq, make_module, make_outcome, make_step, make_user,
)


class BuilderTestCase(TestCase):
    def setUp(self):
        self.staff = make_user(staff=True)
        self.client.force_login(self.staff)
        self.course = make_course("Core Python")
        self.module = make_module(self.course, 1, title="Foundations")
        self.lesson = make_lesson(self.module, 1, title="Variables")
        self.outcome = make_outcome(self.lesson)

    def url(self, name, *args):
        return reverse(f"course_builder:{name}", args=args)


class PermissionTests(BuilderTestCase):
    def test_anonymous_and_students_are_kept_out(self):
        pages = [self.url("course_list"), self.url("course", self.course.pk),
                 self.url("lesson", self.lesson.pk), self.url("search")]
        self.client.logout()
        for page in pages:
            with self.subTest(page=page, who="anonymous"):
                self.assertEqual(self.client.get(page).status_code, 302)
        self.client.force_login(make_user())
        for page in pages:
            with self.subTest(page=page, who="student"):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/users/login/", response.url)
        response = self.client.post(self.url("module_create", self.course.pk), {"title": "Sneaky"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Module.objects.filter(title="Sneaky").exists())


class PageTests(BuilderTestCase):
    def test_every_builder_page_renders(self):
        step = make_step(self.lesson, "TEXT", content={"markdown": "# Hi", "callouts": []})
        for page in (self.url("course_list"), self.url("course_create"), self.url("course", self.course.pk),
                     self.url("course_publish", self.course.pk), self.url("module", self.module.pk),
                     self.url("lesson", self.lesson.pk), self.url("lesson_preview", self.lesson.pk),
                     self.url("step", step.pk)):
            with self.subTest(page=page):
                self.assertEqual(self.client.get(page).status_code, 200)

    def test_course_page_query_count_is_flat(self):
        for pos in range(2, 9):
            make_lesson(make_module(self.course, pos), 1)
        with self.assertNumQueries(7):
            self.client.get(self.url("course", self.course.pk))

    def test_lesson_page_query_count_does_not_grow_with_steps(self):
        for pos in range(1, 4):
            make_step(self.lesson, "QUIZ", position=pos)
        self.client.get(self.url("lesson", self.lesson.pk))  # warm caches
        with self.assertNumQueries(7):
            self.client.get(self.url("lesson", self.lesson.pk))
        for pos in range(4, 9):
            make_step(self.lesson, "CODING", position=pos)
        with self.assertNumQueries(7):
            self.client.get(self.url("lesson", self.lesson.pk))


class StructureEditingTests(BuilderTestCase):
    def test_create_course_then_module_then_lesson(self):
        response = self.client.post(self.url("course_create"), {
            "category": self.course.category.pk, "title": "Data Analytics", "level": "beginner",
            "est_weeks": 8, "access": "premium",
        })
        course = Course.objects.get(title="Data Analytics")
        self.assertRedirects(response, self.url("course", course.pk))
        self.assertEqual(course.created_by, self.staff)

        self.client.post(self.url("module_create", course.pk), {"title": "Pandas Basics"})
        module = course.modules.get()
        self.assertEqual((module.position, module.slug), (1, "pandas-basics"))
        self.client.post(self.url("lesson_create", module.pk), {"title": "Series"})
        self.assertEqual(module.lessons.get().position, 1)

    def test_reorder_and_delete_renumber(self):
        lessons = [self.lesson] + [make_lesson(self.module, p) for p in (2, 3)]
        order = [lessons[2].pk, lessons[0].pk, lessons[1].pk]
        response = self.client.post(self.url("reorder", "lessons", self.module.pk),
                                    data=json.dumps({"ids": order}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(self.module.lessons.order_by("position").values_list("pk", flat=True)), order)

        self.client.post(self.url("lesson_delete", lessons[0].pk))
        self.assertEqual(list(self.module.lessons.order_by("position").values_list("position", flat=True)), [1, 2])

    def test_reorder_rejects_incomplete_or_foreign_ids(self):
        other = make_lesson(make_module(self.course, 2), 1)
        response = self.client.post(self.url("reorder", "lessons", self.module.pk),
                                    data=json.dumps({"ids": [self.lesson.pk, other.pk]}), content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_outcome_add_and_remove(self):
        self.client.post(self.url("outcome_create", self.module.pk),
                         {"code": "PY-M1-L1-O9", "text": "Swap two variables", "lesson": self.lesson.pk})
        added = self.module.outcomes.get(code="PY-M1-L1-O9")
        self.client.post(self.url("outcome_delete", added.pk))
        self.assertFalse(self.module.outcomes.filter(code="PY-M1-L1-O9").exists())


class StepEditorTests(BuilderTestCase):
    def create_step(self, step_type):
        response = self.client.post(self.url("step_create", self.lesson.pk), {"step_type": step_type})
        step = LessonStep.objects.latest("pk")
        self.assertRedirects(response, self.url("step", step.pk))
        return step

    def save(self, step, data):
        payload = {"title": step.title, "required": "on", "outcomes": [self.outcome.pk], **data}
        return self.client.post(self.url("step", step.pk), payload)

    def test_video_step_parses_duration_and_chapters(self):
        step = self.create_step("VIDEO")
        self.save(step, {"provider": "youtube", "video_id": "abc123XYZ", "duration": "7:30",
                         "chapters": "2:15 Why it matters\n0:00 Intro", "transcript": "Hello"})
        step.refresh_from_db()
        self.assertEqual(step.content["duration_s"], 450)
        self.assertEqual(step.content["chapters"], [{"t": 0, "title": "Intro"}, {"t": 135, "title": "Why it matters"}])
        self.assertEqual(step.publish_problems(), [])

    def test_video_step_rejects_bad_chapter_line(self):
        step = self.create_step("VIDEO")
        response = self.save(step, {"provider": "youtube", "video_id": "x", "duration": "1:00", "chapters": "soon Intro"})
        self.assertContains(response, "should look like")

    def test_text_step_with_callouts(self):
        step = self.create_step("TEXT")
        self.save(step, {"markdown": "## Variables\nUse `x = 1`.", "mistake": "Using `=` for comparison."})
        step.refresh_from_db()
        self.assertEqual(step.content["callouts"], [{"kind": "mistake", "markdown": "Using `=` for comparison."}])

    def test_parsons_step_reads_indentation(self):
        step = self.create_step("PARSONS")
        self.save(step, {"language": "python", "solution": "for i in range(3):\n    print(i)\n", "distractors": "print i"})
        step.refresh_from_db()
        self.assertEqual(step.content["lines"], [{"text": "for i in range(3):", "indent": 0}, {"text": "print(i)", "indent": 1}])
        self.assertEqual(step.content["distractors"], ["print i"])

    def test_parsons_rejects_odd_indentation(self):
        step = self.create_step("PARSONS")
        response = self.save(step, {"language": "python", "solution": "if x:\n  y()"})
        self.assertContains(response, "multiples of 4")

    def test_playground_and_quiz_steps_save(self):
        play = self.create_step("PLAYGROUND")
        self.save(play, {"language": "python", "starter_code": "print('hi')", "stdin": "", "instructions": "Run it"})
        play.refresh_from_db()
        self.assertEqual(play.content["starter_code"], "print('hi')")
        quiz = self.create_step("QUIZ")
        self.save(quiz, {"intro": "Check yourself", "pass_percent": 70})
        quiz.refresh_from_db()
        self.assertEqual(quiz.content["pass_percent"], 70)

    def test_coding_step_attaches_question_and_hints(self):
        question = make_coding_question(self.staff, mode="fix")
        step = self.create_step("FIX_BUG")
        self.save(step, {"coding_question": question.pk, "hint_1": "Look at the loop bounds.", "hint_3": "range(1, n + 1)"})
        step.refresh_from_db()
        self.assertEqual(step.coding_question, question)
        self.assertEqual(list(StepHint.objects.filter(step=step).values_list("level", flat=True)), [1, 3])
        self.assertEqual(step.publish_problems(), [])
        # clearing a hint removes it
        self.save(step, {"coding_question": question.pk, "hint_1": "Look at the loop bounds."})
        self.assertEqual(StepHint.objects.filter(step=step).count(), 1)

    def test_mcq_attach_tag_reorder_remove(self):
        step = self.create_step("QUIZ")
        q1, q2 = make_mcq(self.staff, "Q one"), make_mcq(self.staff, "Q two")
        for q in (q1, q2):
            self.assertEqual(self.client.post(self.url("step_question_add", step.pk), {"mcq_id": q.pk}).status_code, 200)
        dup = self.client.post(self.url("step_question_add", step.pk), {"mcq_id": q1.pk})
        self.assertEqual(dup.status_code, 400)

        sq1, sq2 = StepQuestion.objects.filter(step=step).order_by("position")
        self.client.post(self.url("step_question_update", sq1.pk), {"outcome_id": self.outcome.pk})
        foreign = make_outcome(make_lesson(make_module(self.course, 2), 1))
        bad = self.client.post(self.url("step_question_update", sq2.pk), {"outcome_id": foreign.pk})
        self.assertEqual(bad.status_code, 400)

        self.client.post(self.url("reorder", "questions", step.pk),
                         data=json.dumps({"ids": [sq2.pk, sq1.pk]}), content_type="application/json")
        self.assertEqual(list(step.questions.order_by("position").values_list("mcq__title", flat=True)), ["Q two", "Q one"])

        self.client.post(self.url("step_question_remove", sq2.pk))
        sq1.refresh_from_db()
        self.assertEqual((step.questions.count(), sq1.position), (1, 1))

    def test_search_endpoint_filters(self):
        make_mcq(self.staff, "Loops quiz")
        make_coding_question(self.staff, mode="fix", title="Fix the loop")
        make_coding_question(self.staff, mode="scratch", title="Write the loop")
        mcqs = self.client.get(self.url("search"), {"type": "mcq", "q": "loops"}).json()["results"]
        fixes = self.client.get(self.url("search"), {"type": "coding", "mode": "fix", "q": "loop"}).json()["results"]
        self.assertEqual([r["title"] for r in mcqs], ["Loops quiz"])
        self.assertEqual([r["title"] for r in fixes], ["Fix the loop"])


class PublishAndPreviewTests(BuilderTestCase):
    def test_publish_blocked_until_complete_then_succeeds(self):
        step = make_step(self.lesson, "TEXT")
        response = self.client.post(self.url("course_publish", self.course.pk), {"action": "publish"})
        self.assertContains(response, "Write the notes.")
        self.course.refresh_from_db()
        self.assertFalse(self.course.is_published)

        step.content = {"markdown": "Notes", "callouts": []}
        step.save()
        response = self.client.post(self.url("course_publish", self.course.pk), {"action": "publish"})
        self.assertRedirects(response, self.url("course", self.course.pk))
        self.course.refresh_from_db()
        self.assertTrue(self.course.is_published)

        self.client.post(self.url("course_publish", self.course.pk), {"action": "unpublish"})
        self.course.refresh_from_db()
        self.assertFalse(self.course.is_published)

    def test_six_lesson_rule_is_a_warning_not_a_block(self):
        make_step(self.lesson, "TEXT", content={"markdown": "Notes", "callouts": []})
        response = self.client.get(self.url("course_publish", self.course.pk))
        self.assertTrue(response.context["report"].can_publish)
        self.assertIn("designed for 6", " ".join(i.message for i in response.context["report"].warnings))

    def test_preview_sanitises_markdown(self):
        make_step(self.lesson, "TEXT", content={"markdown": "Hi <script>alert(1)</script> **bold**", "callouts": []})
        response = self.client.get(self.url("lesson_preview", self.lesson.pk))
        self.assertContains(response, "<strong>bold</strong>")
        self.assertNotContains(response, "<script>alert(1)</script>")
