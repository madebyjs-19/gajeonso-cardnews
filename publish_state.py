"""Durable run state. JSON is authoritative; Markdown is a human-readable projection."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from git_checkpoint import CheckpointError, checkpoint

ROOT = Path(__file__).resolve().parent
CHANNELS = ('ig_card', 'fb_card', 'ig_reel', 'fb_reel')
BLOCKED = {'success', 'submitted', 'publishing', 'unknown', 'legacy_success'}


def validate_run(run):
    if not re.fullmatch(r'\d{8}[a-z]?', run):
        raise ValueError('Run must be YYYYMMDD with an optional lowercase suffix')
    datetime.strptime(run[:8], '%Y%m%d')
    return run


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.state-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def fingerprint(root, run, captions):
    digest = hashlib.sha256()
    paths = [root / 'cards' / run / f'card{i}.jpg' for i in range(1, 6)]
    paths.append(root / 'cards' / run / 'reel.mp4')
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing or empty approved media: ' + path.name)
        digest.update(path.name.encode())
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
    for caption in captions:
        digest.update(b'\0caption\0')
        digest.update(str(len(caption.encode('utf-8'))).encode() + b':' + caption.encode('utf-8'))
    return digest.hexdigest()


class RunState:
    def __init__(self, root, run):
        self.root, self.run = Path(root), validate_run(run)
        self.path = self.root / 'log' / 'publish-state' / (run + '.json')
        self.log = self.root / 'log' / 'ig-card-news-log.md'
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('version') != 1 or self.data.get('run') != run:
                raise ValueError('Invalid publish state; manual inspection required')
        else:
            self.data = {'version': 1, 'run': run, 'approval': {'status': 'unapproved'},
                         'channels': {}, 'metadata': {}}
            self.import_legacy()

    def matching_rows(self):
        if not self.log.exists():
            return []
        return [line for line in self.log.read_text(encoding='utf-8').splitlines()
                if line.split('|')[0].strip() == self.run]

    def import_legacy(self):
        rows = self.matching_rows()
        if rows:
            self.data['legacy_log'] = rows
        for line in rows:
            parts = [s.strip() for s in line.split('|')]
            if len(parts) >= 6:
                self.data['metadata'] = dict(zip(('topic', 'type', 'cover', 'cards'), parts[1:5]))
            result = parts[-1]
            for channel in CHANNELS:
                marker = re.search(channel.upper() + r'=(SUCCESS|SUBMITTED|PUBLISHING|UNKNOWN|LEGACY_SUCCESS)\b', result)
                if marker:
                    self.data['channels'][channel] = {'status': marker.group(1).lower()}
            # Only positive, explicit publication records; approval alone is never success.
            hits = {'ig_card': r'IG 발행 성공|IG_SUCCESS', 'fb_card': r'FB 발행 성공|FB_SUCCESS',
                    'ig_reel': r'IG 릴스 성공|IG_REEL_SUCCESS',
                    'fb_reel': r'FB 릴스 성공|FB 릴스 요청 완료|FB_REEL_SUCCESS'}
            for channel, pattern in hits.items():
                if re.search(pattern, result):
                    self.data['channels'][channel] = {'status': 'legacy_success'}
            if result == '발행 성공':
                for channel in ('ig_card', 'fb_card'):
                    self.data['channels'][channel] = {'status': 'legacy_success'}

    def save(self):
        self.data['updated_at'] = datetime.now().astimezone().isoformat()
        atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=2) + '\n')
        # Serialize projection writes across different run IDs, too.
        with (self.root / 'log' / '.status.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.update_log()
            checkpoint(self.root, self.run)

    def update_log(self):
        lines = self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []
        meta = self.data['metadata']
        def clean(value):
            return str(value).replace('|', '/').replace('\n', ' ')
        results = [self.data['approval']['status'].upper()]
        if self.data.get('preparation'):
            results.append('PREP=' + self.data['preparation']['status'].upper())
        for channel in CHANNELS:
            item = self.data['channels'].get(channel)
            if item:
                results.append(channel.upper() + '=' + item['status'].upper()
                               + (':' + item['media_id'] if item.get('media_id') else ''))
        row = ' | '.join([self.run] + [clean(meta.get(k, '—')) for k in ('topic', 'type', 'cover', 'cards')]
                         + [' · '.join(results)])
        output, inserted = [], False
        for line in lines:
            if line.split('|')[0].strip() == self.run:
                if not inserted:
                    output.append(row)
                    inserted = True
            else:
                output.append(line)
        if not inserted:
            output.append(row)
        atomic_write(self.log, '\n'.join(output) + '\n')

    def set_channel(self, channel, status, **fields):
        item = self.data['channels'].setdefault(channel, {})
        item.update(status=status, **fields)
        self.save()

    def require_approval(self, captions):
        approval = self.data['approval']
        if approval.get('status') != 'approved':
            raise ValueError('PUBLISH_SKIPPED_NOT_APPROVED')
        if approval.get('chat_id') != os.environ.get('TELEGRAM_CHAT_ID'):
            raise ValueError('Approval chat mismatch')
        if approval.get('fingerprint') != fingerprint(self.root, self.run, captions):
            raise ValueError('Approved content changed; prepare and approve again')


@contextmanager
def locked_state(run, root=ROOT):
    root = Path(root)
    validate_run(run)
    directory = root / 'log' / 'publish-state'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (run + '.lock')).open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Run already active') from None
        yield RunState(root, run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'approve', 'cancel', 'status'))
    parser.add_argument('run')
    parser.add_argument('--ig-caption')
    parser.add_argument('--fb-caption')
    parser.add_argument('--approval-key')
    parser.add_argument('--chat-id')
    parser.add_argument('--callback-id')
    parser.add_argument('--topic', default='—')
    parser.add_argument('--type', default='—')
    parser.add_argument('--cover', default='—')
    parser.add_argument('--cards', default='—')
    args = parser.parse_args()
    try:
        with locked_state(args.run) as state:
            if args.action == 'prepare':
                if any(c['status'] in BLOCKED for c in state.data['channels'].values()):
                    raise ValueError('Run already submitted or unresolved; do not replace approved content')
                if not args.ig_caption or not args.fb_caption:
                    raise ValueError('Both caption paths are required')
                captions = [Path(p).read_text(encoding='utf-8') for p in (args.ig_caption, args.fb_caption)]
                chat = os.environ.get('TELEGRAM_CHAT_ID')
                if not chat:
                    raise ValueError('TELEGRAM_CHAT_ID is required')
                state.data['approval'] = {'status': 'ready_for_approval', 'key': uuid.uuid4().hex,
                                          'chat_id': chat, 'fingerprint': fingerprint(ROOT, args.run, captions)}
                state.data['metadata'] = {k: getattr(args, k) for k in ('topic', 'type', 'cover', 'cards')}
                state.save()
            elif args.action in ('approve', 'cancel'):
                approval = state.data['approval']
                if (approval.get('status') != 'ready_for_approval' or not args.approval_key
                        or args.approval_key != approval.get('key') or not args.callback_id
                        or not args.chat_id or args.chat_id != approval.get('chat_id')
                        or args.chat_id != os.environ.get('TELEGRAM_CHAT_ID')):
                    raise ValueError('Invalid or stale approval callback')
                approval.update(status='approved' if args.action == 'approve' else 'cancelled',
                                callback_id=args.callback_id)
                state.save()
            print(json.dumps(state.data, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, CheckpointError) as exc:
        print(str(exc) if isinstance(exc, ValueError) else 'State operation failed: ' + type(exc).__name__, file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
