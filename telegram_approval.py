"""A dedicated Telegram bot: preview delivery and authenticated callback polling."""
from datetime import datetime
import json
import os
from pathlib import Path
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from git_checkpoint import checkpoint
from publish_state import ROOT, atomic_write, locked_state, validate_run


def bot(method, **params):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    try:
        request = urllib.request.Request('https://api.telegram.org/bot' + token + '/' + method,
                                         json.dumps(params).encode(), {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
        if result.get('ok') is not True:
            raise RuntimeError()
        return result['result']
    except Exception:
        raise RuntimeError('Telegram request failed: ' + method) from None


def verify_bot():
    import re
    chat = os.environ['TELEGRAM_CHAT_ID']
    if not re.fullmatch(r'-?[1-9][0-9]*', chat):
        raise ValueError('TELEGRAM_CHAT_ID must be a numeric chat ID')
    approver = os.environ.get('TELEGRAM_APPROVER_ID') or (chat if int(chat) > 0 else '')
    if not approver:
        raise ValueError('Group chats require TELEGRAM_APPROVER_ID')
    if not re.fullmatch(r'[1-9][0-9]*', approver):
        raise ValueError('TELEGRAM_APPROVER_ID must be a positive numeric user ID')
    # Never silently delete an existing webhook or steal another bot's updates.
    if bot('getWebhookInfo').get('url'):
        raise ValueError('Use a dedicated Telegram bot with no active webhook')
    return chat, approver


def send_preview(run):
    chat, _ = verify_bot()
    with locked_state(run) as state:
        approval = state.data['approval']
        if approval.get('status') != 'ready_for_approval':
            return
        if approval.get('message_id'):
            print('Approval preview already delivered')
            return
        if approval.get('delivery') == 'sending':
            # A previous worker may have died between sending and saving its message ID.
            # Rotate the key: any partially delivered old buttons become invalid.
            approval['key'] = uuid.uuid4().hex
        approval['delivery'] = 'sending'
        state.save()
        directory = ROOT / 'cards' / run
        raw = 'https://raw.githubusercontent.com/madebyjs-19/gajeonso-cardnews/main/cards/' + run
        bot('sendMediaGroup', chat_id=chat, media=[{'type': 'photo', 'media': raw + f'/card{i}.jpg'} for i in range(1, 6)])
        bot('sendVideo', chat_id=chat, video=raw + '/reel.mp4', caption=run + ' 릴스 미리보기')
        brief = json.loads((directory / 'brief.json').read_text(encoding='utf-8'))
        text = (f"[{run} 승인 요청]\n주제: {brief['topic']}\n유형: {brief['type']} / 표지: {brief['cover']}\n"
                + '카드: ' + ', '.join(brief['card_types']) + '\n제품 이미지: 브랜드 일러스트\n'
                + '출처와 확인 사항:\n' + json.dumps(brief['facts'], ensure_ascii=False)
                + '\n주의: ' + '; '.join(brief['warnings'])
                + ('\n수동 테스트: 승인 후 별도 수동 실행에서 즉시 발행합니다.'
                   if state.data.get('manual_test') else '\n승인된 오늘 회차만 오전 11시에 발행합니다.'))
        # Telegram counts UTF-16 code units. Split long text conservatively.
        for heading, content in [('근거', text), ('Instagram 캡션', (directory / 'caption_ig.txt').read_text()),
                                 ('Facebook 캡션', (directory / 'caption_fb.txt').read_text())]:
            for offset in range(0, len(content), 1800):
                bot('sendMessage', chat_id=chat, text=heading + '\n' + content[offset:offset + 1800])
        message = bot('sendMessage', chat_id=chat, text=run + ' 카드 5장·릴스·캡션을 확인한 후 선택해 주세요.',
                      reply_markup={'inline_keyboard': [[
                          {'text': '발행 승인', 'callback_data': f"approve:{run}:{approval['key']}"},
                          {'text': '취소', 'callback_data': f"cancel:{run}:{approval['key']}"}]]})
        approval.update(message_id=message['message_id'], delivery='sent')
        state.save()


def apply_callback(callback, state, chat, approver):
    approval = state.data['approval']
    message = callback.get('message', {})
    data = callback.get('data', '').split(':')
    if (len(data) != 3 or data[0] not in ('approve', 'cancel') or data[1] != state.run
            or data[2] != approval.get('key') or approval.get('status') != 'ready_for_approval'
            or str(message.get('chat', {}).get('id')) != chat
            or str(callback.get('from', {}).get('id')) != approver
            or message.get('message_id') != approval.get('message_id')
            or approval.get('chat_id') != chat or not callback.get('id')):
        return False
    approval.update(status='approved' if data[0] == 'approve' else 'cancelled',
                    callback_id=callback['id'], approved_by=approver,
                    responded_at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat())
    state.save()  # Durable before acknowledging the callback/advancing the cursor.
    return True


def poll(run):
    chat, approver = verify_bot()
    validate_run(run)
    offset_path = ROOT / 'log' / 'telegram-offset.json'
    offset = json.loads(offset_path.read_text()).get('offset', 0) if offset_path.exists() else 0
    # Bounded draining handles old unrelated updates without waiting for a human.
    for _ in range(10):
        updates = bot('getUpdates', offset=offset, timeout=0, limit=100, allowed_updates=['callback_query'])
        if not updates:
            break
        for update in updates:
            callback = update.get('callback_query')
            if callback:
                with locked_state(run) as state:
                    accepted = apply_callback(callback, state, chat, approver)
                try:
                    bot('answerCallbackQuery', callback_query_id=callback['id'],
                        text='승인 기록 완료' if accepted else '처리된 요청 또는 유효하지 않은 요청입니다.')
                except RuntimeError:
                    pass
            offset = max(offset, update['update_id'] + 1)
        atomic_write(offset_path, json.dumps({'offset': offset}) + '\n')
        checkpoint(ROOT, run)
        if len(updates) < 100:
            break
    return offset
