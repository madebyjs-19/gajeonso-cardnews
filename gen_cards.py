#!/usr/bin/env python3
"""가전소 카드뉴스 생성기 (브랜드 가이드 Ver 1.1 기준)

사용법:
  python3 gen_cards.py deck.json OUTDIR
deck.json 형식은 DECK_SPEC.md 참고. 결과: OUTDIR/card1~5.png (1080x1350) + card1~5.jpg (Instagram 업로드용)
deck.json 에 "cover_style": "v2" 를 넣으면 1장(cover·product_cover)이 새 표지 디자인(Do Hyeon 제목, 제품 영역 카드, VS 배지)으로 만들어진다.
"""
import json, os, sys
import math
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter
import qrcode

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.environ.get("GAJEONSO_FONT_DIR", os.path.join(HERE, "fonts"))
LOGO = os.path.join(HERE, "gajeonso_logo.png")
QR_URL = "http://pf.kakao.com/_PHwrX/chat"
CONSULT_TEXT = "상담문의 · 가전소"

W, H, S = 1080, 1350, 2  # S: 슈퍼샘플링 배율(부드러운 선·글자)

NAVY = (0x1A, 0x2A, 0x4A); BLUE = (0x2E, 0x5E, 0xAA); ICE = (0xDC, 0xE8, 0xF5)
WHITE = (0xFD, 0xFE, 0xFE); OFFWHITE = (0xF7, 0xF8, 0xFA)
GRAY = (0x6B, 0x76, 0x88); LGRAY = (0x9A, 0xA6, 0xB2); ORANGE = (0xFF, 0x8A, 0x3D)
ICE_TEXT = (0x18, 0x5F, 0xA5); NAVY_PAGE = (0x6E, 0x86, 0xAC); NAVY_NOTE = (0x8F, 0xA5, 0xC7)
STRIPE = (0xEE, 0xF3, 0xFA)  # 아이스블루 50%

BG = {"navy": NAVY, "ice": ICE, "white": WHITE, "orange": ORANGE, "blue": BLUE}
# 배경별 색 규칙: line(상하 라인), title, body, sub, accent(핵심 수치/강조), page, symbol(선), dot(점)
THEME = {
    "white":  dict(line=NAVY, title=NAVY, body=GRAY, sub=GRAY, accent=BLUE, page=LGRAY, sym=NAVY, dot=NAVY, label=GRAY, stripe=STRIPE, border=True),
    "navy":   dict(line=ICE, title=WHITE, body=ICE, sub=NAVY_NOTE, accent=ICE, page=NAVY_PAGE, sym=ICE, dot=ICE, label=ICE, stripe=(0x24, 0x38, 0x5F), border=False),
    "ice":    dict(line=BLUE, title=NAVY, body=NAVY, sub=BLUE, accent=BLUE, page=GRAY, sym=NAVY, dot=BLUE, label=BLUE, stripe=(0xEA, 0xF1, 0xFA), border=False),
    "blue":   dict(line=ICE, title=WHITE, body=ICE, sub=ICE, accent=WHITE, page=ICE, sym=WHITE, dot=WHITE, label=ICE, stripe=(0x3A, 0x6C, 0xBA), border=False),
    "orange": dict(line=OFFWHITE, title=WHITE, body=WHITE, sub=(0xFF, 0xE3, 0xC8), accent=NAVY, page=(0xFF, 0xE3, 0xC8), sym=OFFWHITE, dot=NAVY, label=(0xFF, 0xE3, 0xC8), stripe=(0xFF, 0x9B, 0x5C), border=False),
}


FONT_URL = "https://raw.githubusercontent.com/orioncactus/pretendard/main/packages/pretendard/dist/public/static/"
DISPLAY_FONT_FILE = "DoHyeon-Regular.ttf"
DISPLAY_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/dohyeon/DoHyeon-Regular.ttf"
DISPLAY_OK = True      # Do Hyeon 사용 가능 여부(다운로드 실패 시 Pretendard Bold 로 대체)
USE_DISPLAY = False    # cover_style v2 일 때 포스터형 헤드라인·태그에도 Do Hyeon 사용


def ensure_fonts():
    """폰트 파일이 없으면 Pretendard(OFL)를 내려받는다."""
    import urllib.request
    os.makedirs(FONT_DIR, exist_ok=True)
    for n in ("Pretendard-Regular.otf", "Pretendard-Medium.otf", "Pretendard-SemiBold.otf", "Pretendard-Bold.otf"):
        p = os.path.join(FONT_DIR, n)
        if not os.path.exists(p) or os.path.getsize(p) < 100000:
            urllib.request.urlretrieve(FONT_URL + n, p)
    global DISPLAY_OK
    p = os.path.join(FONT_DIR, DISPLAY_FONT_FILE)
    try:
        if not os.path.exists(p) or os.path.getsize(p) < 100000:
            urllib.request.urlretrieve(DISPLAY_FONT_URL, p)
        ImageFont.truetype(p, 20)
        DISPLAY_OK = True
    except Exception as e:  # 실패해도 생성은 계속(표지 제목은 Pretendard Bold 로 대체)
        DISPLAY_OK = False
        print("COVER_FONT_FALLBACK: Do Hyeon 사용 불가, Pretendard Bold 로 대체 -", e)


def font(weight, px):
    name = {"regular": "Pretendard-Regular.otf", "medium": "Pretendard-Medium.otf",
            "semibold": "Pretendard-SemiBold.otf", "bold": "Pretendard-Bold.otf"}[weight]
    return ImageFont.truetype(os.path.join(FONT_DIR, name), int(px * S))


def dfont(px):
    """표지·강조용 디자인 폰트(Do Hyeon). 사용 불가면 Pretendard Bold."""
    if DISPLAY_OK:
        return ImageFont.truetype(os.path.join(FONT_DIR, DISPLAY_FONT_FILE), int(px * S))
    return font("bold", px)


