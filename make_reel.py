# 사용: python3.13 make_reel.py out/YYYYMMDD [1,2,3,마지막장] [결과.mp4]   (기본: 1,2,3 과 마지막 장)
# 카드 JPG 로 1080x1920 릴스(mp4, 약 14.5초)를 만든다. 결과: <dir>/reel.mp4 (세 번째 인자로 바꿀 수 있음)
# Actions 는 Flow 영상이 없는 날 이것으로 카드 슬라이드 릴스를 만들어 대신 발행한다(approval_publish.py).
# 연구소 리포트 디자인 틀: 모눈 배경·모서리 크롭 마크·IBM Plex Mono 라벨·Pretendard 제목(카드 design "lab" 과 같은 색).
# - 상단에 "GAJEONSO LAB · REEL" 라벨과 훅 자막(deck.json 의 reel_hook, 없으면 1장 제목, deck.json 이 없으면 <dir>/ig.txt 첫 줄)
# - 가운데 카드(느린 줌인, 장 사이 전환), 마지막에 1장으로 되돌아가 반복 재생을 유도
# - 하단에 마지막 장부터 "SAVE" 저장 유도 자막(deck.json 의 reel_cta 로 변경 가능)
# - 합성 BGM(저작권 없음, 저음량)
import sys, subprocess, os, json, tempfile
from PIL import Image, ImageDraw, ImageFont
import reel_overlay

d = sys.argv[1]
last = 1
while os.path.exists(os.path.join(d, f"card{last + 1}.jpg")):
    last += 1
pick = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else f"1,2,3,{last}").split(",")]
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(d, "reel.mp4")
reel_overlay.ensure_fonts()  # fonts/ 는 커밋하지 않으므로 없으면 내려받는다
HOLD, FADE, LOOP_HOLD = 3.0, 0.5, 2.0
FPS = 30
W, H = 1080, 1920
CARD_X, CARD_Y, CARD_W, CARD_H = 60, 400, 960, 1200   # 카드 자리(원본 1080x1350 을 같은 비율로 축소)
NAVY, BLUE, ORANGE, GRAY = (0x1A, 0x2A, 0x4A), (0x2E, 0x5E, 0xAA), (0xFF, 0x8A, 0x3D), (0x6B, 0x76, 0x88)
PAPER = (0xFD, 0xFE, 0xFE)
GRID = tuple(round(PAPER[i] * 0.94 + NAVY[i] * 0.06) for i in range(3))  # gen_cards.py LAB["white"]["grid"] 와 같은 값
HERE = os.path.dirname(os.path.abspath(__file__))

hook, cta = "", "저장해두고 필요할 때 꺼내보세요"
for p in (os.path.join(HERE, "deck.json"), "deck.json"):
    if os.path.exists(p):
        deck = json.load(open(p, encoding="utf-8"))
        hook = deck.get("reel_hook") or " ".join(str(deck["cards"][0].get("title", "")).split("\n"))
        cta = deck.get("reel_cta", cta)
        break
else:
    ig = os.path.join(d, "ig.txt")
    if os.path.exists(ig):
        hook = next((ln.strip() for ln in open(ig, encoding="utf-8") if ln.strip()), "")


def fnt(name, px):
    return ImageFont.truetype(os.path.join(HERE, "fonts", name), px)


def mono(dr, x, y, text, px, fill, track=0.1):
    """IBM Plex Mono 라벨(자간 넓게). 다음 글자를 쓸 x 를 돌려준다."""
    f = fnt("IBMPlexMono-SemiBold.ttf", px)
    for ch in text:
        dr.text((x, y), ch, font=f, fill=fill)
        x += dr.textlength(ch, font=f) + px * track
    return x


def wrap(dr, text, f, width):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if dr.textlength(t, font=f) > width and cur:
            lines.append(cur); cur = wd
        else:
            cur = t
    return lines + [cur] if cur else lines


