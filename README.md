# 가전소 카드뉴스

첨부된 원본 [브랜드 가이드](docs/gajeonso_brand_guide.pdf)를 변경 없이 보관한다. 기존 `gen_cards.py`와 `make_reel.py`를 사용한다. 브랜드 디자인과 생성기는 변경하지 않았다. 작업 지침은 [AGENTS.md](AGENTS.md)를 따른다.

## 제작 → 승인 → 발행

Asia/Seoul 오전 10시 PREP, 오전 11시 승인된 회차 PUBLISH를 별도로 실행하는 구조다. 이 변경은 스케줄러나 Telegram callback 수신기를 설치하지 않는다. 기존 실행 환경에서 아래 명령과 승인 저장 단계를 연결해야 한다.

```sh
python3.13 gen_cards.py deck.json out/20261012
python3.13 stamp_logo.py out/20261012/card1.png
python3.13 make_reel.py out/20261012
```

최종 검수 후 JPG 5장과 reel.mp4를 `cards/20261012/`에 복사하고 두 캡션도 같은 폴더에 저장한다. `stamp_logo.py`는 첨부된 기존 프롬프트의 로고 합성 방식을 사용하며 PNG와 JPG를 함께 저장한다. 빈 공간이 없으면 종료 코드 2로 중단한다. 이미 로고가 있는 결과에 반복 합성하지 말고 생성기의 원본 PNG에서 시작한다.

```sh
python3.13 publish_state.py prepare 20261012 \
  --ig-caption cards/20261012/caption_ig.txt \
  --fb-caption cards/20261012/caption_fb.txt \
  --topic '주제' --type B --cover navy --cards 'table,compare,checklist'
```

`TELEGRAM_CHAT_ID`가 필요하다. 출력된 `approval.key`를 회차와 함께 Telegram 승인 버튼 callback에 넣는다. 미리보기와 캡션을 전송한다. **실제 Telegram callback을 인증하고 지정된 채팅·회차·키·승인 버튼을 확인한 기존 승인 처리기 또는 운영자만** 다음 명령을 실행한다. 명령 자체는 Telegram과 통신하여 callback을 인증하지 않는다. 키를 안다는 이유로 자동 승인하지 않는다.

```sh
python3.13 publish_state.py approve 20261012 \
  --approval-key ACTUAL_KEY --chat-id ACTUAL_CHAT_ID --callback-id ACTUAL_CALLBACK_ID
# 취소 버튼은 동일한 인자로 approve 대신 cancel
```

상태와 콘텐츠를 main에 커밋·푸시하고, 영구 실행 디렉터리에서 오전 11시에 실행한다. 기존 발행 명령의 위치 인자는 유지된다. 승인 저장 없이 기존 명령만 실행하면 게시가 차단된다.

```sh
python3.13 publish.py 20261012 cards/20261012/caption_ig.txt cards/20261012/caption_fb.txt
python3.13 publish_reel.py 20261012 cards/20261012/caption_ig.txt cards/20261012/caption_fb.txt
python3.13 publish_state.py status 20261012
```

IG: `IG_USER_ID`, `IG_ACCESS_TOKEN`. FB: `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`. 알림: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. 환경변수 값을 출력하지 않는다. 발행 URL은 기존과 같이 이 저장소 main의 raw 파일이다. 발행기는 해당 URL의 바이트가 로컬 승인 파일과 같은지 확인하고 게시한다. 검사 후에도 main 콘텐츠를 교체하지 않는다.

## 영구 상태와 복구

`log/publish-state/RUN.json`은 버전 관리 대상이다. 원자적 파일 교체와 로컬 회차 잠금으로 카드/릴스 동시 실행을 차단한다. 서로 다른 회차의 Markdown 갱신도 잠금으로 보호한다. 회차 ID는 `YYYYMMDD` 또는 기존처럼 소문자 접미사 하나를 허용한다.

- `preparing` / `failed`: 공개 게시 전 실패. 수정 후 동일 승인 콘텐츠로 재실행 가능. 미게시 업로드 객체가 남을 수 있다.
- `success` / `legacy_success`: 재게시 차단. 게시 ID를 응답 직후 저장하므로 링크 조회·Telegram 실패가 성공을 취소하지 않는다.
- `submitted`: Facebook 릴스 finish 요청 접수. 처리 완료를 보장하지 않으며 자동 재게시하지 않는다.
- `publishing` / `unknown`: 공개 게시 요청 직전의 영구 마커 또는 응답 불확실. **자동 재시도하지 않는다.** API가 오류를 반환한 경우도 보수적으로 대조가 필요하다.

복구는 먼저 스케줄러를 멈추고 `status`와 저장된 account/container/video ID, 플랫폼 게시 이력을 대조한다. 게시물이 있으면 해당 채널의 status를 success(미완료 릴스는 submitted), media_id와 확인한 permalink를 기록한다. 공개 게시가 없음을 확실히 확인한 경우에만 failed로 변경하여 같은 회차를 재시도한다. 상태 전체를 삭제하거나 새 회차 ID로 우회하지 않는다. 수동 수정 후 `status` 출력으로 JSON을 확인하고 다음 실행이 Markdown을 갱신하게 한다. 손상된 JSON은 자동 초기화하지 않는다.

발행 후 `log/`를 커밋·푸시한다. 프로세스가 push 전에 죽어도 영구 로컬 JSON을 보존해야 한다. 새 임시 체크아웃마다 실행하는 환경이나 여러 서버는 공유 트랜잭션 저장소·분산 잠금 없이 지원하지 않는다. Git 동기화는 분산 잠금이 아니며 이 구현은 플랫폼과의 원자적 exactly-once 트랜잭션을 보장하지 않는다. 로컬 상태가 남아 있는 경우 불확실한 요청을 다시 보내지 않는 방식으로 중복 위험을 줄인다.

옛 성공 로그는 첫 실행 시 보수적으로 가져온다. Markdown은 기존 회차 메타데이터와 모든 채널 결과를 하나의 행에 유지한다. 원시 예외·인증 URL은 기록하지 않는다. 실행 종료 코드 1은 사전 검사 실패·채널 실패·설정 누락·대조 필요를 뜻한다. Telegram 알림 실패만으로는 성공한 게시를 실패 처리하지 않는다.

## 검증

```sh
python3 -m unittest discover -s tests -v
```

가짜 Meta 응답으로 승인 차단, 내용 변경, 채널별 재실행, 응답 유실, 링크 조회/알림 실패, 프로세스 중단, 잠금, 옛 로그와 릴스 접수 상태를 검증한다. 실제 게시 API는 호출하지 않는다.
