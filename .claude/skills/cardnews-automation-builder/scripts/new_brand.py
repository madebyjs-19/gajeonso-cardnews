#!/usr/bin/env python3
"""가전소 카드뉴스 자동화를 새 브랜드용 저장소로 복제한다.

사용:
  python3 new_brand.py --config brand.json --out /path/new-repo [--source DIR] [--force]

--source 를 주지 않으면 ① 이 스킬의 assets/template/ ② 이 스크립트가 들어 있는 저장소(가전소 저장소) 순서로 원본을 찾는다.
원본 코드는 가전소 값(브랜드명·QR 주소·저장소 이름·색 등)을 그대로 담고 있으므로, 여기서 brand.json 값으로 바꿔 쓴다.
업종에 따라 고쳐야 하는 문장(주제 선정·출처·일러스트 종류 등)은 자동으로 바꾸지 않고 REBRAND_TODO.md 에 줄 번호로 남긴다.
"""
import argparse, colorsys, json, os, pathlib, re, shutil, sys

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent

# 원본에서 그대로 가져올 파일·폴더 (cards/, log/, plan/, 로고·QR·진행자 이미지 등 가전소 전용 자료는 가져오지 않는다)
INCLUDE = [
    "gen_cards.py", "approval_publish.py", "publish.py", "publish_reel.py", "make_reel.py", "reel_overlay.py",
    "collect_metrics.py", "topic_request.py", "ROUTINE_PROMPT.md", "CLAUDE.md", ".gitignore",
    ".github/workflows/publish-on-approval.yml", ".github/workflows/metrics.yml",
    ".github/workflows/meta-check.yml", ".github/workflows/topic-request.yml",
    "design/blueprints", "assets/blueprints", "docs/reel_host.md",
]
RENAME = {"log/reports/20261017.md": "docs/report_example.md"}  # 주간 리포트 형식 예시
TEXT_EXT = {".py", ".md", ".yml", ".yaml", ".sh", ".html", ".txt", ".json", ".gitignore", ".svg"}

# 가전소 기본 팔레트(코드 속 이름: navy, blue, ice, orange)
OLD = {"navy": "1A2A4A", "blue": "2E5EAA", "ice": "DCE8F5", "orange": "FF8A3D"}
# 기본색에서 파생된 보조색: 새 기본색에 맞춰 같은 관계(색상·명도·채도 차이)로 다시 계산한다
DERIVED = {
    "6E86AC": "navy", "8FA5C7": "navy", "B8C7DB": "navy",      # 페이지 번호·주석·점선
    "6B7688": "navy", "9AA6B2": "navy", "6A7C9A": "navy",      # 웜 그레이(부제·페이지 번호)·라이트 그레이·CTA 점선
    "24385F": "navy", "405278": "navy",                        # 네이비 표지 줄무늬·옛 디자인 보조
    "185FA5": "blue", "3A6CBA": "blue",                        # 아이스 배경 글씨·블루 줄무늬
    "EEF3FA": "ice", "EAF1FA": "ice", "F7F8FA": "ice",         # 표 줄무늬·오프화이트
    "C4D5EA": "ice", "A9C4E6": "ice", "8FB1DC": "ice",         # 옛 디자인 보조
    "C9561A": "orange", "FFE3C8": "orange", "FF9B5C": "orange",  # 특가 글씨·주황 배경 보조
}
OLD_TOKENS = ["가전소", "gajeonso", "GAJEONSO", "Gajeonso", "PHwrX", "1KT9JGteGYQLhsHnVDmcU2xAhqZLI-lKl", "家電所"]
DOMAIN_WORDS = (r"가전|하이마트|롯데|한전|KEPCO|kepco|삼성|LG|애플|아이폰|김장|에어컨|냉장고|세탁기|건조기|청소기|TV|정왕|"
                r"kWh|kW|누진|콘센트|드럼|통돌이|설치|소비전력|AS센터|AS |매장|평수|인치|전기요금|Appliance|appliance|navy crew|navy lanyard")
