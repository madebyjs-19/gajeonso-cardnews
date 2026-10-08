#!/usr/bin/env python3
"""가전소 카드뉴스 생성기 (브랜드 가이드 Ver 1.0 기준)

사용법:
  python3 gen_cards.py deck.json OUTDIR
deck.json 형식은 DECK_SPEC.md 참고. 결과: OUTDIR/card1~5.png (1080x1350) + card1~5.jpg (Instagram 업로드용)
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
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

BG = {"navy": NAVY, "ice": ICE, "white": WHITE, "orange": ORANGE}
# 배경별 색 규칙: line(상하 라인), title, body, sub, accent(핵심 수치/강조), page, symbol(선), dot(점)
THEME = {
    "white":  dict(line=NAVY, title=NAVY, body=GRAY, sub=GRAY, accent=BLUE, page=LGRAY, sym=NAVY, dot=NAVY, label=GRAY, stripe=STRIPE, border=True),
    "navy":   dict(line=ICE, title=WHITE, body=ICE, sub=NAVY_NOTE, accent=ICE, page=NAVY_PAGE, sym=ICE, dot=ICE, label=ICE, stripe=(0x24, 0x38, 0x5F), border=False),
    "ice":    dict(line=BLUE, title=NAVY, body=NAVY, sub=BLUE, accent=BLUE, page=GRAY, sym=NAVY, dot=BLUE, label=BLUE, stripe=(0xEA, 0xF1, 0xFA), border=False),
    "orange": dict(line=OFFWHITE, title=WHITE, body=WHITE, sub=(0xFF, 0xE3, 0xC8), accent=NAVY, page=(0xFF, 0xE3, 0xC8), sym=OFFWHITE, dot=NAVY, label=(0xFF, 0xE3, 0xC8), stripe=(0xFF, 0x9B, 0x5C), border=False),
}


FONT_URL = "https://raw.githubusercontent.com/orioncactus/pretendard/main/packages/pretendard/dist/public/static/"


def ensure_fonts():
    """폰트 파일이 없으면 Pretendard(OFL)를 내려받는다."""
    import urllib.request
    os.makedirs(FONT_DIR, exist_ok=True)
    for n in ("Pretendard-Regular.otf", "Pretendard-SemiBold.otf", "Pretendard-Bold.otf"):
        p = os.path.join(FONT_DIR, n)
        if not os.path.exists(p) or os.path.getsize(p) < 100000:
            urllib.request.urlretrieve(FONT_URL + n, p)


def font(weight, px):
    name = {"regular": "Pretendard-Regular.otf", "semibold": "Pretendard-SemiBold.otf", "bold": "Pretendard-Bold.otf"}[weight]
    return ImageFont.truetype(os.path.join(FONT_DIR, name), int(px * S))


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

    def finish(self, n):
        self.frame(); self.symbol(); self.page_no(n); self.qr_badge()

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


BUILDERS = {"cover": b_cover, "formula": b_formula, "table": b_table, "checklist": b_checklist, "compare": b_compare,
            "steps": b_steps, "contact": b_contact, "review": b_review, "deal": b_deal, "cta": b_cta}
LEFT_ALIGNED = {"checklist", "review", "deal", "steps"}  # 문서 레이아웃: 목록·표·후기는 좌측 150px 시작


def render(deck, outdir):
    ensure_fonts()
    os.makedirs(outdir, exist_ok=True)
    cards = deck["cards"]
    assert len(cards) == 5, "게시물은 항상 5장"
    cover_color = deck.get("cover_color", "navy")
    for i, spec in enumerate(cards, 1):
        kind = spec["type"]
        bg = cover_color if i == 1 else ("navy" if i == 5 else spec.get("bg", "white"))
        c = Card(bg)
        build = BUILDERS[kind](spec)
        layout_center(c, build, center=spec.get("center", 690))
        c.finish(i)
        c.save(os.path.join(outdir, f"card{i}"))
    return outdir


if __name__ == "__main__":
    deck = json.load(open(sys.argv[1], encoding="utf-8"))
    print(render(deck, sys.argv[2]))
