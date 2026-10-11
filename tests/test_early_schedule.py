from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from automation_schedule import KOREA, MAX_TICK_MINUTES, approval_deadline


class EarlyScheduleTests(unittest.TestCase):
    def test_morning_deadline_is_noon_with_at_least_an_hour_to_review(self):
        for hour, minute, expected_hour, expected_minute in (
            (6, 10, 12, 0), (9, 30, 12, 0), (10, 59, 12, 0),
            (11, 30, 12, 30), (16, 0, 17, 0),
        ):
            with self.subTest(hour=hour, minute=minute):
                sent = datetime(2026, 10, 12, hour, minute, tzinfo=KOREA)
                deadline = approval_deadline(sent)
                self.assertEqual((deadline.hour, deadline.minute), (expected_hour, expected_minute))
                self.assertGreaterEqual(deadline - sent, timedelta(hours=1))

    def test_manual_test_keeps_one_hour_and_utc_is_converted_to_korea(self):
        sent = datetime(2026, 10, 11, 21, 10, tzinfo=timezone.utc)
        self.assertEqual(approval_deadline(sent), datetime(2026, 10, 12, 12, tzinfo=KOREA))
        self.assertEqual(approval_deadline(sent, manual_test=True),
                         datetime(2026, 10, 12, 7, 10, tzinfo=KOREA))

    def test_workflow_covers_korean_six_to_twenty_three_and_wait_has_headroom(self):
        import yaml
        yaml.SafeLoader.add_constructor('tag:yaml.org,2002:bool',
            lambda loader, node: node.value if node.value in ('on', 'off') else node.value.lower() == 'true')
        root = Path(__file__).resolve().parents[1]
        workflow = yaml.safe_load((root / '.github/workflows/daily-cardnews.yml').read_text())
        schedules = workflow['on']['schedule']
        cron = schedules[0]['cron'].split()
        utc_hours = set()
        for part in cron[1].split(','):
            bounds = [int(value) for value in part.split('-')]
            utc_hours.update(range(bounds[0], bounds[-1] + 1))
        korean_hours = {datetime(2026, 10, 11, hour, 7, tzinfo=timezone.utc).astimezone(KOREA).hour
                        for hour in utc_hours}
        self.assertEqual(korean_hours, set(range(6, 24)))
        self.assertEqual(cron[0], '7,17,27,37,47,57')
        self.assertIn({'cron': '0 2 * * *'}, schedules)
        timeout = workflow['jobs']['daily']['timeout-minutes']
        self.assertGreaterEqual(timeout, MAX_TICK_MINUTES + 30)
        self.assertLessEqual(timeout, 360)


if __name__ == '__main__':
    unittest.main()
