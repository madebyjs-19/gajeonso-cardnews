# 가전소 카드뉴스 작업 규칙 (스케줄 실행 시 반드시 적용)

## 표지 이미지 규칙 (모든 유형 A~D 공통)
- 모든 게시물의 1장 표지에는 주제에 맞는 제품 이미지를 넣는다. 제품이 주인공이 아닌 주제(제도·서비스·행사 안내 등)도 예외가 아니다.
- 이미지가 필요한 표지는 `product_cover` 카드로 만든다(`label`, `title`, `subtitle`, `image`).
  - 1순위: 공식·신뢰 출처의 실물 사진(step2_5 절차대로 내려받아 배경 제거, 출처 URL 기록, 사용권 불분명 시 승인 메시지에 "이미지 사용권 확인 필요" 명시).
  - 2순위(실물을 못 구했거나 주제를 대표하는 특정 제품이 없을 때): `"image": "illust:종류"` 일러스트. 종류는 주제와 가장 가까운 제품군으로 고른다(fridge, kimchi_fridge, washer, washer_drum, washer_top, dryer, tv, aircon, stand_aircon, air_purifier, stick_vacuum, robot_vacuum, microwave, dishwasher, styler, water_purifier, induction, generic). 연구소 디자인에서는 제품 도면(assets/blueprints/)으로 그려진다.
  - 일러스트 사용 시 승인 메시지에 "제품 이미지: 일러스트 사용"이라고 적는다.
- 표지 이후 로고는 `stamp_logo.py`로 합성한다. 이미지·제목·로고가 겹치지 않는지 직접 확인한다.
- 유형 C(포스터형)는 `poster`의 `image` 항목을 쓴다.

## 카드 장수 (7~9장)
- 게시물은 기본 7장, 최대 9장이다: 1장 표지 → 내용 5~7장 → 마지막 장 CTA(상담 접수증). 비교 대상·절차·확인된 수치가 많으면 8장, 서로 다른 핵심 메시지 7개가 확인되는 제도·종합 가이드만 9장. 채우기용 카드는 만들지 않는다.
- 2장은 결론 요약, CTA 바로 앞 장은 캡처해 둘 '저장용 정리'(체크리스트·표). 같은 유형은 최대 2번·연속 금지. 자세한 규칙은 ROUTINE_PROMPT.md step3 [구조].

## 카드 디자인
- deck.json 에 `"design": "lab"` 을 넣어 연구소 리포트 디자인(모눈 배경·FILE 라벨·스펙 시트·제품 도면)으로 만든다. 자세한 규칙은 ROUTINE_PROMPT.md step3.
- 1장 오른쪽 위는 모눈 없는 로고 칸이다. `stamp_logo.py` 가 `LOGO_OK top-right` 를 출력해야 한다.

## 표지·본문 품질 규칙 (ROUTINE_PROMPT.md 의 [표지 콘텐츠 규칙]·[본문 전문성·출처 표기] 와 동일, 매 회차 적용)
- 표지는 결론·핵심 수치를 담은 요약형 제목으로 만들고, 로고는 항상 우측 상단에 둔다.
- 본문은 전문적인 수치·기준·절차 중심으로 쓰고, 내용 카드마다 출처(기관·문서명)를 표기한다. 전체 원문 URL 은 ig.txt·fb.txt·approval.txt 에 싣는다.

## 릴스 (매 회차 발행)
- 사용자가 Google Flow 에서 만든 영상을 텔레그램(또는 드라이브 `릴스영상/YYMMDD`)으로 보내면 그 영상으로 릴스를 발행한다. 영상이 없으면 Actions 가 승인 후 `make_reel.py` 로 카드 표지·2·3장과 마지막 장 슬라이드 릴스(상단 훅 = ig.txt 첫 줄)를 만들어 대신 발행한다. 모델 세션은 `reel.mp4` 를 만들거나 푸시하지 않는다.
- 영상 구성: 맨 앞 카드뉴스 표지 2초(자연스러운 전환) + Flow 본 영상 정확히 8초(잘리지 않음) + 핵심 내용 팝업 자막. 내레이션은 BGM 없이도 들리고, BGM 은 사용자가 텔레그램에서 지정한다.
- 모든 릴스에 같은 진행자(흰 가운·둥근 안경·단발의 가전소 연구원)가 나온다. ROUTINE_PROMPT.md step3 7번의 HOST 문단을 그대로 넣고, 기준 이미지는 `assets/reel_host/`(만드는 법 `docs/reel_host.md`).
- 컨셉은 12가지 목록에서 직전 5회차와 겹치지 않게 고른다. 구성은 정보 설명(최종 2~7.5초, 팝업 자막) → 고정 엔딩(7.5~9.5초): 진행자가 화면 오른쪽 위를 가리키며 "추가 정보와 문의는 가전소에서!", 그 자리에 카드뉴스와 같은 카카오톡 상담 QR 패널을 `reel_overlay.py` 가 합성한다.

