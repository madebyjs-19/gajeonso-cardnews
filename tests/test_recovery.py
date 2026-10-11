from contextlib import ExitStack
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import daily_automation as daily
import publish_state as ps
import telegram_approval as tg
from automation_schedule import approval_deadline
from telegram_text import channel_result, error_text


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.run = '20261012'
        self.now = datetime(2026, 10, 12, 16, 0, tzinfo=ZoneInfo('Asia/Seoul'))
        self.stack.enter_context(patch.dict(os.environ, {'GAJEONSO_DURABLE_GIT': '0', 'GITHUB_ACTIONS': 'test'}))
        self.stack.enter_context(patch.object(daily, 'ROOT', self.root))
        self.stack.enter_context(patch.object(daily, 'locked_state', side_effect=lambda run: ps.locked_state(run, self.root)))
        self.stack.enter_context(patch.object(daily, 'now_korea', side_effect=lambda: self.now))
        self.poll = self.stack.enter_context(patch.object(daily, 'poll'))
        self.notify = self.stack.enter_context(patch.object(daily, 'notify', return_value=True))
        self.posts = self.stack.enter_context(patch.object(daily.subprocess, 'run'))
        self.prep = self.stack.enter_context(patch.object(daily, 'prepare', side_effect=self.ready))

    def state(self):
        return ps.RunState(self.root, self.run)

    def ready(self, run):
        state = self.state()
        state.data['approval'] = {'status': 'ready_for_approval', 'message_id': 42,
                                  'expires_at': (self.now + timedelta(minutes=60)).isoformat()}
        state.save()

    def test_delayed_first_tick_prepares_in_afternoon_without_publishing(self):
        daily.tick(self.run)
        self.prep.assert_called_once_with(self.run)
        self.posts.assert_not_called()
        self.assertEqual(self.state().data['approval']['status'], 'ready_for_approval')
        daily.tick(self.run)
        self.assertEqual(self.prep.call_count, 1)

    def test_out_of_order_ticks_resume_and_approved_work_reaches_publisher(self):
        self.ready(self.run)
        state = self.state()
        state.data['approval']['status'] = 'approved'
        state.save()
        with patch.object(daily, 'publish') as publish:
            daily.tick(self.run)
            publish.assert_called_once_with(self.run)
            daily.tick(self.run)  # retry cooldown
            self.assertEqual(publish.call_count, 1)
        self.prep.assert_not_called()

    def test_approved_work_is_not_published_before_eleven(self):
        self.now = self.now.replace(hour=10)
        self.ready(self.run)
        state = self.state()
        state.data['approval']['status'] = 'approved'
        state.save()
        with patch.object(daily, 'publish') as publish:
            daily.tick(self.run)
            publish.assert_not_called()

    def test_preparation_starts_at_six_but_not_before(self):
        self.now = self.now.replace(hour=5, minute=57)
        daily.tick(self.run)
        self.prep.assert_not_called()
        self.now = self.now.replace(hour=6, minute=7)
        daily.tick(self.run)
        self.prep.assert_called_once_with(self.run)
        self.posts.assert_not_called()

    def test_early_approval_stays_alive_and_publishes_at_eleven(self):
        self.now = self.now.replace(hour=6, minute=10)
        self.ready(self.run)
        state = self.state()
        state.data['approval']['status'] = 'approved'
        state.data['approval']['expires_at'] = approval_deadline(self.now).isoformat()
        state.save()
        elapsed = [0]
        target = self.now.replace(hour=11)
        def advance(seconds):
            self.assertEqual(seconds, 20)
            delta = min(timedelta(hours=1), target - self.now)
            self.now += delta
            elapsed[0] += delta.total_seconds()
        published_at = []
        def complete(run):
            published_at.append(self.now)
            state = self.state()
            state.data['channels'] = {c: {'status': 'success'} for c in ps.CHANNELS}
            state.save()
        with patch.object(daily.time, 'monotonic', side_effect=lambda: elapsed[0]), \
             patch.object(daily.time, 'sleep', side_effect=advance), \
             patch.object(daily, 'publish', side_effect=complete):
            daily.run_tick(self.run)
        self.assertEqual(published_at, [target])
        self.prep.assert_not_called()

    def test_early_pending_preview_remains_approvable_in_late_morning(self):
        self.now = self.now.replace(hour=6, minute=10)
        self.ready(self.run)
        state = self.state()
        state.data['approval'].update(key='key', chat_id='123',
                                     expires_at=approval_deadline(self.now).isoformat())
        state.save()
        self.now = self.now.replace(hour=9, minute=30)
        callback = {'id': 'callback', 'from': {'id': 123},
                    'message': {'chat': {'id': 123}, 'message_id': 42},
                    'data': 'approve:' + self.run + ':key'}
        with patch.object(tg, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = self.now
            self.assertTrue(tg.apply_callback(callback, state, '123', '123'))
        self.assertEqual(self.state().data['approval']['status'], 'approved')
        self.posts.assert_not_called()

    def test_unanswered_preview_expires_from_delivery_not_eleven(self):
        self.ready(self.run)
        daily.publish(self.run)
        self.assertEqual(self.state().data['approval']['status'], 'ready_for_approval')
        self.now += timedelta(minutes=61)
        daily.publish(self.run)
        self.assertEqual(self.state().data['approval']['status'], 'approval_timeout')
        self.posts.assert_not_called()
        self.assertIn('승인 시간 만료', self.notify.call_args.args[0])
        self.assertNotIn('approval_timeout', self.notify.call_args.args[0])

    def test_cancelled_work_is_not_recreated(self):
        state = self.state()
        state.data['approval']['status'] = 'cancelled'
        state.save()
        daily.tick(self.run)
        self.prep.assert_not_called()
        self.posts.assert_not_called()
        self.assertIn('승인 취소', self.notify.call_args.args[0])

    def test_preparation_retries_are_bounded_and_reported(self):
        self.prep.side_effect = RuntimeError('temporary')
        for _ in range(daily.MAX_PREP_ATTEMPTS):
            with self.assertRaises(RuntimeError):
                daily.tick(self.run)
            daily.tick(self.run)  # cooldown: no additional generation
            self.now += timedelta(minutes=31)
        daily.tick(self.run)
        self.assertEqual(self.prep.call_count, 6)
        self.assertIn('여섯 차례', self.notify.call_args.args[0])

    def test_old_scheduled_phases_use_current_recovery_loop(self):
        for phase in ('prepare', 'approval', 'publish'):
            with self.subTest(phase=phase), \
                 patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'schedule'}), \
                 patch.object(daily, 'configuration'), patch.object(daily, 'verify_bot'), \
                 patch.object(daily, 'run_tick') as run_tick, \
                 patch.object(daily, 'publish') as publish, \
                 patch('sys.argv', ['daily.py', phase, '--run', self.run]):
                self.assertEqual(daily.main(), 0)
                run_tick.assert_called_once_with(self.run)
                self.prep.assert_not_called()
                self.poll.assert_not_called()
                publish.assert_not_called()

    def test_old_prepare_rerun_cannot_bypass_retry_cooldown(self):
        self.prep.side_effect = RuntimeError('temporary')
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'schedule'}), \
             patch.object(daily, 'configuration'), patch.object(daily, 'verify_bot'), \
             patch('sys.argv', ['daily.py', 'prepare', '--run', self.run]):
            self.assertEqual(daily.main(), 1)
            self.assertEqual(daily.main(), 0)
        self.prep.assert_called_once_with(self.run)
        self.assertEqual(self.state().data['recovery']['prepare_attempts'], 1)
        self.posts.assert_not_called()

    def test_manual_phases_and_read_only_check_are_preserved(self):
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'workflow_dispatch'}), \
             patch.object(daily, 'configuration'), patch.object(daily, 'verify_bot'), \
             patch.object(daily, 'run_tick') as run_tick, \
             patch.object(daily, 'publish') as publish, \
             patch('sys.argv', ['daily.py', 'publish', '--run', self.run]):
            self.assertEqual(daily.main(), 0)
            publish.assert_called_once_with(self.run)
            run_tick.assert_not_called()
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'schedule'}), \
             patch.object(daily, 'check') as check, \
             patch.object(daily, 'run_tick') as run_tick, \
             patch('sys.argv', ['daily.py', 'check']):
            self.assertEqual(daily.main(), 0)
            check.assert_called_once()
            run_tick.assert_not_called()

    def test_scheduled_recovery_still_rejects_stale_run(self):
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'schedule'}), \
             patch.object(daily, 'configuration'), patch.object(daily, 'verify_bot'), \
             patch.object(daily, 'run_tick') as run_tick, \
             patch('sys.argv', ['daily.py', 'prepare', '--run', '20261011']):
            self.assertEqual(daily.main(), 1)
            run_tick.assert_not_called()
        self.prep.assert_not_called()
        self.posts.assert_not_called()

    def test_live_receiver_observes_approval_without_another_cron(self):
        def approve_after_sleep(seconds):
            self.assertEqual(seconds, 20)
            self.now += timedelta(seconds=seconds)
            state = self.state()
            state.data['approval']['status'] = 'approved'
            state.save()
        with patch.object(daily.time, 'sleep', side_effect=approve_after_sleep), \
             patch.object(daily, 'publish') as publish:
            daily.run_tick(self.run)
        self.prep.assert_called_once()
        # First call only observes pending approval; second sees real saved approval.
        self.assertEqual(publish.call_count, 2)
        self.assertEqual(self.state().data['approval']['status'], 'approved')

    def test_live_receiver_expires_and_stops(self):
        self.ready(self.run)
        def advance(seconds):
            self.now += timedelta(minutes=61)
        with patch.object(daily.time, 'sleep', side_effect=advance) as sleep:
            daily.run_tick(self.run)
        sleep.assert_called_once()
        self.assertEqual(self.state().data['approval']['status'], 'approval_timeout')
        self.posts.assert_not_called()

    def test_partial_delivery_failure_does_not_destroy_ready_state(self):
        self.ready(self.run)
        with patch.object(daily, 'configuration'), patch.object(daily, 'verify_bot'), \
             patch.object(daily, 'tick', side_effect=RuntimeError('secret-value')), \
             patch('sys.argv', ['daily.py', 'tick', '--run', self.run]):
            self.assertEqual(daily.main(), 1)
        self.assertEqual(self.state().data['approval']['status'], 'ready_for_approval')
        self.assertNotIn('secret-value', self.notify.call_args.args[0])

    def test_midnight_rollover_never_publishes_old_run(self):
        def cross_midnight(run):
            self.ready(run)
            self.now += timedelta(days=1)
        self.prep.side_effect = cross_midnight
        daily.tick(self.run)
        self.poll.assert_not_called()
        self.posts.assert_not_called()

    def test_unsafe_channel_states_are_not_treated_as_retryable(self):
        self.ready(self.run)
        state = self.state()
        state.data['approval']['status'] = 'approved'
        state.data['channels'] = {c: {'status': 'unknown'} for c in ps.CHANNELS}
        state.data['recovery'] = {'publish_attempts': 3}
        state.save()
        with patch.object(daily, 'publish') as publish:
            daily.tick(self.run)
        # Publisher is permitted to report blocked channels; its existing tests
        # prove it never repeats a visible request for these channel states.
        publish.assert_called_once()
        self.assertEqual(self.state().data['recovery']['publish_attempts'], 3)


