"""Explicit same-day manual test of a committed, operator-provided content plan."""
import argparse
import hashlib
import json
import os
import uuid

from content_pipeline import render_content, validate_content
from daily_automation import configuration, now_korea, publish
from publish_common import notify, verify_remote_media
from publish_state import BLOCKED, ROOT, fingerprint, locked_state, validate_run
from telegram_approval import poll, send_preview, verify_bot


def request_plan(run):
    validate_run(run)
    if len(run) != 9 or run[:8] != now_korea().strftime('%Y%m%d'):
        raise ValueError('Manual test requires today plus one lowercase suffix')
    path = ROOT / 'automation' / 'manual' / (run + '.json')
    raw = path.read_bytes()
    plan = json.loads(raw)
    if plan.get('run') != run or plan.get('mode') != 'manual_test':
        raise ValueError('Missing explicit manual test request')
    source = 'operator:' + run
    if plan.get('operator_source', {}).get('reference') != source or not plan['operator_source'].get('text'):
        raise ValueError('Manual test requires the actual operator-provided event terms')
    if any(f['source_url'] != source for f in plan['content']['facts']):
        raise ValueError('Manual facts must identify the operator brief without claiming official verification')
    validate_content(plan['content'], operator_source=source,
                     allow_store_branding=plan.get('store_branding_exception') is True)
    return plan, hashlib.sha256(raw).hexdigest()


def require_workflow():
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or os.environ.get('GITHUB_WORKFLOW') != 'Manual gajeonso test'
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('GAJEONSO_DURABLE_GIT') != '1'):
        raise ValueError('Manual test requires its explicit main-branch workflow and durable checkpoints')


def prepare(run, plan, request_hash):
    with locked_state(run) as state:
        if any(c['status'] in BLOCKED for c in state.data['channels'].values()):
            print('MANUAL_PREP_SKIPPED_ALREADY_SUBMITTED')
            return
        if state.data.get('request_hash') not in (None, request_hash):
            raise ValueError('Manual request changed; preserve the existing approval and inspect manually')
        if state.data['approval']['status'] in ('approved', 'cancelled', 'approval_timeout'):
            print('MANUAL_PREP_SKIPPED_EXISTING_DECISION')
            return
        if state.data['approval']['status'] != 'ready_for_approval':
            brief = render_content(run, plan['content'],
                                   {'passed': True, 'basis': 'operator_provided_event_terms',
                                    'independent_official_verification': False},
                                   source_method='operator_brief')
            directory = ROOT / 'cards' / run
            captions = [(directory / f'caption_{p}.txt').read_text(encoding='utf-8') for p in ('ig', 'fb')]
            state.data.update(manual_test=True, request_hash=request_hash,
                              preparation={'status': 'ready'},
                              metadata=dict(topic=brief['topic'], type=brief['type'], cover=brief['cover'],
                                            cards=', '.join(brief['card_types'])))
            state.data['approval'] = {'status': 'ready_for_approval', 'key': uuid.uuid4().hex,
                                      'chat_id': os.environ['TELEGRAM_CHAT_ID'],
                                      'fingerprint': fingerprint(ROOT, run, captions)}
            state.save()
        verify_remote_media(state, False)
        verify_remote_media(state, True)
    send_preview(run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'approval', 'publish'))
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    try:
        require_workflow()
        configuration()
        plan, request_hash = request_plan(args.run)
        verify_bot()
        if args.phase == 'prepare':
            prepare(args.run, plan, request_hash)
        else:
            with locked_state(args.run) as state:
                if not state.data.get('manual_test') or state.data.get('request_hash') != request_hash:
                    raise ValueError('Manual test has not been prepared with this exact request')
            if args.phase == 'approval':
                poll(args.run)
            else:
                # Reuse actual callback authentication, content fingerprints and
                # per-channel duplicate/unknown protection. No fabricated approval.
                publish(args.run)
        return 0
    except Exception as exc:
        # Avoid raw document, subprocess, HTTP or credential-bearing exceptions.
        print('Manual test failed: ' + type(exc).__name__)
        if os.environ.get('TELEGRAM_BOT_TOKEN') and os.environ.get('TELEGRAM_CHAT_ID'):
            notify('수동 테스트가 중단되었습니다. Actions 실행과 저장 상태를 확인해 주세요.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
