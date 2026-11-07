from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from courses import access, catalog
from courses.models import Course, Enrollment, LearningOutcome, LessonStep, StepQuestion
from premium.models import Subscription, SubscriptionPlan

from .factories import make_course, make_lesson, make_mcq, make_module, make_step, make_user


def build_course(title="Core Python", published=True, access_level="free"):
    """An introduction (public preview), module 1 (one preview lesson) and module 2 (locked)."""
    course = make_course(title, is_published=published, access=access_level, subtitle="From print() to projects.",
                         description="A complete path through Python.", est_weeks=12)
    intro = make_module(course, 0, title="Introduction: Why Python", is_introduction=True)
    m1 = make_module(course, 1, title="Getting Started")
    m2 = make_module(course, 2, title="Making Decisions")
    l0 = make_lesson(intro, 1, title="The story of Python", est_minutes=30)
    l1 = make_lesson(m1, 1, title="What is programming?", est_minutes=60, is_free_preview=True)
    l2 = make_lesson(m1, 2, title="Types of languages", est_minutes=45)
    l3 = make_lesson(m2, 1, title="Booleans", est_minutes=50)
    LearningOutcome.objects.create(course=course, code=f"{course.slug}-O1", title="Plan before coding",
                                   text="Plan a solution first.", position=1)
    return course, {"intro": intro, "m1": m1, "m2": m2}, {"l0": l0, "l1": l1, "l2": l2, "l3": l3}


class PublicTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.course, self.modules, self.lessons = build_course()
        self.student = make_user()
        self.staff = make_user(staff=True)

    def preview_url(self, lesson):
        return reverse("courses:preview", args=[self.course.slug, lesson.module.slug, lesson.slug])


class CatalogTests(PublicTestCase):
    def test_lists_published_courses_and_hides_drafts(self):
        build_course("Secret Draft", published=False)
        response = self.client.get(reverse("courses:catalog"))
        self.assertContains(response, "Core Python")
        self.assertContains(response, "4 lessons")
        self.assertNotContains(response, "Secret Draft")
        self.client.force_login(self.staff)
        response = self.client.get(reverse("courses:catalog"))
        self.assertContains(response, "Secret Draft")
        self.assertContains(response, "is-draft")

    def test_marks_enrolled_courses(self):
        Enrollment.objects.create(user=self.student, course=self.course)
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("courses:catalog")), "Enrolled")

    def test_empty_state(self):
        Course.objects.update(is_published=False)
        cache.clear()
        self.assertContains(self.client.get(reverse("courses:catalog")), "Courses are on their way")

    @override_settings(COURSES_CACHE_SECONDS=300)
    def test_cached_and_busted_on_save(self):
        self.client.get(reverse("courses:catalog"))  # warm
        with self.assertNumQueries(0):
            catalog.catalog()
        self.course.title = "Core Python 2026"
        self.course.save()
        self.assertContains(self.client.get(reverse("courses:catalog")), "Core Python 2026")

    @override_settings(COURSES_CACHE_SECONDS=0)
    def test_query_count_is_flat(self):
        with self.assertNumQueries(3):
            self.client.get(reverse("courses:catalog"))
        for n in range(3):
            build_course(f"Extra {n}")
        with self.assertNumQueries(3):
            self.client.get(reverse("courses:catalog"))


