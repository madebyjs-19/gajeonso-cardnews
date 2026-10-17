# 사용(GitHub Actions 전용): python topic_request.py topic_request/RUN.txt
# 루틴이 주제를 못 정했을 때 올린 요청 파일을 텔레그램으로 보내고, 사용자의 답장을 기다려 plan/topic_override.txt 에 저장한다.
# 다음 루틴 실행은 이 파일의 주제로 진행한다(ROUTINE_PROMPT.md step1 0번). 토큰은 환경변수(GitHub Secrets)로만 받는다.
import os, sys, json, time, pathlib, subprocess

E = os.environ
API = f"https://api.telegram.org/bot{E['TELEGRAM_BOT_TOKEN']}/"
CHAT = str(E["TELEGRAM_CHAT_ID"])
WAIT = 7200  # 답장 대기 최대 120분
OUT = pathlib.Path("plan/topic_override.txt")


def tg(method, fields=None, timeout=70):
    cmd = ["curl", "-sS", "-m", str(timeout), API + method]
    for k, v in (fields or {}).items():
        cmd += ["--form-string", f"{k}={v}"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except ValueError:
        return {}


def main(path):
    p = pathlib.Path(path)
    run = p.stem
    body = p.read_text(encoding="utf-8").strip()
    old = tg("getUpdates", {"timeout": "0"}).get("result", [])
    offset = old[-1]["update_id"] + 1 if old else 0
    tg("sendMessage", {"chat_id": CHAT, "text": (
        f"[가전소 주제 요청 {run}]\n{body}\n\n"
        "이 메시지에 답장으로 오늘 다룰 주제를 보내 주세요(120분 안). "
        "답장이 오면 다음 루틴 실행이 그 주제로 카드를 만듭니다.")[:4000]})
    end = time.time() + WAIT
    while time.time() < end:
        r = tg("getUpdates", {"offset": str(offset), "timeout": "50",
                              "allowed_updates": json.dumps(["message"])})
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            text = (m.get("text") or "").strip()
            if str(m.get("chat", {}).get("id")) != CHAT or not text or text.startswith("/"):
                continue
            OUT.write_text(f"{run} | {text}\n", encoding="utf-8")
            tg("getUpdates", {"offset": str(offset), "timeout": "0"})
            tg("sendMessage", {"chat_id": CHAT, "text": f"주제를 받았습니다: {text}\n다음 루틴 실행이 이 주제로 진행합니다."})
            print("TOPIC_SAVED", text)
            return 0
        if not r.get("ok", True):
            time.sleep(10)
    tg("sendMessage", {"chat_id": CHAT, "text": f"[{run}] 120분 안에 답장이 없어 주제 요청을 마칩니다."})
    print("EXPIRED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
