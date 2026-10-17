# 매일 루틴(예약 작업) 설정

카드를 만드는 쪽은 Claude Code 클라우드 세션을 매일 정해진 시각에 새로 띄우는 **예약 작업**이다. 발행 쪽(GitHub Actions)은 저장소에 이미 들어 있다.

## 1. 환경(Environment)
루틴이 도는 클라우드 환경에 필요한 것:
- 새 저장소에 대한 GitHub 접근(push 권한). 클라우드 세션의 저장소 목록에 새 저장소가 있어야 한다.
- 네트워크: 웹 검색·공식 사이트 확인, 폰트 다운로드(raw.githubusercontent.com), 제품 이미지 다운로드. 제한 정책이면 이 호스트들이 열려 있어야 한다.
- `python3.13` 과 `pillow numpy qrcode`. 없으면 환경 설정 스크립트에 `python3.13 -m pip install pillow numpy qrcode` 를 넣는다(없으면 루틴이 첫 단계에서 설치해도 된다).
- 토큰(IG·FB·TELEGRAM)은 루틴 환경에 **필요 없다**. Secrets 에만 둔다.

환경 설정 방법이 헷갈리면 `read_documentation` 도구(environment.setup_script, environment.network, github.access)를 읽고 안내한다.

## 2. 예약 작업 만들기
`create_trigger` 도구(claude-code-remote)가 있으면 사용자 확인 후 직접 만든다. 없으면 사용자에게 claude.ai/code 에서 예약 작업을 만들도록 아래 프롬프트를 준다.
- 이름: `⚡ <브랜드> 카드뉴스 자동화`
- 시각: 한국 시간 오전 11시 전후. cron 은 `CRON_TZ=Asia/Seoul 52 10 * * *` 처럼 정각을 피한다.
- 매 실행 새 세션(create_new_session_on_fire=true), 대상 저장소 = 새 저장소.
- 커넥터는 필요 없다(빈 목록). 푸시 알림만 켠다.

**프롬프트(브랜드·저장소만 바꿔서 그대로)**
```
<브랜드> 카드뉴스 자동 제작 루틴이다.
1. 저장소 <owner/repo> 의 main 을 최신으로 받는다(git pull --rebase origin main).
2. 저장소의 ROUTINE_PROMPT.md 전체와 CLAUDE.md 를 읽고, ROUTINE_PROMPT.md 의 step0 → step1 → step2 → step2_5 → step3 → step3_5(주간 리포트 날만) → step4 순서대로 그대로 수행한다. 중단되면 step5 를 따른다.
   - 주제: plan/content_plan.md 의 오늘 행이 기본, 이슈가 있으면 이슈 우선(step1 [주제 선정 순서]).
   - 1차 출처 확인이 막혀도 바로 중단하지 않는다. 다른 1차 출처·각도·예비 주제로 최소 3개 주제를 시도한 뒤에만 중단한다(step1 d).
   - 카드는 기본 7장, 최대 9장(표지 → 내용 5~7장 → CTA). Flow 영상 프롬프트는 고정 진행자·컨셉 12종 순환·QR 엔딩 규칙(step3 7번)을 따른다.
3. card1~N.jpg(7~9장)·ig.txt·fb.txt·flow_prompt.txt·reel_captions.txt·meta.txt·approval.txt 를 cards/회차명/ 에, 리포트 날은 weekly_report.txt 와 log/reports/회차명.md 를, 계획을 고쳤으면 plan/content_plan.md 를 함께 한 커밋으로 main 에 푸시하면 이 루틴의 작업은 끝난다. approval.txt 는 마지막에 같은 커밋으로 올린다. reel.mp4 는 만들지 않는다(Actions 가 Flow 영상 또는 카드 슬라이드 릴스로 만든다).
4. 텔레그램 승인 요청·승인 대기·Instagram/Facebook 발행·결과 로그는 GitHub Actions 가 처리하므로 직접 하지 않는다. publish.py·publish_reel.py 를 실행하지 않는다.
5. ROUTINE_PROMPT.md 나 CLAUDE.md 를 찾을 수 없으면 아무것도 만들지 말고 알림으로 "지침 파일 없음"을 보고한다.
```

## 3. 첫 실행 확인
1. Actions → Meta 연결 점검이 정상인지 먼저 본다.
2. 예약 작업을 한 번 바로 실행한다(`fire_trigger` 또는 화면의 실행 버튼).
3. 확인할 것: cards/<오늘>/ 에 카드 7~9장과 텍스트 파일이 올라왔는지 → Actions "텔레그램 승인 후 발행"이 시작됐는지 → 텔레그램에 카드 미리보기와 [발행]/[취소]가 왔는지.
4. 첫 회는 [발행] 전에 카드·캡션을 사용자가 꼼꼼히 본다. 시험만 하려면 [취소] → status.txt 가 "승인 취소"가 되고, 같은 회차를 다시 승인 요청할 수 있다.