APPLIANCE = ("가전", "가전제품")


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgbhex(c):
    return "".join(f"{max(0, min(255, round(v))):02X}" for v in c)


def derive(old_derived, old_base, new_base):
    """old_derived 가 old_base 와 갖는 색상·명도·채도 관계를 new_base 에 그대로 옮긴다."""
    hd, ld, sd = colorsys.rgb_to_hls(*[v / 255 for v in hexrgb(old_derived)])
    hb, lb, sb = colorsys.rgb_to_hls(*[v / 255 for v in hexrgb(old_base)])
    hn, ln, sn = colorsys.rgb_to_hls(*[v / 255 for v in hexrgb(new_base)])
    h = (hd + hn - hb) % 1.0
    l = min(0.99, max(0.03, ld + (ln - lb)))
    s = min(1.0, sd * (sn / sb if sb else 1.0))
    return rgbhex([v * 255 for v in colorsys.hls_to_rgb(h, l, s)])


def color_map(palette):
    m = {}
    for k, old in OLD.items():
        new = palette.get(k, "#" + old).lstrip("#").upper()
        if not re.fullmatch(r"[0-9A-F]{6}", new):
            sys.exit(f"palette.{k} 값이 6자리 HEX 가 아닙니다: {palette.get(k)}")
        if new != old:
            m[old] = new
    for d, base in DERIVED.items():
        if base in {k for k, o in OLD.items() if o in m}:
            m[d] = derive(d, OLD[base], m[OLD[base]])
    return m


def apply_colors(text, cmap):
    for old, new in cmap.items():
        o, n = hexrgb(old), hexrgb(new)
        # (0x1A, 0x2A, 0x4A) 형태
        pat = r"\(\s*0x%02X\s*,\s*0x%02X\s*,\s*0x%02X\s*\)" % o
        text = re.sub(pat, "(0x%02X, 0x%02X, 0x%02X)" % n, text, flags=re.I)
        # #1A2A4A, 0x1A2A4A 형태
        text = re.sub(r"(#|0x)" + old + r"\b", lambda mo: mo.group(1) + new, text, flags=re.I)
    return text


def replacements(b):
    slug, en = b["brand_slug"], b["brand_name_en"]
    alt = b.get("brand_alt", "").strip()
    pairs = [
        ("madebyjs-19/gajeonso-cardnews", b["github_repo"]),
        ("1KT9JGteGYQLhsHnVDmcU2xAhqZLI-lKl", b.get("drive_folder_id", "")),
        ("http://pf.kakao.com/_PHwrX/chat", b["consult_url"]),
        ("kakao_qr.png", "consult_qr.png"),
        ("카카오톡", b.get("consult_channel", "카카오톡")),
        ("가전, 제대로 알고 사는 곳", b["tagline"]),
        ("gajeonso_logo.png", f"{slug}_logo.png"),
        ("GAJEONSO_FONT_DIR", f"{slug.upper()}_FONT_DIR"),
        ("log/reports/20261017.md", "docs/report_example.md"),
        ("가전소 브랜드 가이드(Ver 1.1)를 따른다.", "아래 디자인 규칙을 따른다."),       # 가전소 전용 PDF 가이드라 새 브랜드에는 없다
        ("가전소 카드뉴스 생성기 (브랜드 가이드 Ver 1.1 기준)", "가전소 카드뉴스 생성기"),
        ("--headless=new --disable-gpu", "--headless=new --no-sandbox --disable-gpu"),  # 리눅스·root 환경에서도 도면 렌더링
    ]
    pairs += [("家電所", alt)] if alt else [("(家電所, ", "("), ("家電所", b["brand_name"])]
    pairs += [("GAJEONSO", en.upper()), ("Gajeonso", en.title()), ("gajeonso", slug), ("가전소", b["brand_name"])]
    return pairs


