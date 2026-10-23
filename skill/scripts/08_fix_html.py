"""08_fix_html.py — 修复脚本：单独跑 D5（前端）+ 重跑 review。

为什么需要：
- 06_run_one_chapter.py 早期版本有个 bug：_which_done 漏算了 D5 项，导致 zip 截断，D5 永远不跑
- 现在后台 task 的批次（章 02-14）都只跑了 D1-D4，没 HTML
- 这个脚本对指定章节顺序补齐 D5 + 重 review

用法：
    python scripts/08_fix_html.py --book daodejing --chapters 01,02,03
"""
from __future__ import annotations
import argparse, json, sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.review import review_chapter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapters", default="01,02,03,04,05,06,07,08,09,10,11,12,13,14")
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    chap_ids = args.chapters.split(",")
    print(f"\n{'#' * 70}\n#  修复 D5 HTML 缺失 + 重 review\n#  章节：{args.chapters}\n{'#' * 70}\n")

    results = []
    for chap_id in chap_ids:
        chapter_dir = root / "outputs" / args.book / f"chapter_{chap_id}"
        if not chapter_dir.exists():
            print(f"❌ {chap_id}: chapter 目录不存在")
            results.append((chap_id, "MISSING_DIR"))
            continue

        # 跑 D5 前端
        print(f"\n--- D5 (HTML) for {chap_id} ---")
        ret = subprocess.run(
            [sys.executable, "scripts/05_build_frontend.py", "--book", args.book, "--chapter", chap_id],
            cwd=str(root),
        )
        if ret.returncode != 0:
            print(f"   ⚠ D5 退出非零: {ret.returncode}")

        # 重 review
        print(f"--- review for {chap_id} ---")
        v = review_chapter(chapter_dir)
        results.append((chap_id, v["verdict"]))
        sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(v["verdict"], "?")
        print(f"{sym} {chap_id}: {v['verdict']}")

    # 终态：写一个补丁报告
    out = ["# 🔧 D5 HTML 修复 + 重 review 报告", ""]
    out.append("| 章 | verdict |")
    out.append("|---|---|")
    for c, v in results:
        out.append(f"| {c} | {v} |")
    (root / "outputs" / args.book / "_fix_html_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\n报告：{root / 'outputs' / args.book / '_fix_html_report.md'}")


if __name__ == "__main__":
    main()
