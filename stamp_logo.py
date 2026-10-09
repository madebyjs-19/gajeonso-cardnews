# stamp_logo.py  사용: python3 stamp_logo.py out/YYYYMMDD/card1.png [--force]
# 1장 표지에 대표 로고(gajeonso_logo.png)를 합성한다.
# - 항상 네이비 라인 로고만 쓴다(흰색 반전 로고 금지: 얼굴이 음화처럼 보임).
# - 어두운 배경(navy·blue)에서는 아이스블루 둥근 배지 위에 올린다.
import os
import sys
import numpy as np
from PIL import Image, ImageDraw

NAVY, ICE = (0x1A, 0x2A, 0x4A), (0xDC, 0xE8, 0xF5)
LOGO_SRC = os.environ.get("LOGO_SRC", os.path.join(os.path.dirname(__file__), "gajeonso_logo.png"))

def logo_navy(src=LOGO_SRC, pad=6):
    a = np.asarray(Image.open(src).convert("L")).astype(float)
    alpha = np.clip((245 - a) / (245 - 60), 0, 1)          # 흰 배경=0, 네이비 선=1
    alpha[alpha < 0.06] = 0
    ys, xs = np.where(alpha > 0.05)
    if not len(xs):
        raise ValueError("Logo source has no visible lines")
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0),
           min(xs.max() + pad + 1, a.shape[1]), min(ys.max() + pad + 1, a.shape[0]))
    rgba = np.zeros((*a.shape, 4), np.uint8)
    rgba[..., :3] = NAVY
    rgba[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA").crop(box)

def with_badge(logo, dark):
    """어두운 배경이면 아이스블루 둥근 배지를 깔아 돌려준다. 밝은 배경이면 그대로."""
    if not dark:
        return logo
    p = 18
    badge = Image.new("RGBA", (logo.width + 2 * p, logo.height + 2 * p), (0, 0, 0, 0))
    ImageDraw.Draw(badge).rounded_rectangle(
        [0, 0, badge.width - 1, badge.height - 1], radius=34, fill=ICE + (255,))
    badge.alpha_composite(logo, (p, p))
    return badge

def stamp(card_path, force=False):
    card = Image.open(card_path).convert("RGB")
    W, H = card.size
    if (W, H) != (1080, 1350):
        raise ValueError("Expected 1080x1350 cover")
    arr = np.asarray(card).astype(int)
    bg = arr[24, W // 2]                                      # 상단 중앙(테두리 바깥)의 배경색
    dark = (0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) < 128
    base_logo = logo_navy()
    heights = (130,) if force else (175, 150, 130)            # 로고 높이(px), 폭은 비율대로
    for lh in heights:
        lw = round(base_logo.width * lh / base_logo.height)
        logo = with_badge(base_logo.resize((lw, lh), Image.LANCZOS), dark)
        w, h = logo.size
        spots = {"bottom-center": ((W - w) // 2, H - 70 - h),  # 1순위: 하단 중앙
                 "top-center": ((W - w) // 2, 44)}             # 2순위: 상단 중앙
        for name, (x, y) in spots.items():
            if force and name != "bottom-center":
                continue
            if x < 16 or y < 16 or x + w + 16 > W or y + h + 16 > H:
                continue
            x0, y0, x1, y1 = max(x - 16, 0), max(y - 16, 0), x + w + 16, y + h + 16
            region = arr[y0:y1, x0:x1]
            diff = np.abs(region - bg).sum(axis=2) > 40
            if force or diff.mean() < 0.004:                   # 비어 있는 자리만 사용
                out = card.convert("RGBA")
                out.alpha_composite(logo, (x, y))
                out = out.convert("RGB")
                stem = os.path.splitext(card_path)[0]
                out.save(stem + ".png")
                out.save(stem + ".jpg", quality=95)
                print(f"LOGO_OK {name} height={lh} badge={'yes' if dark else 'no'}")
                return 0
    print("NO_CLEAR_SPOT")
    return 2

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stamp the original navy logo on a cover")
    parser.add_argument("card_path")
    parser.add_argument("--force", action="store_true", help="Overwrite bottom area; requires visual QA")
    args = parser.parse_args()
    sys.exit(stamp(args.card_path, force=args.force))