def medal_line(text, crop):
    """CTA 원형 로고(_medal)가 로고의 어느 부분을 쓸지: 가전소 로고에 맞춘 고정 비율을 brand.json 값으로 바꾼다."""
    l, t, r, btm = crop
    return re.sub(r"lg\.crop\(\(int\(w_ \* [0-9.]+\), int\(h_ \* [0-9.]+\), int\(w_ \* [0-9.]+\), int\(h_ \* [0-9.]+\)\)\)",
                  f"lg.crop((int(w_ * {l}), int(h_ * {t}), int(w_ * {r}), int(h_ * {btm})))", text)


WEEKLY = [  # 새 저장소에는 리포트가 없으므로 첫 리포트 시점을 정해 준다
    ("ROUTINE_PROMPT.md", "로부터 7일 이상 지난 날(지금 주기로는 매주 토요일)]",
     "로부터 7일 이상 지난 날. 리포트가 아직 하나도 없으면 log/ig-card-news-log.md 의 첫 발행 성공일로부터 7일 이상 지난 날(그 전에는 쓰지 않는다)]"),
    ("CLAUDE.md", "가장 최근 `log/reports/` 리포트로부터 7일이 지난 날은",
     "가장 최근 `log/reports/` 리포트(없으면 첫 발행 성공일)로부터 7일이 지난 날은"),
]

STAMP_OLD = """        lw = round(base_logo.width * lh / base_logo.height)
"""
STAMP_NEW = """        lw = round(base_logo.width * lh / base_logo.height)
        max_w = 150 - (36 if dark else 0)  # 가로로 긴 로고도 오른쪽 위 로고 칸(x=820~1040) 안에 들어가게 줄인다
        if lw > max_w:
            lh, lw = round(lh * max_w / lw), max_w
"""


def find_source(arg):
    if arg:
        return pathlib.Path(arg).resolve()
    if (SKILL / "assets" / "template" / "gen_cards.py").exists():
        return SKILL / "assets" / "template"
    for p in [HERE, *HERE.parents]:
        if (p / "gen_cards.py").exists() and (p / "ROUTINE_PROMPT.md").exists():
            return p
    sys.exit("원본(가전소 저장소 또는 assets/template)을 찾지 못했습니다. --source 로 지정하세요.")


