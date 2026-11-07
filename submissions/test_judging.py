import json
from unittest import mock

from django.test import Client, TestCase

from problems.models import Language, Problem, TestCase as ProblemTestCase
from submissions import judge0
from submissions.judge import _code_reads_input
from submissions.models import Submission, SubmissionResult, UserSolvedProblem
from users.models import UserStats, Users


def fake_result(stdout='', status_id=3, stderr='', compile_output=''):
    return {'status': {'id': status_id}, 'stdout': stdout, 'stderr': stderr,
            'compile_output': compile_output, 'time': '0.012', 'memory': 3200}


def echo_doubler(items):
    """Pretend Judge0: prints 2 * input for every item."""
    return [fake_result(str(int(item['stdin'].strip() or 0) * 2)) for item in items]


class JudgingBase(TestCase):
    def setUp(self):
        self.user = Users.objects.create_user('j@example.com', 'judge_user', 'Password123!')
        self.lang = Language.objects.create(name='Python', slug='python', judge_id='71', is_active=True)
        self.problem = Problem.objects.create(order_num=900, title='Double It', slug='double-it',
                                              description='x', difficulty='easy')
        for i, (inp, out, sample) in enumerate([('2', '4', True), ('5', '10', True), ('7', '14', False)], 1):
            ProblemTestCase.objects.create(problem=self.problem, order_num=i, input_data=inp,
                                           expected_output=out, is_sample=sample)
        self.code = 'n = int(input())\nprint(n * 2)'

    def post(self, url, payload, client=None):
        client = client or self.client
        return client.post(url, data=json.dumps(payload), content_type='application/json')


