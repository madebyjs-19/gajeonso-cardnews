from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import content_pipeline as content
import manual_test as manual
from publish_state import RunState
from test_automation import sample_content


class ManualTests(unittest.TestCase):
    def test_operator_sources_and_store_exception_do_not_change_daily_defaults(self):
        plan = sample_content()
        plan['facts'][0]['source_url'] = 'operator:20261010a'
        plan['caption_ig'] += '\n롯데하이마트 정왕역점'
        with self.assertRaises(ValueError):
            content.validate_content(plan)
        with self.assertRaises(ValueError):
            content.validate_content(plan, operator_source='operator:20261010a')
        content.validate_content(plan, operator_source='operator:20261010a', allow_store_branding=True)
        plan['facts'][0]['source_url'] = 'operator:another-run'
        with self.assertRaises(ValueError):
            content.validate_content(plan, operator_source='operator:20261010a', allow_store_branding=True)

    def test_manual_requires_explicit_main_dispatch_and_durable_state(self):
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
               'GITHUB_WORKFLOW': 'Manual gajeonso test', 'GITHUB_REF': 'refs/heads/main',
               'GAJEONSO_DURABLE_GIT': '1'}
        with patch.dict(os.environ, env):
            manual.require_workflow()
            for key, value in [('GITHUB_EVENT_NAME', 'schedule'), ('GITHUB_REF', 'refs/heads/test'),
                               ('GAJEONSO_DURABLE_GIT', '0'), ('GITHUB_WORKFLOW', 'Daily gajeonso cardnews')]:
                with patch.dict(os.environ, {key: value}):
                    with self.assertRaises(ValueError):
                        manual.require_workflow()

    def test_stale_unsuffixed_or_changed_requests_are_refused(self):
        now = datetime(2026, 10, 10, 17, tzinfo=ZoneInfo('Asia/Seoul'))
        with tempfile.TemporaryDirectory() as tmp, patch.object(manual, 'ROOT', Path(tmp)), \
             patch.object(manual, 'now_korea', return_value=now):
            for run in ('20261009a', '20261010', '../20261010a'):
                with self.assertRaises(ValueError):
                    manual.request_plan(run)
            plan = {'run': '20261010a', 'mode': 'manual_test', 'operator_source':
                    {'reference': 'operator:20261010a', 'text': 'actual operator brief'},
                    'content': sample_content()}
            plan['content']['facts'][0]['source_url'] = 'operator:20261010a'
            directory = Path(tmp) / 'automation' / 'manual'
            directory.mkdir(parents=True)
            path = directory / '20261010a.json'
            path.write_text(json.dumps(plan))
            _, first = manual.request_plan('20261010a')
            plan['content']['caption_ig'] += '\nChanged caption'
            path.write_text(json.dumps(plan))
            _, second = manual.request_plan('20261010a')
            self.assertNotEqual(first, second)
            state = RunState(tmp, '20261010a')
            state.data['request_hash'] = first
            with patch.object(manual, 'locked_state') as locked, patch.object(manual, 'render_content') as render:
                locked.return_value.__enter__.return_value = state
                with self.assertRaises(ValueError):
                    manual.prepare('20261010a', plan, second)
                render.assert_not_called()

    def test_publish_waits_for_real_approval_without_sending_media(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {'GITHUB_ACTIONS': 'test', 'GAJEONSO_DURABLE_GIT': '0'}):
            state = RunState(tmp, '20261010a')
            state.data.update(manual_test=True, request_hash='request', preparation={'status': 'ready'})
            state.data['approval'] = {'status': 'ready_for_approval'}
            with patch('daily_automation.locked_state') as locked, patch('daily_automation.poll'), \
                 patch('daily_automation.notify', return_value=True), patch('daily_automation.subprocess.run') as post:
                locked.return_value.__enter__.return_value = state
                manual.publish('20261010a')
                post.assert_not_called()
                self.assertEqual(state.data['approval']['status'], 'approval_timeout')


if __name__ == '__main__':
    unittest.main()