class KoreanTests(unittest.TestCase):
    def test_errors_never_forward_arbitrary_secrets(self):
        for exc in (ValueError('SECRET raw URL'), RuntimeError('SECRET body')):
            self.assertNotIn('SECRET', error_text(exc))
            self.assertIn('오류', error_text(exc))
        self.assertEqual(channel_result('ig_card', {'status': 'success'}), '인스타그램 카드: 발행 완료')
        self.assertIn('확인 필요', channel_result('fb_reel', {'status': 'unknown'}))

    def test_expired_callback_does_not_authorize_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = ps.RunState(Path(tmp), '20261012')
            state.data['approval'] = {'status': 'ready_for_approval', 'key': 'key',
                'chat_id': '123', 'message_id': 42, 'expires_at': '2000-01-01T00:00:00+09:00'}
            callback = {'id': 'callback', 'from': {'id': 123},
                'message': {'chat': {'id': 123}, 'message_id': 42}, 'data': 'approve:20261012:key'}
            self.assertFalse(tg.apply_callback(callback, state, '123', '123'))
            self.assertEqual(state.data['approval']['status'], 'ready_for_approval')

    def test_preview_fields_and_buttons_are_korean(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            stack.enter_context(patch.dict(os.environ, {'GAJEONSO_DURABLE_GIT': '0', 'GITHUB_ACTIONS': 'test'}))
            state = ps.RunState(root, '20261012')
            state.data['approval'] = {'status': 'ready_for_approval', 'key': 'key'}
            state.save()
            folder = root / 'cards' / state.run
            folder.mkdir(parents=True)
            (folder / 'brief.json').write_text(json.dumps({'topic': '구매 기준', 'type': 'B', 'cover': 'navy',
                'card_types': ['table', 'checklist', 'steps'], 'facts': [{'claim': '공식 정보',
                'source_url': 'https://example.com', 'verification': '공식 확인'}], 'warnings': ['일러스트 사용']}))
            for p in ('ig', 'fb'):
                (folder / f'caption_{p}.txt').write_text('한글 본문')
            stack.enter_context(patch.object(tg, 'ROOT', root))
            stack.enter_context(patch.object(tg, 'locked_state', side_effect=lambda run: ps.locked_state(run, root)))
            stack.enter_context(patch.object(tg, 'verify_bot', return_value=('123', '123')))
            bot = stack.enter_context(patch.object(tg, 'bot', return_value={'message_id': 42}))
            clock = stack.enter_context(patch.object(tg, 'datetime', wraps=datetime))
            clock.now.return_value = datetime(2026, 10, 12, 6, 10, tzinfo=ZoneInfo('Asia/Seoul'))
            tg.send_preview(state.run)
            text = '\n'.join(c.kwargs.get('text', '') for c in bot.call_args_list)
            self.assertIn('기준표, 확인 목록, 절차', text)
            self.assertIn('출처:', text)
            for forbidden in ('source_url', 'verification', 'checklist', 'Instagram', 'navy'):
                self.assertNotIn(forbidden, text)
            self.assertIn('expires_at', ps.RunState(root, state.run).data['approval'])
            self.assertIn('승인 기한: 10월 12일 12:00', text)
            self.assertEqual(ps.RunState(root, state.run).data['approval']['expires_at'],
                             '2026-10-12T12:00:00+09:00')


if __name__ == '__main__':
    unittest.main()
