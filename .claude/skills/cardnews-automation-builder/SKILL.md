---
name: cardnews-automation-builder
description: 가전소 카드뉴스 자동화(매일 Claude 루틴이 주제 조사·카드 7~9장·캡션·릴스 프롬프트 제작 → GitHub Actions 가 텔레그램 승인 후 Instagram·Facebook 발행)를 새 브랜드·새 인스타 계정용으로 복제해 구축하는 매뉴얼. 브랜드명·로고·색·상담 QR 을 바꾼 새 저장소를 스크립트로 만들고, 업종 규칙 다시 쓰기, 텔레그램 봇·Meta 페이지 토큰·GitHub Secrets 연결, 매일 예약 작업 등록, 첫 발행 점검까지 안내한다. 사용자가 "카드뉴스 자동화를 다른 브랜드/계정에도", "인스타 카드뉴스 자동 발행 새로 세팅", "가전소처럼 만들어줘", "카드뉴스 루틴 복제", "새 계정용 자동화 구축"을 말하거나, 인스타그램·페이스북 카드뉴스를 매일 자동으로 만들고 승인 후 올리는 체계를 새로 만들려 할 때 반드시 사용한다. 이미 돌아가는 가전소 저장소의 하루 작업(오늘 카드 만들기)에는 쓰지 않는다.
---

# 카드뉴스 자동화 새 브랜드 구축

가전소 저장소(madebyjs-19/gajeonso-cardnews)에서 검증된 자동화를 새 브랜드용 **새 저장소**로 복제한다. 코드와 발행 파이프라인은 그대로 쓰고, 바꾸는 것은 브랜드 자료(이름·로고·색·상담 주소)와 업종 판단 규칙, 그리고 계정 연결이다.

먼저 `references/architecture.md` 를 읽어 전체 흐름(루틴은 만들어 푸시만, 게시는 Actions 가 텔레그램 승인 후)을 파악한다. 이 구조를 바꾸지 않는 것이 이 스킬의 핵심이다 — 게시 권한을 루틴에 주거나 승인 단계를 빼면 사람이 보기 전에 글이 올라간다.

## 진행 순서

각 단계 끝에 사용자에게 무엇이 끝났고 다음에 무엇을 하는지 한두 줄로 알린다. 사용자는 개발자가 아닐 수 있으니 용어는 쉽게 풀어 쓴다.

### 1단계. 브랜드 정보 받기
한 번에 묻는다(모르는 건 나중에 채워도 된다고 알린다).
- 브랜드명(한글)·영문명, 업종과 주요 고객, 한 줄 슬로건(예: "화장품, 제대로 알고 사는 곳")
- 로고 파일(단색 선 로고·심볼 권장 — 이유는 rebrand_guide 2번)
- 상담 주소(카카오톡 채널 채팅 URL 등)와 채널 이름
- 브랜드 색 4가지(진한 기본색·포인트 블루·옅은 배경색·강조색). 없으면 가전소 색으로 시작
- 새 GitHub 저장소 이름(공개 저장소여야 함), 발행 시각(기본 오전 11시)
- 금지어·피해야 할 표현(예: 특정 매장명), 말투

`assets/brand.example.json` 을 복사해 `brand.json` 을 채운다. 항목 설명은 `references/rebrand_guide.md` 1번.

### 2단계. 새 저장소 만들기 (스크립트)
```bash
python3.13 -m pip install pillow numpy qrcode   # 없을 때만
python3.13 <스킬>/scripts/new_brand.py --config brand.json --out <새 폴더>
```
- 원본 코드: 스킬에 들어 있는 `assets/template/`(없으면 스크립트가 들어 있는 가전소 저장소). 네트워크가 되면 최신 코드를 쓰는 편이 낫다:
  `git clone --depth 1 https://github.com/madebyjs-19/gajeonso-cardnews <임시폴더>` 후 `--source <임시폴더>`.
- 스크립트가 하는 일: 코드·워크플로·디자인 도면 복사, 브랜드명·영문명·저장소 주소·상담 URL·색 치환, 로고 정리(흰 배경 정사각형), 상담 QR 생성, 빈 계획·로그·README 생성, `REBRAND_TODO.md`(남은 일 목록) 작성.
- 출력의 "남은 옛 브랜드 표기"가 0이 아니면 그 파일을 열어 고친다.

