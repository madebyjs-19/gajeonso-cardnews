# 카드뉴스 자동화 구조 (가전소 방식)

## 하루 흐름

```
09:00  [Actions] 인스타 지표 수집(metrics.yml)      → log/metrics.csv 커밋
09:30  [Actions] Meta 연결 점검(meta-check.yml)     → 문제 있을 때만 텔레그램 알림
11:00경 [Claude 루틴] ROUTINE_PROMPT.md 수행
        주제 선정(plan/content_plan.md + 최근 이슈) → 1차 출처 확인 → deck.json → gen_cards.py 로 카드 7~9장
        → stamp_logo.py 로 표지 로고 → 캡션·Flow 프롬프트·자막 → cards/RUN/ 를 한 커밋으로 main 푸시
        (approval.txt 가 마지막 파일. 이 파일이 main 에 들어가는 순간 발행 워크플로가 시작된다)
즉시   [Actions] 텔레그램 승인 후 발행(publish-on-approval.yml → approval_publish.py)
        Meta 연결 확인 → 카드 미리보기·승인 메시지·캡션·Flow 프롬프트·[발행]/[취소] 버튼 전송 → 최대 120분 대기
        사용자가 Flow 영상을 텔레그램(또는 드라이브 릴스영상/YYMMDD)으로 보내면 reel_overlay.py 로 표지 2초·자막·QR 엔딩 합성
        [발행] → publish.py(IG 캐러셀·FB 사진 게시물) + publish_reel.py(IG·FB 릴스, 영상이 없으면 make_reel.py 슬라이드 릴스)
        → cards/RUN/status.txt, log/ig-card-news-log.md 커밋
```

주제를 못 정하면 루틴은 `topic_request/RUN.txt` 를 푸시하고, topic-request.yml 이 텔레그램으로 사용자에게 묻고 답을 `plan/topic_override.txt` 에 저장한다. 다음 루틴은 그 주제를 최우선으로 쓴다.

## 역할 분리 (왜 이렇게 나눴나)
- **Claude 루틴은 게시하지 않는다.** 자동 모드의 세션에서 외부 게시는 차단되고, 사람이 보기 전에 올라가면 안 되기 때문이다. 루틴은 "파일을 만들어 푸시"까지만 한다.
- **토큰은 GitHub Secrets 에만 있다.** 루틴 환경에는 토큰이 없어도 된다. 그래서 토큰을 바꾸면 Secrets 만 바꾸면 된다.
- **Instagram 은 이미지·영상을 URL 로 가져간다.** publish.py 는 `https://raw.githubusercontent.com/<repo>/main/cards/RUN/cardN.jpg` 를 넘긴다. 그래서 저장소가 공개여야 하고, 푸시 직후 raw 주소가 200 인지 확인한다.

## cards/RUN/ 파일 계약 (루틴이 만들고 Actions 가 읽는다)
| 파일 | 만드는 쪽 | 용도 |
|---|---|---|
| card1.jpg ~ cardN.jpg (N=7~9, 연속) | 루틴 | 캐러셀. 5장 미만이면 승인 요청 안 함 |
| ig.txt / fb.txt | 루틴 | 캡션. ig.txt 첫 줄은 슬라이드 릴스 상단 훅으로도 쓰인다 |
| flow_prompt.txt, reel_captions.txt, (flow_assets.txt, flow_ref/) | 루틴 | Google Flow 영상 프롬프트·팝업 자막·참고 이미지 |
| meta.txt | 루틴 | 로그 앞부분 한 줄 `RUN | 주제 | 유형 | 표지색 | 장수+카드 유형` |
| weekly_report.txt | 루틴(리포트 날) | 승인 요청 맨 앞에 보내는 주간 요약 |
| approval.txt | 루틴(마지막) | 승인 메시지 본문. **푸시되면 발행 워크플로 시작** |
| reel.mp4 | Actions | Flow 영상 또는 슬라이드 릴스 |
| status.txt | Actions | 발행 결과. '성공'이 하나라도 있으면 재실행 시 건너뜀 |

## 재실행
- 같은 회차 다시 승인 요청: Actions → "텔레그램 승인 후 발행" → Run workflow → 회차명(예: 20261017). status.txt 에 '성공'이 없을 때만 다시 묻는다(중복 게시 방지).
- Meta 연결만 확인: Actions → "Meta 연결 점검" → Run workflow. 게시하지 않는다.

## 주요 파일
| 파일 | 역할 |
|---|---|
| gen_cards.py | 카드 생성기(1080×1350). `design: "lab"` 연구소 리포트 디자인, `--cutout` 배경 제거 |
| ROUTINE_PROMPT.md 안의 stamp_logo.py 코드 | 표지 오른쪽 위 로고 합성(매 회차 새로 써서 쓰고 지움) |
| reel_overlay.py | Flow 영상 정리 + 표지 2초 + 팝업 자막 + QR 엔딩. `--check` 로 자막 검사, `--end-card` 로 QR 패널 미리보기 |
| make_reel.py | 카드 슬라이드 릴스(Flow 영상이 없는 날) |
| approval_publish.py | 텔레그램 승인·영상 수신·드라이브 폴백·발행 실행·결과 기록 |
| publish.py / publish_reel.py | Graph API 로 IG·FB 게시 |
| collect_metrics.py | IG 게시물 지표를 회차별로 log/metrics.csv 에 기록 |
| topic_request.py | 텔레그램으로 주제를 묻고 답장 저장 |
| design/blueprints/ | 제품 도면(일러스트) 원본 SVG 생성기. render_png.sh 로 assets/blueprints/*.png 갱신 |
