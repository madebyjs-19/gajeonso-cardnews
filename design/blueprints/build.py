"""가전소 연구소 리포트 스타일 - 제품별 도면 세트 생성기.

python3 design/blueprints/build.py 를 실행하면
  - design/blueprints/catalog.html : 전체 도면 카탈로그 (배경 4종 전환, 클릭하면 크게 보기)
  - design/blueprints/svg/<kind>.svg : 제품별 단독 SVG (네이비 배경용 색)
  - design/blueprints/export.html : PNG 내보내기용 페이지 (render_png.sh 가 사용)
을 만든다. 도면을 고친 뒤에는 render_png.sh 로 assets/blueprints/*.png 를 다시 만든다(gen_cards.py 가 사용).

규칙
  - 세로형 도면은 440×960, 가로형은 900×360 크기에 실제 크기 그대로 그린다 (확대·축소하지 않으므로 선 굵기가 항상 같다).
  - 세로형 제품은 바닥선(y=900) 위에 세운다. 아래 y=945 에 폭 치수선, 왼쪽에 높이 치수선.
  - 선 종류: m 외곽 4px / d 세부 2.5px 반투명 / dd 세부 점선 / a 강조(오렌지) / c 강조 점선 원 / dm 치수선
  - 강조(오렌지)는 제품마다 한 곳에만 쓴다.
"""
import pathlib

HERE = pathlib.Path(__file__).parent

STYLE = """
.m{fill:none;stroke:var(--line);stroke-width:4;stroke-linecap:round;stroke-linejoin:round}
.d{fill:none;stroke:var(--line);stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;opacity:.55}
.dd{fill:none;stroke:var(--line);stroke-width:2.5;stroke-linecap:round;stroke-dasharray:8 8;opacity:.6}
.dot{fill:none;stroke:var(--line);stroke-width:4;stroke-linecap:round;stroke-dasharray:0 14;opacity:.55}
.a{fill:none;stroke:var(--acc);stroke-width:4;stroke-linecap:round;stroke-linejoin:round}
.af{fill:var(--acc);stroke:none}
.c{fill:none;stroke:var(--acc);stroke-width:3;stroke-dasharray:10 10;stroke-linecap:round}
.dm{fill:none;stroke:var(--dimc);stroke-width:2;stroke-linecap:round}
text{font-family:"IBM Plex Mono","Pretendard Variable",monospace;font-size:21px;font-weight:600;letter-spacing:.06em}
.lb{fill:var(--acc)} .tx{fill:var(--dimc)}
"""
NAVY_VARS = "--line:#DCE8F5;--dimc:#8FA5C7;--acc:#FF8A3D"


# ---------- 공통 도구 ----------
def floor(x1=20, x2=420, y=900):
    hatch = "".join(f"M{x} {y}l-10 12" for x in range(x1 + 20, x2 + 1, 28))
    return f'<path class="dm" d="M{x1} {y}H{x2}{hatch}"/>'

def hdim(x1, x2, y=945, cls="dm"):
    return f'<path class="{cls}" d="M{x1} {y}H{x2}M{x1} {y-10}v20M{x2} {y-10}v20"/>'

def vdim(y1, y2, x, cls="dm"):
    return f'<path class="{cls}" d="M{x} {y1}V{y2}M{x-10} {y1}h20M{x-10} {y2}h20"/>'

def callout(cx, cy, r, leader, tx, ty, label, anchor="end"):
    return (f'<circle class="c" cx="{cx}" cy="{cy}" r="{r}"/>'
            f'<path class="a" style="stroke-width:3" d="{leader}"/>'
            f'<text class="lb" x="{tx}" y="{ty}" text-anchor="{anchor}">{label}</text>')

def lines(x1, x2, y1, y2, step, cls="d"):
    return f'<path class="{cls}" d="' + "".join(f"M{x1} {y}H{x2}" for y in range(y1, y2 + 1, step)) + '"/>'


# ---------- 제품별 도면 ----------
P, L = "portrait", "landscape"
D = {}

