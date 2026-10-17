# 계정·토큰 연결 (사용자가 직접 하는 부분)

토큰은 비밀번호와 같다. 사용자에게 **대화창에 붙여 넣지 말고 GitHub Secrets 에 바로 넣으라**고 안내한다. Claude 는 값을 보지 않고, Actions 의 "Meta 연결 점검" 결과로만 확인한다.
아래 순서대로 한 단계씩 안내하고, 각 단계가 끝났는지 확인한 뒤 다음으로 넘어간다.

## 목차
1. GitHub 저장소
2. 텔레그램 봇
3. Meta(Instagram·Facebook) — 앱·페이지 토큰
4. GitHub Secrets 넣기와 확인
5. (선택) 구글 드라이브

---

## 1. GitHub 저장소
1. 새 저장소를 **Public** 으로 만든다(Instagram 이 raw.githubusercontent.com 주소로 카드·영상을 가져가므로 비공개면 발행 실패).
2. new_brand.py 로 만든 폴더를 첫 커밋으로 main 에 올린다(`git init -b main` → `git add -A` → commit → `git remote add origin` → `git push -u origin main`). Claude 세션이 그 저장소에 접근할 수 없으면 사용자가 로컬에서 올리거나, GitHub 연결에서 저장소 접근을 허용받는다.
3. Settings → Actions → General → **Workflow permissions: Read and write permissions** 로 저장한다(Actions 가 결과를 커밋한다).
4. Actions 탭에서 워크플로가 보이는지 확인한다(첫 푸시 후 "I understand… enable" 버튼이 나오면 누른다).

## 2. 텔레그램 봇
1. 텔레그램에서 **@BotFather** → `/newbot` → 이름·아이디 입력 → 받은 토큰이 `TELEGRAM_BOT_TOKEN`.
2. 승인 메시지를 받을 대화방(본인 1:1 대화 또는 그룹)에서 봇에게 아무 메시지나 보낸다(그룹이면 봇을 초대한 뒤).
3. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates` 를 열어 `"chat":{"id": …}` 숫자를 찾는다 → `TELEGRAM_CHAT_ID`(그룹은 -로 시작).
4. 봇은 한 저장소에서만 쓴다. 같은 봇을 두 자동화가 함께 쓰면 승인 버튼 응답을 서로 가져간다.

## 3. Meta(Instagram·Facebook)

**사전 조건**: Instagram 계정이 **프로페셔널(비즈니스·크리에이터) 계정**이고 **Facebook 페이지에 연결**되어 있어야 한다(Instagram 앱 → 설정 → 계정 유형, 페이지 설정 → 연결된 계정).

**앱 만들기(처음 한 번)**
1. https://developers.facebook.com/apps → 앱 만들기 → 유형 "비즈니스"(또는 '기타 → 비즈니스').
2. 제품 추가: "Instagram Graph API"(또는 "Instagram 으로 로그인/Facebook 로그인으로 Instagram API"), "Facebook 로그인".
3. 앱 모드가 "개발"이면 본인 계정·페이지에는 그대로 게시할 수 있다. 앱 대시보드에 '필수 조치'(데이터 사용 확인, 비즈니스 인증 등) 알림이 뜨면 처리한다 — 처리하지 않으면 어느 날 `API access blocked.` 로 막힌다.

**만료 없는 페이지 토큰 받기**
1. https://developers.facebook.com/tools/explorer/ → Meta App 에서 이 앱 선택 → User or Page 는 **User Token**.
2. Permissions 에 추가: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `business_management`, `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights` → **Generate Access Token** → 팝업에서 해당 페이지·인스타 계정을 체크.
3. 생성된 토큰을 https://developers.facebook.com/tools/debug/accesstoken/ 에 넣고 **Debug** → 맨 아래 **Extend Access Token** → 나온 장기 토큰 복사.
4. 탐색기로 돌아가 Access Token 칸에 장기 토큰을 넣고 `me/accounts` 를 **Submit** → 브랜드 페이지 항목의 `access_token`(페이지 토큰)과 `id`(= `FB_PAGE_ID`) 복사.
5. 디버거에 페이지 토큰을 넣고 **Type: Page, Expires: Never** 인지 확인한다. User 이거나 만료 날짜가 보이면 3·4단계를 다시 한다.
6. 인스타 계정 ID: 탐색기에서(페이지 토큰으로) `<FB_PAGE_ID>?fields=instagram_business_account` → `instagram_business_account.id` = `IG_USER_ID`.

`IG_ACCESS_TOKEN` 과 `FB_PAGE_ACCESS_TOKEN` 에는 같은 페이지 토큰을 넣어도 된다.

## 4. GitHub Secrets 넣기와 확인
1. 저장소 → Settings → Secrets and variables → Actions → **New repository secret** 으로 아래를 넣는다. 이미 있는 이름은 연필 아이콘 → Update(새로 만들면 이름이 달라져 반영 안 됨).

| 이름 | 값 |
|---|---|
| TELEGRAM_BOT_TOKEN | 2번 토큰 |
| TELEGRAM_CHAT_ID | 2번 chat id |
| IG_ACCESS_TOKEN | 페이지 토큰 |
| IG_USER_ID | instagram_business_account.id |
| FB_PAGE_ID | 페이지 id |
| FB_PAGE_ACCESS_TOKEN | 페이지 토큰 |
| GOOGLE_SERVICE_ACCOUNT_JSON | (선택) 5번 |

2. Actions → **Meta 연결 점검** → Run workflow. 로그가 이렇게 나오면 끝:
   ```
   Instagram: 정상 - <인스타 아이디> (… 만료 없음, 유형 PAGE)
   Facebook: 정상 - <페이지 이름> (… 만료 없음, 유형 PAGE)
   ```
   "페이지 토큰이 아님", "곧 만료", "실패 - …" 가 보이면 3번을 다시 한다(Claude 가 GitHub 도구로 이 워크플로를 실행·로그 확인해 줄 수 있다).

## 5. (선택) 구글 드라이브 — 큰 Flow 영상·BGM 찾기
텔레그램 봇은 20MB 넘는 파일을 못 받는다. 드라이브를 쓰면 `릴스영상/YYMMDD` 폴더의 최신 영상을 대신 쓴다.
1. Google Cloud 콘솔 → 프로젝트 → Google Drive API 사용 설정 → 서비스 계정 만들기 → 키(JSON) 발급.
2. 드라이브에 `릴스영상` 폴더(하위에 `BGM`, 날짜 폴더 `YYMMDD`)를 만들고 서비스 계정 이메일에 **보기 권한**으로 공유.
3. 폴더 주소(`drive.google.com/drive/folders/<ID>`)의 ID 를 brand.json `drive_folder_id` 에 넣는다. 저장소를 이미 만들었으면 approval_publish.py 의 `DRIVE_ROOT = E.get("DRIVE_FOLDER_ID") or "..."` 따옴표 안에 넣어 커밋한다. JSON 키 전체는 Secret `GOOGLE_SERVICE_ACCOUNT_JSON` 에 넣는다.
드라이브를 안 쓰면 텔레그램으로 20MB 이하 영상만 보내면 된다.
