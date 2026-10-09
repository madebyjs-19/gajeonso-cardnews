"""GitHub Actions entry point for PREP, Telegram approval polling and PUBLISH."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from git_checkpoint import CheckpointError
from publish_state import BLOCKED, ROOT, fingerprint, locked_state, validate_run
from publish_common import notify, verify_remote_media
from telegram_approval import bot, poll, send_preview, verify_bot

REQUIRED = ('GEMINI_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'IG_USER_ID', 'IG_ACCESS_TOKEN')


def now_korea():
    return datetime.now(ZoneInfo('Asia/Seoul'))


def configuration():
    missing = [key for key in REQUIRED if not os.environ.get(key)]
    if bool(os.environ.get('FB_PAGE_ID')) != bool(os.environ.get('FB_PAGE_ACCESS_TOKEN')):
        missing.append('FB_PAGE_ID + FB_PAGE_ACCESS_TOKEN (both required together)')
    if missing:
        raise ValueError('Missing GitHub Actions secrets: ' + ', '.join(missing))


def check():
    configuration()
    from publish_common import call, need
    from gemini_client import check_model
    def telegram_check():
        verify_bot()
        bot('getMe')
    checks = [('Telegram', telegram_check),
              ('Instagram', lambda: need(call('GET', '/' + os.environ['IG_USER_ID'], fields='id', access_token=os.environ['IG_ACCESS_TOKEN']), 'id')),
              ('Gemini', check_model)]
    if os.environ.get('FB_PAGE_ID'):
        checks.append(('Facebook', lambda: need(call('GET', '/' + os.environ['FB_PAGE_ID'], fields='id', access_token=os.environ['FB_PAGE_ACCESS_TOKEN']), 'id')))
    failed = []
    for label, action in checks:
        try:
            action()
            print(label + ': connection read check passed')
        except Exception as exc:
            failed.append(label)
            # Only fixed local messages may be reported. Never echo HTTP bodies or IDs.
            details = str(exc) if isinstance(exc, ValueError) and str(exc) in (
                'TELEGRAM_CHAT_ID must be a numeric chat ID',
                'TELEGRAM_APPROVER_ID must be a positive numeric user ID',
                'Group chats require TELEGRAM_APPROVER_ID',
                'Use a dedicated Telegram bot with no active webhook',
                'Gemini key or model access check failed') else 'Verify the configured credentials and account access'
            print(label + ': ' + details)
    if failed:
        raise ValueError('Connection checks failed: ' + ', '.join(failed))
    print('Configuration read checks passed. No content generated or published.')


def prepare(run):
    from content_pipeline import prepare_content
    with locked_state(run) as state:
        status = state.data['approval'].get('status')
        if any(c['status'] in BLOCKED for c in state.data['channels'].values()):
            print('PREP_SKIPPED_ALREADY_SUBMITTED')
            return
        if status in ('approved', 'cancelled', 'approval_timeout'):
            print('PREP_SKIPPED_EXISTING_DECISION')
            return
        if status == 'ready_for_approval':
            # Retry preview delivery using exactly the same already generated content.
            pass
        else:
            brief = prepare_content(run)
            directory = ROOT / 'cards' / run
            captions = [(directory / f'caption_{p}.txt').read_text(encoding='utf-8') for p in ('ig', 'fb')]
            import uuid
            state.data['preparation'] = {'status': 'ready'}
            state.data['metadata'] = dict(topic=brief['topic'], type=brief['type'], cover=brief['cover'], cards=', '.join(brief['card_types']))
            state.data['approval'] = {'status': 'ready_for_approval', 'key': uuid.uuid4().hex,
                                      'chat_id': os.environ['TELEGRAM_CHAT_ID'],
                                      'fingerprint': fingerprint(ROOT, run, captions)}
            state.save()  # Upload assets and approval record before sending preview URLs.
        verify_remote_media(state, False)
        verify_remote_media(state, True)
    send_preview(run)


def publish(run):
    poll(run)  # Consume the actual Telegram callback; never infer approval.
    with locked_state(run) as state:
        approval = state.data['approval']
        if approval.get('status') != 'approved':
            if approval.get('status') == 'ready_for_approval':
                approval['status'] = 'approval_timeout'
            state.save()
            print('PUBLISH_SKIPPED_' + approval['status'].upper())
            if not state.data.get('skip_notice_sent'):
                if notify('[' + run + '] 승인이 없어 발행하지 않았습니다. 상태: ' + approval['status']):
                    state.data['skip_notice_sent'] = True
                    state.save()
            return
    directory = ROOT / 'cards' / run
    env = {**os.environ, 'GAJEONSO_SILENT_TELEGRAM': '1'}
    failed = False
    for script in ('publish.py', 'publish_reel.py'):
        process = subprocess.run([sys.executable, str(ROOT / script), run,
                                  str(directory / 'caption_ig.txt'), str(directory / 'caption_fb.txt')], cwd=ROOT, env=env)
        failed |= process.returncode != 0
        # If a checkpoint failed and HEAD is ahead/behind remote, the next publisher
        # fails its pre-flight checkpoint too. It cannot proceed to a visible POST.
    with locked_state(run) as state:
        results = [c.upper() + ': ' + item['status'] + (' ' + item['permalink'] if item.get('permalink') else '')
                   for c, item in state.data['channels'].items()]
        marker = json.dumps(results, ensure_ascii=False)
        if state.data.get('last_report') != marker:
            if notify('[' + run + ' 가전소 최종 결과]\n' + '\n'.join(results)):
                state.data['last_report'] = marker
                state.save()
    if failed:
        raise ValueError('One or more channels failed or need reconciliation; see persistent state')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('check', 'prepare', 'approval', 'publish'))
    parser.add_argument('--run')
    args = parser.parse_args()
    run = args.run or now_korea().strftime('%Y%m%d')
    try:
        validate_run(run)
        if args.phase == 'check':
            check()
            return 0
        configuration()
        if run != now_korea().strftime('%Y%m%d'):
            raise ValueError('Automation accepts today only; do not replay stale approved dates')
        hour = now_korea().hour
        if args.phase == 'publish' and not 11 <= hour < 12:
            raise ValueError('Publishing is permitted only between 11:00 and 11:59 Asia/Seoul')
        if args.phase in ('prepare', 'approval') and hour >= 11:
            raise ValueError('Preparation/approval closed for today')
        verify_bot()
        if args.phase == 'prepare':
            prepare(run)
        elif args.phase == 'approval':
            poll(run)
        else:
            publish(run)
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, (ValueError, CheckpointError)) else 'Automation failed: ' + type(exc).__name__
        print(message)
        # Controlled errors only; no raw HTTP/SDK/subprocess output or credentials.
        if args.phase == 'prepare' and run == now_korea().strftime('%Y%m%d'):
            try:
                with locked_state(run) as state:
                    state.data['preparation'] = {'status': 'failed', 'error_type': type(exc).__name__}
                    state.save()
            except Exception:
                print('Failure log checkpoint unavailable; preserve recovery artifact')
        if args.phase != 'check':
            notify('[' + run + ' 가전소] ' + message)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