class Card:
    def __init__(self, bg_name, draw_enabled=True):
        self.bg = bg_name
        self.t = THEME[bg_name]
        self.img = Image.new("RGB", (W * S, H * S), BG[bg_name])
        self.d = ImageDraw.Draw(self.img)

    # --- 기본 도구 ---
    def text_w(self, s, f):
        return self.d.textlength(s, font=f) / S

    def text(self, x, y, s, f, fill, anchor="la"):
        self.d.text((x * S, y * S), s, font=f, fill=fill, anchor=anchor)

    def hline(self, y, x1, x2, color, w=1.5):
        self.d.line((x1 * S, y * S, x2 * S, y * S), fill=color, width=max(1, round(w * S)))

    def wrap(self, s, f, max_w):
        lines = []
        for para in s.split("\n"):
            cur = ""
            for ch in para:
                if self.text_w(cur + ch, f) > max_w and cur:
                    lines.append(cur.rstrip()); cur = ch
                else:
                    cur += ch
            lines.append(cur.rstrip())
        return lines

    # --- 공통 요소 ---
    def frame(self):
        if self.t["border"]:  # 네이비 2px, 가장자리에서 6px 안쪽 (흰 배경만)
            self.d.rectangle((6 * S, 6 * S, (W - 6) * S, (H - 6) * S), outline=NAVY, width=2 * S)

    def symbol(self, cx=990, cy=90, scale=1.15):
        u = scale * S
        c = self.t["sym"]; lw = max(2, round(4 * u / S * 1.0))
        bw, bh = 46 * u, 38 * u
        x1, y1, x2, y2 = cx * S - bw / 2, cy * S - bh / 2 + 4 * u, cx * S + bw / 2, cy * S + bh / 2 + 4 * u
        self.d.rounded_rectangle((x1, y1, x2, y2), radius=10 * u, outline=c, width=lw)
        for dx in (-11, 11):  # 플러그 프롱 2개
            self.d.line((cx * S + dx * u, y1 - 12 * u, cx * S + dx * u, y1 + 2), fill=c, width=lw)
        r = 5.5 * u
        mx, my = cx * S, (y1 + y2) / 2
        self.d.ellipse((mx - r, my - r, mx + r, my + r), fill=self.t["dot"])

    def page_no(self, n, total=5):
        self.text(70, 1280, f"{n} / {total}", font("regular", 24), self.t["page"], "lm")

    def qr_badge(self):
        qr = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(QR_URL); qr.make(fit=True)
        q = qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((112 * S, 112 * S), Image.NEAREST)
        f = font("semibold", 24)
        tw = self.text_w(CONSULT_TEXT, f)
        bw, bh = 16 + 112 + 18 + tw + 22, 144
        x2, y2 = W - 60, H - 56
        x1, y1 = x2 - bw, y2 - bh
        self.d.rounded_rectangle((x1 * S, y1 * S, x2 * S, y2 * S), radius=22 * S, fill=WHITE, outline=BLUE if self.bg != "navy" else ICE, width=2 * S)
        self.img.paste(q, (int((x1 + 16) * S), int((y1 + 16) * S)))
        self.text(x1 + 16 + 112 + 18, (y1 + y2) / 2, CONSULT_TEXT, f, NAVY, "lm")

    def box_lines(self, top, bottom):
        self.hline(top, 90, W - 90, self.t["line"]); self.hline(bottom, 90, W - 90, self.t["line"])

    def finish(self, n, cover_v2=False):
        if cover_v2:  # 새 표지: 테두리·페이지 번호·힌트는 cover_v2()가 그리고, 콘센트 심볼은 쓰지 않는다. QR 상담 배지만 공통
            self.qr_badge()
            return
        self.frame(); self.symbol(); self.page_no(n); self.qr_badge()
        if getattr(self, "illust", False):  # 일러스트 사용 시 실제 제품 사진이 아님을 표기
            self.text(70, 1236, "※ 이해를 돕기 위한 일러스트입니다", font("regular", 22), self.t["page"], "lm")

    def save(self, path_base):
        out = self.img.resize((W, H), Image.LANCZOS)
        out.save(path_base + ".png")
        out.convert("RGB").save(path_base + ".jpg", quality=95, subsampling=0)


# --- 카드 유형: draw(card, y0) -> 높이. y0=None 이면 높이만 계산 ---
def _h(c, items):  # items: list of (kind, args) -> 합계 높이 계산 후 중앙 정렬
    pass


