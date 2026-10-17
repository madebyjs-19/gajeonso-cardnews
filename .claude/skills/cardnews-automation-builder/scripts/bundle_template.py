#!/usr/bin/env python3
"""가전소 저장소의 현재 코드를 이 스킬의 assets/template/ 에 담는다(다른 계정에 스킬 파일로 넘기기 전에 실행).

사용: python3 bundle_template.py [--source <가전소 저장소>] [--dest <스킬>/assets/template]
가전소 저장소 안에서는 assets/template/ 을 커밋하지 않는다(.gitignore). 저장소 코드 자체가 원본이기 때문이다.
"""
import argparse, pathlib, shutil, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from new_brand import INCLUDE, RENAME, find_source  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--dest", default=str(HERE.parent / "assets" / "template"))
    a = ap.parse_args()
    src = find_source(a.source) if a.source else next(
        (p for p in HERE.parents if (p / "gen_cards.py").exists() and (p / "ROUTINE_PROMPT.md").exists()), None)
    if not src:
        sys.exit("가전소 저장소를 찾지 못했습니다. --source 로 지정하세요.")
    dest = pathlib.Path(a.dest).resolve()
    shutil.rmtree(dest, ignore_errors=True)
    n = 0
    for rel in [*INCLUDE, *RENAME]:
        p = src / rel
        items = [q for q in p.rglob("*") if q.is_file() and "__pycache__" not in q.parts] if p.is_dir() else [p] if p.exists() else []
        for q in items:
            d = dest / q.relative_to(src)
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(q, d)
            n += 1
    print(f"OK {n}개 파일 → {dest}")


if __name__ == "__main__":
    main()
