from datetime import timedelta

from django import forms
from django.test import TestCase
from django.utils import timezone

from assessment.forms import (
    AssessmentForm,
    AssessmentQuestionForm,
    AssessmentSectionForm,
    CodingQuestionForm,
    CodingQuestionLanguageFormSet,
    CodingTestCaseFormSet,
    McqOptionFormSet,
    McqQuestionForm,
)
from assessment.models import (
    Assessment,
    AssessmentQuestion,
    AssessmentSection,
    CodingQuestion,
    CodingQuestionLanguage,
    CodingTestCase,
    McqOption,
    McqQuestion,
    ProgrammingLanguage,
)
from users.models import Users


class AssessmentFormTests(TestCase):
    def setUp(self):
        self.user = Users.objects.create_user(
            email='faculty@example.com',
            user_name='faculty',
            password='StrongPass123!',
            is_faculty=True,
        )
        self.lang = ProgrammingLanguage.objects.create(
            name='Python',
            slug='python',
            is_active=True,
            is_judge0_executable=True,
            judge0_language_id=71,
        )
        self.other_lang = ProgrammingLanguage.objects.create(
            name='JavaScript',
            slug='javascript',
            is_active=True,
            is_judge0_executable=True,
            judge0_language_id=63,
        )

    def _mcq_payload(self, **overrides):
        payload = {
            'title': 'What is 2 + 2?',
            'slug': '',
            'question_type': McqQuestion.QuestionType.REGULAR,
            'category': McqQuestion.Category.QUANT,
            'topic': 'Arithmetic',
            'sub_topic': 'Addition',
            'difficulty': McqQuestion.Difficulty.EASY,
            'statement': 'Solve the arithmetic problem.',
            'code_snippet': '',
            'programming_language': self.lang.pk,
            'explanation': 'Because 2 + 2 equals 4.',
            'allow_multiple': False,
            'is_active': True,
        }
        payload.update(overrides)
        return payload

    def _mcq_options_data(self, *, correct_index=0, extra_rows=0):
        options = [
            {'text': '2', 'is_correct': 'on' if i == correct_index else '', 'position': i + 1}
            for i in range(4)
        ]
        form_data = {
            'form-TOTAL_FORMS': str(4 + extra_rows),
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
        }
        for index, option in enumerate(options):
            form_data[f'form-{index}-text'] = option['text']
            form_data[f'form-{index}-is_correct'] = option['is_correct']
            form_data[f'form-{index}-position'] = str(option['position'])
        for index in range(len(options), len(options) + extra_rows):
            form_data[f'form-{index}-text'] = ''
            form_data[f'form-{index}-is_correct'] = ''
            form_data[f'form-{index}-position'] = ''
        return form_data

    def test_valid_mcq_form_and_slug_generation(self):
        form = McqQuestionForm(data=self._mcq_payload())
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.owner = self.user
        instance.save()
        self.assertEqual(instance.slug, 'what-is-2-2')

    def test_mcq_option_formset_requires_valid_counts(self):
        payload = self._mcq_payload()
        question_form = McqQuestionForm(data=payload)
        self.assertTrue(question_form.is_valid(), question_form.errors)
        instance = question_form.save(commit=False)
        instance.owner = self.user
        instance.save()

        formset = McqOptionFormSet(
            data=self._mcq_options_data(correct_index=0),
            instance=instance,
        )
        self.assertTrue(formset.is_valid(), formset.errors)

        invalid = McqOptionFormSet(
            data={
                **self._mcq_options_data(correct_index=0),
                'form-0-is_correct': '',
                'form-1-is_correct': '',
                'form-2-is_correct': '',
                'form-3-is_correct': '',
            },
            instance=instance,
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn('Single-answer MCQs must have exactly one correct option.', str(invalid.non_form_errors()))

    def test_mcq_options_duplicate_positions_and_deleted_rows_are_ignored(self):
        form = McqQuestionForm(data=self._mcq_payload())
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.owner = self.user
        instance.save()

        bad_data = {
            **self._mcq_options_data(correct_index=0),
            'form-1-position': '1',
            'form-2-text': '',
            'form-2-position': '',
            'form-2-is_correct': '',
            'form-2-DELETE': 'on',
        }
        formset = McqOptionFormSet(data=bad_data, instance=instance)
        self.assertFalse(formset.is_valid())
        self.assertTrue(any('Duplicate positions are not allowed.' in str(error) for error in formset.errors))

    def test_multiple_answer_mcq_requires_at_least_one_correct_option(self):
        form = McqQuestionForm(data=self._mcq_payload(allow_multiple=True))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.owner = self.user
        instance.save()

        data = {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-text': 'A',
            'form-0-is_correct': '',
            'form-0-position': '1',
            'form-1-text': 'B',
            'form-1-is_correct': '',
            'form-1-position': '2',
        }
        formset = McqOptionFormSet(data=data, instance=instance)
        self.assertFalse(formset.is_valid())
        self.assertIn('At least one correct option is required for multiple-answer MCQs.', str(formset.non_form_errors()))

    def test_coding_question_and_limits_validation(self):
        payload = {
            'title': 'Sum of two numbers',
            'slug': '',
            'coding_mode': CodingQuestion.CodingMode.SCRATCH,
            'topic': 'Algorithms',
            'subtopic': 'Loops',
            'difficulty': CodingQuestion.Difficulty.EASY,
            'statement': 'Write code to sum numbers.',
            'input_format': 'n',
            'output_format': 'result',
            'constraints_text': '1 <= n <= 10^5',
            'explanation': 'Simple loop solution.',
            'time_limit_seconds': 2,
            'memory_limit_kb': 256000,
            'is_active': True,
        }
        form = CodingQuestionForm(data=payload)
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.owner = self.user
        instance.save()
        self.assertEqual(instance.slug, 'sum-of-two-numbers')

        invalid = CodingQuestionForm(data={**payload, 'time_limit_seconds': 0, 'memory_limit_kb': 0})
        self.assertFalse(invalid.is_valid())
        self.assertIn('Time limit must be at least 1 second.', invalid.errors['time_limit_seconds'])
        self.assertIn('Memory limit must be at least 1 KB.', invalid.errors['memory_limit_kb'])

    def test_coding_language_and_test_case_formsets(self):
        question = CodingQuestion.objects.create(
            owner=self.user,
            title='Palindrome checker',
            slug='palindrome-checker',
            coding_mode=CodingQuestion.CodingMode.COMPLETE,
            topic='Strings',
            subtopic='Palindromes',
            difficulty=CodingQuestion.Difficulty.MEDIUM,
            statement='Check palindrome.',
            is_active=True,
        )

        language_formset = CodingQuestionLanguageFormSet(
            data={
                'form-TOTAL_FORMS': '2',
                'form-INITIAL_FORMS': '0',
                'form-MIN_NUM_FORMS': '0',
                'form-MAX_NUM_FORMS': '1000',
                'form-0-language': str(self.lang.pk),
                'form-0-starter_code': 'def solve():\n    pass',
                'form-0-buggy_code': '',
                'form-1-language': str(self.lang.pk),
                'form-1-starter_code': 'print(1)',
                'form-1-buggy_code': '',
            },
            instance=question,
        )
        self.assertFalse(language_formset.is_valid())
        self.assertTrue(any('Each language can only be selected once.' in str(error) for error in language_formset.errors))

        test_case_data = {
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-input_data': '',
            'form-0-expected_output': '0',
            'form-0-is_sample': 'on',
            'form-0-weight': '1',
            'form-0-position': '1',
            'form-0-explanation': 'Zero-case',
            'form-1-input_data': 'abc',
            'form-1-expected_output': 'cba',
            'form-1-is_sample': '',
            'form-1-weight': '2',
            'form-1-position': '1',
            'form-1-explanation': 'Reverse example',
        }
        formset = CodingTestCaseFormSet(data=test_case_data, instance=question)
        self.assertFalse(formset.is_valid())
        self.assertIn('Duplicate test case positions are not allowed.', str(formset.non_form_errors()))

    def test_assessment_validation_and_section_validation(self):
        now = timezone.now()
        form = AssessmentForm(
            data={
                'name': 'Midterm',
                'slug': '',
                'description': 'A short test.',
                'start_time': (now + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S'),
                'end_time': (now + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S'),
                'duration_minutes': 60,
                'status': Assessment.Status.DRAFT,
                'max_attempts': 2,
                'result_release_policy': Assessment.ResultReleasePolicy.SCHEDULED,
                'results_release_at': '',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('Assessment start time must be earlier than the end time.', form.errors['end_time'])
        self.assertIn('A scheduled result release date/time is required.', form.errors['results_release_at'])

        assessment = Assessment.objects.create(
            created_by=self.user,
            name='Quiz',
            slug='quiz',
            duration_minutes=45,
            max_attempts=1,
        )
        section_form = AssessmentSectionForm(data={
            'title': 'Section 1',
            'instructions': 'Read carefully',
            'position': 1,
            'time_limit_minutes': 0,
        }, assessment=assessment)
        self.assertFalse(section_form.is_valid())
        self.assertIn('Time limit must be at least 1 minute.', section_form.errors['time_limit_minutes'])

    def test_question_assignment_requires_exactly_one_question_type(self):
        assessment = Assessment.objects.create(
            created_by=self.user,
            name='Assessment 1',
            slug='assessment-1',
            duration_minutes=40,
            max_attempts=1,
        )
        section = AssessmentSection.objects.create(
            assessment=assessment,
            title='Section A',
            position=1,
        )
        mcq = McqQuestion.objects.create(
            owner=self.user,
            title='MCQ A',
            slug='mcq-a',
            question_type=McqQuestion.QuestionType.REGULAR,
            category=McqQuestion.Category.APTITUDE,
            topic='Logic',
            difficulty=McqQuestion.Difficulty.EASY,
            statement='Choose the best answer.',
            is_active=True,
        )

        form = AssessmentQuestionForm(
            data={
                'mcq_question': str(mcq.pk),
                'coding_question': '',
                'position': 1,
                'max_score': '10',
                'negative_marks': '0',
            },
            assessment=assessment,
            section=section,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

        coding_question = CodingQuestion.objects.create(
            owner=self.user,
            title='Coding Q',
            slug='coding-q',
            coding_mode=CodingQuestion.CodingMode.SCRATCH,
            topic='Algorithms',
            subtopic='Basics',
            difficulty=CodingQuestion.Difficulty.EASY,
            statement='Write a solution.',
            is_active=True,
        )
        invalid = AssessmentQuestionForm(
            data={
                'mcq_question': str(mcq.pk),
                'coding_question': str(coding_question.pk),
                'position': 2,
                'max_score': '0',
                'negative_marks': '-1',
            },
            assessment=assessment,
            section=section,
            user=self.user,
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn('Select exactly one question type: either an MCQ or a coding question.', invalid.non_field_errors())
        self.assertIn('Maximum score must be positive.', invalid.errors.get('max_score', []))
        self.assertIn('Negative marks cannot be negative.', invalid.errors.get('negative_marks', []))

    def test_question_queryset_restricts_untrusted_ids(self):
        other_user = Users.objects.create_user(
            email='other@example.com',
            user_name='other',
            password='StrongPass123!',
        )
        own_question = McqQuestion.objects.create(
            owner=self.user,
            title='My Question',
            slug='my-question',
            question_type=McqQuestion.QuestionType.REGULAR,
            category=McqQuestion.Category.APTITUDE,
            topic='Reasoning',
            difficulty=McqQuestion.Difficulty.MEDIUM,
            statement='Question statement',
            is_active=True,
        )
        other_question = McqQuestion.objects.create(
            owner=other_user,
            title='Other Question',
            slug='other-question',
            question_type=McqQuestion.QuestionType.REGULAR,
            category=McqQuestion.Category.QUANT,
            topic='Reasoning',
            difficulty=McqQuestion.Difficulty.MEDIUM,
            statement='Other statement',
            is_active=True,
        )
        form = AssessmentQuestionForm(user=self.user)
        self.assertIn(own_question, form.fields['mcq_question'].queryset)
        self.assertNotIn(other_question, form.fields['mcq_question'].queryset)
