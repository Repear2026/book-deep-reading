"""PyMuPDF 工具：按页号读 PDF 文字 + 抽图片。

依赖：pymupdf（pip install pymupdf）。
"""
from __future__ import annotations
from pathlib import Path
import pymupdf


def open_book(book_dir: Path, pdf_path: str):
    p = (book_dir / pdf_path).resolve()
    return pymupdf.open(p), p


def iter_pages(doc, start: int, end: int):
    """PDF 页号 1 起，[start, end] 含两端。"""
    for i in range(start - 1, end):
        if i >= len(doc):
            break
        yield i + 1, doc[i]


def page_text(doc, page_index_0based: int) -> str:
    return doc[page_index_0based].get_text()


def extract_images_on_page(doc, page_index_0based: int, out_dir: Path, prefix: str):
    """抽一页面上的所有位图为 PNG，返回 [(filename, xref)] 列表。"""
    page = doc[page_index_0based]
    images = page.get_images(full=True)
    saved = []
    for idx, img in enumerate(images, start=1):
        xref = img[0]
        try:
            pix = pymupdf.Pixmap(doc, xref)
            if pix.n - pix.alpha > 3:   # CMYK → RGB
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            name = f"{prefix}_p{page_index_0based + 1:03d}_img{idx}.png"
            pix.save(out_dir / name)
            saved.append((name, xref))
        except Exception as e:
            print(f"  ⚠️ 抽图失败 xref={xref}: {e}")
    return saved


def find_figure_numbers(text: str) -> list[str]:
    """从正文里抓 '图X-Y' 标记，便于人工校对。"""
    import re
    return re.findall(r"图\s*\d+\s*[-\u2013\u2014]\s*\d+", text)
