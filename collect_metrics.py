# 사용(GitHub Actions): python collect_metrics.py
# 계정의 최근 Instagram 게시물(카드뉴스·릴스)의 지표를 Graph API 로 가져와 log/metrics.csv 에 회차별로 기록한다.
# 회차 매칭: 게시물 캡션이 cards/<회차>/ig.txt 와 같으면 그 회차로 본다(발행 로그에 미디어 ID 가 없어도 동작).
# 환경변수: IG_ACCESS_TOKEN(instagram_manage_insights 권한 필요), IG_USER_ID
import os, sys, csv, json, pathlib, datetime, urllib.request, urllib.parse, urllib.error

E = os.environ
G = "https://graph.facebook.com/v26.0"
OUT = pathlib.Path("log/metrics.csv")
MIN_AGE_H = 24          # 발행 후 이 시간이 지난 게시물부터 수집
REFRESH_DAYS = 14       # 이 기간 안의 게시물은 매번 갱신, 이후는 마지막 값 유지
FIELDS = ["run", "format", "media_id", "posted_at", "collected_at", "topic", "type", "cover_color", "card_types",
          "views", "reach", "saves", "shares", "likes", "comments", "avg_watch_sec", "permalink"]
METRICS = {"views": "views", "reach": "reach", "saves": "saved", "shares": "shares"}


def call(path, **p):
    url = G + path + "?" + urllib.parse.urlencode(p)
    try:
        return json.load(urllib.request.urlopen(url, timeout=60))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except ValueError:
            return {"error": {"message": f"HTTP {e.code}"}}


def metric(mid, name, token):
    """지표 하나를 조회한다. 해당 게시물 유형이 지원하지 않으면 None."""
    r = call(f"/{mid}/insights", metric=name, access_token=token)
    if "error" in r:
        return None, r["error"].get("message", "")
    try:
        d = r["data"][0]
        v = d["values"][0]["value"] if "values" in d else d["total_value"]["value"]
        return v, ""
    except (KeyError, IndexError):
        return None, "no data"


def local_runs():
    runs = {}
    for f in pathlib.Path("cards").glob("*/ig.txt"):
        d = f.parent
        meta = ["", "", "", "", ""]
        mp = d / "meta.txt"
        if mp.exists():
            parts = [x.strip() for x in mp.read_text(encoding="utf-8").strip().split("|")]
            meta = (parts + [""] * 5)[:5]
        runs[f.read_text(encoding="utf-8").strip()] = (d.name, meta)
    return runs


def main():
    try:
        token, uid = E["IG_ACCESS_TOKEN"], E["IG_USER_ID"]
    except KeyError as e:
        sys.exit(f"{e} 설정 필요")
    rows = {}
    if OUT.exists():
        for r in csv.DictReader(OUT.open(encoding="utf-8")):
            rows[r["media_id"]] = r
    runs = local_runs()
    now = datetime.datetime.now(datetime.timezone.utc)
    lst = call(f"/{uid}/media", fields="id,caption,media_product_type,timestamp,permalink,like_count,comments_count",
               limit=50, access_token=token)
    if "error" in lst:
        sys.exit("미디어 목록 조회 실패: " + lst["error"].get("message", "")[:200])
    errs = {}
    for m in lst.get("data", []):
        posted = datetime.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        age = now - posted
        if age < datetime.timedelta(hours=MIN_AGE_H):
            continue
        if m["id"] in rows and age > datetime.timedelta(days=REFRESH_DAYS):
            continue
        is_reel = m.get("media_product_type") == "REELS"
        run, meta = runs.get((m.get("caption") or "").strip(), ("", ["", "", "", "", ""]))
        row = {"run": run, "format": "reel" if is_reel else "card", "media_id": m["id"],
               "posted_at": posted.strftime("%Y-%m-%d %H:%M"), "collected_at": now.strftime("%Y-%m-%d %H:%M"),
               "topic": meta[1], "type": meta[2], "cover_color": meta[3], "card_types": meta[4],
               "likes": m.get("like_count", ""), "comments": m.get("comments_count", ""),
               "permalink": m.get("permalink", "")}
        for col, name in METRICS.items():
            v, err = metric(m["id"], name, token)
            row[col] = "" if v is None else v
            if err:
                errs[err[:120]] = errs.get(err[:120], 0) + 1
        if is_reel:
            v, err = metric(m["id"], "ig_reels_avg_watch_time", token)
            row["avg_watch_sec"] = "" if v is None else round(v / 1000, 2)  # API 값은 밀리초
        else:
            row["avg_watch_sec"] = ""
        rows[m["id"]] = row
    OUT.parent.mkdir(exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: r["posted_at"], reverse=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)
    print(f"{len(ordered)}개 게시물 기록")
    for e, n in errs.items():
        print(f"조회 오류 {n}건: {e}")
    if errs and not any(r["views"] != "" or r["reach"] != "" for r in ordered):
        sys.exit("모든 지표 조회가 실패했습니다(권한·토큰 확인 필요)")


if __name__ == "__main__":
    main()
