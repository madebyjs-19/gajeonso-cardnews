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
    from gemini_client import GeminiFailure
    if isinstance(exc, GeminiFailure):
        detail = {
            'auth': '인증 또는 모델 접근 권한이 거부되었습니다.',
            'request': '요청 형식이나 입력 조건이 거부되었습니다.',
            'model': '지정된 모델을 찾을 수 없습니다.',
            'server': '제미나이 서버에서 일시적인 오류가 발생했습니다.',
            'http': '제미나이 서버가 요청을 처리하지 못했습니다.',
            'timeout': '제미나이 응답 대기 시간이 초과되었습니다.',
            'network': '제미나이 서버에 연결하지 못했습니다.',
            'blocked': '제미나이에서 콘텐츠 생성을 제한했습니다.',
            'truncated': '생성 결과가 출력 길이 제한으로 잘렸습니다.',
            'incomplete': '제미나이가 콘텐츠 생성을 끝내지 못했습니다.',
            'empty': '제미나이 응답에 생성된 콘텐츠가 없습니다.',
            'schema': '생성 결과가 카드뉴스에 필요한 데이터 형식과 맞지 않습니다.',
        }.get(exc.code, '제미나이 콘텐츠 생성에 실패했습니다.')
        return detail + ' 승인 요청과 발행은 진행하지 않았습니다.'
    value = str(exc)
    known = {
        'Invalid five-card structure': '생성 원고의 카드 5장 구성이 맞지 않습니다.',
        'Invalid interior card types': '내용 카드 유형이 중복되거나 지원되지 않습니다.',
        'Only supported brand illustrations are allowed': '생성 원고의 제품 일러스트 유형이 지원되지 않습니다.',
        'Cover title too long': '생성된 표지 제목의 줄 수 또는 길이가 기준을 넘었습니다.',
        'Cover subtitle too long': '생성된 표지 부제가 길이 기준을 넘었습니다.',
        'Interior title too long': '생성된 내용 카드 제목이 길이 기준을 넘었습니다.',
        'Too many interior rows': '내용 카드의 항목 수가 기준과 맞지 않습니다.',
        'Invalid table/step row width': '생성된 표나 절차의 열 구성이 맞지 않습니다.',
        'Invalid compare columns': '비교 카드의 열 구성이 맞지 않습니다.',
        'Fact must cite a primary source': '생성 원고에 공식 출처로 확인되지 않은 주소가 있습니다.',
        'Invalid caption hashtags': '본문 해시태그의 개수나 필수 태그가 기준과 맞지 않습니다.',
        'Missing brand caption requirements': '본문에 필수 안내 문구가 누락되었습니다.',
        'Disallowed store branding': '생성 원고에 허용하지 않은 매장 안내가 포함되었습니다.',
        'Insufficient recent official appliance sources; no generation or publication': '최근 공식 가전 자료가 부족해 제작을 중단했습니다.',
        'Facts must cite retrieved official articles; invented sources are rejected': '생성 원고가 실제 수집한 공식 기사 외의 출처를 인용해 중단했습니다.',
        'Official fact source could not be re-read; no approval or publication': '공식 출처 원문을 다시 열어 확인하지 못해 중단했습니다.',
        'Generation failed: gen_cards.py': '카드 이미지 생성 중 오류가 발생했습니다.',
        'Generation failed: stamp_logo.py': '표지 로고 합성에 실패했습니다.',
        'Reel generation failed': '릴스 영상 생성에 실패했습니다.',
        'Invalid output dimensions': '생성된 카드 이미지 크기가 기준과 맞지 않습니다.',
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
    if value.startswith('Connection checks failed:'):
        return '외부 서비스 연결 점검에 실패했습니다. 저장소 연결 점검 결과를 확인해 주세요.'
    if value.startswith('Missing GitHub Actions secrets:'):
        return '자동화에 필요한 비밀 설정이 누락되었습니다. 저장소의 실행 설정을 확인해 주세요.'
    return '자동화 처리 중 오류가 발생했습니다. 저장소 실행 기록과 저장 상태를 확인해 주세요.'