## 콘텐츠 계획·주간 리포트
- 주제는 `plan/content_plan.md` 의 오늘 행이 기본값이다. 리콜·안전, 애플 관련 출시·이슈, 지원금 시작·마감, 대형 할인 발표 같은 이슈가 있으면(네이버 뉴스 IT/과학의 노트북·PC·스마트폰·애플 기사도 후보로 조사, 수치는 공식 출처로 재확인) 이슈를 우선하고, 밀린 계획 주제는 다른 날로 옮겨 '결과' 칸에 적는다(ROUTINE_PROMPT.md step1 [주제 선정 순서]).
- 가장 최근 `log/reports/` 리포트로부터 7일이 지난 날은 주간 성과 리포트(`log/reports/RUN.md` + 텔레그램용 `cards/RUN/weekly_report.txt`)를 쓰고, 계획이 7일 이하로 남았으면 다음 달 계획을 이어 쓴다(step3_5).

## 승인·발행 (GitHub Actions 가 처리 — 프롬프트 step5·step6·step7 보다 우선)
모델 세션은 Instagram·Facebook 발행 명령(`publish.py`, `publish_reel.py`)을 실행하지 않는다(자동 모드에서 외부 게시로 차단된다). 텔레그램 승인 요청·응답 대기도 하지 않는다.
대신 카드 완성 후 아래 파일을 `cards/YYYYMMDD/` 에 만들어 **한 커밋으로 main 에 푸시**하면 끝이다.
- `card1~N.jpg` 전부(N=7~9, 번호가 끊기지 않게. 슬라이드 릴스 `reel.mp4` 는 만들지 않는다). Actions 는 card1 부터 이어진 장수만큼 텔레그램 미리보기·Instagram 캐러셀·Facebook 게시물로 올린다(5장 미만이면 승인 요청을 보내지 않는다).
- `ig.txt`, `fb.txt` : Instagram·Facebook 캡션 전문
- `flow_prompt.txt`, `reel_captions.txt`, (선택) `flow_assets.txt`·`flow_ref/` : Google Flow 영상 프롬프트(본 영상 정확히 8초, 맨 앞에 카드뉴스 표지 2초가 자동으로 붙어 전체 약 9.5초)와 핵심 내용 팝업 자막(2~4개, 2초~7.5초 구간. 7.5초 이후는 상담 QR 엔딩), Flow에 넣을 이미지 자료 목록. `python3.13 reel_overlay.py --check cards/YYYYMMDD/reel_captions.txt` 가 CAPTIONS_OK 여야 한다(자세한 규칙은 ROUTINE_PROMPT.md step3 의 7번). 사용자가 Flow 영상을 텔레그램으로 보내면 Actions 가 한글 자막을 합성해 릴스를 교체한다. 승인 대기는 최대 120분.
- `meta.txt` : 로그 앞부분 한 줄 `YYYYMMDD | 주제 | 유형 | 표지색 | 총 장수 + 내용 카드 유형`(예: `7장 formula, table, compare, steps, checklist`)
- `approval.txt` : 승인 메시지 본문(주제 요약, 표지색·총 장수·카드 유형과 이유, 수치·출처, 이미지 출처·사용권, 연구소 디자인 적용 여부, 미확인 항목). **이 파일이 푸시되면 Actions(`.github/workflows/publish-on-approval.yml`)가 시작되므로 반드시 마지막에, 다른 파일과 같은 커밋으로 올린다.**
Actions 가 카드 미리보기, Flow 프롬프트와 [발행]/[취소] 버튼을 텔레그램으로 보내고 120분 기다린 뒤, [발행]일 때만 `publish.py`·`publish_reel.py` 를 실행한다. 결과는 `cards/YYYYMMDD/status.txt` 와 `log/ig-card-news-log.md` 에 Actions 가 기록한다. 모델은 결과 로그 줄을 따로 쓰지 않는다.
- 루틴 환경에 TELEGRAM·IG·FB 환경변수가 없어도 카드 제작과 푸시는 진행한다(토큰은 GitHub Secrets 에 있다). 이전 회차를 다시 승인 요청하려면 Actions 의 workflow_dispatch 에 회차명을 넣어 실행한다.
- main 푸시가 거부되면 Actions 가 돌지 않으므로, 그 사실을 알림으로 보고한다.

## 발행
- 카드 생성·로고 합성은 `python3.13` 으로 실행한다(Pillow·numpy·qrcode가 python3.13에 설치됨).
- `deck.json`, `fonts/`, `out/`, `img/` 는 커밋하지 않는다(.gitignore 등록됨).

## 주제를 못 정했을 때 (텔레그램 질문)
주제 선정이 실패하거나 마땅한 주제가 없으면 모델은 텔레그램을 직접 보내지 않고 `topic_request/RUN.txt`(상황·시도한 주제와 이유·추천 후보 2~3개)를 main 에 푸시한다. Actions(`topic-request.yml`)가 텔레그램으로 질문을 보내고 120분 동안 사용자의 답장을 기다려 `plan/topic_override.txt` 에 저장한다. 다음 루틴 실행은 이 파일의 주제를 모든 규칙보다 우선해 진행하고(ROUTINE_PROMPT.md step1 -1번), 카드와 같은 커밋에서 파일을 삭제한다.