def layout_center(card, builder, center=690, pad=100, min_box=380, max_bottom=1100, align_top=None):
    """builder(card, y, dry) -> content height. 라인 박스를 중앙에 두고 그 안에 콘텐츠를 세로 중앙 배치."""
    h = builder(card, 0, True)
    box_h = max(min_box, h + pad * 2)
    top = int(center - box_h / 2)
    bottom = top + box_h
    if bottom > max_bottom:
        top -= bottom - max_bottom; bottom = max_bottom
    card.box_lines(top, bottom)
    builder(card, top + (box_h - h) // 2, False)


def b_cover(spec):
    def build(c, y, dry):
        t = c.t; cur = y
        if spec.get("logo"):
            if not dry:
                logo = Image.open(LOGO).convert("RGB").resize((340 * S, 340 * S), Image.LANCZOS)
                c.img.paste(logo, (int((W - 340) / 2 * S), int(cur * S)))
            cur += 340 + 30
        if spec.get("label"):
            if not dry: c.text(W / 2, cur, spec["label"], font("regular", 28), t["label"], "ma")
            cur += 28 + 26
        f = font("bold", 46)
        for ln in spec["title"].split("\n"):
            if not dry: c.text(W / 2, cur, ln, f, t["title"], "ma")
            cur += 46 + 22
        cur -= 22
        if spec.get("subtitle"):
            cur += 30
            if not dry: c.text(W / 2, cur, spec["subtitle"], font("regular", 28), t["sub"], "ma")
            cur += 28
        return cur - y
    return build


def b_formula(spec):
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry: c.text(W / 2, cur, spec["title"], font("bold", 40), t["title"], "ma")
        cur += 40 + 22
        if not dry: c.hline(cur, W / 2 - 90, W / 2 + 90, LGRAY if c.bg == "white" else t["line"])
        cur += 50
        if spec.get("kicker"):
            if not dry: c.text(W / 2, cur, spec["kicker"], font("regular", 30), t["body"], "ma")
            cur += 30 + 18
        if not dry: c.text(W / 2, cur, spec["big"], font("bold", 52), t["accent"], "ma")
        cur += 52 + 20
        if spec.get("tail"):
            if not dry: c.text(W / 2, cur, spec["tail"], font("regular", 30), t["body"], "ma")
            cur += 30
        if spec.get("example"):
            cur += 34
            if not dry: c.hline(cur, W / 2 - 150, W / 2 + 150, LGRAY if c.bg == "white" else t["line"], 1)
            cur += 30
            if not dry: c.text(W / 2, cur, spec["example"], font("regular", 28), t["sub"], "ma")
            cur += 28
        return cur - y
    return build


def b_table(spec):
    rows = spec["rows"][:6]
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry: c.text(W / 2, cur, spec["title"], font("bold", 40), t["title"], "ma")
        cur += 40 + 22
        if not dry: c.hline(cur, 190, W - 190, LGRAY if c.bg == "white" else t["line"], 1)
        cur += 34
        rh = 92
        for i, (a, b) in enumerate(rows):
            if not dry:
                if i % 2 == 0:
                    c.d.rectangle((150 * S, cur * S, (W - 150) * S, (cur + rh - 8) * S), fill=t["stripe"])
                c.text(190, cur + (rh - 8) / 2, a, font("semibold", 30), t["title"], "lm")
                c.text(610, cur + (rh - 8) / 2, b, font("semibold", 30), t["accent"], "lm")
            cur += rh
        if spec.get("footnote"):
            cur += 14
            if not dry: c.text(W / 2, cur, spec["footnote"], font("regular", 24), t["sub"], "ma")
            cur += 24
        return cur - y
    return build


def b_checklist(spec):
    items = spec["items"][:5]
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry: c.text(W / 2, cur, spec["title"], font("bold", 40), t["title"], "ma")
        cur += 40 + 22
        if not dry: c.hline(cur, W / 2 - 90, W / 2 + 90, LGRAY if c.bg == "white" else t["line"])
        cur += 52
        f = font("regular", 30)
        for it in items:
            lines = c.wrap(it, f, 700)
            if not dry:
                c.d.ellipse((150 * S, (cur + 15 - 7) * S, (150 + 14) * S, (cur + 15 + 7) * S), fill=ORANGE)
                for k, ln in enumerate(lines):
                    c.text(186, cur + k * 44, ln, f, t["title"] if c.bg != "white" else NAVY)
            cur += len(lines) * 44 + 30
        return cur - 30 - y
    return build


def b_compare(spec):
    rows = spec["rows"][:5]
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry: c.text(W / 2, cur, spec["title"], font("bold", 40), t["title"], "ma")
        cur += 40 + 22
        if not dry: c.hline(cur, 190, W - 190, LGRAY if c.bg == "white" else t["line"], 1)
        cur += 30
        a, b = spec["cols"]
        if not dry:
            c.text(590, cur, a, font("semibold", 28), t["sub"], "ma"); c.text(820, cur, b, font("semibold", 28), t["accent"], "ma")
        cur += 28 + 24
        rh = 96
        for i, (lab, va, vb) in enumerate(rows):
            if not dry:
                if i % 2 == 0:
                    c.d.rectangle((150 * S, cur * S, (W - 150) * S, (cur + rh - 8) * S), fill=t["stripe"])
                mid = cur + (rh - 8) / 2
                c.text(176, mid, lab, font("semibold", 24), GRAY if c.bg == "white" else t["sub"], "lm")
                c.text(590, mid, va, font("regular", 26), t["title"], "mm"); c.text(820, mid, vb, font("semibold", 26), t["accent"], "mm")
            cur += rh
        return cur - y
    return build


def b_steps(spec):
    steps = spec["steps"][:4]
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry: c.text(W / 2, cur, spec["title"], font("bold", 40), t["title"], "ma")
        cur += 40 + 22
        if not dry: c.hline(cur, W / 2 - 90, W / 2 + 90, LGRAY if c.bg == "white" else t["line"])
        cur += 54
        for i, (a, b) in enumerate(steps):
            if not dry:
                cx, cy = 190, cur + 24
                c.d.ellipse(((cx - 24) * S, (cy - 24) * S, (cx + 24) * S, (cy + 24) * S), fill=BLUE)
                c.text(cx, cy, str(i + 1), font("bold", 26), WHITE, "mm")
                c.text(250, cur + 2, a, font("semibold", 30), t["title"])
                c.text(250, cur + 2 + 42, b, font("regular", 24), t["sub"])
            cur += 110
        return cur - 110 + 70 - y
    return build


def b_contact(spec):
    items = spec["items"][:4]
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry: c.text(W / 2, cur, spec["title"], font("bold", 40), t["title"], "ma")
        cur += 40 + 22
        if not dry: c.hline(cur, 190, W - 190, LGRAY if c.bg == "white" else t["line"], 1)
        cur += 34
        for name, sub, num in items:
            if not dry:
                c.d.rounded_rectangle((150 * S, cur * S, (W - 150) * S, (cur + 104) * S), radius=10 * S, fill=ICE)
                c.text(180, cur + 34, name, font("semibold", 30), NAVY, "lm"); c.text(180, cur + 76, sub, font("regular", 22), ICE_TEXT, "lm")
                c.text(W - 180, cur + 52, num, font("bold", 32), BLUE, "rm")
            cur += 128
        return cur - 24 - y
    return build


def b_review(spec):  # 실제 상담 고객에게 받은 후기만 사용. 없으면 tag에 "예시" 표기
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry:
            c.d.rounded_rectangle((150 * S, cur * S, (150 + 20 + c.text_w(spec["tag"], font("semibold", 22)) + 20) * S, (cur + 40) * S), radius=20 * S, outline=BLUE, width=2 * S)
            c.text(160 + 0, cur + 20, spec["tag"], font("semibold", 22), BLUE, "lm")
        cur += 40 + 30
        if not dry: c.text(150, cur - 6, "“", font("bold", 70), BLUE)
        cur += 56
        f = font("semibold", 34)
        for ln in c.wrap(spec["quote"], f, 780):
            if not dry: c.text(150, cur, ln, f, t["title"])
            cur += 52
        cur += 14
        if not dry: c.hline(cur, 150, W - 150, LGRAY, 1)
        cur += 24
        if not dry: c.text(150, cur, spec.get("meta", ""), font("regular", 24), t["sub"])
        cur += 24 + 22
        if not dry:
            c.d.ellipse((150 * S, cur * S, 198 * S, (cur + 48) * S), fill=ICE)
            c.text(174, cur + 24, spec.get("initial", "고"), font("bold", 24), BLUE, "mm")
            c.text(214, cur + 24, spec.get("name", "고객님"), font("semibold", 26), t["title"], "lm")
        cur += 48
        return cur - y
    return build


def b_deal(spec):  # 특가 카드: 실제 정가 대비 할인율 확인 후에만 사용
    def build(c, y, dry):
        t = c.t; cur = y
        if not dry:
            tw = c.text_w(spec["tag"], font("semibold", 22))
            c.d.rounded_rectangle((150 * S, cur * S, (150 + 40 + tw) * S, (cur + 40) * S), radius=20 * S, outline=ORANGE, width=2 * S)
            c.text(170, cur + 20, spec["tag"], font("semibold", 22), ORANGE, "lm")
            if spec.get("pct"): c.text(W - 150, cur + 20, spec["pct"], font("bold", 30), ORANGE, "rm")
        cur += 40 + 34
        if not dry: c.text(150, cur, spec["product"], font("semibold", 34), t["title"])
        cur += 34 + 30
        if not dry:
            c.text(150, cur, spec["original"], font("regular", 24), LGRAY)
            w = c.text_w(spec["original"], font("regular", 24)); c.hline(cur + 14, 150, 150 + w, LGRAY, 1.5)
        cur += 24 + 14
        if not dry: c.text(150, cur, spec["price"], font("bold", 52), ORANGE)
        cur += 52 + 30
        if not dry: c.hline(cur, 150, W - 150, LGRAY, 1)
        cur += 24
        if spec.get("note"):
            if not dry: c.text(150, cur, spec["note"], font("regular", 24), t["sub"])
            cur += 24
        return cur - y
    return build


def b_cta(spec):
    def build(c, y, dry):
        t = c.t; cur = y
        f = font("bold", 40)
        for ln in spec["question"].split("\n"):
            if not dry: c.text(W / 2, cur, ln, f, t["title"], "ma")
            cur += 40 + 20
        cur += 10
        if not dry: c.hline(cur, W / 2 - 90, W / 2 + 90, t["line"], 1)
        cur += 44
        f2 = font("regular", 30)
        for ln in spec["dm"].split("\n"):
            if not dry: c.text(W / 2, cur, ln, f2, t["body"], "ma")
            cur += 30 + 18
        return cur - 18 - y
    return build



# ---------- 제품 이미지: 배경 제거(컷아웃) ----------
def cutout(src, dst=None, tol=18):
    """제품 사진의 흰색/단색 배경을 제거해 투명 PNG로 저장. 실패(배경이 단색이 아님 등)하면 None 반환."""
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        if im.getchannel("A").getextrema()[0] < 250:  # 이미 투명 배경
            out = im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
            if dst: out.save(dst)
            return out
    rgb = im.convert("RGB")
    if max(rgb.size) > 1600:
        k = 1600 / max(rgb.size); rgb = rgb.resize((int(rgb.width * k), int(rgb.height * k)), Image.LANCZOS)
    w, h = rgb.size
    border = [rgb.getpixel((x, 0)) for x in range(0, w, 6)] + [rgb.getpixel((x, h - 1)) for x in range(0, w, 6)] \
        + [rgb.getpixel((0, y)) for y in range(0, h, 6)] + [rgb.getpixel((w - 1, y)) for y in range(0, h, 6)]
    med = tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))
    near = sum(1 for c in border if sum(abs(c[i] - med[i]) for i in range(3)) <= 54) / len(border)
    if near < 0.9:
        return None  # 배경이 단색이 아님 → 사용자에게 흰 배경/투명 PNG 요청
    marker = (255, 0, 255)
    flood = rgb.copy()
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
    for sd in seeds:
        if flood.getpixel(sd) != marker and sum(abs(flood.getpixel(sd)[i] - med[i]) for i in range(3)) <= 54:
            ImageDraw.floodfill(flood, sd, marker, thresh=tol)
    r, g, b = flood.split()
    bgm = ImageChops.darker(ImageChops.darker(r.point(lambda v: 255 if v == 255 else 0), g.point(lambda v: 255 if v == 0 else 0)),
                            b.point(lambda v: 255 if v == 255 else 0))
    alpha = ImageChops.invert(bgm).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.1))
    area = sum(alpha.histogram()[128:]) / (w * h)
    if area < 0.03 or area > 0.97:
        return None
    out = rgb.convert("RGBA"); out.putalpha(alpha)
    out = out.crop(alpha.point(lambda v: 255 if v > 8 else 0).getbbox())
    if dst: out.save(dst)
    return out



