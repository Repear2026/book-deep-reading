"""01b_split_text_book.py — 文本型书籍拆章（替代 PDF 拆页）。

适用：《道德经》《论语》等纯文本、按章切分的公版书。

用法：
    python scripts/01b_split_text_book.py --book daodejing --chapter 01

输入：inputs/<text_source>（JSON，结构 {"chapters": {"01": "原文", ...}}）
输出：与 01_split_chapter.py 完全一致的结构
    outputs/<book>/chapter_NN/pages/pNNN.txt
    outputs/<book>/chapter_NN/chapter_NN.txt
    outputs/<book>/chapter_NN/chapter_NN.yaml
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.book_config import load_books, find_chapter


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
    text_source = book.get("text_source")
    if not text_source:
        raise SystemExit(f"书 {args.book} 未配置 text_source（这是文本型书专用脚本）")

    src = root / "inputs" / text_source
    if not src.exists():
        raise SystemExit(f"找不到文本源：{src}")

    data = json.loads(src.read_text(encoding="utf-8"))
    chapters_map = data.get("chapters") or {}
    cid = str(chap["id"]).zfill(2)
    body = chapters_map.get(cid) or chapters_map.get(str(int(chap["id"])))
    if not body:
        raise SystemExit(f"文本源里找不到第 {cid} 章")

    body = body.strip()
    out_dir = root / "outputs" / book["id"] / f"chapter_{cid}"
    pages_dir = out_dir / "pages"
    figures_dir = out_dir / "figures"
    pages_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    print(f"📜 《{book['title']}》{chap['label']}")
    print(f"   源：{src.name}  ·  字数：{len(body)}")
    print(f"   输出：{out_dir}")

    # 每章 = 一"页"
    page_no = int(chap["id"])
    (pages_dir / f"p{page_no:03d}.txt").write_text(body, encoding="utf-8")

    # 章节全文
    lines = [f"# {chap['label']}", ""]
    if chap.get("hook"):
        lines += [f"> **{chap['hook']}**", ""]
    lines += [
        f"_（源自《{book['title']}》{book['author']} 著 · {data.get('meta', {}).get('version', '')}）_",
        "",
        "---",
        "",
        f"## [第 {page_no} 章]",
        "",
        body,
        "",
    ]
    (out_dir / f"chapter_{cid}.txt").write_text("\n".join(lines), encoding="utf-8")

    # 元数据（与 01 一致）
    import yaml as _yaml
    meta = {
        "book_id": book["id"],
        "book_title": book["title"],
        "author": book["author"],
        "chapter_id": cid,
        "chapter_label": chap["label"],
        "part": chap.get("part", ""),
        "hook": chap.get("hook", ""),
        "pdf_volume": "text",
        "pdf_path": f"inputs/{text_source}",
        "pages_range": [page_no, page_no],
        "pages_extracted": 1,
        "figures": [],
        "char_count": len(body),
        "status": "split-done",
    }
    (out_dir / f"chapter_{cid}.yaml").write_text(
        _yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    print(f"✅ 拆章：1 章 · {len(body)} 字")
    print(f"📌 下一步：python scripts/02_make_notes.py --book {args.book} --chapter {cid}")


if __name__ == "__main__":
    main()