class CourseLandingTests(PublicTestCase):
    def url(self, course=None):
        return reverse("courses:course", args=[(course or self.course).slug])

    def test_anonymous_sees_syllabus_seo_and_login_cta(self):
        response = self.client.get(self.url())
        self.assertContains(response, "<h1 class=\"cx-title\">Core Python</h1>", html=False)
        for text in ("Plan before coding", "Introduction: Why Python", "What is programming?", "Booleans",
                     "Log in to enroll", 'rel="canonical"', '"@type": "Course"', "From print() to projects."):
            self.assertContains(response, text)
        self.assertContains(response, f'href="{self.preview_url(self.lessons["l1"])}"')
        self.assertNotContains(response, f'href="{self.preview_url(self.lessons["l2"])}"')
        self.assertContains(response, "?next=")
        self.assertEqual(response.context["stats"]["lessons"], 4)
        self.assertEqual(response.context["stats"]["modules"], 2)  # the introduction isn't counted

    def test_drafts_are_staff_only(self):
        draft, _, _ = build_course("Draft Course", published=False)
        self.assertEqual(self.client.get(self.url(draft)).status_code, 404)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url(draft)).status_code, 404)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url(draft)), "Only staff can see this page")

    def test_cta_states(self):
        self.client.force_login(self.student)
        response = self.client.get(self.url())
        self.assertContains(response, "Enroll for free")
        Enrollment.objects.create(user=self.student, course=self.course, last_lesson=self.lessons["l2"])
        response = self.client.get(self.url())
        self.assertContains(response, f'href="#lesson-{self.lessons["l2"].pk}"')
        self.assertContains(response, "Up next")
        self.assertEqual(response.context["open_module"], self.modules["m1"].pk)

    def test_premium_course_explains_what_is_free(self):
        premium, _, _ = build_course("Advanced Python", access_level="premium")
        self.client.force_login(self.student)
        self.assertContains(self.client.get(self.url(premium)), "Premium unlocks the rest")
        self.student.is_premium = True
        self.student.save()
        self.assertContains(self.client.get(self.url(premium)), "Included with your Premium plan")

    def test_newest_version_wins(self):
        v3 = make_course("Core Python", category=self.course.category, version=3, is_published=True,
                         slug=self.course.slug)
        self.assertEqual(self.client.get(self.url()).context["course"], v3)

    @override_settings(COURSES_CACHE_SECONDS=0)
    def test_query_count_does_not_grow_with_content(self):
        self.client.get(self.url())
        with self.assertNumQueries(7):
            self.client.get(self.url())
        for pos in range(3, 8):
            make_lesson(make_module(self.course, pos), 1)
        with self.assertNumQueries(7):
            self.client.get(self.url())


class EnrollTests(PublicTestCase):
    def url(self, course=None):
        return reverse("courses:enroll", args=[(course or self.course).slug])

    def test_requires_login_and_post(self):
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_enroll_is_idempotent_and_reactivates(self):
        self.client.force_login(self.student)
        response = self.client.post(self.url(), follow=True)
        self.assertRedirects(response, reverse("courses:course", args=[self.course.slug]) + "#syllabus")
        self.assertContains(response, "You&#x27;re enrolled in Core Python")
        self.client.post(self.url())
        self.assertEqual(Enrollment.objects.filter(user=self.student).count(), 1)
        Enrollment.objects.update(status=Enrollment.Status.DROPPED)
        self.client.post(self.url())
        self.assertEqual(Enrollment.objects.get(user=self.student).status, Enrollment.Status.ACTIVE)

    def test_cannot_enroll_in_a_draft(self):
        draft, _, _ = build_course("Draft Course", published=False)
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(self.url(draft)).status_code, 404)
        self.assertFalse(Enrollment.objects.exists())


