"""GitHub Actions entry point for PREP, Telegram approval polling and PUBLISH."""
import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from automation_schedule import MAX_TICK_MINUTES, PREP_START_HOUR, PUBLISH_HOUR
from git_checkpoint import CheckpointError
from publish_state import BLOCKED, CHANNELS, ROOT, fingerprint, locked_state, validate_run
from telegram_text import channel_result, error_text, status_text
from publish_common import notify, verify_remote_media
from telegram_approval import bot, poll, send_preview, verify_bot

REQUIRED = ('GEMINI_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID')
MAX_PREP_ATTEMPTS = 6
MAX_PUBLISH_ATTEMPTS = 3


def now_korea():
    return datetime.now(ZoneInfo('Asia/Seoul'))


def configuration():
    missing = [key for key in REQUIRED if not os.environ.get(key)]
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
                # A delayed publisher must not end the user's approval window early.
                expires = approval.get('expires_at')
                if not expires or now_korea() < datetime.fromisoformat(expires):
                    return
                approval['status'] = 'approval_timeout'
                state.save()
            if not state.data.get('skip_notice_sent'):
                if notify('[' + run + '] 인스타그램·페이스북 발행을 진행하지 않았습니다. 상태: '
                          + status_text(approval['status'])):
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
        results = [channel_result(c, item) for c, item in state.data['channels'].items()]
        marker = json.dumps(results, ensure_ascii=False)
        if state.data.get('last_report') != marker:
            if notify('[' + run + ' 가전소 최종 결과]\n' + '\n'.join(results)):
                state.data['last_report'] = marker
                state.save()
    if failed:
        raise ValueError('One or more channels failed or need reconciliation; see persistent state')


def tick(run):
    """Resume today's durable state regardless of which cron event actually arrived."""
    current = now_korea()
    if current.hour < PREP_START_HOUR:
        return
    with locked_state(run) as state:
        approval = state.data['approval'].get('status')
        needs_prepare = approval in ('unapproved', 'ready_for_approval')
        needs_prepare &= not any(c['status'] in BLOCKED for c in state.data['channels'].values())
        needs_prepare &= not state.data['approval'].get('message_id')
        if needs_prepare:
            recovery = state.data.setdefault('recovery', {})
            due = recovery.get('prepare_retry_at')
            if recovery.get('prepare_attempts', 0) >= MAX_PREP_ATTEMPTS:
                if not recovery.get('prepare_limit_notice_sent'):
                    if notify('[' + run + '] 제작 복구를 여섯 차례 시도했지만 완료하지 못했습니다. 인스타그램·페이스북 발행은 보류 중입니다. 실행 기록을 확인해 주세요.'):
                        recovery['prepare_limit_notice_sent'] = True
                        state.save()
                return
            if due and current < datetime.fromisoformat(due):
                return
            # Preserve at least an hour for approval before the local date changes.
            if current.hour >= 23:
                if not recovery.get('late_notice_sent'):
                    if notify('[' + run + '] 오늘 제작을 시작하지 못했습니다. 승인 시간을 확보할 수 없어 발행하지 않았습니다. 실행 기록을 확인해 주세요.'):
                        recovery['late_notice_sent'] = True
                        state.save()
                return
            recovery['prepare_attempts'] = recovery.get('prepare_attempts', 0) + 1
            recovery['prepare_retry_at'] = (current + timedelta(minutes=30)).isoformat()
            state.save()
    if needs_prepare:
        prepare(run)
    if now_korea().strftime('%Y%m%d') != run:
        return  # Never publish yesterday's content after a long render crosses midnight.
    poll(run)
    with locked_state(run) as state:
        approval = state.data['approval'].get('status')
        if approval == 'approved' and now_korea().hour >= PUBLISH_HOUR:
            pending = [c for c in CHANNELS if state.data['channels'].get(c, {}).get('status') not in BLOCKED]
            recovery = state.data.setdefault('recovery', {})
            attempts = recovery.get('publish_attempts', 0)
            due = recovery.get('publish_retry_at')
            if pending and attempts >= MAX_PUBLISH_ATTEMPTS:
                if not recovery.get('publish_limit_notice_sent'):
                    if notify('[' + run + '] 발행 복구 시도 한도에 도달했습니다. 완료된 게시물은 유지합니다.\n' + '\n'.join(channel_result(c, item) for c, item in state.data['channels'].items())):
                        recovery['publish_limit_notice_sent'] = True
                        state.save()
                return
            if pending and due and now_korea() < datetime.fromisoformat(due):
                return
            if pending:
                recovery['publish_attempts'] = attempts + 1
                recovery['publish_retry_at'] = (now_korea() + timedelta(minutes=30)).isoformat()
                state.save()
        elif approval not in ('ready_for_approval', 'cancelled', 'approval_timeout'):
            return
    # publish() also expires unanswered previews and reports cancellation in Korean.
    publish(run)


def run_tick(run):
    # Keep the approval receiver alive after preview delivery. A delayed follow-up
    # cron must not be the sole way to observe a timely human approval.
    stop = time.monotonic() + MAX_TICK_MINUTES * 60
    while True:
        tick(run)
        if now_korea().strftime('%Y%m%d') != run:
            return
        with locked_state(run) as state:
            approval = state.data['approval']
            expires = approval.get('expires_at')
            waiting = bool(approval.get('status') == 'ready_for_approval' and expires
                           and now_korea() < datetime.fromisoformat(expires))
            waiting |= approval.get('status') == 'approved' and now_korea().hour < PUBLISH_HOUR
        if not waiting or time.monotonic() >= stop:
            return
        time.sleep(20)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('check', 'prepare', 'approval', 'publish', 'tick'))
    parser.add_argument('--run')
    args = parser.parse_args()
    # Re-running a failed Actions job retains its original workflow definition.
    # Older scheduled jobs still pass prepare/approval/publish, so route them
    # through today's durable recovery loop too. Manual phase controls and the
    # read-only check remain explicit.
    if os.environ.get('GITHUB_EVENT_NAME') == 'schedule' and args.phase != 'check':
        args.phase = 'tick'
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
        if args.phase == 'publish' and hour < PUBLISH_HOUR:
            raise ValueError('Publishing is permitted from 11:00 Asia/Seoul on the same day')
        verify_bot()
        if args.phase == 'tick':
            run_tick(run)
        elif args.phase == 'prepare':
            prepare(run)
        elif args.phase == 'approval':
            poll(run)
        else:
            publish(run)
        return 0
    except Exception as exc:
        message = error_text(exc)
        print(message)
        # Controlled errors only; no raw HTTP/SDK/subprocess output or credentials.
        if args.phase in ('prepare', 'tick') and run == now_korea().strftime('%Y%m%d'):
            try:
                with locked_state(run) as state:
                    if state.data['approval'].get('status') == 'unapproved':
                        state.data['preparation'] = {'status': 'failed', 'error_type': type(exc).__name__}
                    state.data['last_error'] = message
                    state.save()
            except Exception:
                print('Failure log checkpoint unavailable; preserve recovery artifact')
        if args.phase != 'check':
            notify('[' + run + ' 가전소] ' + message + '\n인스타그램·페이스북 결과는 저장 상태를 기준으로 확인합니다. 승인 없는 발행은 진행하지 않습니다.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
