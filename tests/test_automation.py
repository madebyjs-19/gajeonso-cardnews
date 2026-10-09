from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import content_pipeline as content
import daily_automation as daily
import telegram_approval as tg
import publish_common as pub
from git_checkpoint import CheckpointError, checkpoint
from publish_state import RunState


def sample_content():
    return {'safe_to_prepare': True, 'topic': '세탁기 구매 기준', 'type': 'B', 'reason': '구매 도움',
            'candidates': ['세탁기 구매 기준', '냉장고 용량', '청소기 선택'],
            'facts': [{'claim': '세탁기 용량 확인', 'source_url': 'https://www.samsung.com/sec/', 'verification': '공식 자료 확인'}],
            'warnings': ['제품 이미지는 일러스트'],
            'caption_ig': '정확한 수치는 모델·현장별 확인 필요\n상담문의 · 가전소\n#가전소 #가전 #세탁기 #구매 #기준 #설치 #가이드 #정보',
            'caption_fb': '카카오톡 상담 http://pf.kakao.com/_PHwrX/chat\n#가전소 #가전 #구매',
            'deck': {'cover_style': 'v2', 'cover_color': 'navy', 'cards': [
                {'type': 'product_cover', 'tag': '구매 가이드', 'title': '세탁기 구매\n무엇을 볼까?', 'subtitle': '구매 전 확인할 기준', 'image': 'illust:washer'},
                {'type': 'table', 'title': '확인 기준', 'rows': [['용량', '생활에 맞게']], 'footnote': '모델별 확인'},
                {'type': 'checklist', 'title': '구매 전 확인', 'items': ['설치 공간을 확인하세요']},
                {'type': 'steps', 'title': '확인 순서', 'steps': [['공간', '설치 공간 확인']]},
                {'type': 'cta', 'question': '우리 집 가전\n함께 알아볼까요?', 'dm': '상담문의\n가전소'}]}}