D["stick_vacuum"] = ("무선청소기", P, f"""
<rect class="m" x="160" y="60" width="120" height="150" rx="40"/>
<rect class="d" x="190" y="90" width="60" height="80" rx="22"/>
<rect class="d" x="206" y="176" width="28" height="14" rx="5"/>
<rect class="m" x="140" y="200" width="160" height="270" rx="44"/>
<rect class="d" x="165" y="225" width="110" height="140" rx="18"/>
<ellipse class="d" cx="220" cy="255" rx="40" ry="8"/>
{lines(180, 260, 300, 330, 30)}
<rect class="a" x="165" y="385" width="110" height="62" rx="14"/>
<path class="a" style="stroke-width:3" d="M195 400v32M220 400v32M245 400v32"/>
<path class="m" d="M196 470v40h48v-40"/>
<rect class="m" x="190" y="510" width="60" height="26" rx="8"/>
<path class="m" d="M208 536V826M232 536V826"/>
<rect class="d" x="200" y="672" width="40" height="16" rx="6"/>
<circle class="m" cx="220" cy="836" r="16"/>
<rect class="m" x="70" y="850" width="300" height="50" rx="24"/>
<rect class="d" x="95" y="866" width="250" height="20" rx="10"/>
<path class="d" d="{''.join(f'M{x} 866l12 20' for x in range(110, 331, 30))}"/>
{callout(220, 416, 78, "M275 361L330 300H430", 430, 288, "BATTERY")}
{floor()}{vdim(60, 900, 40)}{hdim(70, 370)}
""")

D["robot_vacuum"] = ("로봇청소기", L, f"""
<text class="tx" x="60" y="24">TOP VIEW</text>
<circle class="m" cx="200" cy="180" r="140"/>
<circle class="d" cx="200" cy="180" r="112"/>
<path class="d" d="M89 116A128 128 0 0 1 311 116"/>
<circle class="m" cx="200" cy="120" r="30"/><circle class="d" cx="200" cy="120" r="14"/>
<rect class="d" x="150" y="210" width="100" height="60" rx="14"/>
<path class="a" d="M95 262L58 248M95 262L84 300M95 262L122 296"/><circle class="af" cx="95" cy="262" r="6"/>
{callout(200, 120, 52, "M237 83L270 50H400", 410, 57, "SENSOR", "start")}
{hdim(60, 340, 344)}
<text class="tx" x="480" y="150">SIDE VIEW</text>
<rect class="m" x="480" y="200" width="330" height="80" rx="30"/>
<rect class="m" x="610" y="172" width="70" height="28" rx="8"/>
<circle class="d" cx="570" cy="280" r="22"/>
<path class="d" d="M800 215V265"/>
{floor(460, 840, 302)}{vdim(172, 302, 870)}
""")

D["fridge"] = ("냉장고 (4도어)", P, f"""
<rect class="m" x="80" y="250" width="320" height="640" rx="22"/>
<path class="m" d="M240 250V890M80 610H400M110 890v10M370 890v10"/>
<path class="d" d="M228 300V430M252 300V430M110 632H210M270 632H370M110 870H370"/>
<rect class="d" x="108" y="290" width="56" height="34" rx="6"/>
{floor()}{vdim(250, 900, 44)}
{hdim(80, 400, 948, "a")}
<text class="lb" x="240" y="936" text-anchor="middle">W · 설치 폭</text>
""")

D["kimchi_fridge"] = ("김치냉장고 (스탠드)", P, f"""
<rect class="m" x="60" y="300" width="260" height="590" rx="20"/>
<path class="m" d="M190 300V560M60 560H320M60 725H320M86 890v10M294 890v10"/>
<path class="d" d="M178 340V460M202 340V460M120 582H260M120 747H260"/>
<rect class="d" x="82" y="330" width="52" height="30" rx="6"/>
{callout(190, 642, 92, "M255 577L330 520H436", 436, 508, "DRAWER")}
{floor()}{vdim(300, 900, 30)}{hdim(60, 320)}
""")

def _front_loader(extra):
    return f"""
<rect class="m" x="30" y="400" width="320" height="490" rx="24"/>
<path class="m" d="M30 480H350M56 890v10M324 890v10"/>
<circle class="m" cx="310" cy="440" r="20"/>
<circle class="m" cx="190" cy="680" r="130"/>
<rect class="m" x="306" y="650" width="14" height="60" rx="6"/>
{extra}
{floor()}{vdim(400, 900, 12)}{hdim(30, 350)}
"""

D["washer_drum"] = ("드럼세탁기", P, _front_loader(f"""
<rect class="d" x="52" y="414" width="92" height="46" rx="6"/>
<rect class="d" x="166" y="424" width="100" height="26" rx="5"/>
<circle class="d" cx="190" cy="680" r="100"/><circle class="d" cx="190" cy="680" r="70"/>
<path class="d" d="M150 640l20 10M215 700l20 10M200 630l-8 20"/>
<rect class="d" x="52" y="842" width="60" height="30" rx="6"/>
{callout(190, 680, 160, "M303 567L370 520H436", 436, 508, "DRUM")}
"""))

