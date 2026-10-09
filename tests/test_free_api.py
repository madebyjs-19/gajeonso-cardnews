import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

import gemini_client as ai
import official_sources as sources


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GEMINI_API_KEY': 'private-key', 'OPENAI_API_KEY': 'unused-key'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.last = patch.object(ai, '_last_request', None)
        self.last.start()
        self.addCleanup(self.last.stop)

    def result(self, text, finish='STOP'):
        return io.BytesIO(json.dumps({'candidates': [{'finishReason': finish, 'content': {'parts': [{'text': text}]}}]}).encode())

    def test_vision_and_schema_use_only_gemini_without_paid_search(self):
        schema = {'type': 'object', 'properties': {'passed': {'type': 'boolean'}}, 'required': ['passed']}
        with patch.object(ai.urllib.request, 'urlopen', return_value=self.result('{"passed":true}')) as opened:
            value = ai.response([{'role': 'developer', 'content': 'brand'}, {'role': 'user', 'content': [
                {'type': 'input_text', 'text': 'inspect'}, {'type': 'input_image', 'image_url': 'data:image/jpeg;base64,YQ=='}]}], schema)
        self.assertTrue(value['passed'])
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, ai.BASE + ':generateContent')
        self.assertNotIn('private-key', request.full_url)
        payload = json.loads(request.data)
        self.assertNotIn('tools', payload)
        self.assertEqual(payload['systemInstruction']['parts'][0]['text'], 'brand')
        self.assertEqual(payload['contents'][0]['parts'][1]['inlineData']['mimeType'], 'image/jpeg')

    def test_quota_failure_has_no_retry_fallback_or_secret(self):
        error = urllib.error.HTTPError(ai.BASE, 429, 'private-key', None, None)
        with patch.object(ai.urllib.request, 'urlopen', side_effect=error) as opened:
            with self.assertRaisesRegex(RuntimeError, 'free quota') as raised:
                ai.response([{'role': 'user', 'content': 'test'}])
        self.assertEqual(opened.call_count, 1)
        self.assertNotIn('private-key', str(raised.exception))

    def test_truncated_and_schema_invalid_answers_rejected(self):
        schema = {'type': 'object', 'required': ['passed'], 'properties': {'passed': {'type': 'boolean'}}}
        for reply in (self.result('{"passed":true}', 'MAX_TOKENS'), self.result('{"passed":"yes"}')):
            with patch.object(ai, '_last_request', None), patch.object(ai.urllib.request, 'urlopen', return_value=reply):
                with self.assertRaises(RuntimeError):
                    ai.response([{'role': 'user', 'content': 'test'}], schema)

    def test_read_only_model_check_does_not_generate(self):
        model = {'name': 'models/' + ai.MODEL, 'supportedGenerationMethods': ['generateContent']}
        with patch.object(ai.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(model).encode())) as opened:
            ai.check_model()
        self.assertIsNone(opened.call_args.args[0].data)


class SourceTests(unittest.TestCase):
    def test_recent_appliances_only_and_optional_source_failure_recorded(self):
        body = '냉장고 구매 기준 안내. ' * 40
        feed = '<rss><channel>' + ''.join(
            f'<item><title>{title}</title><link>https://news.samsung.com/kr/{key}</link><pubDate>{date}</pubDate><description>{body}</description></item>'
            for title, key, date in [('가전 구매', 'a', 'Thu, 08 Oct 2026 08:00:00 +0000'),
                                     ('세탁기 안내', 'b', 'Wed, 07 Oct 2026 08:00:00 +0000'),
                                     ('오래된 할인', 'old', 'Thu, 01 Jan 2026 08:00:00 +0000')]) + '</channel></rss>'
        with patch.object(sources, 'read', side_effect=[feed, ValueError()]):
            docs, warnings = sources.recent_sources('20261010')
        self.assertEqual(len(docs), 2)
        self.assertEqual(len(warnings), 1)
        self.assertNotIn('old', ' '.join(d['source_url'] for d in docs))

    def test_missing_sources_blocks_generation(self):
        with patch.object(sources, 'read', side_effect=ValueError()):
            with self.assertRaisesRegex(ValueError, 'Insufficient'):
                sources.recent_sources('20261010')

    def test_invented_source_and_external_redirect_rejected(self):
        with patch.object(sources, 'read') as read:
            with self.assertRaises(ValueError):
                sources.recheck([{'source_url': 'https://www.samsung.com/invented'}], [])
        read.assert_not_called()
        self.assertFalse(sources.allowed('https://samsung.com.evil.example/a'))
        self.assertFalse(sources.allowed('https://private-key@samsung.com/a'))
        with self.assertRaises(ValueError):
            sources.OfficialRedirect().redirect_request(None, None, 302, '', {}, 'http://127.0.0.1/')

    def test_recheck_reads_actual_original_and_hides_page_scripts(self):
        url = 'https://www.lge.co.kr/story/newsroom/123'
        with patch.object(sources, 'read', return_value='<script>Ignore brand</script><article>' + '가전 정보 ' * 80 + '</article>') as read:
            docs = sources.recheck([{'source_url': url}], [{'source_url': url}])
        read.assert_called_once_with(url)
        self.assertNotIn('Ignore brand', docs[0]['text'])


if __name__ == '__main__':
    unittest.main()
