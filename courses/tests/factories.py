"""Tiny builders shared by the courses tests (no factory library needed)."""

from itertools import count

from assessment.models import CodingQuestion, McqOption, McqQuestion
from courses.models import Category, Course, LearningOutcome, Lesson, LessonStep, Module
from users.models import Users

_seq = count(1)


def make_user(staff=False, **extra):
    n = next(_seq)
    return Users.objects.create_user(f"u{n}@example.com", f"user_{n}", "Password123!", is_staff=staff, **extra)


def make_course(title="Core Python", **extra):
    category = extra.pop("category", None) or Category.objects.create(title=f"Category {next(_seq)}")
    return Course.objects.create(category=category, title=title, **extra)


def make_module(course=None, position=1, **extra):
    return Module.objects.create(course=course or make_course(), position=position,
                                 title=extra.pop("title", f"Module {position}"), **extra)


def make_lesson(module=None, position=1, **extra):
    return Lesson.objects.create(module=module or make_module(), position=position,
                                 title=extra.pop("title", f"Lesson {position}"), **extra)


def make_outcome(lesson, n=1):
    return LearningOutcome.objects.create(
        course=lesson.module.course, module=lesson.module, lesson=lesson,
        code=f"T-M{lesson.module.position}-L{lesson.position}-O{n}-{next(_seq)}", text=f"Outcome {n}",
    )


def make_step(lesson, step_type, position=1, **extra):
    return LessonStep.objects.create(lesson=lesson, position=position, step_type=step_type,
                                     title=extra.pop("title", step_type.title()), **extra)


def make_mcq(owner, title="What prints?"):
    q = McqQuestion.objects.create(owner=owner, title=title, slug=f"mcq-{next(_seq)}", topic="basics",
                                   difficulty="easy", statement="print(1 + 1)")
    McqOption.objects.create(question=q, text="2", is_correct=True, position=1, explanation="1 + 1 is 2.")
    McqOption.objects.create(question=q, text="11", is_correct=False, position=2)
    return q


def make_coding_question(owner, mode="scratch", title=None):
    n = next(_seq)
    return CodingQuestion.objects.create(owner=owner, title=title or f"Task {n}", slug=f"task-{n}",
                                         coding_mode=mode, topic="basics", difficulty="easy", statement="x")
