"""07_run_all.py — 顺序跑完全部 14 章（含 review）。

行为：
- 严格按 1 → 2 → ... → 14 顺序
- 每章跑完调 review_chapter 写 review.md
- 致命 FAIL → 写 review.md 后跳过该章继续下章（不阻断）
- 最终写 aggregate_report.md 总结

用法：
    python scripts/07_run_all.py --book shijie_deluoji
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess
from lib.review import review_chapter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--start", default="02")
    ap.add_argument("--end", default="14")
    ap.add_argument("--resume-from", default=None, help="从某章开始（产出已存在的会被重新跑）")
    args = ap.parse_args()

    root = Path(args.codes_root)
    chapter_nums = list(range(int(args.start), int(args.end) + 1))
    start_time = time.time()
    results = []

    print(f"\n{'#' * 70}")
    print(f"# 顺序跑全部章节 {args.start} → {args.end}（{args.book}）")
    print(f"# 行为：每章 D1→D5→review；致命错 → 跳过；警告 → 继续")
    print(f"{'#' * 70}\n")

    for n in chapter_nums:
        chap_id = f"{n:02d}"
        print(f"\n{'=' * 70}\n▶ 第 {chap_id} 章 开始\n{'=' * 70}")
        t0 = time.time()

        # 1) 跑 D1→D5
        ret = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "06_run_one_chapter.py"),
                "--book", args.book,
                "--chapter", chap_id,
            ],
            cwd=str(root),
        )
        elapsed = time.time() - t0

        # 2) 拿 verdict
        chapter_dir = root / "outputs" / args.book / f"chapter_{chap_id}"
        review_path = chapter_dir / "review.json"
        if review_path.exists():
            verdict = json.loads(review_path.read_text(encoding="utf-8"))
        else:
            verdict = {"verdict": "MISSING", "issues": ["review.json 不存在"], "warnings": []}

        results.append({
            "chapter_id": chap_id,
            "elapsed_sec": round(elapsed, 1),
            "verdict": verdict["verdict"],
            "issues": verdict["issues"],
            "warnings": verdict["warnings"],
        })

        sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "MISSING": "❓"}.get(verdict["verdict"], "?")
        print(f"\n{sym} 第 {chap_id} 章 {verdict['verdict']}（{elapsed:.0f}s）")

    total = time.time() - start_time

    # 3) 聚合报告
    report = _aggregate(results, total, args.book)
    (root / "outputs" / args.book / "_aggregate_report.md").write_text(report, encoding="utf-8")
    (root / "outputs" / args.book / "_aggregate_report.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n\n{'#' * 70}\n# 🏁 全部完成 {len(results)} 章 · 用时 {total/60:.1f} 分\n{'#' * 70}")
    print(f"\n聚合报告：{root / 'outputs' / args.book / '_aggregate_report.md'}")
    sys.exit(0)


def _aggregate(results: list[dict], total_sec: float, book_id: str) -> str:
    passes = [r for r in results if r["verdict"] == "PASS"]
    warns = [r for r in results if r["verdict"] == "WARN"]
    fails = [r for r in results if r["verdict"] == "FAIL"]
    misses = [r for r in results if r["verdict"] == "MISSING"]

    out = [f"# 📚 {book_id} · 顺序跑全章节 · 聚合报告", ""]
    out.append(f"- 用时：{total_sec/60:.1f} 分")
    out.append(f"- PASS：{len(passes)} · WARN：{len(warns)} · FAIL：{len(fails)} · MISSING：{len(misses)}")
    out.append("")

    out.append("| 章 | verdict | 用时(秒) | 致命 | 警告 |")
    out.append("|---|---|---|---|---|")
    for r in results:
        out.append(f"| {r['chapter_id']} | {r['verdict']} | {r['elapsed_sec']} | {len(r['issues'])} | {len(r['warnings'])} |")
    out.append("")

    if fails or misses:
        out.append("## ❌ 失败/缺失章节详情")
        for r in fails + misses:
            out.append(f"\n### 第 {r['chapter_id']} 章")
            for i in r["issues"]:
                out.append(f"- {i}")
            for w in r["warnings"]:
                out.append(f"- ⚠ {w}")

    out.append("")
    out.append("## 失败章节补救")
    out.append("- 失败章节可单独重跑：`python scripts/06_run_one_chapter.py --book {book} --chapter {XX}`".format(book=book_id))
    out.append("- 全章节产出索引：`outputs/{book}/chapter_XX/site/index.html`（双击即看）".format(book=book_id))

    return "\n".join(out)


if __name__ == "__main__":
    main()
