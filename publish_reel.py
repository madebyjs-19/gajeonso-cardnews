# 사용: python3.13 publish_reel.py YYYYMMDD ig캡션.txt fb캡션.txt   (텔레그램 승인 후에만)
# cards/YYYYMMDD/reel.mp4 를 main 에 푸시해 둔 상태에서 Instagram 릴스와 Facebook 페이지 릴스로 발행한다.
import os, sys, json, time, urllib.request, urllib.parse, urllib.error
E = os.environ
G = "https://graph.facebook.com/v26.0"
date, ig_cap, fb_cap = sys.argv[1], open(sys.argv[2], encoding="utf-8").read(), open(sys.argv[3], encoding="utf-8").read()
VID = f"https://raw.githubusercontent.com/madebyjs-19/gajeonso-cardnews/main/cards/{date}/reel.mp4"
# 릴스 썸네일(커버): cards/RUN/reel_title.jpg(요약 타이틀 이미지)가 있으면 Instagram cover_url·Facebook 썸네일로 지정한다
TITLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cards", date, "reel_title.jpg")
COVER = f"https://raw.githubusercontent.com/madebyjs-19/gajeonso-cardnews/main/cards/{date}/reel_title.jpg" if os.path.exists(TITLE_PATH) else None


def call(method, path, headers=None, **p):
    url = path if path.startswith("http") else G + path
    data = urllib.parse.urlencode(p).encode() if method == "POST" else None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(p)
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, data, headers or {}, method=method), timeout=120))
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def need(r):
    if "error" in r:
        raise RuntimeError(r["error"].get("message", "unknown error"))
    return r


def tg(text):
    urllib.request.urlopen(f"https://api.telegram.org/bot{E['TELEGRAM_BOT_TOKEN']}/sendMessage",
                           urllib.parse.urlencode({"chat_id": E["TELEGRAM_CHAT_ID"], "text": text}).encode())


res = {}
try:
    t, u = E["IG_ACCESS_TOKEN"], E["IG_USER_ID"]
    extra = {"cover_url": COVER} if COVER else {"thumb_offset": "0"}
    c = need(call("POST", f"/{u}/media", media_type="REELS", video_url=VID, caption=ig_cap, share_to_feed="true",
                  access_token=t, **extra))["id"]
    for _ in range(60):
        s = need(call("GET", f"/{c}", fields="status_code", access_token=t))["status_code"]
        if s == "FINISHED":
            break
        if s == "ERROR":
            raise RuntimeError("container ERROR")
        time.sleep(5)
    else:
        raise RuntimeError("container timeout")
    mid = need(call("POST", f"/{u}/media_publish", creation_id=c, access_token=t))["id"]
    res["Instagram 릴스"] = "발행 완료 " + call("GET", f"/{mid}", fields="permalink", access_token=t).get("permalink", "") + (" (요약 타이틀 썸네일)" if COVER else "")
except KeyError as e:
    res["Instagram 릴스"] = f"건너뜀: {e} 설정 필요"
except Exception as e:
    res["Instagram 릴스"] = "실패: " + str(e)[:150]
try:
    p, t = E["FB_PAGE_ID"], E["FB_PAGE_ACCESS_TOKEN"]
    st = need(call("POST", f"/{p}/video_reels", upload_phase="start", access_token=t))
    vid = st["video_id"]
    need(call("POST", st["upload_url"], headers={"Authorization": "OAuth " + t, "file_url": VID}))
    time.sleep(10)
    need(call("POST", f"/{p}/video_reels", upload_phase="finish", video_id=vid, video_state="PUBLISHED",
              description=fb_cap, access_token=t))
    res["Facebook 릴스"] = "발행 요청 완료 https://www.facebook.com/reel/" + vid
    if COVER:  # 썸네일 지정(실패해도 발행은 유지)
        import subprocess
        r = subprocess.run(["curl", "-sS", "-m", "60", "-F", f"source=@{TITLE_PATH}", "--form-string", "is_preferred=true",
                            "--form-string", f"access_token={t}", f"{G}/{vid}/thumbnails"], capture_output=True, text=True)
        if '"success":true' not in r.stdout.replace(" ", "") and '"id"' not in r.stdout:
            res["Facebook 릴스"] += " (썸네일 지정 실패: 첫 장면이 썸네일)"
except KeyError as e:
    res["Facebook 릴스"] = f"건너뜀: {e} 설정 필요"
except Exception as e:
    res["Facebook 릴스"] = "실패: " + str(e)[:150]
msg = f"[{date} 릴스 최종 보고]\n" + "\n".join(f"{k}: {v}" for k, v in res.items())
tg(msg)
print(msg)
