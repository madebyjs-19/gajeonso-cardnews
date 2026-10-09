# 가전소 매일 카드뉴스

GitHub Actions가 조사·제작 → Telegram 승인 → Instagram/Facebook 발행을 실행한다. 기존 `gen_cards.py`, `make_reel.py`, 원본 로고와 [첨부 브랜드 가이드](docs/gajeonso_brand_guide.pdf)는 그대로 사용한다. 작업 규칙은 [AGENTS.md](AGENTS.md), 제작 지시는 [content_prompt.md](automation/content_prompt.md)에 있다.

## 처음 한 번 설정

1. 이 변경 PR을 main에 병합한다. 예약 실행은 아직 꺼져 있다.
2. [Actions Secrets 설정](https://github.com/madebyjs-19/gajeonso-cardnews/settings/secrets/actions)에서 아래 값을 등록한다. 비밀 값은 채팅·코드·로그에 붙여 넣지 않는다.

| Secret 이름 | 값 |
|---|---|
| GEMINI_API_KEY | Google AI Studio의 **결제 미연결 Free Tier 프로젝트**에서 발급한 Gemini API 키 |
| TELEGRAM_BOT_TOKEN | 이 자동화 전용 Telegram 봇의 토큰 |
| TELEGRAM_CHAT_ID | 미리보기·승인을 받을 개인 채팅 ID |
| IG_USER_ID | 기존 Instagram 전문 계정 ID |
| IG_ACCESS_TOKEN | 해당 계정의 기존 발행 권한 토큰 |
| FB_PAGE_ID | 선택: Facebook 페이지 ID |
| FB_PAGE_ACCESS_TOKEN | 선택: 같은 페이지의 발행 권한 토큰 |
| TELEGRAM_APPROVER_ID | 그룹 채팅일 때 필수: 승인할 Telegram 사용자 ID. 개인 채팅은 기본적으로 채팅 사용자 본인이다. |

Telegram 봇은 BotFather에서 만들고 해당 봇과 개인 채팅을 시작한다. 기존 Claude 자동화가 같은 봇을 조회한다면 그 자동화를 멈추거나 새 봇을 사용한다. 활성 webhook이 있는 봇은 거부한다. 이 코드가 webhook을 삭제하거나 기존 수신기를 교체하지는 않는다. Meta 토큰이 만료되면 갱신하여 같은 Secret 이름으로 교체한다.

3. 저장소 Actions → **Daily gajeonso cardnews** → **Run workflow** → `phase=check`를 실행한다. 이 단계는 Gemini 모델 접근, Telegram 봇, Meta 계정의 연결을 읽기만 하며 콘텐츠 제작·게시를 하지 않는다. 모델 조회 성공은 모든 게시 권한이나 실제 생성 품질을 보장하지 않는다.
4. 오전 11시 이전에 `phase=prepare`를 수동 실행하여 카드 5장·릴스·캡션이 Telegram에 오는지 확인한다. 검수 후 [발행 승인] 또는 [취소]를 누른다. `phase=approval`을 실행하면 선택이 기록된다. 실제 첫 발행은 오전 11시~11시59분에 `phase=publish`로 확인한다. 승인 없이는 게시하지 않는다.
5. 시험 확인 후 Actions **Variables** 탭에서 `GAJEONSO_ENABLED`를 `true`로 등록한다. 이제 매일 예약 실행된다. 중지하려면 `false`로 변경한다. 모델은 무료 입력·출력 등급이 제공되는 `gemini-3.8-flash`로 고정한다. 기존 `OPENAI_API_KEY`와 `OPENAI_MODEL`은 사용하지 않는다.

main의 쓰기 권한이 필요하다. 워크플로는 `contents: write`와 checkout 인증으로 상태·콘텐츠를 푸시한다. 조직 정책/브랜치 보호가 자동 커밋을 차단하면 게시도 중단한다. 보호 설정을 무조건 해제하지 말고 승인된 자동화의 쓰기 방식을 별도로 설정한다.

## 하루 흐름 (Asia/Seoul)

| 시간 | 작업 |
|---|---|
| 오전 10:00 | 최근 공식 자료 조사, 원고 검증, 기존 생성기로 5장 제작·로고 합성·릴스 생성, 이미지 검수, GitHub 저장, Telegram 승인 요청 |
| 오전 10:15 / 10:35 / 10:55 | 실제 Telegram 버튼 응답 확인·저장 |
| 오전 11:00 | 버튼 응답 최종 확인, 승인된 오늘 회차만 카드·릴스 게시, 최종 결과 알림 |

GitHub 예약은 UTC로 설정했다(한국 오전 10시=UTC 01시, 11시=UTC 02시). 예약 실행은 지연되거나 누락될 수 있으므로 정확한 11:00 게시를 보장하지 않는다. 정오 이후 시작된 발행은 중단한다. [GitHub 공식 예약 실행 안내](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

삼성 한국 뉴스룸 RSS와 LG 공식 뉴스룸 공개 기사 목록에서 최근 14일 가전 자료를 직접 수집한다. 초기 조사 범위는 이 두 뉴스룸이며 검색 엔진 전체를 탐색하지 않는다. 수집된 기사 URL만 사실 근거로 허용하고, 최종 원고의 출처를 다시 읽어 Gemini가 독립 검수한다. 최종 이미지 5장도 Gemini가 확인한다. 원문 부족·수집 실패·검수 실패 시 해당 회차를 중단한다. 기존 생성기의 브랜드 일러스트를 사용하며 Telegram 사람 승인까지 있어야 발행한다.

### 무료 API 설정
[Google AI Studio](https://aistudio.google.com/api-keys)에서 결제 미연결 프로젝트의 API 키를 만들고 Secrets에 `GEMINI_API_KEY`로 등록한다. AI Studio에 **Free Tier**로 표시되는지 확인한다. 무료 한도는 프로젝트·지역·모델별로 달라지며 계속 발행을 보장하지 않는다. Google 공식 요금표 기준 `gemini-3.8-flash`의 무료 등급은 텍스트·이미지 입력과 텍스트 출력이 무료다. 유료 Google Search 도구는 호출하지 않는다. 하루 정상 제작은 최대 5회 AI 요청이며 요청 시작을 최소 15초 간격으로 나눈다. 429 한도 오류 시 중단하고 다른 제공자나 모델로 자동 전환하지 않는다.

**프로그램은 API 키만으로 Google 프로젝트의 결제 연결 여부를 검증할 수 없다.** 이미 결제를 연결한 프로젝트의 키를 넣으면 Google 요금이 발생할 수 있으므로 Free Tier 프로젝트를 사용한다. 기존 OpenAI Secret은 남아 있어도 읽거나 호출하지 않는다. `phase=check`는 모델 조회만 하므로 실제 무료 생성 한도까지 보장하지 않는다. [Google 공식 요금표](https://ai.google.dev/gemini-api/docs/pricing), [무료 한도 안내](https://ai.google.dev/gemini-api/docs/rate-limits), [모델 안내](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

출력은 `cards/YYYYMMDD/`: JPG 5장, reel.mp4, IG/FB 캡션, brief.json(출처·검수 메모). 원본 생성 임시 폴더 `out/`·`fonts/`는 커밋하지 않는다. 생성·검수 실패 시 승인 요청·게시를 하지 않는다. 재실행하면 이미 만들어진 승인 대기 콘텐츠를 유지한다. 승인 후 파일·캡션 변경은 차단한다.

## 중복 방지와 장애 복구

`log/publish-state/YYYYMMDD.json`이 상태 기준이고, Markdown은 회차별 한 행으로 갱신되는 요약이다. Telegram callback은 채팅, 승인 사용자, 회차, 키, 메시지 ID를 모두 검증한다. 실제 봇 API에서 받은 응답만 처리하며, 완료된 버튼이나 다른 회차 버튼은 재사용하지 않는다.

모든 운영 실행은 `gajeonso-production` concurrency 그룹을 공유한다. `GAJEONSO_DURABLE_GIT=1`에서 상태를 저장할 때 main의 최신 HEAD를 확인하고 커밋·푸시한다. **공개 게시 요청 직전 `publishing` 기록이 GitHub에 저장되기 전에는 해당 요청을 보내지 않는다.** 낡은 체크아웃·동시 쓰기·push 실패는 중단한다. 서버가 응답 저장 전에 사라져도 다음 실행이 GitHub의 미확정 마커를 보고 재게시를 차단한다. 성공 ID는 링크 조회·알림 전에 저장한다. 이 구조는 플랫폼과 원자적 exactly-once 트랜잭션을 보장하는 대신 불확실한 요청의 자동 재시도를 막는다.

| 채널 상태 | 의미 |
|---|---|
| preparing / failed | 공개 게시 전 실패. 같은 승인 콘텐츠로 재실행 가능. 미게시 업로드 객체는 남을 수 있다. |
| success / legacy_success | 성공 또는 옛 성공 기록. 재게시 차단. |
| submitted | Facebook 릴스 finish 요청 접수. 처리 완료로 표현하지 않으며 재게시 차단. |
| publishing / unknown | 게시 요청 결과 불확실. 자동 재시도 금지, 플랫폼과 대조 필요. |
| skipped | 해당 채널 설정 누락 등. 다른 채널 결과는 유지. |

복구 순서:

1. `GAJEONSO_ENABLED=false`로 예약을 중지한다.
2. 저장된 account/container/video/media ID와 실제 플랫폼 게시 이력을 대조한다. Actions 실패 실행에는 recovery artifact가 남을 수 있지만 공개 게시 전 마커는 main에 먼저 저장되어 있다.
3. 게시물이 있으면 해당 채널만 success(미완료 FB 릴스는 submitted)와 확인한 ID·링크로 정리한다. 공개 게시가 없음을 확실히 확인한 경우에만 failed로 바꿔 동일 회차를 재시도한다.
4. 상태를 main에 저장하고 재개한다. 상태 전체 삭제·새 회차 ID로 우회·force push 금지.

Telegram 알림 실패는 게시 실패가 아니다. 승인 대기 미리보기 전송 중 프로세스가 종료되면 재전송 때 키를 교체하여 옛 버튼을 무효화한다. JSON 손상은 자동 초기화하지 않는다. 운영 환경 외에 보호 없는 로컬 발행기를 병행하지 않는다. 소문자 접미사가 있는 옛 회차는 수동 CLI에서 계속 지원하지만 매일 자동화는 오늘 날짜 하나만 사용한다.

## 수동 도구

```sh
python3.13 gen_cards.py deck.json out/YYYYMMDD
python3.13 stamp_logo.py out/YYYYMMDD/card1.png
python3.13 make_reel.py out/YYYYMMDD
python3.13 publish_state.py status YYYYMMDD
```

`stamp_logo.py`는 첨부 프롬프트의 합성 방식으로 PNG·JPG를 함께 저장한다. 빈 공간이 없으면 종료 코드 2로 멈춘다. 이미 합성한 결과에 반복 합성하지 말고 생성기 원본 PNG에서 시작한다.

기존 `publish.py RUN ig캡션 fb캡션` / `publish_reel.py RUN ig캡션 fb캡션` 인터페이스는 유지된다. 자동화는 `daily_automation.py check|prepare|approval|publish`를 사용한다. 수동 `publish_state.py prepare/approve/cancel`은 운영자 기록 도구로 남아 있지만 자동 승인을 만드는 데 사용하지 않는다.

## 검증

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

가짜 API 응답과 로컬 Git 원격 저장소로 승인 차단, 콘텐츠 검증, 콜백 인증, 중복 재실행, 응답 유실, 동시 쓰기, 서버 종료 마커, 기존 로그와 로고 합성을 검증한다. 테스트는 실제 소셜 게시·Gemini 생성 요청을 하지 않는다.
