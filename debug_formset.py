import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leetcode_project.settings')
import django
django.setup()
import uuid
from assessment.forms import McqQuestionForm, McqOptionFormSet
from assessment.models import McqQuestion, ProgrammingLanguage
from users.models import Users

unique='u'+uuid.uuid4().hex[:8]
user = Users.objects.create_user(email=unique+'@example.com', user_name=unique, password='pw', is_faculty=True)
lang = ProgrammingLanguage.objects.create(name='Python'+unique, slug='python-'+unique, is_active=True, is_judge0_executable=True, judge0_language_id=71)
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
    'programming_language': lang.pk,
    'explanation': 'Because 2 + 2 equals 4.',
    'allow_multiple': False,
    'is_active': True,
}
qform = McqQuestionForm(data=payload)
print('question valid', qform.is_valid(), qform.errors)
q = qform.save(commit=False)
q.owner = user
q.save()

data = {
    'form-TOTAL_FORMS': '4',
    'form-INITIAL_FORMS': '0',
    'form-MIN_NUM_FORMS': '0',
    'form-MAX_NUM_FORMS': '1000',
    'form-0-text': '2',
    'form-0-is_correct': 'on',
    'form-0-position': '1',
    'form-1-text': '3',
    'form-1-is_correct': '',
    'form-1-position': '2',
    'form-2-text': '4',
    'form-2-is_correct': '',
    'form-2-position': '3',
    'form-3-text': '5',
    'form-3-is_correct': '',
    'form-3-position': '4',
}
fs = McqOptionFormSet(data=data, instance=q)
print('total', fs.total_form_count())
print('forms len', len(fs.forms))
print('bound', fs.is_bound)
print('before is_valid?')
print(fs.is_valid())
print('len errors', len(fs.errors))
print('errors', fs.errors)
print('non_form', fs.non_form_errors())
for i, f in enumerate(fs.forms):
    print('FORM', i)
    print('  is_bound', f.is_bound)
    print('  errors', f.errors)
    print('  cleaned', f.cleaned_data)
