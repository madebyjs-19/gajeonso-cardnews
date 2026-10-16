# 사용(GitHub Actions 전용): python approval_publish.py YYYYMMDD [YYYYMMDD ...]
# cards/YYYYMMDD/ 의 카드·릴스를 텔레그램으로 승인 요청하고, [발행]을 누른 경우에만 publish.py·publish_reel.py 를 실행한다.
# 결과는 cards/YYYYMMDD/status.txt 와 log/ig-card-news-log.md 에 남긴다. 토큰은 환경변수(GitHub Secrets)로만 받는다.
import os, re, sys, json, time, shutil, tempfile, subprocess, pathlib

import reel_overlay

E = os.environ
API = f"https://api.telegram.org/bot{E['TELEGRAM_BOT_TOKEN']}/"
CHAT = str(E["TELEGRAM_CHAT_ID"])
WAIT = 7200  # 승인 대기 최대 120분(Flow 영상 제작 시간 포함)
LOG = pathlib.Path("log/ig-card-news-log.md")
HOST_DIR = pathlib.Path("assets/reel_host")  # 릴스 고정 진행자 기준 이미지(docs/reel_host.md 참고)
REPO_RAW = "https://raw.githubusercontent.com/madebyjs-19/gajeonso-cardnews/main/cards"
MAX_DL = 20 * 1024 * 1024  # 텔레그램 봇이 내려받을 수 있는 최대 크기
MAX_DRIVE = 500 * 1024 * 1024
DRIVE_ROOT = E.get("DRIVE_FOLDER_ID") or "1KT9JGteGYQLhsHnVDmcU2xAhqZLI-lKl"  # 구글 드라이브 "릴스영상" 폴더(하위에 YYMMDD 폴더)
FLOW = {}  # 회차 -> 정리가 끝난 Flow 영상 경로(가장 최근에 받은 것)


