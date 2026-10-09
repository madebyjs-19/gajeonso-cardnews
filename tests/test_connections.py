import io
import os
import unittest
from unittest.mock import patch

import daily_automation as daily
import telegram_approval as tg


class ConnectionTests(unittest.TestCase):
    def test_bad_numeric_ids_name_the_setting_without_echoing_value(self):
        for field in ('TELEGRAM_CHAT_ID', 'TELEGRAM_APPROVER_ID'):
            env = {'TELEGRAM_CHAT_ID': '123', 'TELEGRAM_APPROVER_ID': '123', field: 'private-value'}
            with patch.dict(os.environ, env), patch.object(tg, 'bot') as bot:
                with self.assertRaisesRegex(ValueError, field) as error:
                    tg.verify_bot()
            self.assertNotIn('private-value', str(error.exception))
            bot.assert_not_called()

    def test_private_chat_fallback_and_group_requires_approver(self):
        with patch.dict(os.environ, {'TELEGRAM_CHAT_ID': '123', 'TELEGRAM_APPROVER_ID': ''}), patch.object(tg, 'bot', return_value={}):
            self.assertEqual(tg.verify_bot(), ('123', '123'))
        with patch.dict(os.environ, {'TELEGRAM_CHAT_ID': '-100123', 'TELEGRAM_APPROVER_ID': ''}):
            with self.assertRaisesRegex(ValueError, 'Group chats require'):
                tg.verify_bot()

    def test_failure_does_not_prevent_other_read_checks_or_leak_errors(self):
        output = io.StringIO()
        with patch.dict(os.environ, {'IG_USER_ID': '123', 'IG_ACCESS_TOKEN': 'secret', 'FB_PAGE_ID': '456', 'FB_PAGE_ACCESS_TOKEN': 'secret'}), \
             patch.object(daily, 'configuration'), patch.object(daily, 'verify_bot', side_effect=ValueError('TELEGRAM_APPROVER_ID must be a positive numeric user ID')), \
             patch('publish_common.call', side_effect=[RuntimeError('secret error body'), {'id': '456'}]) as meta, \
             patch('gemini_client.check_model') as gemini, patch('sys.stdout', output):
            with self.assertRaisesRegex(ValueError, 'Telegram, Instagram'):
                daily.check()
        gemini.assert_called_once()
        self.assertEqual(meta.call_count, 2)
        self.assertNotIn('secret error body', output.getvalue())
        self.assertIn('Gemini: connection read check passed', output.getvalue())
        self.assertIn('Facebook: connection read check passed', output.getvalue())


if __name__ == '__main__':
    unittest.main()