D["dryer"] = ("건조기", P, _front_loader(f"""
<rect class="d" x="52" y="414" width="120" height="46" rx="6"/>
<rect class="d" x="196" y="424" width="80" height="26" rx="5"/>
<circle class="d" cx="190" cy="680" r="104"/>
<path class="d" d="M130 640q60-30 120 0M130 680q60-30 120 0M130 720q60-30 120 0"/>
<rect class="a" x="150" y="752" width="80" height="18" rx="6"/>
{callout(190, 761, 50, "M240 761H436", 436, 750, "FILTER")}
"""))

D["washer_top"] = ("통돌이 세탁기", P, f"""
<rect class="dd" x="70" y="165" width="240" height="220" rx="16"/>
<rect class="m" x="30" y="385" width="320" height="55" rx="12"/>
<rect class="d" x="140" y="398" width="100" height="26" rx="5"/><circle class="d" cx="310" cy="412" r="14"/>
<rect class="m" x="30" y="440" width="320" height="450" rx="18"/>
<path class="m" d="M56 890v10M324 890v10"/>
<path class="d" d="M30 850H350M70 470H310"/>
<path class="a" d="M335 445C420 380 420 220 330 165M330 165l20 -2M330 165l8 18"/>
<text class="lb" x="436" y="136" text-anchor="end">TOP-LOAD</text>
{floor()}{vdim(385, 900, 12)}{hdim(30, 350)}
""")

D["tv"] = ("TV", L, f"""
<rect class="m" x="190" y="14" width="520" height="292" rx="10"/>
<rect class="d" x="202" y="26" width="496" height="268" rx="4"/>
<path class="m" d="M430 306v16h40v-16"/>
<rect class="m" x="350" y="322" width="200" height="14" rx="7"/>
<path class="c" d="M212 286L688 34"/>
<text class="lb" x="726" y="44">DIAGONAL</text>
<text class="lb" x="726" y="70">= 인치</text>
{floor(100, 800, 340)}{vdim(14, 306, 160)}
""")

D["aircon"] = ("벽걸이 에어컨", L, f"""
<path class="dm" d="M100 20H800{''.join(f'M{x} 20l-10 -12' for x in range(120, 801, 28))}"/>
<rect class="m" x="120" y="40" width="660" height="160" rx="44"/>
<path class="d" d="M140 150H760"/>
<rect class="m" x="170" y="168" width="560" height="20" rx="10"/>
<rect class="d" x="640" y="80" width="80" height="22" rx="5"/>
<path class="c" d="M200 214q30 40 0 90M330 214q30 40 0 90M460 214q30 40 0 90M590 214q30 40 0 90"/>
<text class="lb" x="800" y="270">AIRFLOW</text>
{hdim(120, 780, 340)}
""")

D["stand_aircon"] = ("스탠드 에어컨", P, f"""
<rect class="m" x="150" y="110" width="150" height="770" rx="46"/>
<rect class="m" x="140" y="880" width="170" height="20" rx="8"/>
<rect class="d" x="172" y="150" width="106" height="300" rx="30"/>
{lines(190, 260, 190, 410, 30)}
<circle class="d" cx="225" cy="500" r="16"/>
<rect class="d" x="176" y="560" width="98" height="280" rx="20"/>
{lines(196, 254, 590, 810, 30, "dot")}
{callout(225, 300, 110, "M303 222L350 170H436", 436, 158, "AIRFLOW")}
{floor()}{vdim(110, 900, 110)}{hdim(150, 300)}
""")

D["air_purifier"] = ("공기청정기", P, f"""
<rect class="m" x="70" y="300" width="190" height="590" rx="44"/>
{lines(95, 235, 330, 384, 18)}
<circle class="m" cx="165" cy="430" r="30"/><circle class="d" cx="165" cy="430" r="16"/>
<rect class="d" x="95" y="500" width="140" height="360" rx="22"/>
{lines(115, 215, 530, 830, 28, "dot")}
<path class="dm" d="M262 680H290"/>
<rect class="d" x="296" y="500" width="24" height="360" rx="8"/>
<rect class="a" x="330" y="500" width="24" height="360" rx="8"/>
<rect class="d" x="364" y="500" width="24" height="360" rx="8"/>
<text class="lb" x="430" y="478" text-anchor="end">FILTER</text>
{floor()}{vdim(300, 900, 40)}{hdim(70, 260)}
""")

