"""Shared Korean daily preparation, approval and publication timing."""
from datetime import timedelta
from zoneinfo import ZoneInfo

KOREA = ZoneInfo('Asia/Seoul')
PREP_START_HOUR = 6
PUBLISH_HOUR = 11
MAX_TICK_MINUTES = 330


def approval_deadline(sent_at, manual_test=False):
    """Morning previews survive until noon; every preview has at least an hour.

    Explicit manual tests retain their existing one-hour approval window.
    Existing saved deadlines are never rewritten.
    """
    sent_at = sent_at.astimezone(KOREA)
    minimum = sent_at + timedelta(minutes=60)
    if manual_test:
        return minimum
    noon = sent_at.replace(hour=12, minute=0, second=0, microsecond=0)
    return max(noon, minimum)
