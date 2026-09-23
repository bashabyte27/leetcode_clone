from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from problems.models import DifficultyChoices, Problem
from submissions.models import Submission, SubmissionStatusChoices

from . import services
from .views import PAGE_SIZE

User = get_user_model()
AC = SubmissionStatusChoices.ACCEPTED
WA = SubmissionStatusChoices.WRONG_ANSWER
RE = SubmissionStatusChoices.RUNTIME_ERROR


class LeaderboardTestBase(TestCase):
    _n = 0

    @classmethod
    def make_user(cls, name, **extra):
        return User.objects.create_user(
            email=f'{name}@example.com', user_name=name, password='x', **extra
        )

    @classmethod
    def make_problem(cls, difficulty, **extra):
        cls._n += 1
        return Problem.objects.create(
            title=f'P{cls._n}', slug=f'p{cls._n}', description='d',
            difficulty=difficulty, **extra,
        )

    @staticmethod
    def submit(user, problem, status=AC, times=1):
        for _ in range(times):
            Submission.objects.create(user=user, problem=problem, code='x', status=status)

    def solve(self, user, easy=0, medium=0, hard=0):
        for difficulty, count in (('easy', easy), ('medium', medium), ('hard', hard)):
            for _ in range(count):
                self.submit(user, self.make_problem(difficulty))

    def row_for(self, name):
        for r in services.leaderboard_queryset():
            if r['user__user_name'] == name:
                return r
        return None


class ScoringTests(LeaderboardTestBase):
    def test_user_without_accepted_problems_is_not_ranked(self):
        u = self.make_user('nobody')
        self.submit(u, self.make_problem('easy'), status=WA)
        self.assertIsNone(self.row_for('nobody'))
        st = services.get_user_standing(u.pk)
        self.assertEqual((st['rank'], st['points'], st['solved']), (None, 0, 0))

    def test_single_problem_points(self):
        for name, diff, pts in (('e', 'easy', 10), ('m', 'medium', 25), ('h', 'hard', 50)):
            u = self.make_user(name)
            self.submit(u, self.make_problem(diff))
            row = self.row_for(name)
            self.assertEqual((row['points'], row['solved']), (pts, 1), diff)

    def test_same_problem_accepted_many_times_counts_once(self):
        u = self.make_user('rep')
        p = self.make_problem('medium')
        self.submit(u, p, WA, times=2)
        self.submit(u, p, RE)
        self.submit(u, p, AC, times=3)
        row = self.row_for('rep')
        self.assertEqual((row['points'], row['solved'], row['medium_solved']), (25, 1, 1))

    def test_mixed_difficulties(self):
        u = self.make_user('mix')
        self.solve(u, easy=2, medium=3, hard=1)
        row = self.row_for('mix')
        self.assertEqual(row['points'], 2 * 10 + 3 * 25 + 1 * 50)  # 145
        self.assertEqual(
            (row['easy_solved'], row['medium_solved'], row['hard_solved'], row['solved']),
            (2, 3, 1, 6),
        )

    def test_spec_example_550_points(self):
        u = self.make_user('spec')
        self.solve(u, easy=15, medium=10, hard=3)
        self.assertEqual(self.row_for('spec')['points'], 550)

    def test_inactive_problem_and_inactive_user_excluded(self):
        u = self.make_user('u1')
        self.submit(u, self.make_problem('hard', is_active=False))
        self.assertIsNone(self.row_for('u1'))
        ghost = self.make_user('ghost', is_active=False)
        self.submit(ghost, self.make_problem('easy'))
        self.assertIsNone(self.row_for('ghost'))


class RankingTests(LeaderboardTestBase):
    def test_order_points_then_solved_then_account_age(self):
        now = timezone.now()
        # 50 pts from 1 hard  vs 50 pts from 5 easy -> more solved wins
        hard1 = self.make_user('hard1'); self.solve(hard1, hard=1)
        easy5 = self.make_user('easy5'); self.solve(easy5, easy=5)
        top = self.make_user('top');     self.solve(top, hard=2)
        # exact tie (5 easy) -> older account first
        old = self.make_user('old_acct'); self.solve(old, easy=5)
        User.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=30))
        names = [r['user__user_name'] for r in services.leaderboard_queryset()]
        self.assertEqual(names, ['top', 'old_acct', 'easy5', 'hard1'])

    def test_standing_rank_matches_list_position(self):
        users = []
        for i, (e, m, h) in enumerate([(3, 0, 0), (0, 1, 0), (5, 2, 1), (3, 0, 0), (1, 0, 0), (0, 0, 2)]):
            u = self.make_user(f'u{i}')
            self.solve(u, e, m, h)
            users.append(u)
        listed = [r['user__user_name'] for r in services.leaderboard_queryset()]
        for pos, name in enumerate(listed, start=1):
            uid = User.objects.get(user_name=name).pk
            self.assertEqual(services.get_user_standing(uid)['rank'], pos, name)


