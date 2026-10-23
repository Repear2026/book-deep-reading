"""11_prepare_publish.py — 构建精简发布目录（支持多本书）。

产出：outputs/_publish/
  - index.html                        ← 图书馆总入口（书架）
  - <book_id>/index.html              ← 每本书的章节入口
  - <book_id>/chapter_XX/site/index.html + 引用的 figures/

排除：pages/ notes/ graph/ overview/ glossary/ socrates/ 等中间产物。

用途：把 _publish 目录交给「发布为应用」上公网，手机可访问。
"""
from __future__ import annotations
import argparse, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.book_config import load_books


def copy_book(src: Path, dst: Path, keep_figures: int = 12) -> int:
    """拷一本书的 web 部分，返回字节数。"""
    total = 0
    # 书入口
    if (src / "index.html").exists():
        (dst).mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / "index.html", dst / "index.html")
        total += (dst / "index.html").stat().st_size

    # 每章 site
    for cdir in sorted(src.glob("chapter_*")):
        site = cdir / "site" / "index.html"
        if not site.exists():
            continue
        out_ch = dst / cdir.name / "site"
        out_ch.mkdir(parents=True, exist_ok=True)
        shutil.copy2(site, out_ch / "index.html")
        total += (out_ch / "index.html").stat().st_size

        html = site.read_text(encoding="utf-8")
        refs, seen = re.findall(r'figures/([\w.\-]+\.png)', html), []
        for r in refs:
            if r not in seen:
                seen.append(r)
        figs_out = out_ch / "figures"
        figs_out.mkdir(parents=True, exist_ok=True)
        for name in seen[:keep_figures]:
            fsrc = cdir / "site" / "figures" / name
            if fsrc.exists():
                shutil.copy2(fsrc, figs_out / name)
                total += fsrc.stat().st_size
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--book", default=None, help="只发布指定书；省略则发布全部")
    ap.add_argument("--keep-figures", type=int, default=12, help="每章保留的图形数（与前端展示一致）")
    args = ap.parse_args()

    root = Path(args.codes_root)
    outputs = root / "outputs"
    dst = outputs / "_publish"

    # 确保图书馆入口存在（书架是发布首页）
    library = outputs / "index.html"
    if not library.exists():
        print("⚠ 书架不存在，先生成…")
        import subprocess
        subprocess.run([sys.executable, str(root / "scripts" / "12_build_library.py"), "--codes-root", str(root)])

    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    # 1. 书架首页
    shutil.copy2(library, dst / "index.html")
    total_bytes = (dst / "index.html").stat().st_size

    # 2. 各书
    books = load_books(root / "config" / "books.yaml")
    targets = [b for b in books if (args.book is None or b["id"] == args.book)]
    for b in targets:
        src = outputs / b["id"]
        if not src.exists():
            print(f"   ⚠ 跳过 {b['id']}：outputs 不存在")
            continue
        n = copy_book(src, dst / b["id"], args.keep_figures)
        total_bytes += n
        print(f"   ✓ {b['id']}  {n/1024/1024:.1f} MB")

    n_files = sum(1 for _ in dst.rglob("*") if _.is_file())
    print()
    print(f"✅ 发布目录：{dst}")
    print(f"   文件数：{n_files}")
    print(f"   体积：{total_bytes/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
