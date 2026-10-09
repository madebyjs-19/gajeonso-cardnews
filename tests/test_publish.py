import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import publish_common as pub
from publish_state import RunState, fingerprint, locked_state


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = '20261012'
        self.media = self.root / 'cards' / self.run
        self.media.mkdir(parents=True)
        for name in [f'card{i}.jpg' for i in range(1, 6)] + ['reel.mp4']:
            (self.media / name).write_bytes(name.encode())
        self.captions = ['IG text', 'FB text']
        self.paths = [self.root / 'ig.txt', self.root / 'fb.txt']
        for path, caption in zip(self.paths, self.captions):
            path.write_text(caption)
        self.env = patch.dict(os.environ, {'GITHUB_ACTIONS': 'test', 'GAJEONSO_DURABLE_GIT': '0', 'TELEGRAM_CHAT_ID': '123', 'IG_ACCESS_TOKEN': 'secret-ig',
                              'IG_USER_ID': 'ig', 'FB_PAGE_ACCESS_TOKEN': 'secret-fb', 'FB_PAGE_ID': 'fb'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.state = RunState(self.root, self.run)
        self.state.data['approval'] = {'status': 'approved', 'chat_id': '123',
                                      'fingerprint': fingerprint(self.root, self.run, self.captions)}
        self.state.save()

    def runner(self, fn=None, notify=False, reel=False):
        real_lock = locked_state
        with patch.object(pub, 'locked_state', side_effect=lambda run: real_lock(run, self.root)), \
             patch('sys.argv', ['publish.py', self.run, *map(str, self.paths)]), \
             patch.object(pub, 'call', side_effect=fn or self.api), \
             patch.object(pub.time, 'sleep'), patch.object(pub, 'verify_remote_media'), \
             patch.object(pub, 'notify', return_value=notify):
            return pub.main(reel)

    def api(self, method, path, **params):
        if method == 'GET':
            if params.get('fields') == 'status_code':
                return {'status_code': 'FINISHED'}
            return {}
        if path.endswith('video_reels'):
            if params['upload_phase'] == 'start':
                return {'video_id': 'video', 'upload_url': 'https://rupload.facebook.com/video'}
            return {'success': True}
        if path.startswith('https://rupload'):
            return {'success': True}
        return {'id': 'media'}

    def test_notification_failure_and_repeat_do_not_republish(self):
        self.assertEqual(self.runner(), 0)
        with patch.object(pub, 'instagram', side_effect=AssertionError('duplicate')), \
             patch.object(pub, 'facebook', side_effect=AssertionError('duplicate')):
            self.assertEqual(self.runner(), 0)
        data = RunState(self.root, self.run).data
        self.assertEqual(data['channels']['ig_card']['status'], 'success')
        self.assertEqual(data['channels']['fb_card']['status'], 'success')
        self.assertEqual(len(RunState(self.root, self.run).matching_rows()), 1)

    def test_lost_publish_response_blocks_only_failed_channel(self):
        calls = []
        def api(method, path, **params):
            calls.append(path)
            if path.endswith('media_publish'):
                raise TimeoutError('secret-ig must never be saved')
            return self.api(method, path, **params)
        self.assertEqual(self.runner(api), 1)
        data = RunState(self.root, self.run).data
        self.assertEqual(data['channels']['ig_card']['status'], 'unknown')
        self.assertEqual(data['channels']['fb_card']['status'], 'success')
        self.assertNotIn('secret-ig', self.state.path.read_text())
        calls.clear()
        self.assertEqual(self.runner(api), 1)
        self.assertEqual(calls, [])

    def test_permalink_failure_does_not_undo_success(self):
        def api(method, path, **params):
            if params.get('fields') in ('permalink', 'permalink_url'):
                raise TimeoutError()
            return self.api(method, path, **params)
        self.assertEqual(self.runner(api), 0)
        self.assertEqual(RunState(self.root, self.run).data['channels']['ig_card']['status'], 'success')

    def test_content_and_chat_changes_block_all_api_calls(self):
        with patch.object(pub, 'call', side_effect=AssertionError('must not publish')):
            self.state.data['approval']['status'] = 'ready_for_approval'
            self.state.save()
            self.assertEqual(self.runner(), 1)
        self.state.data['approval']['status'] = 'approved'
        self.state.save()
        (self.media / 'card1.jpg').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.state.require_approval(self.captions)
        (self.media / 'card1.jpg').write_bytes(b'card1.jpg')
        with patch.dict(os.environ, {'TELEGRAM_CHAT_ID': '456'}), self.assertRaises(ValueError):
            self.state.require_approval(self.captions)

    def test_process_crash_marker_survives(self):
        self.state.set_channel('ig_card', 'publishing', container_id='container')
        loaded = RunState(self.root, self.run)
        self.assertEqual(loaded.data['channels']['ig_card']['status'], 'publishing')
        with patch.object(pub, 'instagram', side_effect=AssertionError('duplicate')):
            self.assertEqual(self.runner(), 1)

    def test_reels_are_independent_and_fb_acknowledgement_is_submitted(self):
        self.state.set_channel('ig_card', 'success', media_id='card')
        self.assertEqual(self.runner(reel=True), 0)
        state = RunState(self.root, self.run)
        self.assertEqual(state.data['channels']['ig_reel']['status'], 'success')
        self.assertEqual(state.data['channels']['fb_reel']['status'], 'submitted')
        with patch.object(pub, 'call', side_effect=AssertionError('duplicate')):
            self.assertEqual(self.runner(reel=True), 0)

    def test_run_lock_blocks_concurrent_invocation(self):
        with locked_state(self.run, self.root):
            with self.assertRaises(ValueError):
                with locked_state(self.run, self.root):
                    pass

    def test_legacy_success_and_canonical_row(self):
        self.state.path.unlink()
        self.state.log.write_text('Header\n20261012 | Topic | B | navy | table | 승인됨\n'
                                  '20261012 | Topic | B | navy | table | IG 발행 성공 · FB 릴스 요청 완료\n'
                                  '20261013 | keep this\n')
        state = RunState(self.root, self.run)
        self.assertEqual(state.data['channels']['ig_card']['status'], 'legacy_success')
        self.assertEqual(state.data['channels']['fb_reel']['status'], 'legacy_success')
        state.save()
        self.assertEqual(len(state.matching_rows()), 1)
        self.assertIn('20261013 | keep this', state.log.read_text())


    def test_hosted_bytes_must_match_approved_content(self):
        def response(url, **kwargs):
            return io.BytesIO((self.media / url.rsplit('/', 1)[-1]).read_bytes())
        with patch.object(pub.urllib.request, 'urlopen', side_effect=response):
            pub.verify_remote_media(self.state, False)
            pub.verify_remote_media(self.state, True)
        with patch.object(pub.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
            with self.assertRaises(ValueError):
                pub.verify_remote_media(self.state, False)

    def test_invalid_approval_callback_and_cancel(self):
        from publish_state import main
        args = ['state.py', 'prepare', self.run, '--ig-caption', str(self.paths[0]),
                '--fb-caption', str(self.paths[1])]
        with patch('publish_state.ROOT', self.root), \
             patch('publish_state.locked_state', side_effect=lambda run: locked_state(run, self.root)), \
             patch('sys.argv', args), patch('builtins.print'):
            self.assertEqual(main(), 0)
            key = RunState(self.root, self.run).data['approval']['key']
            approve = ['state.py', 'approve', self.run, '--approval-key', key,
                       '--chat-id', '999', '--callback-id', 'actual-callback']
            with patch('sys.argv', approve):
                self.assertEqual(main(), 1)
            self.assertEqual(RunState(self.root, self.run).data['approval']['status'], 'ready_for_approval')
            approve[6] = '123'
            with patch('sys.argv', approve):
                self.assertEqual(main(), 0)
            self.assertEqual(RunState(self.root, self.run).data['approval']['status'], 'approved')
            with patch('sys.argv', approve):
                self.assertEqual(main(), 1)  # Consumed callback cannot approve twice.

    def test_failure_before_visible_publish_can_retry(self):
        def broken(method, path, **params):
            if path == '/ig/media':
                raise TimeoutError()
            return self.api(method, path, **params)
        self.assertEqual(self.runner(broken), 1)
        self.assertEqual(RunState(self.root, self.run).data['channels']['ig_card']['status'], 'failed')
        with patch.object(pub, 'facebook', side_effect=AssertionError('FB already successful')):
            self.assertEqual(self.runner(), 0)

    def test_corrupt_state_is_not_reset(self):
        self.state.path.write_text('{invalid')
        with self.assertRaises(ValueError):
            RunState(self.root, self.run)
        self.assertEqual(self.state.path.read_text(), '{invalid')

    def test_projection_still_blocks_if_state_is_lost(self):
        self.state.set_channel('ig_card', 'unknown')
        self.state.set_channel('fb_card', 'success', media_id='published-id')
        self.state.path.unlink()
        state = RunState(self.root, self.run)
        self.assertEqual(state.data['channels']['ig_card']['status'], 'unknown')
        self.assertEqual(state.data['channels']['fb_card']['status'], 'success')


if __name__ == '__main__':
    unittest.main()