class RunTests(JudgingBase):
    def test_logged_out_run_gets_json_401(self):
        r = self.post('/submissions/run/double-it/', {'code': self.code, 'language': 'python'})
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.json()['login_required'])

    def test_run_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        r = self.post('/submissions/run/double-it/', {'code': self.code, 'language': 'python'}, csrf_client)
        self.assertEqual(r.status_code, 403)

    @mock.patch('submissions.judge0.execute_batch', side_effect=echo_doubler)
    def test_run_uses_edited_inputs_and_one_batch(self, batch):
        self.client.force_login(self.user)
        r = self.post('/submissions/run/double-it/', {
            'code': self.code, 'language': 'python',
            'cases': [{'tc_num': 1, 'input': '2'}, {'tc_num': 2, 'input': '21'}],
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(batch.call_count, 1)
        first, second = r.json()['test_case_results']
        self.assertEqual((first['status'], first['custom'], first['expected']), ('success', False, '4'))
        self.assertEqual((second['status'], second['custom'], second['actual']), ('success', True, '42'))

    @mock.patch('submissions.judge0.execute_batch', side_effect=echo_doubler)
    def test_run_without_cases_falls_back_to_samples(self, batch):
        self.client.force_login(self.user)
        r = self.post('/submissions/run/double-it/', {'code': self.code, 'language': 'python'})
        self.assertEqual([c['tc_num'] for c in r.json()['test_case_results']], [1, 2])

    def test_inactive_language_rejected(self):
        self.lang.is_active = False
        self.lang.save()
        self.client.force_login(self.user)
        r = self.post('/submissions/run/double-it/', {'code': self.code, 'language': 'python'})
        self.assertEqual(r.status_code, 404)


class SubmitTests(JudgingBase):
    @mock.patch('submissions.judge0.execute_batch', side_effect=echo_doubler)
    def test_accepted_submission_updates_solved_tables(self, batch):
        self.client.force_login(self.user)
        r = self.post('/submissions/submit/double-it/', {'code': self.code, 'language': 'python'})
        self.assertEqual(r.json()['status'], 'accepted')
        self.assertEqual(SubmissionResult.objects.count(), 3)
        solved = UserSolvedProblem.objects.get(user=self.user, problem=self.problem)
        self.assertEqual(solved.attempt_count, 1)
        stats = UserStats.objects.get(user=self.user)
        self.assertEqual((stats.easy_solved, stats.total_submissions, stats.accepted_submissions), (1, 1, 1))

    @mock.patch('submissions.judge0.execute_batch', side_effect=RuntimeError('judge exploded'))
    def test_crash_marks_internal_error_and_hides_details(self, batch):
        self.client.force_login(self.user)
        r = self.post('/submissions/submit/double-it/', {'code': self.code, 'language': 'python'})
        self.assertEqual(Submission.objects.get().status, 'internal_error')
        self.assertNotIn('exploded', r.content.decode())


class Judge0PollingTests(TestCase):
    @mock.patch('submissions.judge0.time.sleep')
    @mock.patch('submissions.judge0.requests.get')
    @mock.patch('submissions.judge0.requests.post')
    def test_batch_polls_all_tokens_in_one_request_per_round(self, post, get, _sleep):
        post.return_value = mock.Mock(status_code=201, json=lambda: [{'token': 'a'}, {'token': 'b'}, {'error': 'bad'}])
        post.return_value.raise_for_status = lambda: None
        rounds = [
            {'submissions': [{'token': 'a', 'status': {'id': 3}, 'stdout': '1'}, {'token': 'b', 'status': {'id': 2}}]},
            {'submissions': [{'token': 'b', 'status': {'id': 3}, 'stdout': '2'}]},
        ]
        get.side_effect = [mock.Mock(json=(lambda d=d: d), raise_for_status=lambda: None) for d in rounds]
        out = judge0.execute_batch([{'language_id': 71, 'source_code': 'x', 'stdin': ''}] * 3)
        self.assertEqual(get.call_count, 2)
        self.assertIn('tokens', get.call_args_list[0].kwargs['params'])
        self.assertEqual([o['status']['id'] for o in out], [3, 3, 13])


class InputDetectionTests(TestCase):
    def test_common_stdin_styles_are_recognised(self):
        for code in ('import sys\ndata = sys.stdin.read()', 'getline(cin, s);', 'c = getchar();',
                     'fgets(buf, 100, stdin);', 'data = open(0).read()',
                     "const t = require('fs').readFileSync(0, 'utf8');",
                     'BufferedReader br = new BufferedReader(new InputStreamReader(System.in));'):
            with self.subTest(code=code):
                self.assertTrue(_code_reads_input(code))
        self.assertFalse(_code_reads_input('print("hello")'))


class CustomCaseAndQueueTests(JudgingBase):
    @mock.patch('submissions.judge0.execute_batch', side_effect=echo_doubler)
    def test_custom_case_label_is_echoed_and_marked_custom(self, batch):
        self.client.force_login(self.user)
        r = self.post('/submissions/run/double-it/', {
            'code': self.code, 'language': 'python',
            'cases': [{'tc_num': 1, 'input': '2'}, {'tc_num': 3, 'input': '50', 'label': 'Custom'}],
        })
        custom = r.json()['test_case_results'][1]
        self.assertEqual((custom['label'], custom['custom'], custom['actual']), ('Custom', True, '100'))

    @mock.patch('submissions.judge0.execute_batch', side_effect=echo_doubler)
    def test_judge_limits_are_sent_to_judge0(self, batch):
        self.problem.time_limit_seconds = 3
        self.problem.memory_limit_mb = 128
        self.problem.save()
        self.client.force_login(self.user)
        self.post('/submissions/submit/double-it/', {'code': self.code, 'language': 'python'})
        item = batch.call_args.args[0][0]
        self.assertEqual((item['cpu_time_limit'], item['memory_limit']), (3.0, 128 * 1024))

    def test_second_submit_while_judging_is_rejected(self):
        Submission.objects.create(user=self.user, problem=self.problem, language=self.lang, code='x', status='running')
        self.client.force_login(self.user)
        r = self.post('/submissions/submit/double-it/', {'code': self.code, 'language': 'python'})
        self.assertEqual(r.status_code, 429)

    @mock.patch('submissions.queue._pool')
    def test_async_submit_returns_immediately_and_detail_reports_pending(self, pool):
        self.client.force_login(self.user)
        with self.settings(JUDGE_ASYNC=True):
            r = self.post('/submissions/submit/double-it/', {'code': self.code, 'language': 'python'})
        self.assertEqual(r.status_code, 202)
        body = r.json()
        self.assertTrue(body['queued'])
        detail = self.client.get(body['poll_url']).json()
        self.assertTrue(detail['pending'])
        self.assertEqual(detail['total'], 3)

    @mock.patch('submissions.judge0.execute_batch', side_effect=echo_doubler)
    def test_percentile_is_stored_for_accepted_submissions(self, batch):
        other = Users.objects.create_user('o@example.com', 'other_user', 'Password123!')
        Submission.objects.create(user=other, problem=self.problem, language=self.lang, code='x',
                                  status='accepted', runtime_ms=50)
        self.client.force_login(self.user)
        data = self.post('/submissions/submit/double-it/', {'code': self.code, 'language': 'python'}).json()
        self.assertEqual(data['runtime_percentile'], '100.00')  # 12 ms beats the 50 ms one

    def test_prompt_check_is_python_only_and_ignores_comments(self):
        from submissions.judge import is_code_safe
        self.assertFalse(is_code_safe('n = input("Enter: ")', self.lang)[0])
        self.assertTrue(is_code_safe('# n = input("Enter: ")\nn = input()', self.lang)[0])
        js = Language(name='JavaScript', slug='javascript')
        self.assertTrue(is_code_safe('const x = input("a")', js)[0])