D["microwave"] = ("전자레인지", L, f"""
<rect class="m" x="150" y="70" width="600" height="262" rx="18"/>
<path class="m" d="M590 70V332M190 332v8M710 332v8"/>
<rect class="m" x="180" y="100" width="380" height="200" rx="10"/>
<rect class="d" x="196" y="116" width="348" height="168" rx="6"/>
<rect class="d" x="615" y="100" width="110" height="34" rx="6"/>
<circle class="m" cx="670" cy="200" r="34"/><circle class="d" cx="670" cy="200" r="8"/>
<rect class="d" x="625" y="270" width="90" height="26" rx="8"/>
<ellipse class="c" cx="370" cy="262" rx="140" ry="18"/>
<path class="a" style="stroke-width:3" d="M230 262H148"/>
<text class="lb" x="140" y="270" text-anchor="end">CAPACITY</text>
{floor(100, 800, 340)}{vdim(70, 332, 790)}
""")

D["dishwasher"] = ("식기세척기", P, f"""
<text class="tx" x="95" y="140">UPPER</text>
<rect class="dd" x="95" y="150" width="250" height="80" rx="10"/>
{''.join(f'<rect class="d" x="{x}" y="166" width="30" height="48" rx="6"/>' for x in (115, 160, 205, 250, 295))}
<text class="tx" x="95" y="280">LOWER</text>
<rect class="dd" x="95" y="290" width="250" height="110" rx="10"/>
<path class="a" d="{''.join(f'M{x} 306V384' for x in range(130, 321, 30))}"/>
<text class="lb" x="436" y="140" text-anchor="end">RACK ×2</text>
<path class="dm" d="M220 410V438M212 428l8 10 8-10"/>
<rect class="m" x="70" y="450" width="300" height="440" rx="16"/>
<path class="m" d="M70 510H370"/>
<rect class="d" x="250" y="468" width="90" height="26" rx="5"/>
<rect class="m" x="150" y="530" width="140" height="16" rx="8"/>
<rect class="d" x="92" y="570" width="256" height="270" rx="10"/>
<path class="d" d="M70 860H370"/>
{floor()}{vdim(450, 900, 40)}{hdim(70, 370)}
""")

D["styler"] = ("의류관리기", P, f"""
<text class="lb" x="220" y="110" text-anchor="middle">HANGER</text>
<rect class="m" x="110" y="130" width="220" height="760" rx="16"/>
<path class="m" d="M130 890v10M310 890v10"/>
<rect class="d" x="128" y="148" width="184" height="690" rx="10"/>
<path class="dd" d="M160 300L130 360L160 375L165 560H275L280 375L310 360L280 300"/>
<path class="a" d="M220 250v-18a12 12 0 1 1 12-12M160 300L220 250L280 300ZM146 252q-12 12 0 24M294 252q12 12 0 24"/>
<rect class="d" x="190" y="852" width="60" height="18" rx="5"/>
{floor()}{vdim(130, 900, 80)}{hdim(110, 330)}
""")

D["water_purifier"] = ("정수기", P, f"""
<rect class="m" x="110" y="300" width="200" height="590" rx="30"/>
<path class="m" d="M136 890v10M284 890v10"/>
<rect class="d" x="160" y="336" width="100" height="40" rx="8"/>
{''.join(f'<circle class="d" cx="{x}" cy="420" r="12"/>' for x in (170, 210, 250))}
<rect class="m" x="140" y="500" width="140" height="290" rx="18"/>
<rect class="m" x="198" y="500" width="24" height="22" rx="6"/>
<path class="c" d="M210 530V620"/>
<path class="af" d="M210 630q-12 18 0 28q12-10 0-28"/>
<path class="dd" d="M172 670L178 760H242L248 670"/>
{lines(160, 260, 772, 772, 10)}
<path class="dm" d="M312 520H334"/>
<rect class="d" x="340" y="400" width="22" height="240" rx="11"/>
<rect class="a" x="372" y="400" width="22" height="240" rx="11"/>
<rect class="d" x="404" y="400" width="22" height="240" rx="11"/>
<text class="lb" x="430" y="378" text-anchor="end">FILTER</text>
{floor()}{vdim(300, 900, 70)}{hdim(110, 310)}
""")