class ContentTests(unittest.TestCase):
    def test_valid_plan_and_unsafe_or_arbitrary_file_rejected(self):
        plan = sample_content()
        content.validate_content(plan)
        for change in ('unsafe', 'file', 'source', 'row', 'tags'):
            bad = deepcopy(plan)
            if change == 'unsafe': bad['safe_to_prepare'] = False
            if change == 'file': bad['deck']['cards'][0]['image'] = '/etc/passwd'
            if change == 'source': bad['facts'][0]['source_url'] = 'https://samsung.com.evil.example/'
            if change == 'row': bad['deck']['cards'][1]['rows'] = [['wrong width']]
            if change == 'tags': bad['caption_ig'] = '#가전소'
            with self.assertRaises(ValueError):
                content.validate_content(bad)

    def test_incomplete_api_response_rejected_and_no_secret_in_errors(self):
        import io
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'do-not-print'}), \
             patch.object(content.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"status":"incomplete"}')):
            with self.assertRaisesRegex(RuntimeError, 'OpenAI content request failed'):
                content.response('test', content.QA_SCHEMA)

    def test_pipeline_with_mocked_api_and_renderers(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Pillow required')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'automation').mkdir()
            (root / 'automation' / 'content_prompt.md').write_text('brand prompt')
            (root / 'log').mkdir()
            (root / 'log' / 'ig-card-news-log.md').write_text('history')
            def process(argv, **kwargs):
                work = root / 'out' / '20261012'
                if argv[1].endswith('gen_cards.py'):
                    for i in range(1, 6):
                        Image.new('RGB', (1080, 1350), 'white').save(work / f'card{i}.jpg')
                if argv[1].endswith('make_reel.py'):
                    (work / 'reel.mp4').write_bytes(b'fake-video')
                return subprocess.CompletedProcess(argv, 0)
            replies = ['research', sample_content(), 'independent fact review',
                       {'passed': True, 'issues': []}, {'passed': True, 'issues': []}]
            with patch.object(content, 'ROOT', root), patch.object(content, 'response', side_effect=replies), \
                 patch.object(content.subprocess, 'run', side_effect=process):
                brief = content.prepare_content('20261012')
            target = root / 'cards' / '20261012'
            self.assertTrue((target / 'brief.json').exists())
            self.assertTrue((target / 'caption_ig.txt').exists())
            self.assertEqual(len(list(target.glob('card*.jpg'))), 5)
            self.assertEqual(brief['card_types'], ['table', 'checklist', 'steps'])


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = RunState(self.root, '20261012')
        self.state.data['approval'] = {'status': 'ready_for_approval', 'key': 'key', 'chat_id': '123', 'message_id': 42}
        self.callback = {'id': 'callback', 'from': {'id': 123}, 'message': {'chat': {'id': 123}, 'message_id': 42},
                         'data': 'approve:20261012:key'}

    def test_only_correct_user_chat_key_run_message_is_accepted(self):
        for field in ('user', 'chat', 'key', 'run', 'message'):
            callback = deepcopy(self.callback)
            if field == 'user': callback['from']['id'] = 456
            if field == 'chat': callback['message']['chat']['id'] = 456
            if field == 'key': callback['data'] = 'approve:20261012:stale'
            if field == 'run': callback['data'] = 'approve:20261013:key'
            if field == 'message': callback['message']['message_id'] = 99
            self.assertFalse(tg.apply_callback(callback, self.state, '123', '123'))
        self.assertTrue(tg.apply_callback(self.callback, self.state, '123', '123'))
        self.assertEqual(RunState(self.root, '20261012').data['approval']['status'], 'approved')
        self.assertFalse(tg.apply_callback(self.callback, self.state, '123', '123'))

    def test_cancel_and_webhook_refusal(self):
        self.callback['data'] = 'cancel:20261012:key'
        self.assertTrue(tg.apply_callback(self.callback, self.state, '123', '123'))
        self.assertEqual(self.state.data['approval']['status'], 'cancelled')
        with patch.object(tg, 'bot', return_value={'url': 'https://existing-handler.example'}):
            with self.assertRaises(ValueError):
                tg.verify_bot()

    def test_poller_durably_saves_decision_and_offset(self):
        self.state.save()
        with patch.object(tg, 'ROOT', self.root), \
             patch.object(tg, 'verify_bot', return_value=('123', '123')), \
             patch.object(tg, 'locked_state', side_effect=lambda run: __import__('publish_state').locked_state(run, self.root)), \
             patch.object(tg, 'bot', side_effect=[[{'update_id': 7, 'callback_query': self.callback}], True]), \
             patch.object(tg, 'checkpoint'):
            self.assertEqual(tg.poll('20261012'), 8)
        self.assertEqual(RunState(self.root, '20261012').data['approval']['status'], 'approved')
        self.assertEqual(json.loads((self.root / 'log' / 'telegram-offset.json').read_text())['offset'], 8)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'work'
        self.remote = Path(self.tmp.name) / 'origin.git'
        self.root.mkdir()
        self.git(self.root, 'init', '-b', 'main')
        self.git(self.root, 'config', 'user.name', 'Test')
        self.git(self.root, 'config', 'user.email', 'test@example.invalid')
        (self.root / 'README.md').write_text('initial')
        self.git(self.root, 'add', '.')
        self.git(self.root, 'commit', '-m', 'initial')
        self.git(Path(self.tmp.name), 'init', '--bare', str(self.remote))
        self.git(self.root, 'remote', 'add', 'origin', str(self.remote))
        self.git(self.root, 'push', 'origin', 'main')

    def git(self, root, *args):
        return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()

    def test_visible_post_has_remote_marker_even_if_response_lost(self):
        state = RunState(self.root, '20261012')
        def api(*args, **kwargs):
            raw = self.git(self.remote, 'show', 'main:log/publish-state/20261012.json')
            self.assertEqual(json.loads(raw)['channels']['ig_card']['status'], 'publishing')
            raise TimeoutError()
        with patch.dict(os.environ, {'GAJEONSO_DURABLE_GIT': '1'}), patch.object(pub, 'call', side_effect=api):
            with self.assertRaises(TimeoutError):
                pub.publish_visible(state, 'ig_card', 'POST', '/ig/media_publish')
        raw = self.git(self.remote, 'show', 'main:log/publish-state/20261012.json')
        self.assertEqual(json.loads(raw)['channels']['ig_card']['status'], 'publishing')

    def test_stale_writer_cannot_publish(self):
        other = Path(self.tmp.name) / 'other'
        self.git(Path(self.tmp.name), 'clone', '-b', 'main', str(self.remote), str(other))
        with patch.dict(os.environ, {'GAJEONSO_DURABLE_GIT': '1'}):
            first = RunState(self.root, '20261012')
            first.set_channel('ig_card', 'publishing')
            stale = RunState(other, '20261012')
            with patch.object(pub, 'call', side_effect=AssertionError('must not post')):
                with self.assertRaises(CheckpointError):
                    pub.publish_visible(stale, 'ig_card', 'POST', '/ig/media_publish')

    def test_disposable_runner_without_checkpoint_is_refused(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GAJEONSO_DURABLE_GIT': '0'}):
            with self.assertRaises(CheckpointError):
                checkpoint(self.root, '20261012')


class ScheduleTests(unittest.TestCase):
    def test_old_dates_and_early_publication_are_refused(self):
        with patch.object(daily, 'configuration'), patch.object(daily, 'verify_bot'), patch.object(daily, 'notify'), \
             patch.object(daily, 'publish', side_effect=AssertionError('must not post')), \
             patch.object(daily, 'now_korea', return_value=datetime(2026, 10, 12, 10, 30, tzinfo=ZoneInfo('Asia/Seoul'))):
            for run in ('20261012', '20261011'):
                with patch('sys.argv', ['daily.py', 'publish', '--run', run]):
                    self.assertEqual(daily.main(), 1)

    def test_workflow_is_gated_serialized_and_default_manual_check(self):
        import yaml
        yaml.SafeLoader.add_constructor('tag:yaml.org,2002:bool', lambda loader, node: node.value.lower() if node.value.lower() in ('on', 'off') else node.value.lower() == 'true')
        workflow = yaml.safe_load((content.ROOT / '.github/workflows/daily-cardnews.yml').read_text())
        self.assertEqual(workflow['on']['workflow_dispatch']['inputs']['phase']['default'], 'check')
        self.assertEqual(workflow['concurrency']['group'], 'gajeonso-production')
        self.assertFalse(workflow['concurrency']['cancel-in-progress'])
        self.assertIn('GAJEONSO_ENABLED', workflow['jobs']['daily']['if'])


if __name__ == '__main__':
    unittest.main()
