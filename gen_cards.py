#!/usr/bin/env python3
"""가전소 카드뉴스 생성기 (브랜드 가이드 Ver 1.1 기준)

사용법:
  python3 gen_cards.py deck.json OUTDIR
deck.json 형식은 DECK_SPEC.md 참고. 결과: OUTDIR/card1~N.png (1080x1350) + card1~N.jpg (Instagram 업로드용). N 은 기본 7장, 최대 9장(예전 5장 덱도 허용)
deck.json 에 "cover_style": "v2" 를 넣으면 1장(cover·product_cover)이 새 표지 디자인(Do Hyeon 제목, 제품 영역 카드, VS 배지)으로 만들어진다.
deck.json 에 "design": "lab" 을 넣으면 모든 장이 연구소 리포트 디자인(모눈 배경·FILE 라벨·스펙 시트·도면 일러스트)으로 만들어진다.
  이때 "illust:종류" 는 assets/blueprints/ 의 도면을 쓰고, 1장 오른쪽 위는 stamp_logo.py 용 로고 칸으로 비워 둔다.
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


MONO_FONT_FILE = "IBMPlexMono-SemiBold.ttf"
MONO_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/IBMPlexMono-SemiBold.ttf"
MONO_OK = True         # IBM Plex Mono 사용 가능 여부(연구소 리포트 디자인의 라벨·숫자용, 실패 시 Pretendard SemiBold)


def ensure_fonts():
    """폰트 파일이 없으면 Pretendard(OFL)를 내려받는다."""
    import urllib.request
    os.makedirs(FONT_DIR, exist_ok=True)
    for n in ("Pretendard-Regular.otf", "Pretendard-Medium.otf", "Pretendard-SemiBold.otf", "Pretendard-Bold.otf", "Pretendard-ExtraBold.otf"):
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
    global MONO_OK
    p = os.path.join(FONT_DIR, MONO_FONT_FILE)
    try:
        if not os.path.exists(p) or os.path.getsize(p) < 50000:
            urllib.request.urlretrieve(MONO_FONT_URL, p)
        ImageFont.truetype(p, 20)
        MONO_OK = True
    except Exception as e:  # 실패해도 생성은 계속(라벨·숫자는 Pretendard SemiBold 로 대체)
        MONO_OK = False
        print("MONO_FONT_FALLBACK: IBM Plex Mono 사용 불가, Pretendard SemiBold 로 대체 -", e)


from functools import lru_cache


@lru_cache(maxsize=None)
def font(weight, px):
    name = {"regular": "Pretendard-Regular.otf", "medium": "Pretendard-Medium.otf",
            "semibold": "Pretendard-SemiBold.otf", "bold": "Pretendard-Bold.otf",
            "extrabold": "Pretendard-ExtraBold.otf"}[weight]
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

    def finish(self, n, cover_v2=False, total=5):
        if cover_v2:  # 새 표지: 테두리·페이지 번호·힌트는 cover_v2()가 그리고, 콘센트 심볼은 쓰지 않는다. QR 상담 배지만 공통
            self.qr_badge()
            return
        self.frame(); self.symbol(); self.page_no(n, total); self.qr_badge()
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
        if spec.get("footnote"):
            cur += 40
            if not dry: c.text(W / 2, cur, spec["footnote"], font("regular", 24), t["sub"], "ma")
            cur += 24
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
        if spec.get("footnote"):
            cur += 6
            if not dry: c.text(W / 2, cur, spec["footnote"], font("regular", 24), t["sub"], "ma")
            cur += 24
            return cur - y
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
        if spec.get("footnote"):
            cur += 6
            if not dry: c.text(W / 2, cur, spec["footnote"], font("regular", 24), t["sub"], "ma")
            cur += 24
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
                "air_purifier", "microwave", "dishwasher", "generic",
                "stand_aircon", "styler", "water_purifier", "induction"]  # 마지막 4종은 연구소 리포트 디자인(도면)에서만 전용 그림, 기존 디자인은 generic


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


# ---------- 연구소 리포트 디자인 (deck "design": "lab") ----------
# 모눈 배경 + 모서리 크롭 마크 + FILE 라벨 + 흰 스펙 시트 패널 + 도면 일러스트.
# 제목 Pretendard ExtraBold, 라벨·숫자 IBM Plex Mono. 도면은 design/blueprints 에서 만든 assets/blueprints/*.png 를 쓴다.
BLUEPRINT_DIR = os.path.join(HERE, "assets", "blueprints")
LAB_ALIAS = {"washer": "washer_drum"}
LAB_LANDSCAPE = {"robot_vacuum", "tv", "aircon", "microwave", "induction"}
LAB_KIND_TAG = {"stick_vacuum": "VACUUM", "robot_vacuum": "ROBOT", "fridge": "FRIDGE", "kimchi_fridge": "KIMCHI",
                "washer_drum": "WASHER", "washer_top": "WASHER", "dryer": "DRYER", "tv": "TV", "aircon": "AIRCON",
                "stand_aircon": "AIRCON", "air_purifier": "AIR", "microwave": "MICROWAVE", "dishwasher": "DISHWASHER",
                "styler": "CLOTHCARE", "water_purifier": "WATER", "induction": "COOKTOP", "generic": "REPORT"}
LAB_FILE = {"formula": "FORMULA", "table": "SPEC SHEET", "checklist": "CHECKLIST", "compare": "COMPARE", "steps": "PROCESS",
            "contact": "CONTACT", "review": "REVIEW", "deal": "DEAL", "cta": "CONSULT", "product": "PRODUCT", "poster": "NOTICE"}
LAB_CONTENT_BG = {"table": "ice", "compare": "ice", "contact": "ice"}  # 그 외 내용 카드·CTA 는 white
DASH = (0xB8, 0xC7, 0xDB)
LOGO_BOX = (820, 24, 1040, 252)   # 표지 로고 칸: stamp_logo.py 가 오른쪽 위에 로고를 넣을 수 있게 모눈 없이 비운다


def _blend(a, b, t):
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


LAB = {
    "navy":   dict(grid=_blend(NAVY, ICE, .08), crop=ICE, label=ICE, file=ORANGE, dim=NAVY_NOTE, title=OFFWHITE, sub=ICE,
                   page=NAVY_NOTE, sym=ICE, dot=ICE, tag_fill=ORANGE, tag_txt=NAVY, art="dark"),
    "blue":   dict(grid=_blend(BLUE, ICE, .12), crop=ICE, label=ICE, file=ORANGE, dim=ICE, title=WHITE, sub=ICE,
                   page=ICE, sym=WHITE, dot=WHITE, tag_fill=ORANGE, tag_txt=NAVY, art="dark"),
    "ice":    dict(grid=_blend(ICE, BLUE, .12), crop=BLUE, label=BLUE, file=ORANGE, dim=BLUE, title=NAVY, sub=GRAY,
                   page=BLUE, sym=NAVY, dot=BLUE, tag_fill=NAVY, tag_txt=OFFWHITE, art="light"),
    "white":  dict(grid=_blend(WHITE, NAVY, .06), crop=NAVY, label=BLUE, file=ORANGE, dim=BLUE, title=NAVY, sub=GRAY,
                   page=BLUE, sym=NAVY, dot=NAVY, tag_fill=ICE, tag_txt=NAVY, art="light"),
    "orange": dict(grid=_blend(ORANGE, NAVY, .10), crop=NAVY, label=NAVY, file=OFFWHITE, dim=NAVY, title=NAVY, sub=NAVY,
                   page=NAVY, sym=OFFWHITE, dot=NAVY, tag_fill=NAVY, tag_txt=OFFWHITE, art="orange"),
}


@lru_cache(maxsize=None)
def mfont(px):
    """라벨·숫자용 고정폭 글꼴(IBM Plex Mono). 사용 불가면 Pretendard SemiBold."""
    if MONO_OK:
        return ImageFont.truetype(os.path.join(FONT_DIR, MONO_FONT_FILE), int(px * S))
    return font("semibold", px)


def _is_kr(ch):
    o = ord(ch)
    return 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F or 0xAC00 <= o <= 0xD7A3 or 0x3000 <= o <= 0x303F \
        or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFFEF


def ttext_w(c, s, f, px, track=0.0, kf=None):
    """글자 간격(track, em 단위)을 넣은 폭. kf 가 있으면 한글은 kf, 나머지는 f(혼합 글꼴)."""
    return sum(c.text_w(ch, kf if (kf and (_is_kr(ch) or ch == " ")) else f) + track * px for ch in s) - (track * px if s else 0)


def ttext(c, x, y, s, f, px, color, track=0.0, kf=None, anchor="ls"):
    """글자 간격을 조절해 한 글자씩 그린다(기준선 y). anchor: ls 왼쪽 / rs 오른쪽 / ms 가운데."""
    w = ttext_w(c, s, f, px, track, kf)
    if anchor == "rs":
        x -= w
    elif anchor == "ms":
        x -= w / 2
    for ch in s:
        ff = kf if (kf and (_is_kr(ch) or ch == " ")) else f
        c.d.text((x * S, y * S), ch, font=ff, fill=color, anchor="ls")
        x += c.text_w(ch, ff) + track * px
    return w


def mtext(c, x, y, s, px, color, track=0.08, anchor="ls", kweight="semibold"):
    """영문·숫자는 Plex Mono, 한글은 Pretendard 로 섞어 쓴다."""
    return ttext(c, x, y, s, mfont(px), px, color, track, font(kweight, px), anchor)


def mtext_w(c, s, px, track=0.08, kweight="semibold"):
    return ttext_w(c, s, mfont(px), px, track, font(kweight, px))


def lab_wrap(c, text, f, px, max_w, track=0.0, kf=None):
    """띄어쓰기 단위로 줄바꿈(한 단어가 너무 길면 글자 단위)."""
    out = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            cand = (cur + " " + word) if cur else word
            if ttext_w(c, cand, f, px, track, kf) <= max_w:
                cur = cand
                continue
            if cur:
                out.append(cur)
            cur = ""
            for ch in word:  # 긴 단어는 글자 단위로 자른다
                if cur and ttext_w(c, cur + ch, f, px, track, kf) > max_w:
                    out.append(cur); cur = ch
                else:
                    cur += ch
        out.append(cur)
    return out


def BL(top, px):
    """글자 상자 위쪽 → 기준선(Pretendard 대략 값)."""
    return top + px * 0.86


def lab_grid(c, clear=None, crops=("tl", "tr", "bl", "br")):
    L = LAB[c.bg]; d = c.d
    for k in range(0, max(W, H) // 54 + 2):
        p = k * 54 - 2
        if p < W: d.rectangle((p * S, 0, (p + 2) * S - 1, H * S), fill=L["grid"])
        if p < H: d.rectangle((0, p * S, W * S, (p + 2) * S - 1), fill=L["grid"])
    if clear:  # 로고 칸: 모눈 없이 비우고 바깥쪽에만 가는 테두리
        x1, y1, x2, y2 = clear
        d.rectangle((x1 * S, y1 * S, x2 * S, y2 * S), fill=BG[c.bg], outline=L["dim"], width=2 * S)
    m, ln, wd = 40, 56, 4
    for cn in crops:
        x = m if cn[1] == "l" else W - m; y = m if cn[0] == "t" else H - m
        sx = 1 if cn[1] == "l" else -1; sy = 1 if cn[0] == "t" else -1
        d.rectangle((min(x, x + sx * ln) * S, min(y, y + sy * wd) * S, max(x, x + sx * ln) * S, max(y, y + sy * wd) * S), fill=L["crop"])
        d.rectangle((min(x, x + sx * wd) * S, min(y, y + sy * ln) * S, max(x, x + sx * wd) * S, max(y, y + sy * ln) * S), fill=L["crop"])


def lab_file(c, parts, y=118):
    """왼쪽 위 FILE 라벨. parts: [(글자, 강조여부)]"""
    L = LAB[c.bg]; x = 96
    for s, hi in parts:
        x += mtext(c, x, y, s, 26, L["file"] if hi else L["label"], 0.1)


def lab_plug(c, cx=952, cy=114, size=76, color=None, dot=None):
    L = LAB[c.bg]; color = color or L["sym"]; dot = dot or L["dot"]
    u = size / 48; d = c.d; lw = max(2, round(3.4 * u * S))
    X = lambda v: (cx - size / 2 + v * u) * S; Y = lambda v: (cy - size / 2 + v * u) * S
    for px_ in (18, 30):
        d.line((X(px_), Y(4), X(px_), Y(15)), fill=color, width=lw)
    d.rounded_rectangle((X(8), Y(15), X(40), Y(42)), radius=8 * u * S, outline=color, width=lw)
    r = 4.6 * u * S
    d.ellipse((X(24) - r, Y(28.5) - r, X(24) + r, Y(28.5) + r), fill=dot)


def lab_page(c, n, total):
    mtext(c, 96, 1266, f"{n:02d}/{total:02d}", 26, LAB[c.bg]["page"], 0.04)


def lab_consult(c):
    """2~4장 오른쪽 아래 작은 상담 QR 배지."""
    x1, y1, x2, y2 = 664, 1150, 970, 1270
    c.d.rounded_rectangle((x1 * S, y1 * S, x2 * S, y2 * S), radius=12 * S, fill=WHITE, outline=NAVY, width=3 * S)
    qr = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(QR_URL); qr.make(fit=True)
    q = qr.make_image(fill_color="black", back_color="white").convert("RGB").resize((96 * S, 96 * S), Image.NEAREST)
    c.img.paste(q, ((x1 + 12) * S, (y1 + 12) * S))
    mtext(c, x1 + 126, y1 + 50, "CONSULT", 18, BLUE, 0.12)
    c.text(x1 + 126, y1 + 86, "상담문의 · 가전소", font("bold", 22), NAVY, "ls")
    c.consult = True


def lab_footnote(c, text, bottom=1218):
    """출처·면책 한 줄(최대 2줄). 아래에서부터 쌓는다. 상담 QR 이 있으면 그 왼쪽까지만."""
    if not text:
        return
    f = font("regular", 24)
    lines = lab_wrap(c, text, f, 24, 540 if getattr(c, "consult", False) else 880)[:2]
    y = bottom - (len(lines) - 1) * 34
    for ln in lines:
        c.text(96, y, ln, f, GRAY if c.bg in ("white", "ice") else LAB[c.bg]["sub"], "ls"); y += 34


def lab_pill(c, x, y, text, px, fill=None, outline=None, color=WHITE, h=None):
    h = h or round(px * 1.75); f = font("bold", px); w = c.text_w(text, f) + px * 1.6
    c.d.rounded_rectangle((x * S, y * S, (x + w) * S, (y + h) * S), radius=h / 2 * S, fill=fill, outline=outline,
                          width=3 * S if outline else 0)
    c.text(x + w / 2, y + h / 2, text, f, color, "mm")
    return w


def lab_dashed(c, x1, y1, x2, y2, color=DASH, w=2, dash=10, gap=8):
    import math as _m
    L_ = _m.hypot(x2 - x1, y2 - y1); n = 0.0
    while n < L_:
        e = min(n + dash, L_)
        c.d.line(((x1 + (x2 - x1) * n / L_) * S, (y1 + (y2 - y1) * n / L_) * S,
                  (x1 + (x2 - x1) * e / L_) * S, (y1 + (y2 - y1) * e / L_) * S), fill=color, width=round(w * S))
        n += dash + gap


def lab_sheet(c, x1, y1, x2, y2, fill=WHITE, border=NAVY, width=3, radius=10):
    c.d.rounded_rectangle((x1 * S, y1 * S, x2 * S, y2 * S), radius=radius * S, fill=fill, outline=border, width=width * S)


def lab_title(c, text, top, max_w=900, max_lines=2, sizes=(76, 70, 64, 58, 52), color=None, track=-0.045, lh=1.14):
    """내지 제목. 정해진 줄 수 안에 들어가는 가장 큰 크기로. 반환: 다음 요소의 y"""
    color = color or LAB[c.bg]["title"]
    for px in sizes:
        f = font("extrabold", px); lines = lab_wrap(c, text, f, px, max_w, track)
        if len(lines) <= max_lines:
            break
    lines = lines[:max_lines + 1]
    y = top
    for ln in lines:
        ttext(c, 90, BL(y, px), ln, f, px, color, track); y += px * lh
    return y - px * (lh - 1)


def _art_path(kind, theme):
    kind = LAB_ALIAS.get(kind, kind)
    p = os.path.join(BLUEPRINT_DIR, f"{kind}_{theme}.png")
    return p if os.path.exists(p) else os.path.join(BLUEPRINT_DIR, f"generic_{theme}.png")


def lab_visual(c, vis, box, full=False, floor=True):
    """도면(illust:종류) 또는 제품 컷을 box 안에 넣는다. full=True 면 도면 캔버스를 그대로(1:1) 붙인다."""
    x1, y1, x2, y2 = box; L = LAB[c.bg]
    if isinstance(vis, str) and vis.startswith("illust:"):
        c.illust = True
        im = Image.open(_art_path(vis.split(":", 1)[1], L["art"])).convert("RGBA")
        if not full:
            im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
        k = min((x2 - x1) * S / im.width, (y2 - y1) * S / im.height, 1.0)
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        px_ = int(x1 * S + ((x2 - x1) * S - im.width) / 2); py_ = int(y2 * S - im.height)
        c.img.paste(im, (px_, py_), im)
        return
    im = Image.open(vis).convert("RGBA")  # 실물 제품 컷: 비율 유지, 바닥선 위에 세운다
    pad = 30
    bw, bh = x2 - x1 - pad * 2, y2 - y1 - pad - 70
    k = min(bw / im.width, bh / im.height, 1.6)
    nw, nh = max(1, int(im.width * k)), max(1, int(im.height * k))
    fy = y2 - 50
    ix = x1 + pad + (bw - nw) / 2; iy = fy - nh
    c.img.paste(im.resize((nw * S, nh * S), Image.LANCZOS), (int(ix * S), int(iy * S)), im.resize((nw * S, nh * S), Image.LANCZOS))
    if floor:  # 도면처럼 바닥선·높이 치수선
        d = c.d; col = L["dim"]
        d.line((x1 * S, fy * S, x2 * S, fy * S), fill=col, width=2 * S)
        for hx in range(int(x1) + 20, int(x2), 28):
            d.line((hx * S, fy * S, (hx - 10) * S, (fy + 12) * S), fill=col, width=2 * S)
        vx = ix - 24
        d.line((vx * S, iy * S, vx * S, fy * S), fill=col, width=2 * S)
        for yy in (iy, fy):
            d.line(((vx - 10) * S, yy * S, (vx + 10) * S, yy * S), fill=col, width=2 * S)


def _visual_kind(vis):
    if isinstance(vis, str) and vis.startswith("illust:"):
        return LAB_ALIAS.get(vis.split(":", 1)[1], vis.split(":", 1)[1])
    return None


def _is_landscape(vis):
    k = _visual_kind(vis)
    if k:
        return k in LAB_LANDSCAPE
    try:
        im = Image.open(vis); return im.width / im.height > 1.25
    except Exception:
        return False


def lab_cover(c, spec, ctx):
    """1장 표지: 큰 제목(왼쪽) + 도면·제품 컷(오른쪽 세로형 / 위쪽 가로형). 오른쪽 위는 로고 칸."""
    L = LAB[c.bg]
    lab_grid(c, clear=LOGO_BOX, crops=("tl", "bl", "br"))
    vis = list(spec.get("visuals") or ([spec["image"]] if spec.get("image") else []))[:2]
    kinds = [k for k in map(_visual_kind, vis) if k]
    tag = spec.get("file_tag") or (LAB_KIND_TAG.get(kinds[0]) if kinds else "REPORT")
    lab_file(c, [("가전소 LAB · ", False), (f"FILE {ctx['run']}", True), (f" · {tag}", False)])
    land = len(vis) == 1 and _is_landscape(vis[0])

    if len(vis) == 1 and land:
        lab_visual(c, vis[0], (90, 250, 990, 610), full=True)
        col_w, tag_y, title_top, bottom = 900, 650, 730, 1150
    elif len(vis) == 1:
        lab_visual(c, vis[0], (570, 200, 1010, 1160), full=True)
        col_w, tag_y, title_top, bottom = 470, 470, 550, 1150
    elif len(vis) == 2:  # 비교형: 오른쪽 칸 위아래 + 가운데 VS
        lab_visual(c, vis[0], (590, 280, 1000, 660)); lab_visual(c, vis[1], (590, 760, 1000, 1140))
        d = c.d; cx, cy = 795, 712
        d.ellipse(((cx - 42) * S, (cy - 42) * S, (cx + 42) * S, (cy + 42) * S), fill=ORANGE if c.bg != "orange" else NAVY)
        mtext(c, cx, cy + 11, spec.get("badge") or "VS", 30, NAVY if c.bg != "orange" else OFFWHITE, 0.02, "ms")
        labels = spec.get("labels") or list(_split_vs(spec.get("title", "").split("\n")[0]) or [])
        if len(labels) == 2 and not kinds:  # 실물 컷 비교일 때만 이름표(도면에는 영문 라벨이 이미 있다)
            for lb, yy in zip(labels, (300, 780)):
                c.text(600, yy, lb, font("extrabold", 34), L["title"], "ls")
        col_w, tag_y, title_top, bottom = 470, 470, 550, 1150
    else:
        col_w, tag_y, title_top, bottom = 900, 470, 550, 1150

    if spec.get("tag"):
        lab_pill(c, 96, tag_y, spec["tag"], 30, fill=L["tag_fill"], color=L["tag_txt"], h=56)
    # 제목: 칸 너비 안에서 줄바꿈, 부제까지 bottom 안에 들어가는 가장 큰 크기
    title = spec.get("title", "").replace("\n", " ") if col_w < 900 else spec.get("title", "")
    title = " vs ".join(p.strip() for p in VS_RE.split(title)) if VS_RE.search(title) else title
    sub = spec.get("subtitle") or spec.get("label") or ""
    fs = font("medium", 30)
    sub_lines = lab_wrap(c, sub, fs, 30, col_w)[:2] if sub else []
    sub_h = (30 + len(sub_lines) * 42) if sub_lines else 0
    track = -0.05
    for px in (112, 104, 96, 88, 80, 72, 64):
        f = font("extrabold", px); lines = lab_wrap(c, title, f, px, col_w, track)
        if title_top + len(lines) * px * 1.06 + sub_h <= bottom:
            break
    y = title_top
    for ln in lines:
        x = 90
        for i, part in enumerate(re.split(r"(\bvs\b)", ln)):
            if part == "vs":
                x += ttext(c, x, BL(y, px), "vs", mfont(px * 0.82), px * 0.82, ORANGE if c.bg != "orange" else OFFWHITE, -0.02)
            elif part:
                x += ttext(c, x, BL(y, px), part, f, px, L["title"], track)
        y += px * 1.06
    y += 30
    for ln in sub_lines:
        c.text(96, y + 30, ln, fs, L["sub"] if c.bg != "navy" else ICE, "ls"); y += 42
    if getattr(c, "illust", False):
        c.text(96, 1214, "※ 이해를 돕기 위한 일러스트입니다", font("regular", 22), L["dim"], "ls")
    lab_page(c, 1, ctx["total"])
    mtext(c, 970, 1266, "SWIPE →", 24, L["dim"], 0.12, "rs")


def lab_header(c, spec, n, ctx, kind, title=True):
    """내용 카드 공통: 모눈·크롭 마크·FILE 라벨·콘센트 심볼·상담 QR·제목(+부제). 반환: 본문 시작 y"""
    lab_grid(c); lab_consult(c)
    lab_file(c, [(f"{LAB_FILE.get(kind, kind.upper())} · {n:02d}", False)])
    lab_plug(c)
    y = 160
    if title and spec.get("title"):
        y = lab_title(c, spec["title"], 160)
    sub = spec.get("subtitle") or spec.get("kicker_top")
    if sub:
        f = font("semibold", 30)
        for ln in lab_wrap(c, sub, f, 30, 900)[:2]:
            c.text(96, y + 24 + 26, ln, f, GRAY if c.bg in ("white", "ice") else LAB[c.bg]["sub"], "ls"); y += 42
        y += 10
    return y + 50


KS = (1.0, 0.93, 0.86, 0.8, 0.74, 0.68)


def _fit(b, top, bottom, rows=0, cap=56):
    """b(k, y, dry, ex) -> 높이. 들어가는 가장 큰 배율 k 를 고르고, 남는 높이는 줄마다 ex 만큼 나눠 패널을 아래로 늘린다."""
    avail = bottom - top
    for k in KS:
        h = b(k, top, True, 0)
        if h <= avail:
            break
    ex = max(0.0, min(cap, (avail - 30 - h) / rows)) if rows else 0.0
    return k, ex, b(k, top, True, ex)


def _rows_text(c, text, weight, px, max_w, track=-0.02):
    f = font(weight, px); return f, lab_wrap(c, text, f, px, max_w, track)


def _lines(c, x, y, lines, f, lh, color, track=-0.02):
    for ln in lines:
        ttext(c, x, BL(y, f.size / S), ln, f, f.size / S, color, track); y += lh
    return y


def lab_formula(c, spec, top, bottom):
    mw = 812; x = 134
    def b(k, y0, dry, ex):
        y = y0 + 40 + ex
        if spec.get("kicker"):
            f, ls = _rows_text(c, spec["kicker"], "semibold", 30 * k, mw)
            y = _lines(c, x, y, ls, f, 42 * k, GRAY, 0) if not dry else y + len(ls) * 42 * k
            y += 16 * k
        px = 128 * k
        while px > 60 and mtext_w(c, spec["big"], px, -0.03, "extrabold") > mw:
            px -= 4
        if not dry: mtext(c, x, BL(y, px), spec["big"], px, BLUE, -0.03, kweight="extrabold")
        y += px * 1.12
        if spec.get("tail"):
            f, ls = _rows_text(c, spec["tail"], "medium", 30 * k, mw)
            y = _lines(c, x, y, ls, f, 42 * k, GRAY, 0) if not dry else y + len(ls) * 42 * k
        y += 36 * k + ex
        if spec.get("example"):
            if not dry: lab_dashed(c, 93, y, 987, y)
            y += 40 * k + ex
            f, ls = _rows_text(c, spec["example"], "bold", 34 * k, mw - 60)
            h = len(ls) * 48 * k + 44 * k
            if not dry:
                c.d.rounded_rectangle((x * S, y * S, (990 - 44) * S, (y + h) * S), radius=10 * S, fill=NAVY)
                _lines(c, x + 30, y + 22 * k, ls, f, 48 * k, OFFWHITE)
            y += h + 44 * k + ex
        return y - y0
    k, ex, h = _fit(b, top, bottom, rows=4, cap=48)
    lab_sheet(c, 90, top, 990, top + h)
    b(k, top, False, ex)


def lab_table(c, spec, top, bottom):
    rows = spec.get("rows", [])[:6]
    def b(k, y0, dry, ex):
        y = y0
        for i, (a, v) in enumerate(rows):
            fa, la = _rows_text(c, a, "semibold", 28 * k, 220, 0)
            fv, lv = _rows_text(c, v, "extrabold", 42 * k, 540, -0.03)
            ha, hv = len(la) * 38 * k, len(lv) * 54 * k
            rh = max(ha, hv) + 56 * k + ex
            if not dry:
                if i % 2 == 1:
                    c.d.rectangle((93 * S, y * S, 987 * S, (y + rh) * S), fill=STRIPE)
                if i:
                    lab_dashed(c, 93, y, 987, y)
                _lines(c, 134, y + (rh - ha) / 2 + 4 * k, la, fa, 38 * k, GRAY, 0)
                _lines(c, 384, y + (rh - hv) / 2, lv, fv, 54 * k, NAVY, -0.03)
            y += rh
        return y - y0
    k, ex, h = _fit(b, top, bottom, rows=len(rows), cap=60)
    lab_sheet(c, 90, top, 990, top + h)
    b(k, top, False, ex)
    lab_sheet(c, 90, top, 990, top + h, fill=None)


def lab_checklist(c, spec, top, bottom):
    items = spec.get("items", [])[:5]
    def b(k, y0, dry, ex):
        y = y0
        if not dry:
            mtext(c, 134, y + 46, "NO", 22, BLUE, 0.08); mtext(c, 230, y + 46, "항목", 22, BLUE, 0.08)
            mtext(c, 946, y + 46, "CHECK", 22, BLUE, 0.08, "rs")
            c.d.rectangle((93 * S, (y + 70) * S, 987 * S, (y + 73) * S), fill=NAVY)
        y += 73
        for i, it in enumerate(items):
            f, ls = _rows_text(c, it, "extrabold", 38 * k, 630, -0.03)
            rh = max(len(ls) * 50 * k + 56 * k, 118 * k) + ex
            if not dry:
                if i: lab_dashed(c, 93, y, 987, y)
                mid = y + rh / 2
                mtext(c, 134, mid + 12 * k, f"{i + 1:02d}", 34 * k, BLUE, 0.02)
                _lines(c, 230, mid - len(ls) * 50 * k / 2, ls, f, 50 * k, NAVY, -0.03)
                bs = 56 * k
                c.d.rounded_rectangle(((946 - bs) * S, (mid - bs / 2) * S, 946 * S, (mid + bs / 2) * S), radius=10 * S, outline=NAVY, width=4 * S)
            y += rh
        return y - y0
    k, ex, h = _fit(b, top, bottom, rows=len(items), cap=50)
    lab_sheet(c, 90, top, 990, top + h)
    b(k, top, False, ex)


def lab_compare(c, spec, top, bottom):
    rows = spec.get("rows", [])[:5]; ca, cb = (list(spec.get("cols", ["A", "B"])) + ["A", "B"])[:2]
    XL, XA, XB, XR = 93, 293, 640, 987; PB = 76
    def b(k, y0, dry, ex):
        y = y0; hh = 116
        if not dry:
            c.d.rectangle((XB * S, y * S, XR * S, (y + hh) * S), fill=NAVY)
            mtext(c, XA + 30, y + 44, "A", 22, GRAY, 0.1); mtext(c, XB + PB, y + 44, "B", 22, ORANGE, 0.1)
            for txt, x, col, mw in ((ca, XA + 30, NAVY, XB - XA - 80), (cb, XB + PB, OFFWHITE, XR - XB - PB - 20)):
                px = 36
                while px > 22 and ttext_w(c, txt, font("extrabold", px), px, -0.03) > mw: px -= 2
                ttext(c, x, y + 92, txt, font("extrabold", px), px, col, -0.03)
            c.d.rectangle((XL * S, (y + hh) * S, XR * S, (y + hh + 3) * S), fill=NAVY)
            cx, cy = XB, y + hh / 2
            c.d.ellipse(((cx - 46) * S, (cy - 46) * S, (cx + 46) * S, (cy + 46) * S), fill=WHITE)
            c.d.ellipse(((cx - 40) * S, (cy - 40) * S, (cx + 40) * S, (cy + 40) * S), fill=ORANGE)
            mtext(c, cx, cy + 10, "VS", 28, NAVY, 0.02, "ms")
        y += hh + 3
        for i, r in enumerate(rows):
            lab_, va, vb = (list(r) + ["", "", ""])[:3]
            fl, ll = _rows_text(c, lab_, "bold", 28 * k, XA - XL - 50, 0)
            fa, la = _rows_text(c, va, "bold", 32 * k, XB - XA - 60)
            fb, lb = _rows_text(c, vb, "extrabold", 32 * k, XR - XB - PB - 20)
            rh = max(len(ll) * 40 * k, len(la) * 44 * k, len(lb) * 44 * k) + 56 * k + ex
            if not dry:
                c.d.rectangle((XB * S, y * S, XR * S, (y + rh) * S), fill=STRIPE)
                if i: lab_dashed(c, XL, y, XR, y)
                for col_lines, f, x, color, lh in ((ll, fl, 134, GRAY, 40 * k), (la, fa, XA + 30, GRAY, 44 * k), (lb, fb, XB + PB, NAVY, 44 * k)):
                    _lines(c, x, y + (rh - len(col_lines) * lh) / 2, col_lines, f, lh, color)
            y += rh
        return y - y0
    k, ex, h = _fit(b, top, bottom, rows=len(rows), cap=56)
    lab_sheet(c, 90, top, 990, top + h)
    b(k, top, False, ex)
    lab_sheet(c, 90, top, 990, top + h, fill=None)


def lab_steps(c, spec, top, bottom):
    steps = spec.get("steps", [])[:4]
    def b(k, y0, dry, ex):
        y = y0; centers = []
        for i, st in enumerate(steps):
            name, desc = (list(st) + [""])[:2]
            fn, ln_ = _rows_text(c, name, "extrabold", 40 * k, 690, -0.03)
            fd, ld = _rows_text(c, desc, "medium", 26 * k, 690, 0)
            bh = 26 * k + 28 * k + len(ln_) * 50 * k + len(ld) * 36 * k + 22 * k + ex
            if not dry:
                lab_sheet(c, 230, y, 990, y + bh)
                yy = y + 22 * k + ex / 2
                mtext(c, 264, BL(yy, 20 * k), f"STEP {i + 1:02d}", 20 * k, BLUE, 0.1); yy += 30 * k
                yy = _lines(c, 264, yy, ln_, fn, 50 * k, NAVY, -0.03)
                _lines(c, 264, yy, ld, fd, 36 * k, GRAY, 0)
            centers.append(y + bh / 2)
            y += bh + 26 * k
        if not dry:
            if len(centers) > 1:
                lab_dashed(c, 150, centers[0], 150, centers[-1], DASH, 4, 10, 10)
            for i, cy in enumerate(centers):
                last = i == len(centers) - 1; r = 50 * k
                c.d.ellipse(((150 - r - 10) * S, (cy - r - 10) * S, (150 + r + 10) * S, (cy + r + 10) * S), fill=BG[c.bg])
                c.d.ellipse(((150 - r) * S, (cy - r) * S, (150 + r) * S, (cy + r) * S), fill=ORANGE if last else NAVY)
                mtext(c, 150, cy + 13 * k, f"{i + 1:02d}", 36 * k, NAVY if last else OFFWHITE, 0.02, "ms")
        return y - 26 * k - y0
    k, ex, h = _fit(b, top, bottom, rows=len(steps), cap=50)
    b(k, top, False, ex)


def lab_contact(c, spec, top, bottom):
    items = spec.get("items", [])[:4]
    def b(k, y0, dry, ex):
        y = y0
        for it in items:
            name, sub, num = (list(it) + ["", "", ""])[:3]
            npx = 58 * k
            while npx > 34 and mtext_w(c, num, npx, -0.01) > 380: npx -= 2
            nw = mtext_w(c, num, npx, -0.01)
            fn, ln_ = _rows_text(c, name, "extrabold", 44 * k, 900 - 250 - nw, -0.03)
            fs, ls = _rows_text(c, sub, "medium", 24 * k, 900 - 250 - nw, 0)
            ch = len(ln_) * 54 * k + len(ls) * 34 * k
            th = max(ch + 60 * k, 150 * k) + ex
            if not dry:
                lab_sheet(c, 90, y, 990, y + th)
                cy = y + th / 2; r = 42 * k
                c.d.ellipse(((176 - r) * S, (cy - r) * S, (176 + r) * S, (cy + r) * S), fill=ICE)
                mtext(c, 176, cy + 8 * k, "TEL", 22 * k, BLUE, 0.04, "ms")
                yy = _lines(c, 250, cy - ch / 2, ln_, fn, 54 * k, NAVY, -0.03)
                _lines(c, 250, yy, ls, fs, 34 * k, GRAY, 0)
                mtext(c, 946, cy + npx * 0.36, num, npx, BLUE, -0.01, "rs")
            y += th + 26 * k
        return y - 26 * k - y0
    k, ex, h = _fit(b, top, bottom, rows=len(items), cap=40)
    b(k, top, False, ex)


def _quote_mark(c, x, y, size, color):
    """여는 큰따옴표(“) 두 개: 둥근 머리 + 위로 뻗는 꼬리."""
    r = size * 0.2
    for dx in (0, size * 0.55):
        cx, cy = x + dx + r, y + size - r
        c.d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=color)
        c.d.polygon([((cx - r * 0.95) * S, (cy - r * 0.2) * S), ((cx + r * 0.55) * S, (cy - r * 2.6) * S),
                     ((cx + r * 1.15) * S, (cy - r * 2.2) * S), ((cx + r * 0.3) * S, (cy - r * 0.55) * S)], fill=color)


def lab_review(c, spec, top, bottom):
    def b(k, y0, dry, ex):
        y = y0
        if spec.get("tag") and not dry:
            lab_pill(c, 96, y, spec["tag"], 28, outline=BLUE, color=BLUE, h=52)
        y += 52 + 40 * k + ex
        if not dry: _quote_mark(c, 96, y, 120 * k, ORANGE)
        y += 150 * k
        f, ls = _rows_text(c, spec.get("quote", ""), "extrabold", 60 * k, 888, -0.045)
        y = _lines(c, 96, y, ls[:6], f, 60 * k * 1.28, NAVY, -0.045) if not dry else y + len(ls[:6]) * 60 * k * 1.28
        y += 34 * k + ex
        if spec.get("meta"):
            if not dry: lab_dashed(c, 90, y, 990, y)
            y += 40 * k
            if not dry: mtext(c, 96, BL(y, 22 * k), "CASE NOTE", 22 * k, BLUE, 0.1)
            y += 36 * k
            fm, lm = _rows_text(c, spec["meta"], "bold", 34 * k, 888, 0)
            y = _lines(c, 96, y, lm[:3], fm, 48 * k, NAVY, 0) if not dry else y + len(lm[:3]) * 48 * k
            y += 34 * k + ex
        if not dry:
            r = 42; cy = y + r
            c.d.ellipse((96 * S, (cy - r) * S, (96 + 2 * r) * S, (cy + r) * S), fill=ICE)
            c.text(96 + r, cy, spec.get("initial", "고"), font("extrabold", 34), BLUE, "mm")
            c.text(200, cy - 6, spec.get("name", "고객님"), font("extrabold", 30), NAVY, "ls")
            c.text(200, cy + 30, "가전소 상담 고객", font("medium", 24), GRAY, "ls")
        y += 84
        return y - y0
    k, ex, h = _fit(b, top, bottom, rows=3, cap=50)
    b(k, top, False, ex)


def lab_deal(c, spec, top, bottom):
    x = 230; mw = 990 - 56 - x
    def b(k, y0, dry, ex):
        y = y0 + 52 * k + ex / 2
        if not dry and spec.get("tag"):
            lab_pill(c, x, y, spec["tag"], 28 * k, outline=ORANGE, color=(0xC9, 0x56, 0x1A), h=50 * k)
        y += 50 * k + 30 * k
        pct_r = 82 * k if spec.get("pct") else 0
        fp, lp = _rows_text(c, spec.get("product", ""), "extrabold", 52 * k, mw - (pct_r * 2 + 20 if pct_r else 0), -0.04)
        y = _lines(c, x, y, lp[:3], fp, 64 * k, NAVY, -0.04) if not dry else y + len(lp[:3]) * 64 * k
        y += 30 * k + ex
        if not dry: lab_dashed(c, x, y, 990 - 56, y)
        y += 36 * k + ex
        if spec.get("original"):
            if not dry: c.text(x, BL(y, 22 * k), "정가", font("bold", 22 * k), BLUE, "ls")
            y += 34 * k
            fo = font("semibold", 44 * k)
            if not dry:
                c.text(x, BL(y, 44 * k), spec["original"], fo, LGRAY, "ls")
                wv = c.text_w(spec["original"], fo); c.d.rectangle((x * S, (y + 26 * k) * S, (x + wv) * S, (y + 30 * k) * S), fill=LGRAY)
            y += 64 * k
        if not dry: c.text(x, BL(y, 22 * k), "특가", font("bold", 22 * k), (0xC9, 0x56, 0x1A), "ls")
        y += 34 * k
        px = 118 * k
        while px > 56 and ttext_w(c, spec.get("price", ""), font("extrabold", px), px, -0.04) > mw: px -= 4
        if not dry: ttext(c, x, BL(y, px), spec.get("price", ""), font("extrabold", px), px, ORANGE, -0.04)
        y += px * 1.1 + 44 * k + ex / 2
        if not dry and spec.get("pct"):
            cx, cy = 990 - 56 - pct_r, y0 + 52 * k + ex / 2 + pct_r
            c.d.ellipse(((cx - pct_r) * S, (cy - pct_r) * S, (cx + pct_r) * S, (cy + pct_r) * S), fill=ORANGE)
            ppx = 52 * k
            while ppx > 26 and mtext_w(c, spec["pct"], ppx, -0.02) > pct_r * 1.7: ppx -= 2
            mtext(c, cx, cy + ppx * 0.36, spec["pct"], ppx, NAVY, -0.02, "ms", "extrabold")
        return y - y0
    k, ex, h = _fit(b, top, bottom, rows=4, cap=44)
    lab_sheet(c, 90, top, 990, top + h, border=NAVY, width=4)
    lab_dashed(c, 200, top + 4, 200, top + h - 4, DASH, 3, 10, 8)
    c.d.ellipse((124 * S, (top + 56) * S, 168 * S, (top + 100) * S), fill=ORANGE, outline=NAVY, width=4 * S)
    b(k, top, False, ex)


def _medal(d_px):
    """원형 로고(캐릭터 얼굴 부분)."""
    lg = Image.open(LOGO).convert("RGB")
    w_, h_ = lg.size
    lg = lg.crop((int(w_ * 0.222), int(h_ * 0.1667), int(w_ * 0.778), int(h_ * 0.7222))).resize((d_px * S, d_px * S), Image.LANCZOS)
    m = Image.new("L", lg.size, 0); ImageDraw.Draw(m).ellipse((0, 0, lg.width - 1, lg.height - 1), fill=255)
    return lg, m


def lab_cta(c, spec, n, ctx):
    lab_grid(c)
    lab_plug(c, cy=108)
    snap = c.img.copy()
    x1, y1, x2, y2 = 110, 180, 970, 1080
    c.d.rounded_rectangle((x1 * S, y1 * S, x2 * S, y2 * S), radius=28 * S, fill=NAVY)
    ny = 780
    for nx in (x1, x2):  # 접수증 옆 홈
        r = 34; m = Image.new("L", c.img.size, 0)
        ImageDraw.Draw(m).ellipse(((nx - r) * S, (ny - r) * S, (nx + r) * S, (ny + r) * S), fill=255)
        c.img.paste(snap, (0, 0), m)
    mtext(c, x1 + 60, y1 + 80, "CONSULT TICKET", 24, NAVY_NOTE, 0.12)
    c.text(x2 - 60, y1 + 80, "가전소", font("bold", 26), ORANGE, "rs")
    q = spec.get("question", "").split("\n")
    lines, idx = [], []
    for px in (104, 96, 88, 80, 72, 64):
        f = font("extrabold", px); lines, idx = [], []
        for i, part in enumerate(q):
            for ln in lab_wrap(c, part, f, px, x2 - x1 - 112, -0.05):
                lines.append(ln); idx.append(i)
        if len(lines) * px * 1.08 <= ny - 60 - (y1 + 150):
            break
    yy = y1 + 150
    for ln, i in zip(lines, idx):
        ttext(c, x1 + 56, BL(yy, px), ln, f, px, ORANGE if (i == len(q) - 1 and len(q) > 1) else OFFWHITE, -0.05)
        yy += px * 1.08
    lab_dashed(c, x1 + 60, ny, x2 - 60, ny, (0x6A, 0x7C, 0x9A), 4, 12, 10)
    qr = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(QR_URL); qr.make(fit=True)
    qs = 170; qx, qy = x1 + 60, ny + 60
    c.d.rounded_rectangle((qx * S, qy * S, (qx + qs) * S, (qy + qs) * S), radius=14 * S, fill=WHITE)
    qi = qr.make_image(fill_color="black", back_color="white").convert("RGB").resize(((qs - 24) * S, (qs - 24) * S), Image.NEAREST)
    c.img.paste(qi, (int((qx + 12) * S), int((qy + 12) * S)))
    f2 = font("bold", 34); tx = qx + qs + 40
    dm = lab_wrap(c, spec.get("dm", ""), f2, 34, x2 - 60 - tx)[:3]
    yy = qy + (qs - len(dm) * 48 - 40) / 2
    for ln in dm:
        c.text(tx, BL(yy, 34), ln, f2, ICE, "ls"); yy += 48
    c.text(tx, BL(yy + 8, 22), "QR을 찍으면 상담 채팅으로 연결됩니다", font("medium", 22), NAVY_NOTE, "ls")
    lg, m = _medal(104)
    c.d.ellipse(((x1 - 3) * S, (1150 - 3) * S, (x1 + 107) * S, (1257) * S), fill=NAVY)
    c.img.paste(lg, (x1 * S, 1150 * S), m)
    c.text(x1 + 130, 1196, "가전소", font("extrabold", 28), NAVY, "ls")
    c.text(x1 + 130, 1232, "가전, 제대로 알고 사는 곳", font("medium", 22), GRAY, "ls")
    mtext(c, x2, 1232, f"{n:02d}/{ctx['total']:02d}", 26, LGRAY, 0.04, "rs")


def lab_product(c, spec, n, ctx):
    lab_grid(c); lab_consult(c)
    lab_file(c, [(f"PRODUCT · {n:02d}", False)])
    lab_plug(c)
    L = LAB[c.bg]; y = 170
    if spec.get("tag"):
        lab_pill(c, 96, y, spec["tag"], 26, outline=ORANGE, color=ORANGE, h=48); y += 48 + 30
    for px in (64, 58, 52, 46):
        f = font("extrabold", px); ls = lab_wrap(c, spec.get("title", ""), f, px, 450, -0.045)
        if len(ls) <= 3: break
    for ln in ls:
        ttext(c, 90, BL(y, px), ln, f, px, L["title"], -0.045); y += px * 1.12
    if spec.get("subtitle"):
        fs = font("medium", 28)
        for ln in lab_wrap(c, spec["subtitle"], fs, 28, 450)[:2]:
            c.text(96, BL(y + 10, 28), ln, fs, GRAY, "ls"); y += 40
    y += 40
    specs = spec.get("specs", [])[:4]
    if specs:
        rows = []
        for lab_, val in specs:
            fv, lv = _rows_text(c, val, "extrabold", 32, 390, -0.03); rows.append((lab_, fv, lv))
        h = sum(34 + len(lv) * 42 + 36 for _, _, lv in rows)
        lab_sheet(c, 90, y, 540, y + h)
        yy = y
        for i, (lab_, fv, lv) in enumerate(rows):
            if i: lab_dashed(c, 93, yy, 537, yy)
            yy += 22
            c.text(124, BL(yy, 22), lab_, font("bold", 22), BLUE, "ls"); yy += 34
            for ln in lv:
                ttext(c, 124, BL(yy, 32), ln, fv, 32, NAVY, -0.03); yy += 42
            yy += 14
        y += h + 30
    if spec.get("price"):
        if spec.get("original"):
            fo = font("semibold", 28); c.text(96, BL(y, 28), spec["original"], fo, LGRAY, "ls")
            c.d.rectangle((96 * S, (y + 16) * S, (96 + c.text_w(spec["original"], fo)) * S, (y + 19) * S), fill=LGRAY); y += 40
        px = 64
        while px > 40 and ttext_w(c, spec["price"], font("extrabold", px), px, -0.04) > 450: px -= 4
        ttext(c, 90, BL(y, px), spec["price"], font("extrabold", px), px, ORANGE, -0.04); y += px * 1.15
        if spec.get("price_note"):
            c.text(96, BL(y, 22), spec["price_note"], font("regular", 22), GRAY, "ls")
    if spec.get("image"):
        land = _is_landscape(spec["image"])
        lab_visual(c, spec["image"], (550, 600, 1010, 1110) if land else (570, 180, 1010, 1140),
                   full=_visual_kind(spec["image"]) is not None and not land)
    lab_footnote(c, spec.get("source") or spec.get("footnote"))
    if getattr(c, "illust", False) and not (spec.get("source") or spec.get("footnote")):
        lab_footnote(c, "※ 이해를 돕기 위한 일러스트입니다")
    lab_page(c, n, ctx["total"])


def lab_poster(c, spec, n, ctx):
    L = LAB[c.bg]; mode = spec.get("mode", "headline")
    first = n == 1
    lab_grid(c, clear=LOGO_BOX if first else None, crops=("tl", "bl", "br") if first else ("tl", "tr", "bl", "br"))
    lab_file(c, [("가전소 LAB · ", False), (f"FILE {ctx['run']}", True), (" · NOTICE", False)] if first else [(f"NOTICE · {n:02d}", False)])
    if not first:
        lab_plug(c); lab_consult(c)
    if mode == "headline":
        y = 200
        if spec.get("tag"):
            lab_pill(c, 96, y, spec["tag"], 30, fill=L["tag_fill"], color=L["tag_txt"], h=56); y += 56 + 30
        hl = spec.get("highlight", 1)
        lines = spec.get("headline", "").split("\n")[:3]
        px = 112
        while px > 64 and max(ttext_w(c, ln, font("extrabold", px), px, -0.05) for ln in lines) > (880 if not first else 700): px -= 4
        f = font("extrabold", px)
        for i, ln in enumerate(lines):
            if i == hl:
                w_ = ttext_w(c, ln, f, px, -0.05)
                c.d.rounded_rectangle((76 * S, (y - 4) * S, (90 + w_ + 20) * S, (y + px * 1.08) * S), radius=12 * S,
                                      fill=NAVY if c.bg != "navy" else ORANGE)
                ttext(c, 90, BL(y, px), ln, f, px, ORANGE if c.bg != "navy" else NAVY, -0.05)
            else:
                ttext(c, 90, BL(y, px), ln, f, px, L["title"], -0.05)
            y += px * 1.14
        if spec.get("subtitle"):
            c.text(96, BL(y + 16, 32), spec["subtitle"], font("bold", 32), L["sub"], "ls"); y += 70
        top_img = y + 30
        if spec.get("image"):
            lab_visual(c, spec["image"], (90, top_img, 620, 1150), full=False)
        if spec.get("burst_main"):
            cx, cy, r = (810, top_img + 230, 170) if spec.get("image") else (540, top_img + 250, 210)
            c.d.ellipse(((cx - r - 18) * S, (cy - r - 18) * S, (cx + r + 18) * S, (cy + r + 18) * S), outline=L["dim"], width=2 * S)
            c.d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=NAVY if c.bg != "navy" else ORANGE)
            main_c = OFFWHITE if c.bg != "navy" else NAVY
            if spec.get("burst_top"): c.text(cx, cy - r * 0.48, spec["burst_top"], font("bold", 30), ICE if c.bg != "navy" else NAVY, "mm")
            bp = 100
            while bp > 48 and ttext_w(c, spec["burst_main"], font("extrabold", bp), bp, -0.04) > r * 1.7: bp -= 4
            ttext(c, cx, cy + bp * 0.32, spec["burst_main"], font("extrabold", bp), bp, main_c, -0.04, anchor="ms")
            if spec.get("burst_sub"): c.text(cx, cy + r * 0.55, spec["burst_sub"], font("bold", 26), ICE if c.bg != "navy" else NAVY, "mm")
    else:  # benefits
        y = lab_title(c, spec.get("title", ""), 160) + 10
        if spec.get("subtitle"):
            c.text(96, BL(y + 10, 30), spec["subtitle"], font("semibold", 30), L["sub"], "ls"); y += 52
        y += 30
        items = spec.get("items", [])[:4]
        base = [40 + 48 + len(_rows_text(c, it[1], "medium", 26, 520 if (len(it) > 2 and it[2]) else 700)[1][:2]) * 36 + 30 for it in items]
        ex = max(0, min(60, (1130 - y - sum(base) - 22 * len(items)) / max(1, len(items))))
        for i, it in enumerate(items, 1):
            head, desc = it[0], it[1]; val = it[2] if len(it) > 2 else None
            fd, ld = _rows_text(c, desc, "medium", 26, 520 if val else 700)
            bh = base[i - 1] + ex
            lab_sheet(c, 90, y, 990, y + bh)
            cy = y + bh / 2
            c.d.ellipse((126 * S, (cy - 44) * S, 214 * S, (cy + 44) * S), fill=NAVY)
            mtext(c, 170, cy + 13, f"{i:02d}", 36, OFFWHITE, 0.02, "ms")
            ty = cy - (48 + len(ld[:2]) * 36 + 8) / 2  # 글자 덩어리를 상자 가운데에
            ttext(c, 250, BL(ty, 40), head, font("extrabold", 40), 40, NAVY, -0.03)
            yy = ty + 56
            for ln in ld[:2]:
                c.text(250, BL(yy, 26), ln, fd, GRAY, "ls"); yy += 36
            if val:
                vp = 54
                while vp > 30 and ttext_w(c, val, font("extrabold", vp), vp, -0.03) > 220: vp -= 2
                ttext(c, 950, cy + vp * 0.36, val, font("extrabold", vp), vp, ORANGE, -0.03, anchor="rs")
            y += bh + 22
    lab_footnote(c, spec.get("note"))
    lab_page(c, n, ctx["total"])


LAB_BODY = {"formula": lab_formula, "table": lab_table, "checklist": lab_checklist, "compare": lab_compare,
            "steps": lab_steps, "contact": lab_contact, "review": lab_review, "deal": lab_deal}


def render_lab_card(c, spec, n, ctx):
    kind = spec["type"]
    if n == 1 and kind in ("cover", "product_cover"):
        lab_cover(c, spec, ctx)
    elif kind == "cta":
        lab_cta(c, spec, n, ctx)
    elif kind == "product":
        lab_product(c, spec, n, ctx)
    elif kind == "poster":
        lab_poster(c, spec, n, ctx)
    elif kind in ("cover", "product_cover"):  # 2장 이후의 표지형 카드: 제목만 크게
        top = lab_header(c, {"title": spec.get("title", "")}, n, ctx, "cover")
        lab_page(c, n, ctx["total"])
    else:
        if kind == "deal":
            top = lab_header(c, {"title": spec.get("title") or "특가 정보"}, n, ctx, kind)
        elif kind == "review":
            lab_header(c, {}, n, ctx, kind, title=False); top = 180
        else:
            top = lab_header(c, spec, n, ctx, kind)
        LAB_BODY[kind](c, spec, top, 1130)
        lab_footnote(c, spec.get("footnote") or (spec.get("note") if kind == "deal" else None))
        lab_page(c, n, ctx["total"])


FULL = {"product_cover": full_product_cover, "product": full_product, "poster": full_poster}

BUILDERS = {"cover": b_cover, "formula": b_formula, "table": b_table, "checklist": b_checklist, "compare": b_compare,
            "steps": b_steps, "contact": b_contact, "review": b_review, "deal": b_deal, "cta": b_cta}
LEFT_ALIGNED = {"checklist", "review", "deal", "steps"}  # 문서 레이아웃: 목록·표·후기는 좌측 150px 시작


def render(deck, outdir):
    global USE_DISPLAY
    ensure_fonts()
    os.makedirs(outdir, exist_ok=True)
    cards = deck["cards"]
    assert 5 <= len(cards) <= 9, f"게시물은 7~9장(예전 덱은 5장)이어야 합니다: 지금 {len(cards)}장"
    assert cards[-1]["type"] == "cta", "마지막 장은 cta(상담 접수증)여야 합니다"
    cover_color = deck.get("cover_color", "navy")
    cover_style = deck.get("cover_style")
    USE_DISPLAY = (cover_style == "v2")
    lab = deck.get("design") == "lab"
    m = re.search(r"(\d{8})", os.path.basename(os.path.normpath(outdir)))
    ctx = {"run": str(deck.get("run") or (m.group(1) if m else "00000000"))[-4:], "total": len(cards)}
    for i, spec in enumerate(cards, 1):
        kind = spec["type"]
        if lab and not (kind == "cover" and spec.get("logo")):  # 연구소 리포트 디자인 (브랜드 소개 logo:true 표지만 기존 레이아웃)
            bg = spec.get("bg") or (cover_color if i == 1 else LAB_CONTENT_BG.get(kind, "white"))
            c = Card(bg if bg in LAB else "white")
            render_lab_card(c, spec, i, ctx)
            c.save(os.path.join(outdir, f"card{i}"))
            continue
        bg = spec.get("bg") or (cover_color if i == 1 else ("navy" if i == len(cards) else "white"))
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
        c.finish(i, cover_v2=v2, total=len(cards))
        c.save(os.path.join(outdir, f"card{i}"))
    return outdir


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--cutout":  # python3 gen_cards.py --cutout in.jpg out.png [tol: 18(기본)/40/60 — 그림자가 남으면 값을 올린다]
        r = cutout(sys.argv[2], sys.argv[3], tol=int(sys.argv[4]) if len(sys.argv) > 4 else 18); print("OK" if r is not None else "FAIL: 배경이 단색이 아니거나 제거 불가")
        sys.exit(0 if r is not None else 2)
    deck = json.load(open(sys.argv[1], encoding="utf-8"))
    print(render(deck, sys.argv[2]))
