import io
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from zoneinfo import ZoneInfo

import ai_efficiency as efficiency
import content_pipeline as pipeline
import gemini_client as ai
from git_checkpoint import CheckpointError
from test_automation import sample_content


def reply(value):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return io.BytesIO(json.dumps({'candidates': [{'finishReason': 'STOP',
        'content': {'parts': [{'text': text}]}}]}).encode())


class EfficiencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for target, value in [('automation/content_prompt.md', 'brand'),
                              ('log/ig-card-news-log.md', 'history')]:
            path = self.root / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        for patcher in [patch.object(ai.time, 'sleep'),
                        patch.object(ai, '_last_request', None),
                        patch.dict(ai.os.environ, {'GEMINI_API_KEY': 'private-key',
                                                   'GITHUB_ACTIONS': 'test', 'GAJEONSO_DURABLE_GIT': '0'})]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def session(self):
        return efficiency.Session(self.root, '20261012')

    def test_success_is_reused_across_process_sessions_and_changed_input_is_not(self):
        for text, expected_calls in [('first', 1), ('first', 0), ('changed', 1)]:
            token = efficiency.ACTIVE.set(self.session())
            try:
                with patch.object(ai.urllib.request, 'urlopen', return_value=reply('done')) as opened:
                    self.assertEqual(ai.response([{'role': 'user', 'content': text}]), 'done')
                    self.assertEqual(opened.call_count, expected_calls)
            finally:
                efficiency.ACTIVE.reset(token)

    def test_transient_attempts_count_and_budget_stops_before_http(self):
        token = efficiency.ACTIVE.set(self.session())
        self.addCleanup(efficiency.ACTIVE.reset, token)
        error = urllib.error.HTTPError(ai.BASE, 503, 'secret', None, None)
        with patch.object(efficiency, 'DAILY_REQUEST_BUDGET', 2), \
             patch.object(ai.urllib.request, 'urlopen', side_effect=error) as opened:
            with self.assertRaises(efficiency.QuotaPause):
                ai.response([{'role': 'user', 'content': 'draft'}])
            self.assertEqual(opened.call_count, 2)
        path = next((self.root / 'log/ai-budget').glob('*.json'))
        self.assertEqual(json.loads(path.read_text())['requests'], 2)

    def test_checkpoint_failure_prevents_request(self):
        token = efficiency.ACTIVE.set(self.session())
        self.addCleanup(efficiency.ACTIVE.reset, token)
        with patch.object(efficiency, 'checkpoint', side_effect=CheckpointError()), \
             patch.object(ai.urllib.request, 'urlopen') as opened:
            with self.assertRaises(CheckpointError):
                ai.response([{'role': 'user', 'content': 'draft'}])
            opened.assert_not_called()

    def test_quota_details_are_classified_without_leaking_raw_body(self):
        for quota, kind in [('GenerateRequestsPerDayPerProjectPerModel', 'daily'),
                            ('GenerateRequestsPerMinutePerProjectPerModel', 'minute'),
                            ('', 'unknown')]:
            body = {'error': {'message': 'private-key', 'details': [
                {'violations': [{'quotaId': quota}]}]}}
            error = urllib.error.HTTPError(ai.BASE, 429, 'private-key', None,
                                          io.BytesIO(json.dumps(body).encode()))
            with patch.object(ai.urllib.request, 'urlopen', side_effect=error) as opened:
                with self.assertRaises(efficiency.QuotaPause) as raised:
                    ai.response([{'role': 'user', 'content': 'draft'}])
                self.assertEqual(raised.exception.kind, kind)
                self.assertNotIn('private-key', str(raised.exception))
                self.assertEqual(opened.call_count, 1)

    def test_daily_pause_ends_on_pacific_date_change(self):
        with patch.object(efficiency, 'now_pacific', return_value=datetime(2026, 10, 11, 23, 59, tzinfo=ZoneInfo('America/Los_Angeles'))):
            session = self.session()
            session.pause('daily')
            with self.assertRaises(efficiency.QuotaPause):
                session.reserve()
        with patch.object(efficiency, 'now_pacific', return_value=datetime(2026, 10, 12, 0, 3, tzinfo=ZoneInfo('America/Los_Angeles'))):
            self.session().reserve()

    def test_render_failure_resumes_without_repeating_draft_or_fact_review(self):
        sources = [{'source_url': 'https://www.samsung.com/sec/', 'text': 'official'}]
        with patch.object(pipeline, 'ROOT', self.root), \
             patch.object(pipeline, 'recent_sources', return_value=(sources, [])) as retrieve, \
             patch.object(pipeline, 'recheck', return_value=sources), \
             patch.object(pipeline, 'render_content', side_effect=[ValueError('renderer'), 'done']), \
             patch.object(ai.urllib.request, 'urlopen', side_effect=[reply(sample_content()), reply({'passed': True, 'issues': []})]) as opened:
            with self.assertRaisesRegex(ValueError, 'renderer'):
                pipeline.prepare_content('20261012')
            (self.root / 'log/ig-card-news-log.md').write_text('changed operational history')
            self.assertEqual(pipeline.prepare_content('20261012'), 'done')
            self.assertEqual(opened.call_count, 2)
            self.assertEqual(retrieve.call_count, 1)


if __name__ == '__main__':
    unittest.main()
