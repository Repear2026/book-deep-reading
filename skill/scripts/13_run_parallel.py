"""13_run_parallel.py — 并行跑多章（加速大批量章节）。

用法：
    python scripts/13_run_parallel.py --book daodejing --start 01 --end 81 --workers 4

机制：
  - 用线程池同时跑多个 `06_run_one_chapter.py` 子进程
  - 06 内部对已完成的 D 步会自动跳过（--skip-finished），所以中断后可安全重跑
  - 06 用 --no-library 关闭书架刷新，避免多进程抢写 outputs/index.html
  - 全部完成后统一刷一次书架 + 聚合报告

适用：短章书籍（道德经这类一章几十字的），PDF 大部头别用（会撞 LLM rate limit）。
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_one(root: Path, book: str, chap_id: str) -> dict:
    t0 = time.time()
    ret = subprocess.run(
        [sys.executable, "scripts/06_run_one_chapter.py",
         "--book", book, "--chapter", chap_id, "--no-library"],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    elapsed = time.time() - t0
    # 读 verdict
    rj = root / "outputs" / book / f"chapter_{chap_id}" / "review.json"
    verdict = "MISSING"
    if rj.exists():
        try:
            verdict = json.loads(rj.read_text(encoding="utf-8")).get("verdict", "?")
        except Exception:
            pass
    sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(verdict, "❓")
    print(f"  {sym} ch{chap_id}  {verdict}  {elapsed:.0f}s", flush=True)
    return {"chapter_id": chap_id, "verdict": verdict, "elapsed": elapsed, "returncode": ret.returncode}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--start", default="01")
    ap.add_argument("--end", default="81")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    chaps = [f"{i:02d}" for i in range(int(args.start), int(args.end) + 1)]

    print(f"\n{'='*64}")
    print(f"并行跑 {args.book} · {len(chaps)} 章 · {args.workers} 路并发")
    print(f"{'='*64}\n")

    t0 = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_one, root, args.book, c): c for c in chaps}
        for fut in cf.as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                cid = futures[fut]
                print(f"  ❌ ch{cid} 异常: {type(e).__name__}: {str(e)[:120]}", flush=True)
                results.append({"chapter_id": cid, "verdict": "ERROR", "elapsed": 0})

    total = time.time() - t0
    passes = sum(1 for r in results if r["verdict"] == "PASS")
    warns = sum(1 for r in results if r["verdict"] == "WARN")
    fails = [r for r in results if r["verdict"] not in ("PASS", "WARN")]

    print(f"\n{'='*64}")
    print(f"完成：{len(results)} 章 · PASS {passes} / WARN {warns} / 异常 {len(fails)} · 用时 {total/60:.1f} 分")
    print(f"{'='*64}")
    if fails:
        print("需补跑：" + ", ".join(r["chapter_id"] for r in fails))

    # 统一刷书架 + 聚合
    print("\n刷新书架…")
    subprocess.run([sys.executable, "scripts/12_build_library.py", "--codes-root", str(root)], cwd=str(root))
    print("生成全书入口…")
    subprocess.run([sys.executable, "scripts/10_build_book_index.py", "--book", args.book], cwd=str(root))

    out = root / "outputs" / args.book / "_parallel_report.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告：{out}")


if __name__ == "__main__":
    main()
