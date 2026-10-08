# 사용: python3.13 publish.py YYYYMMDD caption_ig.txt caption_fb.txt
# 승인된 카드(cards/YYYYMMDD/card1~5.jpg)를 Instagram 캐러셀과 Facebook 페이지에 발행하고 텔레그램에 결과를 알린다.
import os, sys, json, time, urllib.request, urllib.parse, urllib.error

E = os.environ
G = "https://graph.facebook.com/v26.0"
date, ig_cap, fb_cap = sys.argv[1], open(sys.argv[2], encoding="utf-8").read(), open(sys.argv[3], encoding="utf-8").read()
URL = f"https://raw.githubusercontent.com/madebyjs-19/gajeonso-cardnews/main/cards/{date}/card%d.jpg"


def call(method, path, **p):
    data = urllib.parse.urlencode(p).encode() if method == "POST" else None
    url = G + path + ("?" + urllib.parse.urlencode(p) if method == "GET" else "")
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, data), timeout=90))
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def need(r):
    if "error" in r:
        raise RuntimeError(r["error"].get("message", "unknown error"))
    return r


def wait(cid, t):
    for _ in range(24):
        s = need(call("GET", f"/{cid}", fields="status_code", access_token=t))["status_code"]
        if s == "FINISHED":
            return
        if s == "ERROR":
            raise RuntimeError("container ERROR")
        time.sleep(5)
    raise RuntimeError("container timeout")


def tg(text):
    urllib.request.urlopen(f"https://api.telegram.org/bot{E['TELEGRAM_BOT_TOKEN']}/sendMessage",
                           urllib.parse.urlencode({"chat_id": E["TELEGRAM_CHAT_ID"], "text": text}).encode())


res = {}
try:
    t, u = E["IG_ACCESS_TOKEN"], E["IG_USER_ID"]
    ids = [need(call("POST", f"/{u}/media", image_url=URL % i, is_carousel_item="true", access_token=t))["id"] for i in range(1, 6)]
    for c in ids:
        wait(c, t)
    car = need(call("POST", f"/{u}/media", media_type="CAROUSEL", children=",".join(ids), caption=ig_cap, access_token=t))["id"]
    wait(car, t)
    mid = need(call("POST", f"/{u}/media_publish", creation_id=car, access_token=t))["id"]
    res["Instagram"] = "발행 완료 " + call("GET", f"/{mid}", fields="permalink", access_token=t).get("permalink", "")
except KeyError as e:
    res["Instagram"] = f"건너뜀: {e} 설정 필요"
except Exception as e:
    res["Instagram"] = "실패: " + str(e)[:150]
try:
    p, t = E["FB_PAGE_ID"], E["FB_PAGE_ACCESS_TOKEN"]
    ph = [need(call("POST", f"/{p}/photos", url=URL % i, published="false", access_token=t))["id"] for i in range(1, 6)]
    media = {f"attached_media[{i}]": json.dumps({"media_fbid": x}) for i, x in enumerate(ph)}
    pid = need(call("POST", f"/{p}/feed", message=fb_cap, access_token=t, **media))["id"]
    res["Facebook"] = "발행 완료 " + call("GET", f"/{pid}", fields="permalink_url", access_token=t).get("permalink_url", "")
except KeyError as e:
    res["Facebook"] = f"건너뜀: {e} 설정 필요"
except Exception as e:
    res["Facebook"] = "실패: " + str(e)[:150]
msg = f"[{date} 최종 보고]\n" + "\n".join(f"{k}: {v}" for k, v in res.items())
tg(msg)
print(msg)