def prepare_logo(src, dst):
    """로고를 흰 배경 RGB PNG 로 정리한다(투명 PNG 를 그대로 쓰면 stamp_logo 가 배경까지 잉크로 읽는다)."""
    from PIL import Image
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    im = im.convert("RGB")
    w, h = im.size  # 정사각형 캔버스(여백 8%)로 맞춘다: 표지 로고·브랜드 소개 표지가 정사각형을 가정한다
    side = int(max(w, h) * 1.08)
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    canvas.paste(im, ((side - w) // 2, (side - h) // 2))
    if side < 700:
        canvas = canvas.resize((700, 700), Image.LANCZOS)
    canvas.save(dst)
    return dst


def symbol_box(logo_path):
    """로고의 심볼 영역(px). 심볼과 글자(워드마크) 사이에 빈 줄 띠가 있으면 위쪽 심볼만, 없으면 잉크 전체."""
    from PIL import Image
    im = Image.open(logo_path).convert("L")
    w, h = im.size
    ink = im.point(lambda v: 255 if v < 200 else 0)
    box = ink.getbbox() or (0, 0, w, h)
    rows = [ink.crop((0, y, w, y + 1)).getbbox() is not None for y in range(box[1], box[3])]
    segs, start = [], None
    for i, r in enumerate(rows + [False]):
        if r and start is None:
            start = i
        elif not r and start is not None:
            segs.append((start, i)); start = None
    total = box[3] - box[1]
    merged = [list(segs[0])] if segs else []
    for a, b in segs[1:]:  # 3% 미만의 작은 틈은 같은 덩어리로 본다
        if a - merged[-1][1] < total * 0.03:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    if len(merged) >= 2 and (merged[0][1] - merged[0][0]) >= total * 0.4:
        top, bottom = box[1] + merged[0][0], box[1] + merged[0][1]
        box = ink.crop((0, top, w, bottom)).getbbox()
        box = (box[0], top, box[2], bottom)
    return box, (w, h)


def auto_medal_crop(logo_path):
    """CTA 원형 로고 영역(비율): 심볼을 감싸는 정사각형 + 여백. 직접 정하려면 brand.json 의 logo_medal_crop."""
    box, (w, h) = symbol_box(logo_path)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    half = max(box[2] - box[0], box[3] - box[1]) / 2 * 1.3
    l, t, r, b = cx - half, cy - half, cx + half, cy + half
    return [round(max(0, l) / w, 4), round(max(0, t) / h, 4), round(min(w, r) / w, 4), round(min(h, b) / h, 4)]


def make_mark(logo_path, dst):
    """카드 오른쪽 위 작은 심볼(가전소의 콘센트 자리)용 마스크: 심볼 부분을 정사각형 L 이미지로(잉크=255)."""
    from PIL import Image
    box, _ = symbol_box(logo_path)
    im = Image.open(logo_path).convert("L").crop(box)
    side = max(im.size)
    sq = Image.new("L", (side, side), 255)
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    sq.point(lambda v: max(0, min(255, int((245 - v) * 255 / 185)))).resize((256, 256), Image.LANCZOS).save(dst)


PLUG_NEW = '''def lab_plug(c, cx=952, cy=114, size=76, color=None, dot=None):
    """브랜드 심볼(assets/brand_mark.png)을 한 색으로 찍는다(원본 디자인의 콘센트 심볼 자리)."""
    L = LAB[c.bg]; color = color or L["sym"]
    m = Image.open(os.path.join(HERE, "assets", "brand_mark.png")).convert("L")
    side = int(size * S); m = m.resize((side, side), Image.LANCZOS)
    c.img.paste(Image.new("RGB", m.size, color), (int((cx - size / 2) * S), int((cy - size / 2) * S)), m)


'''
GENERIC_NEW = '''D["generic"] = ("공통 (상자형 포장)", P, f"""
<rect class="m" x="90" y="600" width="240" height="300" rx="10"/>
<path class="m" d="M90 600L122 540H298L330 600"/>
<path class="d" d="M122 540L152 600M298 540L268 600"/>
<path class="dd" d="M210 600V900"/>
<rect class="d" x="130" y="700" width="160" height="90" rx="10"/>
<path class="d" d="M150 730H270M150 760H240"/>
<circle class="c" cx="210" cy="745" r="72"/>
<text class="tx" x="90" y="520">GENERIC</text>
{floor()}{vdim(540, 900, 50)}{hdim(90, 330)}
""")

'''


def render_blueprints(out):
    """도면 PNG 를 새 색·새 generic 으로 다시 그린다(크롬 필요). 성공하면 True."""
    import subprocess
    cands = [os.environ.get("CHROME"), "/opt/pw-browsers/chromium", shutil.which("google-chrome"), shutil.which("chromium"),
             shutil.which("chromium-browser"), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    ch = next((c for c in cands if c and os.path.exists(c)), None)
    if not ch:
        return False
    r = subprocess.run(["bash", "design/blueprints/render_png.sh"], cwd=out, env={**os.environ, "CHROME": ch},
                       capture_output=True, text=True, timeout=1800)
    return r.returncode == 0


def make_qr(url, dst):
    import qrcode
    q = qrcode.QRCode(border=2, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(url)
    q.make(fit=True)
    q.make_image(fill_color="black", back_color="white").convert("L").resize((310, 310)).save(dst)


def plan_skeleton(b):
    return f"""# {b['brand_name']} 콘텐츠 계획 — (시작일) ~ (종료일)

이 계획은 기본값이다. 매일 루틴은 오늘 날짜 행을 먼저 보고, 더 중요한 이슈가 있으면 이슈를 우선한다(판단 기준: ROUTINE_PROMPT.md step1 [주제 선정 순서]).
- **계획** 날: 특별한 이슈가 없으면 이 주제로 진행한다.
- **이슈** 날(화·금): 최근 48시간 안의 {b.get('domain', '업계')} 이슈를 고른다. 마땅한 이슈가 없으면 맨 아래 [예비 주제]에서 하나를 쓴다.
- 날짜·행사·수치는 계획일 뿐이다. 진행하는 날 1차 출처로 다시 확인하고, 확인 안 되면 쓰지 않는다.

## 주차별 테마
| 주 | 기간 | 테마 |
|---|---|---|

## 일정
| 날짜 | 구분 | 주제(가제) | 저장·공유할 이유 | 유형·표지(제안) | 결과 |
|---|---|---|---|---|---|

## 예비 주제 (이슈 날에 이슈가 없거나, 계획 주제의 사실 확인이 안 될 때)
-

## 다음 계획
- 계획이 7일 이하로 남은 주간 리포트 날 루틴이 다음 달 계획을 이 파일 아래에 이어 쓴다.
"""


def readme(b):
    return f"""# {b['brand_name']} 카드뉴스 자동화

매일 정해진 시각에 Claude 루틴이 주제 조사 → 카드 7~9장·캡션·릴스 프롬프트를 만들어 main 에 올리면,
GitHub Actions 가 텔레그램으로 승인 요청을 보내고 [발행]을 누르면 Instagram·Facebook 에 카드뉴스와 릴스를 올립니다.

## 구성
- `ROUTINE_PROMPT.md`, `CLAUDE.md`: 매일 루틴이 따르는 작업 규칙
- `gen_cards.py`: 카드 생성기(연구소 리포트 디자인), `{b['brand_slug']}_logo.png`: 대표 로고
- `approval_publish.py`, `publish.py`, `publish_reel.py`, `make_reel.py`, `reel_overlay.py`: 승인·발행·릴스
- `.github/workflows/`: 승인 후 발행, 지표 수집(매일 09:00), Meta 연결 점검(매일 09:30), 주제 요청

## GitHub Secrets (Settings → Secrets and variables → Actions)
| 이름 | 내용 |
|---|---|
| TELEGRAM_BOT_TOKEN | 텔레그램 봇 토큰 |
| TELEGRAM_CHAT_ID | 승인 메시지를 받을 대화방 ID |
| IG_ACCESS_TOKEN | 페이지 액세스 토큰(만료 없음, instagram_content_publish 권한) |
| IG_USER_ID | 인스타그램 비즈니스 계정 ID |
| FB_PAGE_ID | 페이스북 페이지 ID |
| FB_PAGE_ACCESS_TOKEN | 페이지 액세스 토큰(만료 없음) |
| GOOGLE_SERVICE_ACCOUNT_JSON | (선택) 드라이브에서 Flow 영상·BGM 을 찾을 서비스 계정 키 |

토큰을 바꾼 뒤에는 Actions → **Meta 연결 점검** 을 실행해 IG·FB 모두 "정상 … 유형 PAGE, 만료 없음" 인지 확인합니다.

## 주의
- Instagram 이 `raw.githubusercontent.com` 주소에서 카드·영상을 가져가므로 이 저장소는 **공개(public)** 여야 합니다.
- `deck.json`, `fonts/`, `out/`, `img/` 는 커밋하지 않습니다.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source")
    ap.add_argument("--force", action="store_true", help="out 폴더가 비어 있지 않아도 덮어쓴다")
    a = ap.parse_args()
    try:
        import PIL, qrcode  # noqa: F401
    except ImportError as e:
        sys.exit(f"필요한 패키지가 없습니다({e.name}). 먼저 실행: {sys.executable} -m pip install pillow numpy qrcode")

    b = json.load(open(a.config, encoding="utf-8"))
    need = ["brand_name", "brand_name_en", "brand_slug", "tagline", "consult_url", "github_repo", "logo_file"]
    miss = [k for k in need if not str(b.get(k, "")).strip()]
    if miss:
        sys.exit(f"brand.json 에 빠진 값: {', '.join(miss)}")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", b["brand_slug"]):
        sys.exit("brand_slug 는 영문 소문자·숫자·밑줄만 씁니다(예: beautyso)")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]*", b["brand_name_en"]):
        sys.exit("brand_name_en 은 영문으로 씁니다(예: BEAUTYSO)")
    cfg_dir = pathlib.Path(a.config).resolve().parent
    logo_src = (cfg_dir / b["logo_file"]).resolve() if not os.path.isabs(b["logo_file"]) else pathlib.Path(b["logo_file"])
    if not logo_src.exists():
        sys.exit(f"로고 파일이 없습니다: {logo_src}")

    src, out = find_source(a.source), pathlib.Path(a.out).resolve()
    if out.exists() and any(p.name != ".git" for p in out.iterdir()) and not a.force:
        sys.exit(f"{out} 가 비어 있지 않습니다. 새 폴더를 쓰거나 --force 를 붙이세요.")
    out.mkdir(parents=True, exist_ok=True)

    files = []
    for rel in INCLUDE:
        p = src / rel
        if p.is_dir():
            files += [q for q in p.rglob("*") if q.is_file() and "__pycache__" not in q.parts]
        elif p.exists():
            files.append(p)
        else:
            print(f"경고: 원본에 {rel} 이(가) 없어 건너뜁니다")
    for old_rel in RENAME:
        if (src / old_rel).exists():
            files.append(src / old_rel)

    pairs, cmap = replacements(b), color_map(b.get("palette", {}))
    appliance = b.get("domain", "가전") in APPLIANCE
    logo_dst = out / f"{b['brand_slug']}_logo.png"
    prepare_logo(logo_src, logo_dst)
    crop = b.get("logo_medal_crop") or auto_medal_crop(logo_dst)

    for f in files:
        rel = f.relative_to(src).as_posix()
        rel = RENAME.get(rel, rel)
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if f.suffix in TEXT_EXT or f.name in TEXT_EXT:
            text = f.read_text(encoding="utf-8")
            for old, new in pairs:
                text = text.replace(old, new)
            text = apply_colors(text, cmap)
            if rel == "gen_cards.py":
                text = medal_line(text, crop)
                if not appliance:  # 콘센트 심볼 → 브랜드 심볼
                    text, n = re.subn(r"def lab_plug\(.*?\n\n\n", lambda _: PLUG_NEW, text, count=1, flags=re.S)
                    if not n:
                        print("경고: gen_cards.py 의 lab_plug 를 찾지 못해 콘센트 심볼이 남습니다")
            if rel == "design/blueprints/build.py" and not appliance:  # 가전 모양 generic 도면 → 상자형 포장
                text, n = re.subn(r'D\["generic"\] = \(.*?"""\)\n\n', lambda _: GENERIC_NEW, text, count=1, flags=re.S)
                if not n:
                    print("경고: build.py 의 generic 도면을 찾지 못했습니다")
            for fname, old, new in WEEKLY:
                if rel == fname:
                    if old not in text:
                        print(f"경고: {fname} 의 주간 리포트 시작 조건 문장을 찾지 못했습니다")
                    text = text.replace(old, new)
            if rel == "ROUTINE_PROMPT.md":
                if STAMP_OLD not in text:
                    print("경고: ROUTINE_PROMPT.md 의 stamp_logo 코드 모양이 달라 가로 로고 보정을 넣지 못했습니다")
                text = text.replace(STAMP_OLD, STAMP_NEW, 1)
            if rel == "docs/report_example.md":
                text = "> 주간 성과 리포트 **형식 예시**입니다(다른 브랜드의 실제 수치). 형식만 참고하세요.\n\n" + text
            dst.write_text(text, encoding="utf-8")
            if os.access(f, os.X_OK):
                dst.chmod(0o755)
        else:
            shutil.copy2(f, dst)

    # 브랜드 자료와 빈 기록 폴더
    (out / "assets" / "reel").mkdir(parents=True, exist_ok=True)
    make_qr(b["consult_url"], out / "assets" / "reel" / "consult_qr.png")
    host_dir = out / "assets" / "reel_host"
    host_dir.mkdir(parents=True, exist_ok=True)
    if b.get("host_image"):
        hp = (cfg_dir / b["host_image"]).resolve()
        if hp.exists():
            shutil.copy2(hp, host_dir / ("host" + hp.suffix.lower()))
        else:
            print(f"경고: 진행자 이미지가 없습니다: {hp}")
    if not appliance:
        make_mark(logo_dst, out / "assets" / "brand_mark.png")
    rendered = None
    if cmap or not appliance:
        rendered = render_blueprints(out)
    for d in ["cards", "log/reports", "topic_request"]:
        (out / d).mkdir(parents=True, exist_ok=True)
        (out / d / ".gitkeep").touch()
    (out / "log" / "ig-card-news-log.md").write_text("# 인스타그램 카드뉴스 발행 로그\n\n날짜 | 주제 | 유형 | 표지색 | 장수·카드 유형 | 결과\n", encoding="utf-8")
    (out / "plan").mkdir(exist_ok=True)
    if not (out / "plan" / "content_plan.md").exists():
        (out / "plan" / "content_plan.md").write_text(plan_skeleton(b), encoding="utf-8")
    (out / "README.md").write_text(readme(b), encoding="utf-8")
    (out / "brand.json").write_text(json.dumps({**b, "logo_file": logo_dst.name, "logo_medal_crop": crop},
                                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 업종 문장 점검 목록: 자동으로 못 바꾸는 부분
    todo = []
    if b.get("domain", "가전") not in ("가전", "가전제품"):
        for name in ["ROUTINE_PROMPT.md", "CLAUDE.md"]:
            for i, ln in enumerate((out / name).read_text(encoding="utf-8").splitlines(), 1):
                if re.search(DOMAIN_WORDS, ln):
                    todo.append(f"- {name}:{i}  {ln.strip()[:140]}")
    left = []
    for p in out.rglob("*"):
        if p.is_file() and (p.suffix in TEXT_EXT) and ".git" not in p.parts and p.name not in ("brand.json", "REBRAND_TODO.md"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            hits = [tok for tok in OLD_TOKENS if tok in t]
            if hits:
                left.append(f"- {p.relative_to(out)}: {', '.join(hits)}")
    body = [f"# {b['brand_name']} 리브랜딩 남은 일", "",
            "자동 치환이 끝난 뒤 사람이(또는 Claude 가) 직접 고칠 부분입니다. 다 고치면 이 파일을 지웁니다.", ""]
    if left:
        body += ["## 남은 옛 브랜드 표기(반드시 0개)", *left, ""]
    if todo:
        body += [f"## 업종 문장 ({b.get('domain')} 에 맞게 다시 쓰기)", *todo, ""]
    if (cmap or not appliance) and not rendered:
        body += ["## 도면을 다시 그려야 합니다(크롬을 찾지 못함)", "- assets/blueprints/*.png 는 옛 색으로 그려져 있습니다. 도면을 쓰려면 "
                 "`CHROME=<크롬 실행 파일> bash design/blueprints/render_png.sh` 로 다시 그리세요"
                 "(예: CHROME=/opt/pw-browsers/chromium, macOS 는 기본값).", ""]
    (out / "REBRAND_TODO.md").write_text("\n".join(body) + "\n", encoding="utf-8")

    print(f"OK  {out}")
    print(f"    원본: {src}")
    print(f"    파일 {len(files)}개 복사, 색 변경 {len(cmap)}개, 원형 로고 영역 {crop}")
    if rendered is not None:
        print(f"    도면 다시 그리기: {'완료' if rendered else '실패/크롬 없음 → REBRAND_TODO.md 참고'}")
    print(f"    남은 옛 브랜드 표기 {len(left)}곳, 업종 문장 점검 {len(todo)}줄 → REBRAND_TODO.md")
    print(f"    다음: python3 {HERE / 'check_brand.py'} {out}")


if __name__ == "__main__":
    main()
