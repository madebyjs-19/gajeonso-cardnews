# 사용:
#   python3.13 reel_overlay.py --check out_or_cards/RUN/reel_captions.txt        자막 파일 검사(글자 지원·길이·시간)
#   python3.13 reel_overlay.py 원본.mp4 결과.mp4 [reel_captions.txt] [card1.jpg] [bgm.mp3]
#       영상 정리(1080x1920) + 앞에 타이틀 카드 2초(자연스러운 전환) + 한글 팝업 자막 + (있으면) BGM
# 한글 깨짐 방지: AI 영상 안에는 글자를 넣지 않고, 자막은 여기서 Do Hyeon 폰트로 직접 그려 얹는다.
# reel_captions.txt 형식: 한 줄에 하나, "시작초-끝초|자막문구"  예) 2.5-4.5|계산식/포기 수×2L÷0.8  (시간은 최종 영상 기준, 앞 2초는 타이틀 카드)
import os, sys, re, subprocess, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
FONTS = {
    "DoHyeon-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/dohyeon/DoHyeon-Regular.ttf",
    "Pretendard-Bold.otf": "https://raw.githubusercontent.com/orioncactus/pretendard/main/packages/pretendard/dist/public/static/Pretendard-Bold.otf",
}
MAX_SEC = 10.0       # 최종 영상 길이 상한
TITLE_SEC = 2.0      # 맨 앞 카드뉴스 표지(타이틀 카드) 노출 시간(전환 구간 포함)
CLIP_SEC = 8.0       # 본 영상(Flow) 길이. 이 길이를 넘는 영상만 줄인다(앞부분을 자르지 않고 약간 빠르게)
CLIP_TOL = 0.3       # 본 영상이 8초를 이만큼까지 넘으면 잘라내지 않고 속도를 맞춘다
FADE_SEC = 0.5       # 타이틀 카드 → 본 영상 전환(크로스페이드) 길이
NARRATION_DB = -45.0 # 본 영상 평균 음량이 이보다 크면 내레이션이 있는 것으로 본다
MAX_CAPS = 6
MAX_LINE = 12        # 자막 한 줄 최대 글자 수(공백 제외하지 않음)
MAX_LINES = 2
W, H = 1080, 1920
NAVY, WHITE = (0x1A, 0x2A, 0x4A), (0xF7, 0xF8, 0xFA)
ALLOWED = re.compile(r"^[0-9A-Za-z가-힣 .,%!?~:·()\-+/↓↑→×÷=≈]+$")


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


def check(path, title=True):
    """문제 목록을 돌려준다(빈 목록이면 통과). title=True 면 앞 TITLE_SEC 초는 타이틀 카드 구간이라 자막을 둘 수 없다."""
    ensure_fonts()
    font = load_font("DoHyeon-Regular.ttf", 60)
    errs = []
    try:
        caps = parse(path)
    except ValueError as e:
        return [str(e)]
    if not caps:
        errs.append("자막이 한 줄도 없습니다")
    if len(caps) > MAX_CAPS:
        errs.append(f"자막은 최대 {MAX_CAPS}개입니다(현재 {len(caps)}개)")
    lo = TITLE_SEC if title else 0
    hi = (TITLE_SEC + CLIP_SEC - FADE_SEC) if title else MAX_SEC
    for s, e, text, n in caps:
        if not (lo <= s < e <= hi):
            errs.append(f"{n}번째 줄 시간 오류: {s}-{e}초({lo:g}~{hi:g}초 안이어야 함. 앞 {TITLE_SEC:g}초는 타이틀 카드)")
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


def probe(path, entries, *extra):
    out = subprocess.run(["ffprobe", "-v", "error", *extra, "-show_entries", entries, "-of", "csv=p=0", path],
                         capture_output=True, text=True)
    return out.stdout.strip()


