from contextlib import ExitStack
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from PIL import Image

import daily_automation as daily
import prepared_content as prepared
import publish_state as ps
from test_automation import sample_content


class PreparedTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.run = '20261012'
        self.directory = self.root / 'cards' / self.run
        self.directory.mkdir(parents=True)
        self.stack.enter_context(patch.dict(os.environ, {'GAJEONSO_DURABLE_GIT': '0', 'GITHUB_ACTIONS': 'test',
            'GAJEONSO_CONTENT_MODE': 'prepared', 'TELEGRAM_CHAT_ID': '123', 'TELEGRAM_BOT_TOKEN': 'test'}))
        content = sample_content()
        brief = {k: content[k] for k in ('topic', 'type', 'facts', 'warnings', 'reason', 'candidates')}
        brief.update(cover='navy', card_types=['table', 'checklist', 'steps'], source_method='chatgpt_reviewed',
                     fact_qa={'passed': True}, visual_qa={'passed': True})
        for name, value in [('content.json', content), ('brief.json', brief)]:
            (self.directory / name).write_text(json.dumps(value, ensure_ascii=False))
        for platform in ('ig', 'fb'):
            (self.directory / f'caption_{platform}.txt').write_text(content[f'caption_{platform}'])
        for i in range(1, 6):
            Image.new('RGB', (1080, 1350)).save(self.directory / f'card{i}.jpg')
        (self.directory / 'reel.mp4').write_bytes(b'video')
        self.review = dict(version=1, run=self.run, reviewer='ChatGPT', fact_review=True, visual_review=True,
                           inspected_cards=[1,2,3,4,5], checked_at='2026-10-12T18:00:00+09:00', notes=['Reviewed sources and all five images'])
        self.sign()

    def sign(self):
        self.review['sha256'] = {name: hashlib.sha256((self.directory / name).read_bytes()).hexdigest() for name in prepared.FILES}
        (self.directory / 'review.json').write_text(json.dumps(self.review))

    def bind_worker(self):
        self.stack.enter_context(patch.object(daily, 'ROOT', self.root))
        self.stack.enter_context(patch.object(daily, 'locked_state', side_effect=lambda run: ps.locked_state(run, self.root)))
        self.stack.enter_context(patch.object(daily, 'now_korea', return_value=datetime(2026,10,12,18,tzinfo=ZoneInfo('Asia/Seoul'))))

    def test_changed_media_and_caption_fail_before_approval(self):
        for name in ('card3.jpg', 'reel.mp4', 'caption_ig.txt', 'brief.json'):
            original = (self.directory / name).read_bytes()
            (self.directory / name).write_bytes(original+b'changed')
            with self.assertRaisesRegex(ValueError, 'changed after review'):
                prepared.load_prepared(self.root, self.run)
            (self.directory / name).write_bytes(original)

    def test_missing_or_incomplete_review_rejected(self):
        self.review['inspected_cards'] = [1,2,3,4]
        self.sign()
        with self.assertRaisesRegex(ValueError, 'review missing'):
            prepared.load_prepared(self.root, self.run)

    def test_caption_disagrees_even_if_manifest_updated(self):
        (self.directory/'caption_ig.txt').write_text('changed')
        self.sign()
        with self.assertRaisesRegex(ValueError, 'captions differ'):
            prepared.load_prepared(self.root, self.run)

    def test_prepare_without_gemini_does_not_fabricate_approval(self):
        self.bind_worker()
        with patch('content_pipeline.prepare_content', side_effect=AssertionError('Gemini forbidden')), \
             patch.object(daily, 'verify_remote_media'), patch.object(daily, 'send_preview') as preview:
            daily.prepare(self.run)
        state = ps.RunState(self.root, self.run).data
        self.assertEqual(state['approval']['status'], 'ready_for_approval')
        self.assertEqual(state['channels'], {})
        preview.assert_called_once_with(self.run)

    def test_prepared_delivery_resumes_after_gemini_budget_and_retry_limit(self):
        self.bind_worker()
        state = ps.RunState(self.root, self.run)
        state.data.update(recovery={'prepare_attempts': 6, 'prepare_retry_at': '2026-10-13T00:00:00+09:00'}, preparation={'status':'failed'})
        state.save()
        with patch('ai_efficiency.read', return_value={'requests':18,'paused':'daily'}), \
             patch.object(daily, 'prepare') as prep, patch.object(daily, 'poll'), patch.object(daily, 'publish') as publish:
            daily.tick(self.run)
        prep.assert_called_once_with(self.run)
        publish.assert_not_called()

    def test_existing_approval_is_never_replaced(self):
        self.bind_worker()
        for status in ('approved', 'cancelled', 'approval_timeout'):
            state = ps.RunState(self.root, self.run)
            state.data['approval'] = {'status': status, 'key':'existing'}
            state.save()
            with patch.object(daily, 'send_preview') as preview:
                daily.prepare(self.run)
            self.assertEqual(ps.RunState(self.root,self.run).data['approval']['key'], 'existing')
            preview.assert_not_called()

    def test_missing_delivery_waits_without_generating_or_spending_retries(self):
        self.bind_worker()
        (self.directory/'review.json').unlink()
        with patch.object(daily, 'prepare') as prep, patch.object(daily, 'notify', return_value=True) as notify:
            daily.tick(self.run)
            daily.tick(self.run)
        prep.assert_not_called()
        notify.assert_called_once()
        self.assertEqual(ps.RunState(self.root,self.run).data['recovery'].get('prepare_attempts',0),0)

    def test_prepared_mode_configuration_needs_no_gemini_key(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':''}):
            daily.configuration()