### 3단계. 업종에 맞게 규칙 다시 쓰기 (Claude 가 직접)
`REBRAND_TODO.md` 의 줄과 `references/rebrand_guide.md` 3번 표를 따라 ROUTINE_PROMPT.md·CLAUDE.md 의 업종 문장을 다시 쓴다.
- 바꾸는 것: 역할·톤, 우선 이슈 종류, 조사 출처·검색어, 사실 확인 순서, 예시, 제품 이미지 출처, 금지어, 진행자 묘사(원하면).
- 바꾸지 않는 것: step0·step3 생성 방법·카드 구조(7~9장)·step4 파일 계약과 한 커밋 푸시·approval.txt 마지막·게시 금지·토큰 비노출. 이 규칙들이 Actions 와 맞물려 있어서 고치면 발행이 깨진다.
- 가전이 아닌 업종이면 일러스트(도면) 방침을 정한다(rebrand_guide 4번). 빠르게 시작하려면 "실물 사진 우선, 없으면 illust:generic".
- `plan/content_plan.md` 에 첫 4~6주 계획을 사용자와 함께 채운다(rebrand_guide 5번).
- 끝나면 `REBRAND_TODO.md` 를 지운다.

### 4단계. 동작 점검
```bash
python3.13 <스킬>/scripts/check_brand.py <새 폴더>
```
옛 브랜드 표기·문법·필수 파일·샘플 카드 7장·표지 로고(LOGO_OK top-right)·릴스 자막·QR 엔딩·슬라이드 릴스를 점검한다(게시·전송 없음).
- FAIL 이 있으면 고치고 다시 돌린다.
- **미리보기를 직접 열어 본다**: `out/_check/20990101/card1.jpg`(표지 로고·색), `card7.jpg`(CTA 원형 로고·QR), `out/_check/end_card.png`(릴스 QR). 글씨가 배경에 묻히거나 원형 로고가 어색하면 palette·`logo_medal_crop` 을 고쳐 2단계부터 다시. 사용자에게도 이미지를 보여 주고 확인받는다.
- 색을 바꿨고 도면을 쓸 거면 도면을 다시 그린다(rebrand_guide 4번).

### 5단계. 저장소 올리기
새 GitHub 저장소(Public)에 main 으로 첫 푸시하고, Workflow permissions 를 Read and write 로 바꾼다(`references/accounts_setup.md` 1번). 이 세션이 그 저장소에 접근할 수 없으면 `add_repo`/`list_repos` 로 확인하고, 안 되면 사용자에게 로컬 푸시 방법을 안내한다.

### 6단계. 계정 연결 (사용자가 직접, Claude 는 안내·확인)
`references/accounts_setup.md` 2~4번을 **한 단계씩** 안내한다: 텔레그램 봇 → Meta 앱·만료 없는 페이지 토큰 → GitHub Secrets.
- 토큰 값을 대화창에 받지 않는다. Secrets 에 넣은 뒤 Actions "Meta 연결 점검"을 실행해 로그로 확인한다(GitHub 도구로 실행·로그 확인 가능).
- 통과 기준: IG·FB 모두 "정상 … 유형 PAGE, 만료 없음". 사용자 토큰·만료 임박이면 accounts_setup 3번을 다시 안내한다(가전소에서 실제로 반복된 실수다).

### 7단계. 매일 루틴 등록과 첫 실행
`references/routine_setup.md` 대로 환경을 확인하고, 사용자 확인 후 예약 작업을 만든다. 한 번 바로 실행해 텔레그램 승인 요청까지 오는지 본다. 첫 회는 사용자가 카드를 보고 [발행] 또는 [취소]를 고른다.

## 마무리 보고
사용자에게 표로 정리한다: 새 저장소 주소, 점검 결과, Meta 연결 결과, 예약 작업 시각, 사용자가 아직 할 일(예: 진행자 이미지 만들기, 드라이브 연결). 문제가 생기면 `references/troubleshooting.md` 를 먼저 본다.

## 참고 파일
| 파일 | 언제 |
|---|---|
| references/architecture.md | 시작할 때, 파이프라인 질문에 답할 때 |
| references/rebrand_guide.md | brand.json 작성, 로고·색, 업종 규칙 다시 쓰기, 도면, 콘텐츠 계획 |
| references/accounts_setup.md | 저장소·텔레그램·Meta·Secrets·드라이브 연결 안내 |
| references/routine_setup.md | 예약 작업 프롬프트·환경·첫 실행 |
| references/troubleshooting.md | 발행 실패·토큰·로고·자막 문제 |
| scripts/new_brand.py | 새 저장소 생성 |
| scripts/check_brand.py | 동작 점검(샘플 카드·로고·자막·릴스) |
| assets/brand.example.json, sample_deck.json, sample_captions.txt | 설정 예시·점검용 샘플 |