# ---------- 제품 일러스트 (적절한 실물 이미지를 못 찾았을 때 사용) ----------
ILLUST_KINDS = ["stick_vacuum", "robot_vacuum", "fridge", "kimchi_fridge", "washer", "washer_drum", "washer_top", "dryer", "tv", "aircon",
                "air_purifier", "microwave", "dishwasher", "generic"]


def illustration(kind):
    """브랜드 스타일(네이비 선 + 아이스블루 면 + 오렌지 포인트) 평면 일러스트를 RGBA로 반환. 특정 모델을 흉내내지 않는 범용 형태."""
    K = 2; LW = 9 * K
    OUT = NAVY; MID = (0x40, 0x52, 0x78); FILL = ICE; SHADE = (0xC4, 0xD5, 0xEA); GLASS = (0xA9, 0xC4, 0xE6)
    sizes = {"stick_vacuum": (420, 1100), "robot_vacuum": (800, 800), "fridge": (600, 1050), "kimchi_fridge": (760, 860),
             "washer": (700, 820), "washer_drum": (700, 820), "washer_top": (700, 820), "dryer": (700, 820), "tv": (1000, 720), "aircon": (1000, 340), "air_purifier": (520, 860),
             "microwave": (860, 600), "dishwasher": (700, 780), "generic": (700, 700)}
    w, h = sizes.get(kind, sizes["generic"]); w2, h2 = w * K, h * K
    im = Image.new("RGBA", (w2, h2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)

    def rr(x1, y1, x2, y2, r, fill=FILL, outline=OUT, ow=LW):
        d.rounded_rectangle((x1 * K, y1 * K, x2 * K, y2 * K), radius=r * K, fill=fill, outline=outline, width=ow)

    def ov(cx, cy, r, fill=FILL, outline=OUT, ow=LW):
        d.ellipse(((cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K), fill=fill, outline=outline, width=ow)

    def ln(x1, y1, x2, y2, wd=LW, c=OUT):
        d.line((x1 * K, y1 * K, x2 * K, y2 * K), fill=c, width=wd)

    m = 14
    if kind == "stick_vacuum":
        rr(130, m, 290, 110, 40)                       # 손잡이
        rr(100, 100, 320, 520, 50)                     # 본체
        rr(140, 150, 280, 330, 26, fill=BLUE)          # 먼지통
        ov(210, 420, 24, fill=ORANGE)                  # 버튼
        rr(190, 520, 230, 900, 8, fill=SHADE)          # 파이프
        rr(40, 900, 380, 1040, 56, fill=MID)           # 헤드
        ov(210, 970, 26, fill=ORANGE, outline=ORANGE)
    elif kind == "robot_vacuum":
        ov(400, 400, 380); ov(400, 400, 290, fill=WHITE, ow=LW - 2)
        ov(400, 400, 70, fill=ORANGE); ov(400, 400, 22, fill=NAVY, outline=NAVY)
        rr(300, 90, 500, 130, 14, fill=SHADE, ow=LW - 3)
        ov(150, 190, 14, fill=NAVY, outline=NAVY); ov(650, 190, 14, fill=NAVY, outline=NAVY)
    elif kind in ("fridge", "kimchi_fridge"):
        tall = kind == "fridge"
        rr(m, m, w - m, h - m, 38)
        top = 40 if tall else 30
        if tall:
            ln(w / 2, m, w / 2, h * 0.62); ln(m, h * 0.62, w - m, h * 0.62)
            rr(w / 2 - 40, 120, w / 2 - 22, 360, 8, fill=NAVY); rr(w / 2 + 22, 120, w / 2 + 40, 360, 8, fill=NAVY)
            rr(w / 2 - 110, h * 0.62 + 40, w / 2 + 110, h * 0.62 + 62, 10, fill=NAVY)
            ov(w - 90, h * 0.62 + 120, 12, fill=ORANGE, outline=ORANGE)
        else:
            ln(m, h * 0.30, w - m, h * 0.30)
            rr(90, 90, w - 90, 130, 12, fill=SHADE, ow=LW - 3)
            rr(w - 130, h * 0.30 + 70, w - 100, h * 0.30 + 320, 10, fill=NAVY)
            ov(110, h * 0.30 + 110, 14, fill=ORANGE, outline=ORANGE)
    elif kind in ("washer", "washer_drum", "dryer"):
        rr(m, m, w - m, h - m, 36)
        ln(m, 170, w - m, 170)
        ov(130, 92, 36, fill=SHADE); rr(230, 62, 470, 124, 16, fill=NAVY)
        ov(w - 120, 92, 14, fill=ORANGE, outline=ORANGE)
        ov(w / 2, 500, 250); ov(w / 2, 500, 190, fill=GLASS); ov(w / 2, 500, 190, fill=None, ow=LW - 3)
        if kind in ("washer", "washer_drum"):
            ov(w / 2 - 20, 560, 90, fill=(0x8F, 0xB1, 0xDC), outline=None, ow=0)
        else:
            for i in range(4): ln(w / 2 - 110, 430 + i * 52, w / 2 + 110, 430 + i * 52, 6, SHADE)
        d.arc(((w / 2 - 150) * K, (500 - 150) * K, (w / 2 + 150) * K, (500 + 150) * K), 200, 260, fill=WHITE, width=12 * K // 2)
    elif kind == "washer_top":                         # 통돌이(상부 투입형): 윗면 뚜껑 + 조작부
        rr(m, 130, w - m, h - m, 36)
        rr(70, m, w - 70, 190, 30, fill=SHADE)         # 뚜껑
        ov(w / 2, 102, 30, fill=BLUE)                  # 뚜껑 손잡이
        ln(m, 270, w - m, 270)
        ov(130, 350, 38, fill=SHADE); rr(260, 322, 500, 380, 16, fill=NAVY)
        ov(w - 120, 350, 14, fill=ORANGE, outline=ORANGE)
        rr(130, 470, w - 130, h - 120, 28, fill=SHADE, ow=LW - 3)
    elif kind == "tv":
        rr(m, m, w - m, 600, 26, fill=MID)
        rr(m + 22, m + 22, w - m - 22, 578, 14, fill=(0x2E, 0x5E, 0xAA))
        d.polygon([(130 * K, 578 * K), (420 * K, 578 * K), (240 * K, m * K + 22 * K), (130 * K, m * K + 22 * K)], fill=(0x3A, 0x6C, 0xBA))
        ov(w - 90, 580, 6, fill=ORANGE, outline=ORANGE, ow=0)
        rr(w / 2 - 40, 600, w / 2 + 40, 650, 4, fill=SHADE); rr(w / 2 - 190, 650, w / 2 + 190, 700, 22)
    elif kind == "aircon":
        rr(m, m, w - m, 250, 60)
        rr(70, 170, w - 70, 220, 22, fill=NAVY)
        ov(w - 130, 100, 11, fill=ORANGE, outline=ORANGE); rr(100, 80, 300, 118, 12, fill=SHADE, ow=LW - 3)
        for i, x in enumerate((220, 420, 620, 820)):
            d.arc(((x - 60) * K, 250 * K, (x + 60) * K, 330 * K), 20, 160, fill=BLUE, width=9 * K)
    elif kind == "air_purifier":
        rr(m, m, w - m, h - m, 70)
        for i in range(6): ln(120, 100 + i * 24, w - 120, 100 + i * 24, 7)
        ov(w / 2, 470, 190); ov(w / 2, 470, 120, fill=SHADE)
        for i in range(5): ln(w / 2 - 100, 420 + i * 24, w / 2 + 100, 420 + i * 24, 6, WHITE)
        ov(w / 2, 740, 14, fill=ORANGE, outline=ORANGE)
    elif kind == "microwave":
        rr(m, m, w - m, h - m, 36)
        rr(60, 70, 590, 530, 20, fill=GLASS); rr(90, 100, 560, 500, 12, fill=(0x8F, 0xB1, 0xDC), outline=None, ow=0)
        ln(640, 70, 640, 530)
        rr(680, 90, 800, 160, 14, fill=NAVY); ov(740, 250, 40); ov(740, 360, 14, fill=ORANGE, outline=ORANGE)
        rr(690, 430, 790, 500, 14, fill=SHADE)
    elif kind == "dishwasher":
        rr(m, m, w - m, h - m, 36)
        rr(70, 70, w - 70, 150, 20, fill=NAVY); ov(w - 130, 110, 12, fill=ORANGE, outline=ORANGE)
        rr(70, 200, w - 70, h - 150, 22, fill=SHADE, ow=LW - 3)
        rr(w / 2 - 140, 230, w / 2 + 140, 262, 14, fill=NAVY)
    else:
        rr(m, m, w - m, h - m, 120); ov(w / 2, h / 2, 110, fill=NAVY, outline=NAVY)
        ln(w / 2 - 70, m, w / 2 - 70, -40); ov(w / 2, h / 2, 40, fill=ORANGE, outline=ORANGE)
    return im.resize((w, h), Image.LANCZOS)


def place_image(c, path, box, anchor="center", max_up=1.4):
    """제품 이미지를 비율 유지한 채 box(x1,y1,x2,y2) 안에 배치. 늘리거나 자르지 않는다."""
    if isinstance(path, str) and path.startswith("illust:"):
        im = illustration(path.split(":", 1)[1]); c.illust = True; max_up = max(max_up, 1.8)
    else:
        im = Image.open(path).convert("RGBA")
    bw, bh = box[2] - box[0], box[3] - box[1]
    k = min(bw / im.width, bh / im.height, max_up)
    nw, nh = max(1, int(im.width * k)), max(1, int(im.height * k))
    im = im.resize((nw * S, nh * S), Image.LANCZOS)
    x = box[0] + (bw - nw) / 2
    y = box[1] + (bh - nh) / 2 if anchor == "center" else box[3] - nh
    c.img.paste(im, (int(x * S), int(y * S)), im)
    return (x, y, x + nw, y + nh)


def pill(c, x, y, text, size=26, fill=None, outline=None, color=WHITE, h=46, display=False):
    f = dfont(size) if display else font("semibold", size); w = c.text_w(text, f) + 40
    c.d.rounded_rectangle((x * S, y * S, (x + w) * S, (y + h) * S), radius=h / 2 * S, fill=fill, outline=outline, width=2 * S if outline else 0)
    c.text(x + w / 2, y + h / 2, text, f, color, "mm")
    return w


def burst(c, cx, cy, r, fill, points=22, inner=0.86):
    pts = []
    for i in range(points * 2):
        rr = r if i % 2 == 0 else r * inner
        a = math.pi * i / points - math.pi / 2
        pts.append(((cx + rr * math.cos(a)) * S, (cy + rr * math.sin(a)) * S))
    c.d.polygon(pts, fill=fill)


# ---------- 전체 레이아웃 카드 (제품 / 포스터) ----------
def full_product_cover(c, spec):
    """제품 뉴스 표지: 제목은 위, 제품 전체 모습을 배경·프레임 없이 크게."""
    t = c.t
    if spec.get("label"): c.text(W / 2, 190, spec["label"], font("regular", 28), t["label"], "ma")
    y = 190 + (28 + 26 if spec.get("label") else 0)
    for ln in spec["title"].split("\n"):
        c.text(W / 2, y, ln, font("bold", 46), t["title"], "ma"); y += 46 + 22
    if spec.get("subtitle"):
        c.text(W / 2, y + 8, spec["subtitle"], font("regular", 28), t["sub"], "ma"); y += 8 + 28
    if spec.get("image"):
        place_image(c, spec["image"], (110, y + 60, W - 110, 1110))
    if spec.get("source"):
        c.text(90, 1230, spec["source"], font("regular", 20), t["page"], "lm")


def full_product(c, spec):
    """제품 카드: 좌측 텍스트·스펙, 우측 제품 전체 컷."""
    t = c.t
    y = 170
    if spec.get("tag"): pill(c, 90, y, spec["tag"], fill=None, outline=ORANGE, color=ORANGE); y += 46 + 40
    f = font("bold", 46)
    for ln in c.wrap(spec["title"], f, 470):
        c.text(90, y, ln, f, t["title"]); y += 46 + 16
    if spec.get("subtitle"):
        y += 6
        for ln in c.wrap(spec["subtitle"], font("regular", 28), 470):
            c.text(90, y, ln, font("regular", 28), t["sub"]); y += 28 + 14
    y += 20
    c.d.rectangle((90 * S, y * S, 150 * S, (y + 4) * S), fill=ORANGE if c.bg != "orange" else NAVY); y += 40
    for lab, val in spec.get("specs", [])[:4]:
        c.text(90, y, lab, font("semibold", 24), t["sub"]); c.text(90, y + 34, val, font("bold", 34), t["title"]); y += 104
    if spec.get("price"):
        if spec.get("original"):
            c.text(90, y, spec["original"], font("regular", 26), t["page"])
            c.hline(y + 15, 90, 90 + c.text_w(spec["original"], font("regular", 26)), t["page"], 1.5); y += 40
        c.text(90, y, spec["price"], font("bold", 64), ORANGE); y += 74
        if spec.get("price_note"): c.text(90, y, spec["price_note"], font("regular", 24), t["sub"]); y += 30
    if spec.get("image"):
        place_image(c, spec["image"], (540, 220, W - 50, 1110))
    if spec.get("source"):
        c.text(90, 1230, spec["source"], font("regular", 20), t["page"], "lm")


def full_poster(c, spec):
    """혜택·행사 안내용 전단/포스터형 카드."""
    t = c.t; mode = spec.get("mode", "headline")
    pill_fill, pill_txt = (NAVY, WHITE) if c.bg in ("orange", "blue", "ice") else (ORANGE, WHITE)
    if mode == "headline":
        y = 150
        if spec.get("tag"): pill(c, 90, y, spec["tag"], size=30, fill=pill_fill, color=pill_txt, h=56, display=USE_DISPLAY); y += 56 + 36
        hl = spec.get("highlight", 1)
        f = dfont(104) if USE_DISPLAY else font("bold", 96)
        for i, ln in enumerate(spec["headline"].split("\n")):
            tw = c.text_w(ln, f)
            if i == hl:
                c.d.rectangle((70 * S, (y + 4) * S, (90 + tw + 24) * S, (y + 118) * S), fill=NAVY if c.bg != "navy" else ORANGE)
                c.text(90, y, ln, f, WHITE)
            else:
                c.text(90, y, ln, f, t["title"])
            y += 128
        if spec.get("subtitle"): c.text(90, y + 14, spec["subtitle"], font("semibold", 32), t["sub"] if c.bg != "orange" else WHITE); y += 14 + 32
        top_img = y + 30
        if spec.get("image"):
            place_image(c, spec["image"], (60, top_img, 700, 1100), anchor="bottom", max_up=1.6)
        if spec.get("burst_main"):
            cx, cy = (790, top_img + 190) if spec.get("image") else (W / 2, top_img + 230)
            burst(c, cx, cy, 200, NAVY if c.bg != "navy" else ORANGE)
            if spec.get("burst_top"): c.text(cx, cy - 92, spec["burst_top"], font("semibold", 34), ICE, "mm")
            c.text(cx, cy - 8, spec["burst_main"], dfont(100) if USE_DISPLAY else font("bold", 92), WHITE, "mm")
            if spec.get("burst_sub"): c.text(cx, cy + 84, spec["burst_sub"], font("semibold", 28), ICE, "mm")
        if spec.get("note"):
            ny = 1120
            for ln in c.wrap(spec["note"], font("regular", 24), 560):
                c.text(90, ny, ln, font("regular", 24), t["sub"] if c.bg != "orange" else WHITE); ny += 34
    else:  # benefits
        c.text(90, 160, spec["title"], font("bold", 64), t["title"])
        if spec.get("subtitle"): c.text(90, 250, spec["subtitle"], font("regular", 30), t["sub"] if c.bg != "orange" else WHITE)
        y = 330
        for i, it in enumerate(spec["items"][:4], 1):
            head, desc = it[0], it[1]; val = it[2] if len(it) > 2 else None
            c.d.rounded_rectangle((90 * S, y * S, (W - 90) * S, (y + 170) * S), radius=28 * S, fill=WHITE)
            c.d.ellipse((124 * S, (y + 41) * S, 212 * S, (y + 129) * S), fill=NAVY)
            c.text(168, y + 85, str(i), font("bold", 46), WHITE, "mm")
            c.text(244, y + 62, head, font("bold", 40), NAVY, "lm"); c.text(244, y + 116, desc, font("regular", 26), GRAY, "lm")
            if val: c.text(W - 126, y + 85, val, font("bold", 54), ORANGE, "rm")
            y += 170 + 24
        if spec.get("note"): c.text(90, y + 10, spec["note"], font("regular", 24), t["sub"] if c.bg != "orange" else WHITE)


# ---------- 새 표지(cover_style v2): 큰 제목 + 제품 영역 카드 ----------
import re

# 표지색별 색 조합 (태그 알약, VS 배지, 제목 1·2줄, 부제, 힌트, 페이지 번호, 제품 영역 카드)
V2 = {
    "ice":    dict(t1=NAVY,     t2=BLUE,       sub=BLUE,       tag_fill=ORANGE, tag_txt=WHITE,    badge=ORANGE, vs=BLUE,       hint=BLUE,       page=NAVY,     panel=WHITE),
    "white":  dict(t1=NAVY,     t2=BLUE,       sub=BLUE,       tag_fill=ORANGE, tag_txt=WHITE,    badge=ORANGE, vs=BLUE,       hint=BLUE,       page=NAVY,     panel=STRIPE),
    "navy":   dict(t1=OFFWHITE, t2=NAVY_NOTE,  sub=NAVY_NOTE,  tag_fill=ORANGE, tag_txt=WHITE,    badge=ORANGE, vs=NAVY_NOTE,  hint=NAVY_NOTE,  page=OFFWHITE, panel=WHITE),
    "orange": dict(t1=NAVY,     t2=NAVY,       sub=NAVY,       tag_fill=NAVY,   tag_txt=OFFWHITE, badge=NAVY,   vs=NAVY,       hint=NAVY,       page=NAVY,     panel=WHITE),
    "blue":   dict(t1=WHITE,    t2=ICE,        sub=ICE,        tag_fill=ORANGE, tag_txt=WHITE,    badge=ORANGE, vs=ICE,        hint=ICE,        page=ICE,      panel=WHITE),
}
VS_RE = re.compile(r"\s+(?:vs\.?|VS\.?)\s+")


def _split_vs(line):
    parts = VS_RE.split(line, maxsplit=1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else None


def _line_w(c, ln, px):
    sv = _split_vs(ln)
    if sv:
        return c.text_w(sv[0], dfont(px)) + 28 + c.text_w("vs", dfont(px * 0.61)) + 28 + c.text_w(sv[1], dfont(px))
    return c.text_w(ln, dfont(px))


def _draw_line(c, x, y, ln, px, color, vs_color):
    sv = _split_vs(ln)
    if not sv:
        c.text(x, y, ln, dfont(px), color, "ls"); return
    f, fv = dfont(px), dfont(px * 0.61)
    c.text(x, y, sv[0], f, color, "ls"); x += c.text_w(sv[0], f) + 28
    c.text(x, y, "vs", fv, vs_color, "ls"); x += c.text_w("vs", fv) + 28
    c.text(x, y, sv[1], f, color, "ls")


def cover_v2(c, spec, total=5):
    """1장 표지. 태그 → 제목 2줄(Do Hyeon 128) → 부제 → 제품 영역 카드 → 하단 힌트·페이지 번호. 로고는 stamp_logo.py 가 하단 중앙에 넣는다."""
    p = V2[c.bg]; d = c.d
    if c.bg == "ice":      # 6px 네이비 테두리, 가장자리 안쪽 30px
        d.rectangle((30 * S, 30 * S, (W - 30) * S, (H - 30) * S), outline=NAVY, width=6 * S)
    elif c.bg == "white":  # 기존 흰 배경 카드 규칙
        c.frame()
    vis = list(spec.get("visuals") or [])
    if not vis and spec.get("image"):
        vis = [spec["image"]]
    vis = vis[:2]
    lines = spec["title"].split("\n")[: (2 if vis else 3)]

    # 태그 알약
    if spec.get("tag"):
        tf = dfont(38); tw = c.text_w(spec["tag"], tf)
        d.rounded_rectangle((90 * S, 105 * S, (90 + tw + 80) * S, (105 + 74) * S), radius=37 * S, fill=p["tag_fill"])
        c.text(90 + 40, 156, spec["tag"], tf, p["tag_txt"], "ls")

    # 제목: 폭 900px 안에 들어오도록 8px씩 줄임(최소 96px)
    px = 128 if vis else 144
    while px > 96 and max(_line_w(c, ln, px) for ln in lines) > 900:
        px -= 8
    step = round(px * 1.094)
    y = 330 if vis else 440     # 제품 영역이 없으면 위쪽이 너무 비지 않도록 조금 아래에서 시작
    for i, ln in enumerate(lines):
        _draw_line(c, 90, y, ln, px, p["t1"] if i == 0 else p["t2"], p["vs"])
        y += step
    last = y - step

    # 부제
    sub_y = 575 if vis else last + 100
    if spec.get("subtitle"):
        sz = 40
        while sz > 30 and c.text_w(spec["subtitle"], font("medium", sz)) > 900:
            sz -= 2
        c.text(90, sub_y, spec["subtitle"], font("medium", sz), p["sub"], "ls")

    # 제품 영역 카드
    if vis:
        d.rounded_rectangle((90 * S, 630 * S, 990 * S, 1080 * S), radius=40 * S, fill=p["panel"])
        if len(vis) == 1:
            place_image(c, vis[0], (130, 655, 950, 1040))
        else:
            place_image(c, vis[0], (130, 655, 500, 990)); place_image(c, vis[1], (580, 655, 950, 990))
            if spec.get("badge"):
                d.ellipse((482 * S, 772 * S, 598 * S, 888 * S), fill=p["badge"])
                c.text(540, 830, spec["badge"], dfont(52), p["tag_txt"], "mm")
            labels = spec.get("labels")
            if not labels:
                sv = _split_vs(lines[0]); labels = list(sv) if sv else None
            if labels and len(labels) == 2:
                c.text(315, 1030, labels[0], dfont(46), NAVY, "mm"); c.text(765, 1030, labels[1], dfont(46), NAVY, "mm")
        if getattr(c, "illust", False):
            c.text(540, 1064, "※ 이해를 돕기 위한 일러스트입니다", font("regular", 22), GRAY, "mm")

    # 하단 좌측: 힌트 + 페이지 번호
    c.text(90, 1210, "넘겨서 확인하기 →", font("medium", 34), p["hint"], "ls")
    c.text(90, 1262, f"1 / {total}", dfont(34), p["page"], "ls")


FULL = {"product_cover": full_product_cover, "product": full_product, "poster": full_poster}

BUILDERS = {"cover": b_cover, "formula": b_formula, "table": b_table, "checklist": b_checklist, "compare": b_compare,
            "steps": b_steps, "contact": b_contact, "review": b_review, "deal": b_deal, "cta": b_cta}
LEFT_ALIGNED = {"checklist", "review", "deal", "steps"}  # 문서 레이아웃: 목록·표·후기는 좌측 150px 시작


def render(deck, outdir):
    global USE_DISPLAY
    ensure_fonts()
    os.makedirs(outdir, exist_ok=True)
    cards = deck["cards"]
    assert len(cards) == 5, "게시물은 항상 5장"
    cover_color = deck.get("cover_color", "navy")
    cover_style = deck.get("cover_style")
    USE_DISPLAY = (cover_style == "v2")
    for i, spec in enumerate(cards, 1):
        kind = spec["type"]
        bg = spec.get("bg") or (cover_color if i == 1 else ("navy" if i == 5 else "white"))
        # 새 표지: 1장의 cover·product_cover (브랜드 소개용 logo:true 표지는 기존 레이아웃 유지)
        v2 = (i == 1 and cover_style == "v2" and kind in ("cover", "product_cover")
              and not (kind == "cover" and spec.get("logo")) and bg in V2)
        c = Card(bg)
        if v2:
            cover_v2(c, spec, total=len(cards))
        elif kind in FULL:
            FULL[kind](c, spec)
        else:
            build = BUILDERS[kind](spec)
            layout_center(c, build, center=spec.get("center", 690))
        c.finish(i, cover_v2=v2)
        c.save(os.path.join(outdir, f"card{i}"))
    return outdir


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--cutout":  # python3 gen_cards.py --cutout in.jpg out.png [tol: 18(기본)/40/60 — 그림자가 남으면 값을 올린다]
        r = cutout(sys.argv[2], sys.argv[3], tol=int(sys.argv[4]) if len(sys.argv) > 4 else 18); print("OK" if r is not None else "FAIL: 배경이 단색이 아니거나 제거 불가")
        sys.exit(0 if r is not None else 2)
    deck = json.load(open(sys.argv[1], encoding="utf-8"))
    print(render(deck, sys.argv[2]))