D["induction"] = ("인덕션", L, f"""
<text class="tx" x="200" y="22">TOP VIEW</text>
<rect class="m" x="200" y="30" width="500" height="290" rx="22"/>
<circle class="m" cx="330" cy="160" r="85"/><circle class="d" cx="330" cy="160" r="60"/><circle class="d" cx="330" cy="160" r="35"/>
<circle class="m" cx="570" cy="110" r="52"/><circle class="d" cx="570" cy="110" r="30"/>
<circle class="m" cx="570" cy="235" r="58"/><circle class="d" cx="570" cy="235" r="34"/>
<path class="d" d="M220 282H680"/>
{''.join(f'<circle class="d" cx="{x}" cy="301" r="7"/>' for x in range(300, 601, 60))}
{callout(330, 160, 110, "M252 82L222 56H195", 190, 63, "ZONE")}
{hdim(200, 700, 345)}{vdim(30, 320, 730)}
""")

D["generic"] = ("기타 가전 (공통)", P, f"""
<rect class="m" x="90" y="520" width="240" height="370" rx="32"/>
<rect class="d" x="120" y="560" width="180" height="120" rx="14"/>
<circle class="d" cx="210" cy="770" r="40"/>
<path class="m" d="M114 890v10M306 890v10"/>
<path class="a" d="M330 790C356 790 352 862 366 862"/>
<g transform="translate(352 820) scale(1.6)"><path class="a" style="stroke-width:2.5" d="M18 4v11M30 4v11"/><rect class="a" style="stroke-width:2.5" x="8" y="15" width="32" height="27" rx="8"/><circle class="af" cx="24" cy="28.5" r="4.6"/></g>
<text class="tx" x="90" y="500">GENERIC</text>
{floor()}{vdim(520, 900, 50)}{hdim(90, 330)}
""")

ORDER = ["stick_vacuum", "robot_vacuum", "fridge", "kimchi_fridge", "washer_drum", "washer_top", "dryer", "tv",
         "aircon", "stand_aircon", "air_purifier", "microwave", "dishwasher", "styler", "water_purifier", "induction", "generic"]
NEW = {"stand_aircon", "styler", "water_purifier", "induction"}


def svg(kind, standalone=False):
    _, o, body = D[kind]
    w, h = (440, 960) if o == P else (900, 360)
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="bp {o}" data-kind="{kind}">'
    if standalone:
        head += f"<style>svg{{{NAVY_VARS}}}{STYLE}</style>"
    return head + body.strip() + "</svg>"


def build():
    out = HERE / "svg"; out.mkdir(exist_ok=True)
    for k in ORDER:
        (out / f"{k}.svg").write_text(svg(k, standalone=True))
    tiles = "\n".join(
        f'<figure class="tile {D[k][1]}" data-i="{i}"><div class="pad">{svg(k)}</div>'
        f'<figcaption><b>{D[k][0]}</b><span>{k}{" · 새로 추가" if k in NEW else ""}</span></figcaption></figure>'
        for i, k in enumerate(ORDER))
    tpl = (HERE / "template.html").read_text()
    html = tpl.replace("/*STYLE*/", STYLE).replace("<!--TILES-->", tiles) \
              .replace("<!--FRIDGE-->", svg("fridge")).replace("<!--TV-->", svg("tv"))
    (HERE / "catalog.html").write_text(html)
    # PNG 내보내기용: 배경 없이 도면 하나만, #kind=..&t=dark|light|orange
    themes = {"dark": "--line:#DCE8F5;--dimc:#8FA5C7;--acc:#FF8A3D",
              "light": "--line:#1A2A4A;--dimc:#2E5EAA;--acc:#FF8A3D",
              "orange": "--line:#1A2A4A;--dimc:#1A2A4A;--acc:#FDFEFE"}
    exp = tpl.split("<style>")[0] + "<style>html,body{margin:0;background:transparent}svg{display:block}" + STYLE \
        + "".join(f".t-{k}{{{v}}}" for k, v in themes.items()) + "</style></head><body>" \
        + "".join(f'<template id="{k}">{svg(k)}</template>' for k in ORDER) \
        + "<script>const h=new URLSearchParams(location.hash.slice(1));const s=document.getElementById(h.get('kind')).content.cloneNode(true);"\
          "document.body.className='t-'+(h.get('t')||'dark');document.body.append(s);</script></body></html>"
    (HERE / "export.html").write_text(exp)
    print("ok", len(ORDER), "kinds")


if __name__ == "__main__":
    build()
