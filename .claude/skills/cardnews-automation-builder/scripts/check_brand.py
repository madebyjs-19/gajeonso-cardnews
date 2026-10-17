#!/usr/bin/env python3
"""새 브랜드 저장소가 실제로 돌아가는지 점검한다(게시·텔레그램 전송 없음).

사용: python3 check_brand.py /path/new-repo [--python python3.13]

점검: 옛 브랜드 표기 0개 · 파이썬 문법 · 필수 파일 · 샘플 카드 7장 생성 · 표지 로고 합성(LOGO_OK) ·
      릴스 자막 검사(CAPTIONS_OK) · 릴스 QR 엔딩 패널 · (ffmpeg 가 있으면) 카드 슬라이드 릴스.
결과 이미지는 <repo>/out/_check/ 에 남는다(out/ 은 .gitignore 대상, 매번 새로 만든다 — 비교하려면 먼저 복사해 둔다).
이미지를 직접 열어 눈으로도 확인한다.
"""
import json, os, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
OLD_TOKENS = ["가전소", "gajeonso", "GAJEONSO", "Gajeonso", "PHwrX", "1KT9JGteGYQLhsHnVDmcU2xAhqZLI-lKl", "家電所"]
TEXT_EXT = {".py", ".md", ".yml", ".yaml", ".sh", ".html", ".txt", ".svg"}

results = []


def ok(name, passed, detail=""):
    """passed=None 은 경고(실패로 세지 않음)."""
    if passed is not None:
        results.append((name, passed, detail))
    print({True: "PASS ", False: "FAIL ", None: "WARN "}[passed] + name + (f" — {detail}" if detail else ""))


