"""Korean-only operational messages; never forward raw exception text."""
STATUS = {
    'unapproved': '미승인', 'ready_for_approval': '승인 대기', 'approved': '승인 완료',
    'cancelled': '승인 취소', 'approval_timeout': '승인 시간 만료',
    'preparing': '발행 준비 중', 'failed': '실패', 'skipped': '설정 누락으로 건너뜀',
    'success': '발행 완료', 'legacy_success': '이전 발행 완료',
    'submitted': '발행 요청 접수·처리 중', 'publishing': '게시 결과 확인 필요',
    'unknown': '게시 결과 확인 필요',
}
CHANNEL = {'ig_card': '인스타그램 카드', 'fb_card': '페이스북 카드',
           'ig_reel': '인스타그램 릴스', 'fb_reel': '페이스북 릴스'}
TYPE = {'A': '제품 소식', 'B': '구매 가이드·비교', 'C': '혜택·행사', 'D': '서비스 안내'}
COLOR = {'navy': '네이비', 'ice': '아이스 블루', 'white': '화이트', 'orange': '오렌지', 'blue': '블루'}
CARD = {'formula': '계산 공식', 'table': '기준표', 'checklist': '확인 목록', 'compare': '비교',
        'steps': '절차', 'contact': '연락처', 'product': '제품 정보', 'poster': '행사 안내'}


def status_text(status):
    return STATUS.get(status, '상태 확인 필요')


def channel_result(channel, item):
    return CHANNEL.get(channel, '발행 채널') + ': ' + status_text(item.get('status')) + (
        ' ' + item['permalink'] if item.get('permalink') else '')


def error_text(exc):
    # Match controlled local errors only. API bodies, URLs and credentials stay private.
    value = str(exc)
    known = {
        'Visual QA rejected content': '카드 이미지 검수를 통과하지 못했습니다.',
        'Fact QA rejected content': '내용의 사실 검증을 통과하지 못했습니다.',
        'Insufficient verified facts or topic candidates': '확인된 자료가 부족해 제작을 중단했습니다.',
        'Approved content changed; prepare and approve again': '승인 후 콘텐츠가 변경되어 발행을 중단했습니다. 재검수와 새 승인이 필요합니다.',
        'Hosted media differs from approved media': '공개 이미지와 승인된 파일이 달라 발행을 중단했습니다.',
        'Preparation/approval closed for today': '오늘 제작·승인 시간이 종료되었습니다.',
        'One or more channels failed or need reconciliation; see persistent state': '일부 채널의 발행이 실패했거나 게시 결과 확인이 필요합니다.',
        'Use a dedicated Telegram bot with no active webhook': '텔레그램 봇에 다른 수신 연결이 있습니다. 전용 봇 설정을 확인해 주세요.',
        'TELEGRAM_CHAT_ID must be a numeric chat ID': '텔레그램 채팅 식별자는 숫자로 설정해 주세요.',
        'TELEGRAM_APPROVER_ID must be a positive numeric user ID': '텔레그램 승인자 식별자는 양의 정수로 설정해 주세요.',
        'Group chats require TELEGRAM_APPROVER_ID': '그룹 채팅의 승인자 식별자 설정이 필요합니다.',
        'Gemini free quota unavailable or exhausted; no fallback, approval or publication': '제미나이 무료 사용 한도를 확인할 수 없거나 한도가 소진되었습니다. 다음 복구 점검에서 다시 확인합니다.',
        'Gemini content request failed; nothing approved or published': '제미나이 콘텐츠 생성 요청에 실패했습니다. 다음 복구 점검에서 다시 확인합니다.',
    }
    if value in known:
        return known[value]
    if type(exc).__name__ == 'CheckpointError':
        return '저장소에 진행 상태를 저장하지 못해 중단했습니다. 다음 실행에서 최신 상태를 확인합니다.'
    if value.startswith('Missing GitHub Actions secrets:'):
        return '자동화에 필요한 비밀 설정이 누락되었습니다. 저장소의 실행 설정을 확인해 주세요.'
    return '자동화 처리 중 오류가 발생했습니다. 저장소 실행 기록과 저장 상태를 확인해 주세요.'
