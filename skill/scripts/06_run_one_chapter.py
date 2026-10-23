"""06_run_one_chapter.py — 一章一键跑（D1→D5 + review）。

用法:
    python scripts/06_run_one_chapter.py --book shijie_deluoji --chapter 02 [--skip-finished]
"""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.review import review_chapter
from lib.book_config import load_books


STEPS = [
    ("D1 拆页", "scripts/01_split_chapter.py"),
    ("D2 笔记", "scripts/02_make_notes.py"),
    ("D3 图谱", "scripts/03_make_graph.py"),
    ("D4 草稿", "scripts/04_make_overview.py"),
    ("D5 前端", "scripts/05_build_frontend.py"),
]

STEP_TEXT_BOOK = "scripts/01b_split_text_book.py"   # 文本型书籍（道德经等）


def _which_done(root, book, chap) -> list[tuple[bool, str]]:
    """每个 D 步的产物是否已存在。长度必须等于 len(STEPS)。"""
    base = Path(root) / "outputs" / book / f"chapter_{chap}"
    checks = [
        (base / "chapter_NN.txt".replace("NN", chap)).exists() or (base / "pages").exists(),  # D1
        (base / "notes" / "notes.json").exists(),                                                # D2
        (base / "graph" / "graph.mmd").exists(),                                                 # D3
        # D4 产出三份：overview / glossary / socrates，必须齐全才算完成
        ((base / "overview" / "overview.md").exists()
         and (base / "glossary" / "glossary.md").exists()
         and (base / "socrates" / "socrates.md").exists()),                                     # D4
        # D5：HTML 集成最新 md，每次重跑（False = 不跳）让产物为最新
        False,
    ]
    assert len(checks) == len(STEPS), f"which_done 返回 {len(checks)} 项，应为 {len(STEPS)}"
    return [(b, "(跳)" if b else "(跑)") for b in checks]


def _resolve_steps(root: Path, book_id: str) -> list[tuple[str, str]]:
    """按书籍类型决定 D1 用哪个脚本（PDF 拆页 / 文本拆章）。"""
    try:
        books = load_books(root / "config" / "books.yaml")
        book = next((b for b in books if b["id"] == book_id), None)
        if book and (book.get("source_type") == "text" or book.get("text_source")):
            steps = list(STEPS)
            steps[0] = ("D1 拆章(文本)", STEP_TEXT_BOOK)
            return steps
    except Exception as e:
        print(f"   ⚠ 读取书目失败，按 PDF 处理：{e}")
    return list(STEPS)


def run_step(label: str, script: str, args: list[str]) -> bool:
    cmd = [sys.executable, script, *args]
    print(f"\n=== ▶ {label}: {' '.join(cmd)} ===")
    ret = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent.parent))
    return ret.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--skip-finished", action="store_true", default=True, help="若产物已存在则跳过该 D 步（默认开）")
    ap.add_argument("--no-library", action="store_true", help="不自动刷新书架（并行跑时用，避免多进程抢写）")
    args = ap.parse_args()

    base_args = ["--book", args.book, "--chapter", args.chapter]
    print(f"\n{'#' * 64}\n#  跑第 {args.chapter} 章 全流程 D1→D5\n{'#' * 64}\n")

    # 检测每个 D 步产物是否存在
    skip_map = _which_done(args.codes_root, args.book, args.chapter)
    steps = _resolve_steps(Path(args.codes_root), args.book)
    for (label, script), (skip, key) in zip(steps, skip_map):
        if args.skip_finished and skip:
            print(f"\n=== ↩ {label}（产物已存在，跳过 LLM 调用）{key}")
            continue
        ok = run_step(label, script, base_args)
        if not ok:
            print(f"   ⚠ {label} 退出非零；继续 review（review 会报告致命问题）")

    # 校对 + 自测
    print(f"\n=== 🔎 review (校对 + 自测) ===")
    chapter_dir = Path(args.codes_root) / "outputs" / args.book / f"chapter_{args.chapter}"
    if not chapter_dir.exists():
        print(f"❌ chapter dir 不存在: {chapter_dir}")
        sys.exit(2)
    verdict = review_chapter(chapter_dir)
    sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(verdict["verdict"], "?")
    print(f"\n{sym} 第 {args.chapter} 章: {verdict['verdict']}")
    print(f"  致命问题: {len(verdict['issues'])}")
    print(f"  警告: {len(verdict['warnings'])}")
    print(f"  报告: {chapter_dir / 'review.md'}")

    # 自动刷新图书馆总入口（跑完一章 → 书架自动更新，零手工）
    if not args.no_library:
        try:
            auto_library = Path(args.codes_root) / "scripts" / "12_build_library.py"
            if auto_library.exists():
                print("\n=== 📚 刷新图书馆总入口 ===")
                subprocess.run([sys.executable, str(auto_library), "--codes-root", args.codes_root],
                               cwd=str(Path(args.codes_root)))
        except Exception as e:
            print(f"   ⚠ 图书馆刷新失败（不影响本章）：{e}")

    sys.exit(0 if verdict["verdict"] != "FAIL" else 1)


if __name__ == "__main__":
    main()