def run(cmd, cwd, timeout=600):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def main():
    repo = pathlib.Path(sys.argv[1]).resolve()
    py = sys.argv[sys.argv.index("--python") + 1] if "--python" in sys.argv else (shutil.which("python3.13") or sys.executable)
    brand = json.loads((repo / "brand.json").read_text(encoding="utf-8")) if (repo / "brand.json").exists() else {}
    slug = brand.get("brand_slug", "")

    # 1. 옛 브랜드 표기
    left = []
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix in TEXT_EXT and not {".git", "out", "fonts"} & set(p.relative_to(repo).parts) \
                and p.name != "REBRAND_TODO.md":
            t = p.read_text(encoding="utf-8", errors="ignore")
            left += [f"{p.relative_to(repo)}:{tok}" for tok in OLD_TOKENS if tok in t]
    ok("옛 브랜드 표기 없음", not left, ", ".join(left[:8]))

    # 2. 필수 파일
    need = ["gen_cards.py", "approval_publish.py", "publish.py", "publish_reel.py", "make_reel.py", "reel_overlay.py",
            "collect_metrics.py", "topic_request.py", "ROUTINE_PROMPT.md", "CLAUDE.md", f"{slug}_logo.png",
            "assets/reel/consult_qr.png", ".github/workflows/publish-on-approval.yml", ".github/workflows/meta-check.yml",
            "plan/content_plan.md", "log/ig-card-news-log.md"]
    if "brand_mark.png" in (repo / "gen_cards.py").read_text(encoding="utf-8"):
        need.append("assets/brand_mark.png")  # 콘센트 심볼 대신 브랜드 심볼을 쓰는 저장소
    miss = [n for n in need if not (repo / n).exists()]
    ok("필수 파일", not miss, ", ".join(miss))
    ok("진행자 기준 이미지(assets/reel_host/)", True if any((repo / "assets" / "reel_host").glob("host.*")) else None,
       "없으면 docs/reel_host.md 대로 만들어 넣기(릴스 인물 고정용, 없어도 동작)")

    # 3. 문법
    bad = []
    for f in repo.glob("*.py"):
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except SyntaxError as e:
            bad.append(f"{f.name}:{e.lineno} {e.msg}")
    ok("파이썬 문법", not bad, "; ".join(bad))

    # 4. 저장소 주소가 코드에 들어갔는지
    gh = brand.get("github_repo", "")
    pub = (repo / "publish.py").read_text(encoding="utf-8")
    ok("발행 이미지 주소(raw.githubusercontent.com/<repo>)", bool(gh) and gh in pub, gh)

    # 5. 샘플 카드 생성 + 로고 합성
    chk = repo / "out" / "_check"
    shutil.rmtree(chk, ignore_errors=True)
    (chk / "20990101").mkdir(parents=True)
    deck = json.loads((ASSETS / "sample_deck.json").read_text(encoding="utf-8"))
    (chk / "deck.json").write_text(json.dumps(deck, ensure_ascii=False), encoding="utf-8")
    code, outp = run([py, "gen_cards.py", str(chk / "deck.json"), str(chk / "20990101")], repo)
    cards = sorted((chk / "20990101").glob("card*.jpg"))
    ok("샘플 카드 생성(7장)", code == 0 and len(cards) == 7, outp.splitlines()[-1][:160] if outp else "")

    prompt = (repo / "ROUTINE_PROMPT.md").read_text(encoding="utf-8")
    m = re.search(r"```python\n(# stamp_logo\.py.*?)```", prompt, re.S)
    if m and cards:
        (chk / "stamp_logo.py").write_text(m.group(1), encoding="utf-8")
        env_logo = str(repo / f"{slug}_logo.png")
        p = subprocess.run([py, str(chk / "stamp_logo.py"), str(chk / "20990101" / "card1.png")], cwd=repo,
                           capture_output=True, text=True, env={**os.environ, "LOGO_SRC": env_logo})
        out = (p.stdout + p.stderr).strip()
        ok("표지 로고 합성(LOGO_OK top-right)", "LOGO_OK top-right" in out, out[:120])
    else:
        ok("표지 로고 합성(LOGO_OK top-right)", False, "ROUTINE_PROMPT.md 에서 stamp_logo.py 코드를 찾지 못함" if not m else "카드 없음")

    # 5-2. 밝은 표지(ice): 로고가 배지 없이 들어가는지
    if m:
        deck["cover_color"] = "ice"
        (chk / "deck_ice.json").write_text(json.dumps(deck, ensure_ascii=False), encoding="utf-8")
        (chk / "20990102").mkdir()
        code, outp = run([py, "gen_cards.py", str(chk / "deck_ice.json"), str(chk / "20990102")], repo)
        p = subprocess.run([py, str(chk / "stamp_logo.py"), str(chk / "20990102" / "card1.png")], cwd=repo,
                           capture_output=True, text=True, env={**os.environ, "LOGO_SRC": str(repo / f"{slug}_logo.png")})
        out = (p.stdout + p.stderr).strip()
        ok("밝은 표지 로고(ice, 배지 없음)", code == 0 and "LOGO_OK top-right" in out, out[:120])

    # 6. 릴스 자막 검사 + QR 엔딩 패널
    code, outp = run([py, "reel_overlay.py", "--check", str(ASSETS / "sample_captions.txt")], repo)
    ok("릴스 자막 검사(CAPTIONS_OK)", "CAPTIONS_OK" in outp, outp.splitlines()[-1][:120] if outp else "")
    code, outp = run([py, "reel_overlay.py", "--end-card", str(chk / "end_card.png")], repo)
    ok("릴스 QR 엔딩 패널", code == 0 and (chk / "end_card.png").exists(), outp[-120:])

    # 7. 카드 슬라이드 릴스(ffmpeg 필요, 없으면 건너뜀)
    if shutil.which("ffmpeg") and cards:
        (chk / "20990101" / "ig.txt").write_text("브랜드 점검용 샘플 훅 문장입니다\n", encoding="utf-8")
        code, outp = run([py, "make_reel.py", str(chk / "20990101"), "", str(chk / "reel.mp4")], repo, timeout=900)
        ok("카드 슬라이드 릴스(make_reel)", code == 0 and (chk / "reel.mp4").exists(), outp[-120:])
    else:
        print("SKIP 카드 슬라이드 릴스 — ffmpeg 없음(Actions 에서는 설치되어 동작)")

    failed = [r for r in results if not r[1]]
    print()
    print(f"결과: {len(results) - len(failed)}/{len(results)} 통과. 미리보기: {chk}/20990101/card1.jpg·card2.jpg·card7.jpg, {chk}/20990102/card1.jpg, {chk}/end_card.png")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
