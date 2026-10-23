"""读 books.yaml → 内存结构。"""
from __future__ import annotations
from pathlib import Path
import yaml


def load_books(books_yaml: Path) -> list[dict]:
    data = yaml.safe_load(books_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{books_yaml} 应是一个 YAML 列表（每个元素是一本书）")
    for b in data:
        _expand_auto_chapters(b)
    return data


def _expand_auto_chapters(book: dict) -> None:
    """文本型书籍支持：`auto_chapters: N` 自动生成 N 个章节配置。

    适用于《道德经》这类纯文本、按章切分的书，免去手写 81 条。
    """
    if not book.get("auto_chapters") or book.get("chapters"):
        return
    n = int(book["auto_chapters"])
    label_fmt = book.get("auto_label_format", "第 {n} 章")
    part = book.get("auto_part", "")
    book["chapters"] = [
        {
            "id": f"{i:02d}",
            "label": label_fmt.format(n=i),
            "hook": "",
            "volume": book.get("auto_volume", "text"),
            "pages": [i, i],
            "part": part,
            "status": "todo",
        }
        for i in range(1, n + 1)
    ]
    if not book.get("volumes"):
        book["volumes"] = [{
            "id": book.get("auto_volume", "text"),
            "path": book.get("text_source", ""),
            "pages": n,
        }]


def find_chapter(books: list[dict], book_id: str, chapter_id: str) -> dict:
    book = next((b for b in books if b["id"] == book_id), None)
    if book is None:
        raise KeyError(f"找不到书 id={book_id}")
    chap = next((c for c in book["chapters"] if str(c["id"]) == str(chapter_id)), None)
    if chap is None:
        raise KeyError(f"书 {book_id} 找不到章节 {chapter_id}")
    return chap


def find_volume(book: dict, volume_id: str) -> dict:
    v = next((v for v in book["volumes"] if v["id"] == volume_id), None)
    if v is None:
        raise KeyError(f"书 {book['id']} 找不到分册 {volume_id}")
    return v
