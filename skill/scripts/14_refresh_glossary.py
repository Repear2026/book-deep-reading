"""14_refresh_glossary.py — 批量重刷 glossary（新 L3 prompt 上线后用）。

为什么需要：04_make_overview.py 的 SYSTEM 从"严格不得补充"改成"分层原则"后，
旧的 glossary.md 是旧 prompt 产物（L3 全是"未提供，不作补充"）。此脚本只重跑 glossary 层，
不动 notes / graph / overview / socrates，成本低。

用法：
    python scripts/14_refresh_glossary.py --book daodejing --workers 4
    python scripts/14_refresh_glossary.py --book daodejing --chapters 08,29,30
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, importlib.util, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_one(root: Path, book: str, chap_id: str) -> dict:
    t0 = time.time()
    ret = subprocess.run(
        [sys.executable, "scripts/04_make_overview.py",
         "--book", book, "--chapter", chap_id, "--only", "glossary"],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    ok = ret.returncode == 0
    # 重刷后重建 HTML（glossary 变了）
    if ok:
        subprocess.run(
            [sys.executable, "scripts/05_build_frontend.py", "--book", book, "--chapter", chap_id],
            cwd=str(root), capture_output=True,
        )
    print(f"  {'✅' if ok else '❌'} ch{chap_id}  {time.time()-t0:.0f}s", flush=True)
    return {"chapter_id": chap_id, "ok": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapters", default=None, help="逗号分隔；省略则全部")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    if args.chapters:
        chaps = [c.strip() for c in args.chapters.split(",")]
    else:
        chaps = sorted(p.name.replace("chapter_", "")
                       for p in (root / "outputs" / args.book).glob("chapter_*"))

    print(f"\n重刷 glossary：{args.book} · {len(chaps)} 章 · {args.workers} 路\n")
    t0 = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, root, args.book, c): c for c in chaps}
        for f in cf.as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:
                print(f"  ❌ ch{futs[f]} {type(e).__name__}", flush=True)

    ok_n = sum(1 for r in results if r["ok"])
    print(f"\n完成：{ok_n}/{len(results)} 成功 · {time.time()-t0:.1f} 分")

    # 书架 + 聚合
    subprocess.run([sys.executable, "scripts/12_build_library.py", "--codes-root", str(root)], cwd=str(root))
    subprocess.run([sys.executable, "scripts/09_reaggregate.py", "--book", args.book], cwd=str(root))


if __name__ == "__main__":
    main()
