"""D1 拆书脚本。

用法：
    python scripts/01_split_chapter.py --book shijie_deluoji --chapter 01

做什么：
    1. 读 config/books.yaml 找书 + 章节
    2. 打开对应分册 PDF
    3. 章节首页 mark / 末页 mark：输出每页 txt 到 pages/p{NN}.txt
    4. 抽首页的 hook 引语段
    5. 抽所有页面图到 figures/
    6. 合并成 chapter_{NN}.txt（含 hook + 全文，去空白页）
    7. 写 chapter_{NN}.yaml（meta + 初步清单）
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.book_config import load_books, find_chapter, find_volume
from lib.pdf_tools import open_book, iter_pages, page_text, extract_images_on_page, find_figure_numbers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    books = load_books(root / "config" / "books.yaml")
    book = next((b for b in books if b["id"] == args.book), None)
    if book is None:
        raise SystemExit(f"找不到书 id={args.book}")

    chap = find_chapter(books, args.book, args.chapter)
    volume = find_volume(book, chap["volume"])

    inputs_dir = root / "inputs"
    out_dir = root / "outputs" / book["id"] / f"chapter_{chap['id']}"
    pages_dir = out_dir / "pages"
    figures_dir = out_dir / "figures"
    pages_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    print(f"📖 《{book['title']}》")
    print(f"   章节: {chap['label']}")
    print(f"   分册: {volume['id']} ({volume['path']})")
    print(f"   页范围: PDF 第 {chap['pages'][0]}–{chap['pages'][1]} 页")
    print(f"   输出: {out_dir}")

    doc, pdf_path = open_book(inputs_dir, volume["path"])

    start, end = chap["pages"]
    n_pages = 0
    n_figures = 0
    figure_index = []   # [(page, fig_label_found_in_text, filename)]

    chapter_lines: list[str] = []
    chapter_lines.append(f"# {chap['label']}")
    if chap.get("hook"):
        chapter_lines.append("")
        chapter_lines.append(f"> **{chap['hook']}**")
        chapter_lines.append("")
    chapter_lines.append(f"_（源自《{book['title']}》{book['author']} 著；PDF 第 {start}–{end} 页）_")
    chapter_lines.append("")
    chapter_lines.append("---")
    chapter_lines.append("")

    for page_num, page in iter_pages(doc, start, end):
        text = page_text(doc, page_num - 1)
        if not text.strip():
            continue
        n_pages += 1
        txt_path = pages_dir / f"p{page_num:03d}.txt"
        txt_path.write_text(text.strip(), encoding="utf-8")

        # 图抽
        figs = extract_images_on_page(doc, page_num - 1, figures_dir, prefix=f"ch{chap['id']}")
        for fn, _ in figs:
            figure_index.append((page_num, fn))
            n_figures += 1

        # 找文中 '图X-Y' 标记（不强求每次都有）
        labels = find_figure_numbers(text)

        chapter_lines.append(f"\n## [第 {page_num} 页]")
        chapter_lines.append("")
        chapter_lines.append(text.strip())
        if labels:
            chapter_lines.append("")
            chapter_lines.append(f"_本页含图标记：{'、'.join(labels)}_")
        chapter_lines.append("")

    # 写章节全文
    (out_dir / f"chapter_{chap['id']}.txt").write_text("\n".join(chapter_lines), encoding="utf-8")

    # 元数据 yaml
    meta = {
        "book_id": book["id"],
        "book_title": book["title"],
        "author": book["author"],
        "chapter_id": chap["id"],
        "chapter_label": chap["label"],
        "part": chap.get("part", ""),
        "hook": chap.get("hook", ""),
        "pdf_volume": volume["id"],
        "pdf_path": str(pdf_path.relative_to(root)),
        "pages_range": [start, end],
        "pages_extracted": n_pages,
        "figures": [{"page": p, "filename": fn} for p, fn in figure_index],
        "status": "split-done",
    }
    import yaml as _yaml
    (out_dir / f"chapter_{chap['id']}.yaml").write_text(
        _yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print()
    print(f"✅ 拆页：{n_pages} 页 → {pages_dir}")
    print(f"✅ 抽图：{n_figures} 张 → {figures_dir}")
    print(f"✅ 全文：chapter_{chap['id']}.txt")
    print(f"✅ 元数据：chapter_{chap['id']}.yaml")
    print()
    print(f"📌 下一步 (D2)：python scripts/02_make_notes.py --book {args.book} --chapter {args.chapter}")


if __name__ == "__main__":
    main()
