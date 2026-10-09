# 사용(GitHub Actions 전용): python approval_publish.py YYYYMMDD [YYYYMMDD ...]
# cards/YYYYMMDD/ 의 카드·릴스를 텔레그램으로 승인 요청하고, [발행]을 누른 경우에만 publish.py·publish_reel.py 를 실행한다.
# 결과는 cards/YYYYMMDD/status.txt 와 log/ig-card-news-log.md 에 남긴다. 토큰은 환경변수(GitHub Secrets)로만 받는다.
import os, re, sys, json, time, subprocess, pathlib

E = os.environ
API = f"https://api.telegram.org/bot{E['TELEGRAM_BOT_TOKEN']}/"
CHAT = str(E["TELEGRAM_CHAT_ID"])
WAIT = 3600  # 승인 대기 최대 60분
LOG = pathlib.Path("log/ig-card-news-log.md")


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


def request_approval(d, folder):
    media = [{"type": "photo", "media": f"attach://c{i}"} for i in range(1, 6)]
    tg("sendMediaGroup", {"chat_id": CHAT, "media": json.dumps(media)},
       {f"c{i}": folder / f"card{i}.jpg" for i in range(1, 6)}, timeout=180)
    if (folder / "reel.mp4").exists():
        tg("sendVideo", {"chat_id": CHAT, "caption": "릴스 미리보기"}, {"video": folder / "reel.mp4"}, timeout=180)
    note = folder / "approval.txt"
    say(note.read_text(encoding="utf-8") if note.exists() else f"[가전소 카드뉴스 승인 요청 {d}]")
    say("[Instagram 캡션]\n" + (folder / "ig.txt").read_text(encoding="utf-8"))
    kb = {"inline_keyboard": [[{"text": "✅ 발행 (Instagram + Facebook)", "callback_data": f"approve_{d}"},
                               {"text": "❌ 취소", "callback_data": f"cancel_{d}"}]]}
    r = tg("sendMessage", {"chat_id": CHAT, "reply_markup": json.dumps(kb),
                           "text": "[Facebook 캡션]\n" + (folder / "fb.txt").read_text(encoding="utf-8")})
    return bool(r.get("ok"))


def wait_decision(d):
    # 이전에 쌓인 업데이트는 건너뛴다(이번 요청 이후의 버튼만 인정)
    old = tg("getUpdates", {"timeout": "0"}).get("result", [])
    offset = old[-1]["update_id"] + 1 if old else 0
    end = time.time() + WAIT
    while time.time() < end:
        r = tg("getUpdates", {"offset": str(offset), "timeout": "50",
                              "allowed_updates": json.dumps(["callback_query"])})
        for u in r.get("result", []):
            offset = u["update_id"] + 1
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
    missing = [n for n in [f"card{i}.jpg" for i in range(1, 6)] + ["ig.txt", "fb.txt"] if not (folder / n).exists()]
    if missing:
        say(f"[{d}] 승인 요청 불가: {', '.join(missing)} 없음")
        return
    if not request_approval(d, folder):
        say(f"[{d}] 승인 요청 전송 실패, 발행 안 함")
        result = "승인 요청 전송 실패"
    else:
        decision = wait_decision(d)
        if decision == "approve":
            out = run("publish.py", d, folder)
            if (folder / "reel.mp4").exists():
                out += run("publish_reel.py", d, folder)
            result = summarize(out)
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
