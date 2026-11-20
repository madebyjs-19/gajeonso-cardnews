# 사용: python3.13 make_reel_title.py cards/RUN        → cards/RUN/reel_title.jpg (1080x1920)
# 릴스 맨 앞 1.5초에 붙는 '요약 타이틀 이미지'이자 릴스 썸네일(커버)이다.
# 입력: cards/RUN/reel_title.txt
#   1줄: 태그(짧은 주제 분류, 예: 겨울 빨래 · 전기요금)
#   2줄: 제목 1줄(대상, 예: 건조기 vs 제습기)
#   3줄: 제목 2줄(결론·궁금증, 예: 전기요금 승자는?)
#   4줄~: "- " 로 시작하는 요약 2~3줄(카드뉴스 핵심 수치·결론, 줄마다 22자 이내)
# 디자인: 카드뉴스 연구소 디자인과 같은 톤(모눈 배경·FILE 라벨·네이비/오렌지·Do Hyeon 제목·하마준수 로고).
# 인스타 프로필 격자는 릴스 썸네일을 가운데 3:4(위아래 240px 잘림)로 보여 주므로, 글자는 모두 y 260~1660 안에 둔다.
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

import reel_overlay as ro

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "hamajunsu_logo.png")
W, H = 1080, 1920
NAVY, BLUE, ORANGE = (0x1A, 0x2A, 0x4A), (0x2F, 0x60, 0xAF), (0xFF, 0x8A, 0x3D)
ICE, BG, GRID, GRAY = (0xDC, 0xE8, 0xF5), (0xEE, 0xF3, 0xFA), (0xD9, 0xE4, 0xF1), (0x6B, 0x76, 0x88)
WHITE = (0xF7, 0xF8, 0xFA)


def logo_navy(h):
    a = np.asarray(Image.open(LOGO).convert("L")).astype(float)
    alpha = np.clip((245 - a) / (245 - 60), 0, 1)
    alpha[alpha < 0.06] = 0
    ys, xs = np.where(alpha > 0.05)
    rgba = np.zeros((*a.shape, 4), np.uint8)
    rgba[..., :3] = NAVY
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA").crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def fit(d, text, px, max_w, font_name=None):
    """폭에 맞을 때까지 글자 크기를 줄인다. Do Hyeon 에 없는 글자가 있으면 Pretendard."""
    while px > 30:
        f, dy = ro._line_font(text, px) if font_name is None else (ro.load_font(font_name, px), 0)
        if d.textlength(text, font=f) <= max_w:
            return f, dy, px
        px -= 4
    return f, dy, px


def parse(path):
    lines = [x.rstrip() for x in open(path, encoding="utf-8").read().splitlines() if x.strip()]
    if len(lines) < 4:
        raise ValueError("reel_title.txt 는 태그·제목 2줄·요약 2~3줄이 필요합니다")
    tag, t1, t2 = lines[0].strip(), lines[1].strip(), lines[2].strip()
    pts = [x.strip()[1:].strip() for x in lines[3:] if x.strip().startswith("-")][:3]
    if len(pts) < 2:
        raise ValueError("요약은 '- ' 로 시작하는 줄 2~3개가 필요합니다")
    return tag, t1, t2, pts


def make(folder):
    ro.ensure_fonts()
    tag, t1, t2, pts = parse(os.path.join(folder, "reel_title.txt"))
    run = os.path.basename(os.path.normpath(folder))
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 54):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 54):
        d.line([(0, y), (W, y)], fill=GRID, width=1)
    # 모서리 크롭 마크(연구소 카드와 같은 틀)
    for (x, y, sx, sy) in ((60, 250, 1, 1), (W - 60, 250, -1, 1), (60, 1670, 1, -1), (W - 60, 1670, -1, -1)):
        d.line([(x, y), (x + 50 * sx, y)], fill=NAVY, width=5)
        d.line([(x, y), (x, y + 50 * sy)], fill=NAVY, width=5)
    mono = ro.load_font(ro.TAG_FONT, 30)
    lab = f"HAMAJUNSU LAB · REEL {run[4:8] if len(run) >= 8 else run}"
    d.text((100, 300), lab, font=mono, fill=BLUE)
    lg = logo_navy(190)
    im.paste(lg, (W - 100 - lg.width, 285), lg)
    # 태그 칩
    tf = ro.load_font("Pretendard-Bold.otf", 40)
    tw = int(d.textlength(tag, font=tf)) + 56
    d.rounded_rectangle([100, 540, 100 + tw, 612], radius=36, fill=ORANGE)
    d.text((100 + tw // 2, 577), tag, font=tf, fill=NAVY, anchor="mm")
    # 제목 2줄(Do Hyeon, 둘째 줄은 블루로 강조)
    y = 650
    for txt, col, px in ((t1, NAVY, 128), (t2, BLUE, 128)):
        f, dy, px2 = fit(d, txt, px, W - 200)
        d.text((100, y + dy), txt, font=f, fill=col)
        y += int(px2 * 1.12)
    # 요약 카드
    top = max(y + 50, 960)
    rows = len(pts)
    bh = 110 + rows * 118
    d.rounded_rectangle([100 + 10, top + 12, W - 100 + 10, top + bh + 12], radius=30, fill=(0x1A, 0x2A, 0x4A, 60))
    d.rounded_rectangle([100, top, W - 100, top + bh], radius=30, fill=NAVY)
    d.text((150, top + 46), "SUMMARY", font=mono, fill=ICE)
    d.rectangle([150, top + 92, 214, top + 98], fill=ORANGE)
    yy = top + 130
    nf = ro.load_font(ro.POP_FONT, 64)
    for i, p in enumerate(pts, 1):
        d.text((150, yy), f"{i:02d}", font=nf, fill=ORANGE)
        f, dy, _ = fit(d, p, 56, W - 100 - 260 - 40)
        d.text((260, yy + 4 + dy), p, font=f, fill=WHITE)
        yy += 118
    # 하단 서명
    fy = min(top + bh + 70, 1560)
    d.text((W // 2, fy), "하마준수", font=ro.load_font("Pretendard-ExtraBold.otf", 46), fill=NAVY, anchor="ma")
    d.text((W // 2, fy + 62), "가전, 제대로 알고 사는 곳", font=ro.load_font("Pretendard-Bold.otf", 30), fill=GRAY, anchor="ma")
    out = os.path.join(folder, "reel_title.jpg")
    im.save(out, quality=92)
    print("REEL_TITLE_OK", out)
    return out


if __name__ == "__main__":
    sys.exit(0 if make(sys.argv[1]) else 1)
