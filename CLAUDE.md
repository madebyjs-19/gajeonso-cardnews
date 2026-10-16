# 가전소 카드뉴스 작업 규칙 (스케줄 실행 시 반드시 적용)

## 표지 이미지 규칙 (모든 유형 A~D 공통)
- 모든 게시물의 1장 표지에는 주제에 맞는 제품 이미지를 넣는다. 제품이 주인공이 아닌 주제(제도·서비스·행사 안내 등)도 예외가 아니다.
- 이미지가 필요한 표지는 `product_cover` 카드로 만든다(`label`, `title`, `subtitle`, `image`).
  - 1순위: 공식·신뢰 출처의 실물 사진(step2_5 절차대로 내려받아 배경 제거, 출처 URL 기록, 사용권 불분명 시 승인 메시지에 "이미지 사용권 확인 필요" 명시).
  - 2순위(실물을 못 구했거나 주제를 대표하는 특정 제품이 없을 때): `"image": "illust:종류"` 일러스트. 종류는 주제와 가장 가까운 제품군으로 고른다(fridge, kimchi_fridge, washer, washer_drum, washer_top, dryer, tv, aircon, stand_aircon, air_purifier, stick_vacuum, robot_vacuum, microwave, dishwasher, styler, water_purifier, induction, generic). 연구소 디자인에서는 제품 도면(assets/blueprints/)으로 그려진다.
  - 일러스트 사용 시 승인 메시지에 "제품 이미지: 일러스트 사용"이라고 적는다.
- 표지 이후 로고는 `stamp_logo.py`로 합성한다. 이미지·제목·로고가 겹치지 않는지 직접 확인한다.
- 유형 C(포스터형)는 `poster`의 `image` 항목을 쓴다.

## 카드 디자인
- deck.json 에 `"design": "lab"` 을 넣어 연구소 리포트 디자인(모눈 배경·FILE 라벨·스펙 시트·제품 도면)으로 만든다. 자세한 규칙은 ROUTINE_PROMPT.md step3.
- 1장 오른쪽 위는 모눈 없는 로고 칸이다. `stamp_logo.py` 가 `LOGO_OK top-right` 를 출력해야 한다.

## 표지·본문 품질 규칙 (ROUTINE_PROMPT.md 의 [표지 콘텐츠 규칙]·[본문 전문성·출처 표기] 와 동일, 매 회차 적용)
- 표지는 결론·핵심 수치를 담은 요약형 제목으로 만들고, 로고는 항상 우측 상단에 둔다.
- 본문은 전문적인 수치·기준·절차 중심으로 쓰고, 2~4장 카드에 출처(기관·문서명)를 표기한다. 전체 원문 URL 은 ig.txt·fb.txt·approval.txt 에 싣는다.

## 릴스 (Flow 영상이 있을 때만)
- 카드뉴스만으로 만든 슬라이드 릴스(`make_reel.py`)는 더 이상 만들거나 올리지 않는다. 릴스는 사용자가 Google Flow 에서 만든 영상을 텔레그램(또는 드라이브 `릴스영상/YYMMDD`)으로 보냈을 때만 Actions 가 발행하며, 영상이 없으면 카드뉴스(캐러셀)만 발행한다.
- 영상 구성: 맨 앞 카드뉴스 표지 2초(자연스러운 전환) + Flow 본 영상 정확히 8초(잘리지 않음) + 핵심 내용 팝업 자막. 내레이션은 BGM 없이도 들리고, BGM 은 사용자가 텔레그램에서 지정한다.

## 승인·발행 (GitHub Actions 가 처리 — 프롬프트 step5·step6·step7 보다 우선)
모델 세션은 Instagram·Facebook 발행 명령(`publish.py`, `publish_reel.py`)을 실행하지 않는다(자동 모드에서 외부 게시로 차단된다). 텔레그램 승인 요청·응답 대기도 하지 않는다.
대신 카드 완성 후 아래 파일을 `cards/YYYYMMDD/` 에 만들어 **한 커밋으로 main 에 푸시**하면 끝이다.
- `card1~5.jpg` (슬라이드 릴스 `reel.mp4` 는 만들지 않는다)
- `ig.txt`, `fb.txt` : Instagram·Facebook 캡션 전문
- `flow_prompt.txt`, `reel_captions.txt`, (선택) `flow_assets.txt`·`flow_ref/` : Google Flow 영상 프롬프트(본 영상 정확히 8초, 맨 앞에 카드뉴스 표지 2초가 자동으로 붙어 전체 약 9.5초)와 핵심 내용 팝업 자막(3~6개, 2초~9.5초 구간), Flow에 넣을 이미지 자료 목록. `python3.13 reel_overlay.py --check cards/YYYYMMDD/reel_captions.txt` 가 CAPTIONS_OK 여야 한다(자세한 규칙은 ROUTINE_PROMPT.md step3 의 7번). 사용자가 Flow 영상을 텔레그램으로 보내면 Actions 가 한글 자막을 합성해 릴스를 교체한다. 승인 대기는 최대 120분.
- `meta.txt` : 로그 앞부분 한 줄 `YYYYMMDD | 주제 | 유형 | 표지색 | 2~4장 카드 유형`
- `approval.txt` : 승인 메시지 본문(주제 요약, 표지색·카드 유형과 이유, 수치·출처, 이미지 출처·사용권, 연구소 디자인 적용 여부, 미확인 항목). **이 파일이 푸시되면 Actions(`.github/workflows/publish-on-approval.yml`)가 시작되므로 반드시 마지막에, 다른 파일과 같은 커밋으로 올린다.**
Actions 가 카드 미리보기, Flow 프롬프트와 [발행]/[취소] 버튼을 텔레그램으로 보내고 120분 기다린 뒤, [발행]일 때만 `publish.py`·`publish_reel.py` 를 실행한다. 결과는 `cards/YYYYMMDD/status.txt` 와 `log/ig-card-news-log.md` 에 Actions 가 기록한다. 모델은 결과 로그 줄을 따로 쓰지 않는다.
- 루틴 환경에 TELEGRAM·IG·FB 환경변수가 없어도 카드 제작과 푸시는 진행한다(토큰은 GitHub Secrets 에 있다). 이전 회차를 다시 승인 요청하려면 Actions 의 workflow_dispatch 에 회차명을 넣어 실행한다.
- main 푸시가 거부되면 Actions 가 돌지 않으므로, 그 사실을 알림으로 보고한다.

## 발행
- 카드 생성·로고 합성은 `python3.13` 으로 실행한다(Pillow·numpy·qrcode가 python3.13에 설치됨).
- `deck.json`, `fonts/`, `out/`, `img/` 는 커밋하지 않는다(.gitignore 등록됨).
