# 사용: python3.13 make_reel.py out/YYYYMMDD [1,2,3,5] [결과.mp4]
# 카드 JPG 로 1080x1920 릴스(mp4, 약 14초)를 만든다. 결과: <dir>/reel.mp4 (세 번째 인자로 바꿀 수 있음)
# Actions 는 Flow 영상이 없는 날 이것으로 카드 슬라이드 릴스를 만들어 대신 발행한다(approval_publish.py).
# - 상단 띠에 훅 자막(deck.json 의 reel_hook, 없으면 1장 제목, deck.json 이 없으면 <dir>/ig.txt 첫 줄)을 처음부터 끝까지 고정
# - 각 장에 느린 줌인 모션, 마지막에 1장으로 되돌아가 반복 재생을 유도
# - 하단 띠에 마지막 장부터 "저장" 유도 자막(deck.json 의 reel_cta 로 변경 가능)
# - 합성 BGM(저작권 없음, 저음량)
import sys, subprocess, os, json
from PIL import Image, ImageDraw, ImageFont
import reel_overlay

d = sys.argv[1]
pick = [int(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "1,2,3,5").split(",")]
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(d, "reel.mp4")
reel_overlay.ensure_fonts()  # fonts/ 는 커밋하지 않으므로 없으면 내려받는다(DoHyeon·Pretendard-Bold)
HOLD, FADE, LOOP_HOLD = 3.0, 0.5, 2.0
FPS = 30
NAVY, WHITE, ICE, ORANGE = (0x1A, 0x2A, 0x4A), (0xF7, 0xF8, 0xFA), (0xDC, 0xE8, 0xF5), (0xFF, 0x8A, 0x3D)
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

def strip_png(text, path, w, h, font_file, px, fill, align_top=False):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if text:
        dr = ImageDraw.Draw(im)
        f = fnt(font_file, px)
        words, lines, cur = text.split(), [], ""
        for wd in words:  # 폭 960px 안에서 줄바꿈
            t = (cur + " " + wd).strip()
            if dr.textlength(t, font=f) > 960 and cur:
                lines.append(cur); cur = wd
            else:
                cur = t
        lines.append(cur)
        if len(lines) > 2 and px > 44:  # 두 줄에 안 들어가면 글자를 줄여 다시 나눈다
            return strip_png(text, path, w, h, font_file, px - 6, fill)
        lines = lines[:2]
        lh = int(px * 1.25)
        y = (h - lh * len(lines)) // 2
        for ln in lines:
            dr.text((w // 2, y), ln, font=f, fill=fill, anchor="ma")
            y += lh
    im.save(path)

top_png, bot_png = os.path.join(d, "_reel_top.png"), os.path.join(d, "_reel_bot.png")
strip_png(hook, top_png, 1080, 285, "DoHyeon-Regular.ttf", 66, WHITE)
strip_png(cta, bot_png, 1080, 285, "Pretendard-Bold.otf", 42, ICE)

seq = pick + [pick[0]]                      # 마지막에 1장으로 복귀(반복 재생 유도)
holds = [HOLD] * len(pick) + [LOOP_HOLD]
inputs, filt = [], []
for n, (i, hold) in enumerate(zip(seq, holds)):
    frames = int((hold + FADE) * FPS)
    inputs += ["-loop", "1", "-t", str(hold + FADE), "-i", os.path.join(d, f"card{i}.jpg")]
    filt.append(f"[{n}:v]scale=1080:1350,zoompan=z='min(1+0.0009*on,1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s=1080x1350:fps={FPS},pad=1080:1920:0:285:color=0x1A2A4A,setsar=1,format=yuv420p[v{n}]")
prev, off = "v0", 0.0
for n in range(1, len(seq)):
    off += holds[n - 1]
    filt.append(f"[{prev}][v{n}]xfade=transition=fade:duration={FADE}:offset={off}[x{n}]")
    prev = f"x{n}"
total = sum(holds) + FADE
cta_start = HOLD * (len(pick) - 1)          # 마지막 내용 장(CTA)부터 하단 자막
inputs += ["-loop", "1", "-i", top_png, "-loop", "1", "-i", bot_png]
t_i, b_i, a_i = len(seq), len(seq) + 1, len(seq) + 2
filt.append(f"[{prev}][{t_i}:v]overlay=0:0:format=auto[o1]")
filt.append(f"[o1][{b_i}:v]overlay=0:1635:format=auto:enable='gte(t,{cta_start})'[ov]")
inputs += ["-f", "lavfi", "-t", str(total),
           "-i", "aevalsrc=0.5*(sin(2*PI*220*t)+0.8*sin(2*PI*277.18*t)+0.7*sin(2*PI*329.63*t))*(0.6+0.4*sin(2*PI*0.25*t)):s=44100:c=stereo"]
filt.append(f"[{a_i}:a]volume=0.12,afade=t=in:d=0.8,afade=t=out:st={total-1.2:.2f}:d=1.2[a]")
cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[ov]", "-map", "[a]",
       "-t", str(total), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-shortest",
       "-movflags", "+faststart", out]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr[-1500:])
for p in (top_png, bot_png):
    os.remove(p)
print(out, f"{total:.1f}s")