class ViewTests(LeaderboardTestBase):
    url = property(lambda self: reverse('leaderboard:leaderboard'))

    def test_empty_state(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No one is ranked yet')

    def test_public_and_hides_private_data(self):
        u = self.make_user('pub')
        self.submit(u, self.make_problem('easy'))
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'pub')
        self.assertNotContains(r, 'pub@example.com')
        self.assertNotContains(r, 'href="/users/pub/"')  # anonymous: no profile link

    def _make_many(self, n, start=0):
        for i in range(start, start + n):
            u = self.make_user(f'user{i:03d}')
            self.submit(u, self.make_problem('easy'))

    def test_pagination_first_middle_last_and_out_of_range(self):
        self._make_many(PAGE_SIZE * 3 + 5)  # 80 users -> 4 pages
        r1 = self.client.get(self.url)
        self.assertEqual(len(r1.context['rows']), PAGE_SIZE)
        self.assertEqual(r1.context['rows'][0]['rank'], 1)
        r2 = self.client.get(self.url, {'page': 2})
        self.assertEqual(r2.context['rows'][0]['rank'], PAGE_SIZE + 1)
        r4 = self.client.get(self.url, {'page': 4})
        self.assertEqual(len(r4.context['rows']), 5)
        self.assertEqual(r4.context['rows'][-1]['rank'], PAGE_SIZE * 3 + 5)
        self.assertFalse(r4.context['page_obj'].has_next())
        r99 = self.client.get(self.url, {'page': 99})   # clamps to last page
        self.assertEqual(r99.context['page_obj'].number, 4)
        rbad = self.client.get(self.url, {'page': 'abc'})  # falls back to page 1
        self.assertEqual(rbad.context['page_obj'].number, 1)

    def test_current_user_highlighted_on_page(self):
        me = self.make_user('me')
        self.solve(me, hard=1)
        self.client.force_login(me)
        r = self.client.get(self.url)
        self.assertContains(r, 'lb-row-me')
        self.assertContains(r, 'href="/users/me/"')
        self.assertIsNone(r.context['my_standing'])

    def test_current_user_off_page_gets_rank_strip(self):
        self._make_many(PAGE_SIZE + 10)            # everyone: 10 pts
        me = self.make_user('zz_me')               # newest account, 10 pts -> last
        self.submit(me, self.make_problem('easy'))
        self.client.force_login(me)
        r = self.client.get(self.url)              # page 1
        st = r.context['my_standing']
        self.assertEqual(st['rank'], PAGE_SIZE + 11)
        self.assertEqual(st['page'], 2)
        self.assertContains(r, 'Go to my position')
        self.assertNotContains(r, 'lb-row-me')
        # ...and their row is highlighted on the page the link points to
        r2 = self.client.get(self.url, {'page': st['page']})
        self.assertContains(r2, 'lb-row-me')

    def test_signed_in_user_with_no_points_sees_unranked(self):
        me = self.make_user('fresh')
        self.client.force_login(me)
        r = self.client.get(self.url)
        self.assertContains(r, 'Unranked')

    def test_query_count_does_not_grow_with_users(self):
        self._make_many(PAGE_SIZE)
        with self.assertNumQueries(2):          # total count + one page of rows
            self.client.get(self.url)
        self._make_many(PAGE_SIZE * 3, start=PAGE_SIZE)
        with self.assertNumQueries(2):          # unchanged with 4x the users
            self.client.get(self.url)

    def test_username_search_is_case_insensitive_and_supports_clear(self):
        user = self.make_user('SearchUser')
        self.submit(user, self.make_problem('easy'))
        found = self.client.get(self.url, {'q': 's'})
        self.assertContains(found, 'SearchUser')
        missing = self.client.get(self.url, {'q': 'unknown'})
        self.assertContains(missing, 'User not found')
        restored = self.client.get(self.url)
        self.assertContains(restored, 'SearchUser')

    def test_period_tabs_filter_recent_rankings(self):
        now = timezone.now()
        old_user = self.make_user('old_user')
        recent_user = self.make_user('recent_user')
        self.submit(old_user, self.make_problem('easy'))
        self.submit(recent_user, self.make_problem('easy'))

        old_submission = Submission.objects.get(user=old_user)
        recent_submission = Submission.objects.get(user=recent_user)
        old_submission.submitted_at = now - timedelta(days=40)
        recent_submission.submitted_at = now - timedelta(days=2)
        old_submission.save(update_fields=['submitted_at'])
        recent_submission.save(update_fields=['submitted_at'])

        all_time = self.client.get(self.url)
        week_view = self.client.get(self.url, {'period': 'week'})
        month_view = self.client.get(self.url, {'period': 'month'})

        self.assertContains(all_time, 'old_user')
        self.assertContains(all_time, 'recent_user')
        self.assertContains(week_view, 'recent_user')
        self.assertNotContains(week_view, 'old_user')
        self.assertContains(month_view, 'recent_user')
        self.assertNotContains(month_view, 'old_user')