def frame_png(path):
    """배경 틀: 모눈 + 크롭 마크 + 상단 라벨·훅 + 카드 테두리."""
    im = Image.new("RGB", (W, H), PAPER)
    dr = ImageDraw.Draw(im)
    for k in range(0, H // 54 + 2):
        p = k * 54 - 2
        if p < W: dr.rectangle((p, 0, p + 1, H), fill=GRID)
        if p < H: dr.rectangle((0, p, W, p + 1), fill=GRID)
    m, ln, wd = 40, 56, 4
    for cy in ("t", "b"):
        for cx in ("l", "r"):
            x = m if cx == "l" else W - m; y = m if cy == "t" else H - m
            sx = 1 if cx == "l" else -1; sy = 1 if cy == "t" else -1
            dr.rectangle((min(x, x + sx * ln), min(y, y + sy * wd), max(x, x + sx * ln), max(y, y + sy * wd)), fill=NAVY)
            dr.rectangle((min(x, x + sx * wd), min(y, y + sy * ln), max(x, x + sx * wd), max(y, y + sy * ln)), fill=NAVY)
    x = mono(dr, 96, 118, "GAJEONSO LAB", 26, BLUE)
    x = mono(dr, x, 118, " · ", 26, BLUE)
    mono(dr, x, 118, "REEL", 26, ORANGE)
    if hook:
        px = 64
        while True:  # 두 줄 안에 들어갈 때까지 글자를 줄인다
            f = fnt("Pretendard-ExtraBold.otf", px)
            lines = wrap(dr, hook, f, W - 192)
            if len(lines) <= 2 or px <= 44:
                break
            px -= 4
        lh = int(px * 1.28)
        y = 172 + (2 - min(len(lines), 2)) * lh // 2
        for t in lines[:2]:
            dr.text((96, y), t, font=f, fill=NAVY)
            y += lh
    dr.rectangle((CARD_X - 4, CARD_Y - 4, CARD_X + CARD_W + 3, CARD_Y + CARD_H + 3), outline=NAVY, width=4)
    im.save(path)


def cta_png(path):
    im = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    x = mono(dr, 96, 22, "SAVE", 26, ORANGE)
    dr.text((x + 22, 14), cta, font=fnt("Pretendard-Bold.otf", 40), fill=NAVY)
    im.save(path)


tmp = tempfile.mkdtemp()
bg_png, bot_png = os.path.join(tmp, "frame.png"), os.path.join(tmp, "cta.png")
frame_png(bg_png)
cta_png(bot_png)

seq = pick + [pick[0]]                      # 마지막에 1장으로 복귀(반복 재생 유도)
holds = [HOLD] * len(pick) + [LOOP_HOLD]
total = sum(holds) + FADE
inputs, filt = ["-loop", "1", "-t", f"{total:.2f}", "-i", bg_png], []
for n, (i, hold) in enumerate(zip(seq, holds), 1):
    frames = int((hold + FADE) * FPS)
    inputs += ["-loop", "1", "-t", str(hold + FADE), "-i", os.path.join(d, f"card{i}.jpg")]
    filt.append(f"[{n}:v]scale={CARD_W}:{CARD_H},zoompan=z='min(1+0.0009*on,1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={CARD_W}x{CARD_H}:fps={FPS},setsar=1,format=yuv420p[v{n}]")
prev, off = "v1", 0.0
for n in range(2, len(seq) + 1):
    off += holds[n - 2]
    filt.append(f"[{prev}][v{n}]xfade=transition=fade:duration={FADE}:offset={off}[x{n}]")
    prev = f"x{n}"
cta_start = HOLD * (len(pick) - 1)          # 마지막 내용 장(CTA)부터 하단 자막
b_i, a_i = len(seq) + 1, len(seq) + 2
inputs += ["-loop", "1", "-i", bot_png]
filt.append(f"[0:v]fps={FPS},format=yuv420p[bg]")
filt.append(f"[bg][{prev}]overlay={CARD_X}:{CARD_Y}:format=auto[o1]")
filt.append(f"[o1][{b_i}:v]overlay=0:{CARD_Y + CARD_H + 40}:format=auto:enable='gte(t,{cta_start})',format=yuv420p[ov]")
inputs += ["-f", "lavfi", "-t", str(total),
           "-i", "aevalsrc=0.5*(sin(2*PI*220*t)+0.8*sin(2*PI*277.18*t)+0.7*sin(2*PI*329.63*t))*(0.6+0.4*sin(2*PI*0.25*t)):s=44100:c=stereo"]
filt.append(f"[{a_i}:a]volume=0.12,afade=t=in:d=0.8,afade=t=out:st={total-1.2:.2f}:d=1.2[a]")
cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[ov]", "-map", "[a]",
       "-t", str(total), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-shortest",
       "-movflags", "+faststart", out]
r = subprocess.run(cmd, capture_output=True, text=True)
for p in (bg_png, bot_png):
    os.remove(p)
os.rmdir(tmp)
if r.returncode:
    sys.exit(r.stderr[-1500:])
print(out, f"{total:.1f}s")