def tg(method, fields=None, files=None, timeout=70):
    cmd = ["curl", "-sS", "-m", str(timeout), API + method]
    for k, v in (fields or {}).items():
        cmd += ["--form-string", f"{k}={v}"]
    for k, v in (files or {}).items():
        cmd += ["-F", f"{k}=@{v}"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except ValueError:
        return {}


def say(text):
    tg("sendMessage", {"chat_id": CHAT, "text": text[:4000]})


def card_files(folder):
    """card1.jpg 부터 끊기지 않고 이어진 카드 목록(7~9장, 예전 회차는 5장)."""
    out = []
    while (folder / f"card{len(out) + 1}.jpg").exists() and len(out) < 10:
        out.append(folder / f"card{len(out) + 1}.jpg")
    return out


def request_approval(d, folder):
    wr = folder / "weekly_report.txt"  # 주간 성과 리포트 날이면 맨 앞에 보낸다
    if wr.exists():
        say(wr.read_text(encoding="utf-8").strip())
    cards = card_files(folder)  # 텔레그램 앨범은 한 번에 2~10장
    media = [{"type": "photo", "media": f"attach://c{i}"} for i in range(1, len(cards) + 1)]
    tg("sendMediaGroup", {"chat_id": CHAT, "media": json.dumps(media)},
       {f"c{i}": f for i, f in enumerate(cards, 1)}, timeout=240)
    note = folder / "approval.txt"
    say(note.read_text(encoding="utf-8") if note.exists() else f"[가전소 카드뉴스 승인 요청 {d}]")
    say("[Instagram 캡션]\n" + (folder / "ig.txt").read_text(encoding="utf-8"))
    fp, rc = folder / "flow_prompt.txt", folder / "reel_captions.txt"
    if fp.exists():
        # 고정 진행자 기준 이미지(assets/reel_host/): 매 회차 같은 인물이 나오도록 Flow 의 재료(Ingredients)로 넣는다
        for f in sorted(HOST_DIR.glob("*"))[:3] if HOST_DIR.exists() else []:
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                tg("sendDocument", {"chat_id": CHAT, "caption": f"[Flow 고정 진행자] {f.name} — Flow '재료(Ingredients)'에 꼭 넣어 주세요. 매 회차 같은 인물이 나오게 합니다."},
                   {"document": f}, timeout=120)
        # Flow 에서 쓸 참고 이미지: 타이틀 카드(card1)와 cards/<회차>/flow_ref/ 의 파일을 원본 화질로 보낸다
        refs = [folder / "card1.jpg"] + sorted((folder / "flow_ref").glob("*"))[:5] if (folder / "flow_ref").exists() \
            else [folder / "card1.jpg"]
        for i, f in enumerate(r for r in refs if r.is_file()):
            cap = "[Flow 참고 이미지] 타이틀 카드(영상 맨 앞 2초에 자동으로 붙습니다. Flow에 따로 넣을 필요는 없고, 분위기 참고용)" if i == 0 \
                else f"[Flow 참고 이미지] {f.name}"
            tg("sendDocument", {"chat_id": CHAT, "caption": cap}, {"document": f}, timeout=120)
        fa = folder / "flow_assets.txt"
        # 프롬프트는 설명 없이 그것만 담은 메시지로 따로 보내서 길게 눌러 바로 복사할 수 있게 한다
        lines = fp.read_text(encoding="utf-8").strip().splitlines()
        while lines and lines[0].strip().startswith("[") and lines[0].strip().endswith("]"):
            lines.pop(0)  # 혹시 들어간 제목 줄은 뺀다
        say("[Flow 영상 프롬프트] 바로 다음 메시지가 프롬프트입니다. 그 메시지를 길게 눌러 복사해서 Flow에 붙여 넣으세요.")
        say("\n".join(lines).strip())
        if fa.exists():
            say("[Flow에 넣을 이미지 자료] 직접 준비해서 Flow에 올려 주세요.\n" + fa.read_text(encoding="utf-8").strip())
        if rc.exists():
            say("[팝업 자막 목록] 핵심 내용이 영상에 자동 합성됩니다(맨 앞 2초는 표지, 마지막 2초는 상담 QR). 영상 속에는 글자를 넣지 마세요.\n" + rc.read_text(encoding="utf-8").strip())
        say("[영상 보내는 방법]"
            "\n1) 영상 맨 앞에 카드뉴스 표지(타이틀 카드) 2초가 자연스러운 전환과 함께 자동으로 붙고, 팝업 자막은 그 뒤에 나옵니다. 본 영상은 정확히 8초로 만드세요(총 약 9.5초)."
            "\n   마지막 2초는 진행자가 화면 오른쪽 위를 가리키는 장면이고, 그 자리에 카드뉴스와 같은 상담 QR이 자동으로 얹힙니다(Flow에서 QR을 그리지 마세요)."
            "\n   8.3초까지는 잘라내지 않고 속도만 맞추며, 그보다 길면 뒷부분이 잘립니다."
            "\n2) 만든 영상(20MB 이하)을 이 대화방에 보내 주세요. [발행] 버튼을 누르기 전에 보내야 반영됩니다. 대기 시간 최대 120분."
            f"\n   용량이 커서 못 보내면 구글 드라이브 '릴스영상/{d[2:]}' 폴더에 올려 두세요. 텔레그램 영상이 없으면 그 폴더의 가장 최근 영상을 씁니다."
            "\n3) 내레이션이 있는 영상은 BGM이 없어도 소리가 그대로 들립니다."
            "\n4) BGM이 필요하면 영상을 보낼 때 캡션에(또는 따로 메시지로) 이렇게 적어 주세요."
            "\n   BGM: 제목  → 드라이브 '릴스영상/BGM' 폴더에서 파일 이름에 그 제목이 들어간 음원"
            "\n   BGM: https://…/음원.mp3  → 음원 파일 직링크"
            "\n   또는 음원 파일(mp3 등)을 이 대화방에 함께 보내 주세요."
            "\n   ※ 인스타그램 음악 라이브러리의 곡 제목, 유튜브·스트리밍 링크는 사용할 수 없습니다(저작권·이용약관, 자동 발행에서는 인스타 음악 선택 불가)."
            "\n5) 영상을 보내지 않으면 카드 표지·2·3장과 마지막 장으로 만든 슬라이드 릴스가 자동으로 함께 발행됩니다.")
    kb = {"inline_keyboard": [[{"text": "✅ 발행 (Instagram + Facebook)", "callback_data": f"approve_{d}"},
                               {"text": "❌ 취소", "callback_data": f"cancel_{d}"}]]}
    r = tg("sendMessage", {"chat_id": CHAT, "reply_markup": json.dumps(kb),
                           "text": "[Facebook 캡션]\n" + (folder / "fb.txt").read_text(encoding="utf-8")})
    return bool(r.get("ok"))


BLOCKED_HOSTS = ("youtube.", "youtu.be", "instagram.", "spotify.", "tiktok.", "soundcloud.", "melon.", "genie.", "bugs.",
                 "apple.com", "naver.", "vibe.", "facebook.", "fb.watch", "music.")
AUDIO_EXT = (".mp3", ".m4a", ".wav", ".aac", ".ogg")
MAX_BGM = 30 * 1024 * 1024
STATE = {}  # 회차 -> {"raw": 받은 본 영상 경로, "bgm": 쓸 BGM 경로}


def st(d):
    return STATE.setdefault(d, {"raw": None, "bgm": None})


def tmpdir():
    return pathlib.Path(tempfile.gettempdir())  # 저장소 밖에 둬서 결과 커밋에 섞이지 않게 한다


def tg_download(d, f, dest, what):
    """텔레그램 파일(f)을 dest 로 내려받는다. 실패하면 사유를 알리고 False."""
    if f.get("file_size", 0) > MAX_DL:
        extra = (f" 구글 드라이브 '릴스영상/{d[2:]}' 폴더에 올려 두시면 [발행] 시 그 영상을 씁니다." if what == "영상"
                 else " 드라이브 '릴스영상/BGM' 폴더에 넣고 제목을 알려 주세요.")
        say(f"[{d}] {what}이(가) 20MB를 넘어 텔레그램으로는 받을 수 없습니다.{extra}")
        return False
    path = (tg("getFile", {"file_id": f["file_id"]}).get("result") or {}).get("file_path")
    if not path:
        say(f"[{d}] {what}을(를) 내려받지 못했습니다(파일이 너무 크거나 만료됨). 다시 보내 주세요.")
        return False
    dl = subprocess.run(["curl", "-sS", "-f", "-m", "300", "-o", str(dest),
                         f"https://api.telegram.org/file/bot{E['TELEGRAM_BOT_TOKEN']}/{path}"], capture_output=True, text=True)
    if dl.returncode != 0 or not dest.exists():
        say(f"[{d}] {what} 다운로드 실패. 다시 보내 주세요.")
        return False
    return True


def parse_bgm(text):
    m = re.search(r"(?im)^\s*(?:bgm|비지엠|배경\s*음악)\s*[:：=\-]?\s*(.+?)\s*$", text or "")
    return m.group(1).strip() if m else None


def fetch_bgm_url(d, url):
    import urllib.parse, urllib.request
    u = urllib.parse.urlparse(url)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not host or host == "localhost" or re.fullmatch(r"[0-9.]+", host) or host.endswith(".local"):
        say(f"[{d}] BGM 링크는 https 로 시작하는 공개 주소만 가능합니다.")
        return None
    if any(b in host for b in BLOCKED_HOSTS):
        say(f"[{d}] 유튜브·인스타그램·스트리밍 서비스 링크에서는 저작권·이용약관 문제로 음원을 가져오지 않습니다. "
            "직접 보유한 음원 파일(mp3 등)을 이 대화방에 보내거나, 드라이브 '릴스영상/BGM' 폴더에 넣고 제목을 알려 주세요.")
        return None
    if not u.path.lower().endswith(AUDIO_EXT):
        say(f"[{d}] BGM 링크는 음원 파일 직링크({', '.join(AUDIO_EXT)})만 가능합니다.")
        return None
    dest = tmpdir() / f"{d}_bgm{pathlib.Path(u.path).suffix.lower()}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
            n = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                n += len(chunk)
                if n > MAX_BGM:
                    raise ValueError("30MB 초과")
                f.write(chunk)
    except Exception as e:
        say(f"[{d}] BGM 링크 다운로드 실패: {str(e)[:100]}")
        return None
    return dest


def drive_find_bgm(d, title):
    """드라이브 '릴스영상/BGM' 폴더에서 파일 이름에 title 이 들어간 음원을 찾아 내려받는다."""
    try:
        sess = drive_session()
        if sess is None:
            say(f"[{d}] BGM 제목으로 찾으려면 드라이브 접근 설정(GOOGLE_SERVICE_ACCOUNT_JSON)이 필요합니다. 음원 파일을 이 대화방에 직접 보내 주세요.")
            return None
        sub = drive_list(sess, f"'{DRIVE_ROOT}' in parents and name = 'BGM' and "
                               "mimeType = 'application/vnd.google-apps.folder' and trashed = false")
        if not sub:
            say(f"[{d}] 드라이브 '릴스영상' 안에 'BGM' 폴더가 없습니다. 만들고 음원을 넣어 주세요.")
            return None
        files = drive_list(sess, f"'{sub[0]['id']}' in parents and trashed = false")
        files = [f for f in files if f["name"].lower().endswith(AUDIO_EXT)]
        hit = [f for f in files if title.lower() in f["name"].lower()]
        if not hit:
            names = ", ".join(f["name"] for f in files[:10]) or "(비어 있음)"
            say(f"[{d}] BGM 폴더에서 '{title}'이(가) 들어간 음원을 찾지 못했습니다. 폴더에 있는 파일: {names}")
            return None
        f = hit[0]
        if int(f.get("size", 0)) > MAX_BGM:
            say(f"[{d}] BGM '{f['name']}'이(가) 30MB를 넘습니다.")
            return None
        dest = tmpdir() / f"{d}_bgm{pathlib.Path(f['name']).suffix.lower()}"
        with sess.get(f"https://www.googleapis.com/drive/v3/files/{f['id']}",
                      params={"alt": "media", "supportsAllDrives": "true"}, stream=True, timeout=300) as r:
            r.raise_for_status()
            with dest.open("wb") as out:
                for chunk in r.iter_content(1 << 20):
                    out.write(chunk)
        return dest
    except Exception as e:
        say(f"[{d}] BGM 찾기 실패: {type(e).__name__} {str(e)[:120]}")
        return None


def receive_message(d, folder, msg):
    """등록된 채팅에서 온 본 영상·BGM(음원 파일, 'BGM: 제목' 또는 음원 직링크)을 받아 반영한다."""
    if str(msg.get("chat", {}).get("id")) != CHAT:
        return
    doc = msg.get("document") or {}
    mime = str(doc.get("mime_type", ""))
    video = msg.get("video") or (doc if mime.startswith("video/") else None)
    audio = msg.get("audio") or (doc if (mime.startswith("audio/") or str(doc.get("file_name", "")).lower().endswith(AUDIO_EXT)) else None)
    spec = parse_bgm(msg.get("caption") or msg.get("text") or "")
    if not (video or audio or spec):
        return
    s_ = st(d)
    changed = False
    if video:
        raw = tmpdir() / f"{d}_flow_raw.mp4"
        if tg_download(d, video, raw, "영상"):
            s_["raw"], changed = raw, True
    if audio:
        dest = tmpdir() / f"{d}_bgm{pathlib.Path(audio.get('file_name') or 'x.mp3').suffix.lower() or '.mp3'}"
        if tg_download(d, audio, dest, "음원 파일"):
            s_["bgm"], changed = dest, True
    if spec:
        b = fetch_bgm_url(d, spec) if re.match(r"https?://", spec) else drive_find_bgm(d, spec)
        if b:
            s_["bgm"], changed = b, True
    if changed:
        rebuild(d, folder)


def rebuild(d, folder):
    s_ = st(d)
    if not s_["raw"]:
        say(f"[{d}] BGM을 받았습니다. 본 영상을 보내 주시면 함께 합성합니다.")
        return
    res = make_flow(d, folder, s_["raw"], s_["bgm"])
    if res:
        note, warn, out = res
        tg("sendVideo", {"chat_id": CHAT, "caption": f"[{d}] Flow 영상 반영본 미리보기 ({note}). 이대로면 [발행]을 누르세요. "
                         f"영상이나 BGM('BGM: 제목' 또는 음원 파일)을 다시 보내시면 교체됩니다.{warn}"[:1000]},
           {"video": out}, timeout=180)


def make_flow(d, folder, raw, bgm=None):
    """원본 영상을 정리·자막·BGM 합성해 FLOW[d] 에 등록한다. 성공하면 (설명, 경고, 경로), 실패하면 None."""
    missing = [t for t in ("ffmpeg", "ffprobe") if not shutil.which(t)]
    if missing:
        say(f"[{d}] 영상 변환 도구({', '.join(missing)})가 설치되어 있지 않아 영상을 반영할 수 없습니다. 릴스 없이 카드뉴스만 발행됩니다.")
        return None
    out = tmpdir() / f"{d}_flow_reel.mp4"
    caps = folder / "reel_captions.txt"
    card = str(folder / "card1.jpg")
    bgm = str(bgm) if bgm else None
    warn = ""
    try:
        note = reel_overlay.build(str(raw), str(out), str(caps), card, bgm)
    except ValueError as e:  # 자막 검사 실패: 글자가 깨질 수 있으므로 자막 없이 합성
        warn = "\n자막 검사에서 문제가 있어 자막 없이 합성했습니다:\n" + str(e)[:600]
        try:
            note = reel_overlay.build(str(raw), str(out), None, card, bgm)
        except Exception as e2:
            say(f"[{d}] 영상 변환 실패: {str(e2)[:200]}")
            return None
    except Exception as e:
        say(f"[{d}] 영상 변환 실패: {str(e)[:200]}")
        return None
    FLOW[d] = out
    return note, warn, out


def drive_session():
    raw = E.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return AuthorizedSession(creds)


def drive_list(sess, q):
    r = sess.get("https://www.googleapis.com/drive/v3/files",
                 params={"q": q, "fields": "files(id,name,size,modifiedTime)", "orderBy": "modifiedTime desc",
                         "pageSize": 20, "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}, timeout=60)
    r.raise_for_status()
    return r.json().get("files", [])


def drive_fallback(d, folder):
    """텔레그램으로 영상이 오지 않았을 때 구글 드라이브 '릴스영상/YYMMDD' 폴더의 가장 최근 영상을 쓴다."""
    ymd = d[2:]  # 20261016 -> 261016, 20261016b -> 261016b
    names = [ymd] + ([ymd[:-1]] if ymd[-1].isalpha() else [])
    try:
        sess = drive_session()
        if sess is None:
            say(f"[{d}] 텔레그램 영상이 없고 드라이브 접근 설정(GOOGLE_SERVICE_ACCOUNT_JSON)도 없어 릴스 없이 카드뉴스만 발행합니다.")
            return
        sub = []
        for n in names:
            sub = drive_list(sess, f"'{DRIVE_ROOT}' in parents and name = '{n}' and "
                                   "mimeType = 'application/vnd.google-apps.folder' and trashed = false")
            if sub:
                break
        if not sub:
            say(f"[{d}] 드라이브에 '{names[0]}' 폴더가 없어 릴스 없이 카드뉴스만 발행합니다.")
            return
        vids = drive_list(sess, f"'{sub[0]['id']}' in parents and mimeType contains 'video/' and trashed = false")
        if not vids:
            say(f"[{d}] 드라이브 '{names[0]}' 폴더에 영상이 없어 릴스 없이 카드뉴스만 발행합니다.")
            return
        v = vids[0]  # 가장 최근에 수정된 영상
        if int(v.get("size", 0)) > MAX_DRIVE:
            say(f"[{d}] 드라이브 영상 '{v['name']}'이 500MB를 넘어 릴스 없이 카드뉴스만 발행합니다.")
            return
        raw = pathlib.Path(tempfile.gettempdir()) / f"{d}_flow_raw.mp4"
        with sess.get(f"https://www.googleapis.com/drive/v3/files/{v['id']}",
                      params={"alt": "media", "supportsAllDrives": "true"}, stream=True, timeout=600) as r:
            r.raise_for_status()
            with raw.open("wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        st(d)["raw"] = raw
        res = make_flow(d, folder, raw, st(d)["bgm"])
        if res:
            say(f"[{d}] 드라이브 영상 '{v['name']}'을 사용합니다({res[0]}).{res[1]}")
    except Exception as e:
        say(f"[{d}] 드라이브 영상 확인 실패, 릴스 없이 카드뉴스만 발행합니다: {type(e).__name__} {str(e)[:150]}")


def slide_reel(d, folder):
    """Flow 영상이 없는 날: 표지·2·3장과 마지막 장(상담 접수증)으로 슬라이드 릴스를 만든다(약 14.5초). 실패하면 None."""
    out = tmpdir() / f"{d}_slide_reel.mp4"
    pick = f"1,2,3,{len(card_files(folder))}"
    r = subprocess.run([sys.executable, "make_reel.py", str(folder), pick, str(out)], capture_output=True, text=True)
    if r.returncode or not out.exists():
        say(f"[{d}] 카드 슬라이드 릴스 생성 실패, 카드뉴스만 발행됩니다: {(r.stderr or r.stdout)[-200:]}")
        return None
    return out


def push_reel(d, folder, src=None, label="Flow 영상"):
    """릴스 영상(기본: Flow 영상)을 cards/<회차>/reel.mp4 로 교체해 main 에 올리고 raw 주소에 반영될 때까지 기다린다."""
    src = src or FLOW.get(d)
    if not src or not src.exists():
        return ""
    dst = folder / "reel.mp4"
    shutil.copyfile(src, dst)
    sh = lambda *a: subprocess.run(a, capture_output=True, text=True)
    sh("git", "config", "user.name", "github-actions[bot]")
    sh("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    sh("git", "add", str(dst))
    sh("git", "commit", "-m", f"{label} 릴스 반영: {d}")
    pushed = False
    for _ in range(3):
        if sh("git", "pull", "--rebase", "--autostash", "origin", "main").returncode == 0 and \
                sh("git", "push", "origin", "HEAD:main").returncode == 0:
            pushed = True
            break
        time.sleep(5)
    if not pushed:
        say(f"[{d}] {label} 커밋·푸시 실패, 릴스 없이 카드뉴스만 발행됩니다.")
        return ""
    size = dst.stat().st_size
    for _ in range(60):  # 최대 약 10분: raw 주소가 새 파일로 바뀔 때까지
        head = sh("curl", "-sSIL", "-m", "20", f"{REPO_RAW}/{d}/reel.mp4").stdout
        m = re.findall(r"(?im)^content-length:\s*(\d+)", head)
        if m and int(m[-1]) == size:
            return f" · {label} 사용"
        time.sleep(10)
    say(f"[{d}] 새 영상이 아직 공개 주소에 반영되지 않아 릴스 발행이 실패할 수 있습니다.")
    return f" · {label} 사용(반영 지연)"


def wait_decision(d, folder):
    # 이전에 쌓인 업데이트는 건너뛴다(이번 요청 이후의 버튼만 인정)
    old = tg("getUpdates", {"timeout": "0"}).get("result", [])
    offset = old[-1]["update_id"] + 1 if old else 0
    end = time.time() + WAIT
    while time.time() < end:
        r = tg("getUpdates", {"offset": str(offset), "timeout": "50",
                              "allowed_updates": json.dumps(["callback_query", "message"])})
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            if u.get("message"):
                receive_message(d, folder, u["message"])
                continue
            cq = u.get("callback_query") or {}
            if str(cq.get("message", {}).get("chat", {}).get("id")) != CHAT:
                continue
            if cq.get("data") in (f"approve_{d}", f"cancel_{d}"):
                tg("answerCallbackQuery", {"callback_query_id": cq["id"]})
                tg("getUpdates", {"offset": str(offset), "timeout": "0"})  # 처리한 업데이트 확인 처리
                return cq["data"].split("_", 1)[0]
        if not r.get("ok", True):
            time.sleep(10)
    return "expired"


def summarize(out):
    names = {"Instagram": "IG", "Facebook": "FB", "Instagram 릴스": "IG 릴스", "Facebook 릴스": "FB 릴스"}
    parts = []
    for line in out.splitlines():
        k, _, v = line.partition(": ")
        if k in names:
            label = names[k]
            if v.startswith("발행"):
                parts.append(f"{label} 발행 성공" if "릴스" not in label else f"{label} 성공")
            elif v.startswith("건너뜀"):
                parts.append(f"{label} 설정 누락")
            else:
                parts.append(f"{label} 실패({v.removeprefix('실패: ')[:60]})")
    return " · ".join(parts) or "결과 확인 불가"


def run(script, d, folder):
    p = subprocess.run([sys.executable, script, d, str(folder / "ig.txt"), str(folder / "fb.txt")],
                       capture_output=True, text=True, timeout=1200)
    print(p.stdout)
    if p.returncode != 0:
        tail = (p.stderr.strip().splitlines() or ["알 수 없는 오류"])[-1][:150]
        say(f"[{d}] {script} 실행 오류: {tail}")
        return p.stdout + f"\n{'Instagram 릴스' if 'reel' in script else 'Instagram'}: 실패: 스크립트 오류"
    return p.stdout


def process(d):
    if not re.fullmatch(r"\d{8}[a-z]?", d):
        print(f"잘못된 회차 이름: {d}")
        return
    folder = pathlib.Path("cards") / d
    status = folder / "status.txt"
    if status.exists():
        print(f"{d}: 이미 처리됨({status.read_text(encoding='utf-8').strip()}), 건너뜀")
        return
    missing = [n for n in ["ig.txt", "fb.txt"] if not (folder / n).exists()]
    if len(card_files(folder)) < 5:
        missing.insert(0, f"카드(card1~ 이어진 것 {len(card_files(folder))}장, 5장 이상 필요)")
    if missing:
        say(f"[{d}] 승인 요청 불가: {', '.join(missing)} 없음")
        return
    if not request_approval(d, folder):
        say(f"[{d}] 승인 요청 전송 실패, 발행 안 함")
        result = "승인 요청 전송 실패"
    else:
        decision = wait_decision(d, folder)
        if decision == "approve":
            if d not in FLOW:  # 텔레그램으로 영상이 안 왔으면 구글 드라이브 폴더에서 찾는다
                drive_fallback(d, folder)
            flow_note = push_reel(d, folder)
            if not flow_note:  # Flow 영상이 없으면 카드 슬라이드 릴스로 대신 발행한다(릴스가 새 사람에게 닿는 주 통로)
                slide = slide_reel(d, folder)
                flow_note = push_reel(d, folder, slide, "카드 슬라이드") if slide else ""
            out = run("publish.py", d, folder)
            if flow_note:
                out += run("publish_reel.py", d, folder)
                result = summarize(out) + flow_note
            else:
                result = summarize(out) + " · 릴스 미발행(영상 생성 실패)"
        elif decision == "cancel":
            say(f"[{d}] 취소됨, 발행 안 함")
            result = "승인 취소"
        else:
            say(f"[{d}] 승인 대기 시간 만료, 발행 안 함")
            result = "승인 만료"
    status.write_text(result + "\n", encoding="utf-8")
    meta = folder / "meta.txt"
    head = meta.read_text(encoding="utf-8").strip() if meta.exists() else f"{d} | (meta.txt 없음) | | | "
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{head} | {result} (Actions)\n")
    print(f"{d}: {result}")


if __name__ == "__main__":
    for d in sys.argv[1:]:
        process(d)
