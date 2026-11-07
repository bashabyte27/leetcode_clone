from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from courses.models import Course, LessonStep, StepHint, StepQuestion
from courses.steps import STEP_TYPES, structure_errors

from .factories import (
    make_coding_question, make_course, make_lesson, make_mcq, make_module, make_outcome, make_step, make_user,
)


class SlugAndOrderingTests(TestCase):
    def test_slugs_are_generated_and_unique_within_scope(self):
        course = make_course("Core Python")
        a = make_module(course, 1, title="Variables & Types")
        b = make_module(course, 2, title="Variables & Types")
        self.assertEqual(course.slug, "core-python")
        self.assertEqual((a.slug, b.slug), ("variables-types", "variables-types-2"))
        # The same title in another course may reuse the slug
        self.assertEqual(make_module(make_course("Other"), 1, title="Variables & Types").slug, "variables-types")

    def test_position_is_unique_per_parent(self):
        module = make_module()
        make_lesson(module, 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_lesson(module, 1, title="Duplicate")

    def test_course_slug_unique_per_version(self):
        course = make_course("Core Python")
        Course.objects.create(category=course.category, title="Core Python", slug="core-python", version=2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Course.objects.create(category=course.category, title="Again", slug="core-python", version=2)

    def test_mark_published_sets_timestamp_once(self):
        course = make_course()
        course.mark_published()
        first = course.published_at
        course.mark_published()
        self.assertTrue(course.is_published)
        self.assertEqual(course.published_at, first)


class StepContentTests(TestCase):
    def setUp(self):
        self.lesson = make_lesson()

    def test_every_type_gets_valid_default_content(self):
        for i, code in enumerate(STEP_TYPES, start=1):
            step = make_step(self.lesson, code, position=i)
            self.assertEqual(structure_errors(code, step.content), [], code)

    def test_malformed_content_is_never_saved(self):
        bad = {
            "VIDEO": {"provider": "vimeo"},
            "TEXT": {"markdown": 5},
            "QUIZ": {"pass_percent": 150},
            "PARSONS": {"lines": [{"text": "x", "indent": 9}]},
            "PLAYGROUND": {"starter_code": ["not", "text"]},
            "CODING": {"surprise": True},
        }
        for code, content in bad.items():
            with self.subTest(code=code), self.assertRaises(ValidationError):
                LessonStep(lesson=self.lesson, position=50, step_type=code, title="x", content=content).save()
        self.assertFalse(LessonStep.objects.exists())

    def test_coding_question_only_allowed_on_coding_steps(self):
        step = make_step(self.lesson, "TEXT")
        step.coding_question = make_coding_question(make_user())
        with self.assertRaises(ValidationError):
            step.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            step.save()

    def test_hint_levels_limited_to_three(self):
        step = make_step(self.lesson, "CODING")
        StepHint.objects.create(step=step, level=3, text="Last hint")
        with self.assertRaises(IntegrityError), transaction.atomic():
            StepHint.objects.create(step=step, level=4, text="Too many")

    def test_outcome_lesson_must_match_module(self):
        other_lesson = make_lesson(make_module(self.lesson.module.course, 2))
        outcome = make_outcome(self.lesson)
        outcome.lesson = other_lesson
        with self.assertRaises(ValidationError):
            outcome.full_clean()


class PublishProblemTests(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.lesson = make_lesson()
        self.outcome = make_outcome(self.lesson)

    def test_empty_steps_report_what_is_missing(self):
        expectations = {
            "VIDEO": "video id", "TEXT": "notes", "PLAYGROUND": "starter code",
            "PARSONS": "two code lines", "QUIZ": "Attach at least one MCQ", "CODING": "Attach a coding question",
        }
        for i, (code, phrase) in enumerate(expectations.items(), start=1):
            with self.subTest(code=code):
                problems = " ".join(make_step(self.lesson, code, position=i).publish_problems())
                self.assertIn(phrase, problems)

    def test_quiz_questions_need_outcome_tags(self):
        step = make_step(self.lesson, "QUIZ")
        sq = StepQuestion.objects.create(step=step, mcq=make_mcq(self.owner), position=1)
        self.assertIn("Tag every question", " ".join(step.publish_problems()))
        sq.outcome = self.outcome
        sq.save()
        self.assertEqual(step.publish_problems(), [])

    def test_fix_bug_requires_fix_mode_question_and_outcome(self):
        step = make_step(self.lesson, "FIX_BUG", coding_question=make_coding_question(self.owner, mode="scratch"))
        problems = " ".join(step.publish_problems())
        self.assertIn("Fix the Bug", problems)
        self.assertIn("learning outcome", problems)
        step.coding_question = make_coding_question(self.owner, mode="fix")
        step.save()
        step.outcomes.add(self.outcome)
        self.assertEqual(step.publish_problems(), [])