class PreviewTests(PublicTestCase):
    def setUp(self):
        super().setUp()
        lesson = self.lessons["l1"]
        quiz = make_step(lesson, "QUIZ", position=1, title="Quick check")
        mcq = make_mcq(self.staff, "What prints?")
        mcq.explanation = "SECRET-EXPLANATION"
        mcq.save()
        StepQuestion.objects.create(step=quiz, mcq=mcq, position=1)
        make_step(lesson, "PARSONS", position=2, title="Arrange", content={
            "language": "python", "instructions": "", "use_indentation": True, "explanation": "",
            "lines": [{"text": f"line_{n}()", "indent": 0} for n in range(1, 7)], "distractors": ["nope()"]})
        make_step(lesson, "TEXT", position=3, title="Notes", content={"markdown": "## Hello\n\n<script>x</script>",
                                                                      "callouts": []})

    def test_public_preview_hides_answers(self):
        response = self.client.get(self.preview_url(self.lessons["l1"]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("print(1 + 1)", html)          # the question statement students see
        self.assertNotIn("is-correct", html)
        self.assertNotIn("SECRET-EXPLANATION", html)
        self.assertNotIn("1 + 1 is 2.", html)        # per-option explanation
        self.assertNotIn("distractor", html)
        self.assertNotIn("<script>x</script>", html)  # markdown is sanitised
        self.assertIn("<h2>Hello</h2>", html)

    def test_parsons_lines_are_shuffled_the_same_way_every_time(self):
        def order():
            response = self.client.get(self.preview_url(self.lessons["l1"]))
            step = next(s for s in response.context["steps"] if s.step_type == "PARSONS")
            return [line["text"] for line in step.parsons_lines]
        first = order()
        self.assertEqual(first, order())
        self.assertNotEqual(first, [f"line_{n}()" for n in range(1, 7)] + ["nope()"])

    def test_introduction_lessons_are_public(self):
        self.assertEqual(self.client.get(self.preview_url(self.lessons["l0"])).status_code, 200)

    def test_locked_lessons_redirect_to_the_syllabus(self):
        response = self.client.get(self.preview_url(self.lessons["l3"]), follow=True)
        self.assertRedirects(response, reverse("courses:course", args=[self.course.slug])
                             + f"#lesson-{self.lessons['l3'].pk}")
        self.assertContains(response, "opens in the lesson player once you enroll")

    def test_staff_can_open_any_lesson(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.preview_url(self.lessons["l3"])), "Staff view.")

    def test_unknown_lesson_404(self):
        url = reverse("courses:preview", args=[self.course.slug, "nope", "nope"])
        self.assertEqual(self.client.get(url).status_code, 404)


class MyLearningTests(PublicTestCase):
    def test_login_required(self):
        response = self.client.get(reverse("courses:my_learning"))
        self.assertEqual(response.status_code, 302)

    def test_lists_active_enrollments_with_continue_links(self):
        dropped, _, _ = build_course("Old Course")
        Enrollment.objects.create(user=self.student, course=self.course)
        Enrollment.objects.create(user=self.student, course=dropped, status=Enrollment.Status.DROPPED)
        self.client.force_login(self.student)
        response = self.client.get(reverse("courses:my_learning"))
        self.assertContains(response, "Core Python")
        self.assertNotContains(response, "Old Course")
        first = self.lessons["l0"]
        self.assertContains(response, f'{reverse("courses:course", args=[self.course.slug])}#lesson-{first.pk}')

    def test_empty_state(self):
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse("courses:my_learning")), "No courses yet")


class AccessTests(PublicTestCase):
    def test_premium_by_flag_or_live_subscription(self):
        self.assertFalse(access.has_premium(self.student))
        plan = SubscriptionPlan.objects.create(name="Pro", slug="pro", price_monthly=100, price_yearly=1000)
        now = timezone.now()
        sub = Subscription.objects.create(user=self.student, plan=plan, status="active",
                                          current_period_start=now - timedelta(days=1),
                                          current_period_end=now + timedelta(days=29))
        self.assertTrue(access.has_premium(self.student))
        sub.current_period_end = now - timedelta(minutes=1)
        sub.save()
        self.assertFalse(access.has_premium(self.student))

    def test_free_to_enrolled_rules(self):
        premium, modules, lessons = build_course("Pro Course", access_level="premium")
        self.assertTrue(access.is_free_to_enrolled(lessons["l0"], modules["intro"], premium))
        self.assertTrue(access.is_free_to_enrolled(lessons["l2"], modules["m1"], premium))   # first module
        self.assertFalse(access.is_free_to_enrolled(lessons["l3"], modules["m2"], premium))
        with override_settings(COURSES_PREMIUM_GATING=False):
            self.assertTrue(access.is_free_to_enrolled(lessons["l3"], modules["m2"], premium))
            self.assertFalse(access.premium_locked(self.student, premium))
        self.assertTrue(access.premium_locked(self.student, premium))
        self.assertFalse(access.premium_locked(self.staff, premium))


class SiteNavTests(TestCase):
    def test_home_and_base_link_to_courses(self):
        self.assertContains(self.client.get(reverse("home")), f'href="{reverse("courses:catalog")}"')
        self.client.force_login(make_user())
        self.assertContains(self.client.get(reverse("problems:problem_list")), f'href="{reverse("courses:catalog")}"')


class StepCountTests(PublicTestCase):
    def test_outline_counts_steps_by_kind(self):
        lesson = self.lessons["l1"]
        make_step(lesson, "VIDEO", position=1)
        make_step(lesson, "PREDICT", position=2)
        make_step(lesson, "QUIZ", position=3)
        stats = catalog.outline(self.course, staff=True)["stats"]
        self.assertEqual((stats["videos"], stats["quizzes"], stats["coding"]), (1, 2, 0))
        self.assertEqual(LessonStep.objects.count(), 3)