def mean_volume(src):
    """영상 오디오의 평균 음량(dB). 오디오가 없거나 측정 실패면 None."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-vn", "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[0-9.]+|-inf) dB", r.stderr)
    if not m or m.group(1) == "-inf":
        return None
    return float(m.group(1))


def build(src, dst, captions_path=None, title_card=None, bgm=None):
    """영상을 1080x1920·30fps로 정리하고, 맨 앞에 타이틀 카드(card1)를 TITLE_SEC 초 붙여(크로스페이드 전환)
    팝업 자막을 얹는다. 본 영상은 CLIP_SEC(8초) 기준으로 앞부분을 자르지 않는다.
    오디오: 본 영상에 내레이션이 있으면 항상 들리게 유지하고, bgm 이 있으면 그 아래에 깐다. 결과 설명 문자열을 돌려준다."""
    ensure_fonts()
    use_title = bool(title_card and os.path.exists(title_card))
    caps = []
    if captions_path and os.path.exists(captions_path):
        errs = check(captions_path, title=use_title)
        if errs:
            raise ValueError("자막 검사 실패:\n- " + "\n- ".join(errs))
        caps = parse(captions_path)
    dur = float(probe(src, "format=duration") or 0) or CLIP_SEC
    has_audio = bool(probe(src, "stream=codec_type", "-select_streams", "a"))
    mv = mean_volume(src) if has_audio else None
    narration = mv is not None and mv > NARRATION_DB
    # 본 영상 길이: 8초 이하는 그대로, 8.3초까지는 잘라내지 않고 속도만 맞추고, 그보다 길면 8초까지만 사용
    cut = dur > CLIP_SEC + CLIP_TOL
    speed = dur / CLIP_SEC if (CLIP_SEC < dur <= CLIP_SEC + CLIP_TOL) else 1.0
    clip_len = CLIP_SEC if (cut or speed != 1.0) else dur
    head = TITLE_SEC if use_title else 0.0
    total = clip_len + (head - FADE_SEC if use_title else 0.0)
    clip_start = head - FADE_SEC if use_title else 0.0     # 최종 영상에서 본 영상이 시작되는 시각
    tmp = os.path.dirname(os.path.abspath(dst))
    pngs = []
    norm = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x1A2A4A,setsar=1,fps=30,format=yuv420p")
    vfit = f"trim=duration={clip_len * speed:.3f},setpts=(PTS-STARTPTS)/{speed:.5f},"
    inputs = ["-i", src]
    filt = [f"[0:v]{vfit}{norm}[vc]"]
    idx = 1
    if use_title:
        inputs += ["-loop", "1", "-t", f"{head:.3f}", "-i", title_card]
        filt.append(f"[{idx}:v]{norm}[vt]")
        idx += 1
        filt.append(f"[vt][vc]xfade=transition=fade:duration={FADE_SEC}:offset={head - FADE_SEC:.3f},format=yuv420p[b0]")
    else:
        filt.append("[vc]null[b0]")
    # --- 오디오 ---
    fmt = "aformat=sample_fmts=fltp:channel_layouts=stereo"
    parts = []
    if narration:
        atempo = f",atempo={speed:.5f}" if speed != 1.0 else ""
        delay = int(round(clip_start * 1000))
        filt.append(f"[0:a]atrim=duration={clip_len * speed:.3f},asetpts=PTS-STARTPTS,aresample=44100,{fmt}{atempo},"
                    f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100,{fmt},adelay={delay}|{delay}[an]")
        parts.append("[an]")
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", bgm]
        vol = 0.18 if narration else 0.7          # 내레이션이 있으면 BGM 은 작게 깔고, 없으면 크게
        filt.append(f"[{idx}:a]aresample=44100,{fmt},atrim=duration={total:.3f},asetpts=PTS-STARTPTS,volume={vol},"
                    f"afade=t=in:d=0.4,afade=t=out:st={max(total - 0.8, 0):.3f}:d=0.8[ab]")
        idx += 1
        parts.append("[ab]")
    if len(parts) == 2:
        filt.append(f"{parts[0]}{parts[1]}amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95,apad[aout]")
    elif len(parts) == 1:
        filt.append(f"{parts[0]}apad[aout]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
        filt.append(f"[{idx}:a]{fmt}[aout]")
        idx += 1
    prev = "b0"
    for i, (s, e, text, _) in enumerate(caps):
        p = os.path.join(tmp, f"_cap{i}.png")
        caption_png(text, p)
        pngs.append(p)
        inputs += ["-loop", "1", "-i", p]
        filt.append(f"[{prev}][{idx}:v]overlay=(W-w)/2:1330:format=auto:enable='between(t,{s},{e})'[b{i + 1}]")
        idx += 1
        prev = f"b{i + 1}"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-map", "[aout]",
           "-t", f"{total:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    for p in pngs:
        os.remove(p)
    if r.returncode:
        raise RuntimeError("ffmpeg 실패: " + r.stderr[-600:])
    note = f"{total:.1f}초"
    if use_title:
        note += f"(타이틀 카드 {head:g}초 + 본 영상 {clip_len:.1f}초, 전환 {FADE_SEC:g}초)"
    if speed != 1.0:
        note += f", 원본 {dur:.1f}초를 8초로 맞춤(잘라내지 않음)"
    if cut:
        note += f", ⚠ 원본 {dur:.1f}초 중 뒷부분 {dur - CLIP_SEC:.1f}초가 잘렸습니다(8초 영상으로 다시 만들어 주세요)"
    note += ", 내레이션 유지" if narration else (", 본 영상 소리 없음" if not has_audio or mv is None else ", 본 영상 소리 매우 작음")
    if bgm:
        note += ", BGM 삽입"
    return note + (f", 팝업 자막 {len(caps)}개" if caps else ", 자막 없음")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        errs = check(sys.argv[2], title="--no-title" not in sys.argv)
        print("\n".join(errs) if errs else "CAPTIONS_OK")
        sys.exit(1 if errs else 0)
    if len(sys.argv) >= 3:
        a = sys.argv
        print(build(a[1], a[2], a[3] if len(a) > 3 else None, a[4] if len(a) > 4 else None, a[5] if len(a) > 5 else None))
        sys.exit(0)
    sys.exit(__doc__)
