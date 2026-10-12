"""Durable successful responses and conservative per-Pacific-day HTTP budget."""
from contextvars import ContextVar
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
from zoneinfo import ZoneInfo

from git_checkpoint import checkpoint
from publish_state import atomic_write, validate_run

ACTIVE = ContextVar('ai_session', default=None)
DAILY_REQUEST_BUDGET = 18  # Keep two requests of the observed 20 RPD as headroom.


def now_pacific():
    return datetime.now(ZoneInfo('America/Los_Angeles'))


def reset_at():
    current = now_pacific()
    return (current + timedelta(days=1)).replace(hour=0, minute=2, second=0,
                                                microsecond=0).isoformat()


class QuotaPause(RuntimeError):
    def __init__(self, kind, retry_at=None):
        self.kind = kind
        self.retry_at = retry_at or reset_at()
        super().__init__('Gemini free quota paused; ' + kind)


def read(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


class Session:
    def __init__(self, root, run):
        self.root, self.run = root, validate_run(run)
        self.path = root / 'log' / 'ai-cache' / (run + '.json')
        self.cache = read(self.path, {'version': 1, 'responses': {}})
        if self.cache.get('version') != 1:
            raise ValueError('Invalid AI cache')

    def save(self, path, value):
        atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2))
        checkpoint(self.root, self.run)

    def reserve(self):
        path = self.root / 'log' / 'ai-budget' / (now_pacific().strftime('%Y%m%d') + '.json')
        budget = read(path, {'requests': 0})
        if budget.get('paused') or budget['requests'] >= DAILY_REQUEST_BUDGET:
            raise QuotaPause(budget.get('paused', 'budget'))
        # Save BEFORE every HTTP attempt, including retries and lost responses.
        budget['requests'] += 1
        self.save(path, budget)

    def pause(self, kind):
        path = self.root / 'log' / 'ai-budget' / (now_pacific().strftime('%Y%m%d') + '.json')
        budget = read(path, {'requests': 0})
        budget['paused'] = kind
        self.save(path, budget)

    def key(self, payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def remember(self, key, value):
        self.cache['responses'][key] = value
        self.save(self.path, self.cache)


def durable_ai(func):
    @wraps(func)
    def wrapper(run, *args, **kwargs):
        if ACTIVE.get() is not None:
            return func(run, *args, **kwargs)
        token = ACTIVE.set(Session(func.__globals__['ROOT'], run))
        try:
            return func(run, *args, **kwargs)
        finally:
            ACTIVE.reset(token)
    return wrapper
