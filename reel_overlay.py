# 사용:
#   python3.13 reel_overlay.py --check out_or_cards/RUN/reel_captions.txt        자막 파일 검사(글자 지원·길이·시간)
#   python3.13 reel_overlay.py 원본.mp4 결과.mp4 [reel_captions.txt]              영상 정리(1080x1920·최대 10초) + 한글 자막 합성
# 한글 깨짐 방지: AI 영상 안에는 글자를 넣지 않고, 자막은 여기서 Do Hyeon 폰트로 직접 그려 얹는다.
# reel_captions.txt 형식: 한 줄에 하나, "시작초-끝초|자막문구"  예) 0-2.5|이거 모르면 손해
import os, sys, re, subprocess, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
FONTS = {
    "DoHyeon-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/dohyeon/DoHyeon-Regular.ttf",
    "Pretendard-Bold.otf": "https://raw.githubusercontent.com/orioncactus/pretendard/main/packages/pretendard/dist/public/static/Pretendard-Bold.otf",
}
MAX_SEC = 10.0
MAX_LINE = 12        # 자막 한 줄 최대 글자 수(공백 제외하지 않음)
MAX_LINES = 2
W, H = 1080, 1920
NAVY, WHITE = (0x1A, 0x2A, 0x4A), (0xF7, 0xF8, 0xFA)
ALLOWED = re.compile(r"^[0-9A-Za-z가-힣 .,%!?~:·()\-+/↓↑→×~]+$")


def ensure_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    for name, url in FONTS.items():
        p = os.path.join(FONT_DIR, name)
        if not os.path.exists(p) or os.path.getsize(p) < 100000:
            urllib.request.urlretrieve(url, p)


def load_font(name, px):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), px)


def has_glyph(font, ch):
    """폰트에 글자가 실제로 있는지 확인(없는 글자는 빈 칸·네모로 나온다)."""
    if ch.isspace():
        return True
    missing = font.getmask("\U0010FFFF")
    m = font.getmask(ch)
    return bool(m.getbbox()) and bytes(m) != bytes(missing)


def parse(path):
    caps = []
    for n, raw in enumerate(open(path, encoding="utf-8").read().splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        m = re.fullmatch(r"([0-9.]+)\s*-\s*([0-9.]+)\s*\|\s*(.+)", raw)
        if not m:
            raise ValueError(f"{n}번째 줄 형식 오류(시작초-끝초|문구): {raw}")
        caps.append((float(m.group(1)), float(m.group(2)), m.group(3).strip(), n))
    return caps


def check(path):
    """문제 목록을 돌려준다(빈 목록이면 통과)."""
    ensure_fonts()
    font = load_font("DoHyeon-Regular.ttf", 60)
    errs = []
    try:
        caps = parse(path)
    except ValueError as e:
        return [str(e)]
    if not caps:
        errs.append("자막이 한 줄도 없습니다")
    for s, e, text, n in caps:
        if not (0 <= s < e <= MAX_SEC):
            errs.append(f"{n}번째 줄 시간 오류: {s}-{e}초(0~{MAX_SEC:g}초 안이어야 함)")
        lines = text.split("/")
        if len(lines) > MAX_LINES:
            errs.append(f"{n}번째 줄 자막은 최대 {MAX_LINES}줄('/' 로 줄바꿈): {text}")
        for ln in lines:
            ln = ln.strip()
            if len(ln) > MAX_LINE:
                errs.append(f"{n}번째 줄 한 줄이 {MAX_LINE}자를 넘음({len(ln)}자): {ln}")
            if not ALLOWED.match(ln):
                bad = "".join(sorted({c for c in ln if not ALLOWED.match(c)}))
                errs.append(f"{n}번째 줄 허용되지 않는 문자 '{bad}': {ln}")
            bad_glyph = "".join(sorted({c for c in ln if not has_glyph(font, c)}))
            if bad_glyph:
                errs.append(f"{n}번째 줄 폰트에 없는 글자 '{bad_glyph}': {ln}")
    return errs


def caption_png(text, path):
    lines = [x.strip() for x in text.split("/")]
    f = load_font("DoHyeon-Regular.ttf", 84)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lh = 108
    bw = int(max(probe.textlength(x, font=f) for x in lines)) + 90
    bh = lh * len(lines) + 50
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=36, fill=NAVY + (215,))
    y = 25
    for x in lines:
        d.text((bw // 2, y), x, font=f, fill=WHITE, anchor="ma")
        y += lh
    im.save(path)
    return bw, bh


def probe(path, entries):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "csv=p=0", path],
                         capture_output=True, text=True)
    return out.stdout.strip()


def build(src, dst, captions_path=None):
    """영상을 1080x1920·30fps·최대 10초로 정리하고 자막을 얹는다. 결과 설명 문자열을 돌려준다."""
    ensure_fonts()
    caps = []
    if captions_path and os.path.exists(captions_path):
        errs = check(captions_path)
        if errs:
            raise ValueError("자막 검사 실패:\n- " + "\n- ".join(errs))
        caps = parse(captions_path)
    dur = float(probe(src, "format=duration") or 0)
    has_audio = bool(probe(src, "stream=codec_type -select_streams a"))
    tmp = os.path.dirname(os.path.abspath(dst))
    pngs = []
    inputs = ["-i", src]
    filt = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x1A2A4A,setsar=1,fps=30,format=yuv420p[b0]"]
    prev = "b0"
    for i, (s, e, text, _) in enumerate(caps):
        p = os.path.join(tmp, f"_cap{i}.png")
        bw, bh = caption_png(text, p)
        pngs.append(p)
        inputs += ["-loop", "1", "-i", p]
        filt.append(f"[{prev}][{i + 1}:v]overlay=(W-w)/2:1330:format=auto:enable='between(t,{s},{e})'[b{i + 1}]")
        prev = f"b{i + 1}"
    cmd = ["ffmpeg", "-y", *inputs]
    if has_audio:
        amap = "0:a:0"
    else:
        cmd += ["-f", "lavfi", "-t", str(MAX_SEC), "-i", "anullsrc=r=44100:cl=stereo"]
        amap = f"{len(caps) + 1}:a"
    cmd += ["-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-map", amap,
            "-t", str(min(dur or MAX_SEC, MAX_SEC)), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-shortest", "-movflags", "+faststart", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    for p in pngs:
        os.remove(p)
    if r.returncode:
        raise RuntimeError("ffmpeg 실패: " + r.stderr[-600:])
    note = f"{min(dur, MAX_SEC):.1f}초"
    if dur > MAX_SEC + 0.05:
        note += f"(원본 {dur:.1f}초 중 앞 {MAX_SEC:g}초만 사용)"
    return note + (f", 자막 {len(caps)}개" if caps else ", 자막 없음")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        errs = check(sys.argv[2])
        print("\n".join(errs) if errs else "CAPTIONS_OK")
        sys.exit(1 if errs else 0)
    if len(sys.argv) >= 3:
        print(build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
        sys.exit(0)
    sys.exit(__doc__)
