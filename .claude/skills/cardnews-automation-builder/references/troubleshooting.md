# 문제 해결 (가전소 운영 중 실제로 겪은 것)

| 증상 | 원인 | 조치 |
|---|---|---|
| 발행 결과 `IG 실패(API access blocked.)`, `FB 실패(Cannot call API for app … on behalf of user …)`, 같은 날 지표 수집도 실패 | Meta 앱이 제한됨(필수 조치 미처리) 또는 앱 연결 해제 | developers.facebook.com 앱 대시보드의 제한·필수 조치 처리 → 페이스북 설정 '비즈니스 통합'에서 앱 연결 확인 → accounts_setup 3번으로 페이지 토큰 재발급 → Secrets 교체 → Meta 연결 점검 → 실패한 회차를 Run workflow 로 재승인 |
| Meta 연결 점검: "페이지 토큰이 아님", "곧 만료: N시간" | 그래프 탐색기의 단기 **사용자** 토큰을 그대로 넣음 | 연장(Extend) → `me/accounts` 의 페이지 `access_token` 을 넣는다. 디버거에서 Type Page·Expires Never 확인 |
| 토큰을 넣었다는데 점검 결과가 그대로 | Secret 이름이 달라 새 Secret 이 생겼거나, 사용자 토큰을 다시 넣음 | Secrets 목록에서 정확한 이름을 연필 아이콘으로 Update. 점검 로그의 "발급일"이 바뀌었는지로 반영 여부를 판단 |
| 같은 회차를 다시 실행해도 "이미 처리됨, 건너뜀" | status.txt 에 '성공'이 있음(일부라도 게시됨) | 중복 게시 방지라 정상. 다시 올려야 하면 게시된 쪽을 확인한 뒤 status.txt 를 사람이 정리 |
| 루틴이 "1차 출처 확인 실패"로 중단 | 공식 사이트 503·시간 초과 | 루틴이 최소 3개 주제를 시도하고, 그래도 안 되면 topic_request 로 텔레그램 질문. 사용자가 답하면 다음 실행에 반영 |
| 승인 요청이 안 옴 | approval.txt 가 다른 파일보다 먼저/따로 푸시됨, 카드 5장 미만, 워크플로 권한 | 한 커밋 푸시인지 확인, Actions 로그 확인, Settings → Actions → Workflow permissions: Read and write |
| 인스타 발행 실패 `Media download has failed`/이미지 URL 오류 | 저장소 비공개 또는 raw 주소 반영 전 | 저장소 Public, 푸시 후 raw 주소 200 확인(step4 3번) |
| 표지 로고가 아래 가운데로 감 | 제목·태그가 오른쪽 위 로고 칸을 침범, 또는 가로로 긴 로고 | deck.json 제목을 줄여 다시 생성. 새 브랜드 저장소는 가로 로고 자동 축소가 들어 있음 |
| CTA 원형 로고가 엉뚱한 부분을 보여 줌 | `logo_medal_crop` 영역이 로고와 안 맞음 | brand.json 의 비율을 고쳐 new_brand.py 재실행, 또는 gen_cards.py `_medal` 의 crop 비율 직접 수정 |
| 자막 검사 실패 | 12자 초과·허용 안 되는 문자(이모지 등)·2~7.5초 밖 | 문구를 줄이고 `reel_overlay.py --check` 재실행 |
| 텔레그램 영상이 반영 안 됨 | 20MB 초과, [발행] 후에 보냄 | 드라이브 `릴스영상/YYMMDD` 에 올리거나 [발행] 전에 보내기 |
| 도면 PNG 가 옛 색 | 색을 바꾼 뒤 다시 그리지 않음 | `CHROME=<chrome> bash design/blueprints/render_png.sh` (리눅스는 --no-sandbox 가 들어간 새 저장소 버전 사용) |
| 지표 수집 실패 | Meta 토큰 문제(위 첫 줄과 같음) | 토큰 해결 후 Actions → 인스타 지표 수집 Run workflow |
