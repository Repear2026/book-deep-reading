"""D7：本地 HTML 单页（双击即用）。

输入：chapter_01/ 下所有产物（pages / figures / notes / graph / overview / glossary / socrates）
输出：chapter_01/site/index.html

页面结构：
1. 头部：章节 label + hook + 章首引语
2. 4 步导读（点卡展开）
3. 知识图谱（Mermaid，CDN 加载）
4. 笔记展开（核心命题/论据/案例/概念/跨章）
5. 错题本（localStorage）
6. 苏格拉底 prompt（4 模板 + 5-7 引导问题，一键复制）
7. 术语表 L0-L3
8. 5 张插图

零依赖，可双击。无 JS 框架。
"""
from __future__ import annotations
import argparse, html as html_lib, json, sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def md_to_html(text: str) -> str:
    """非常粗的 markdown→html：#标题 / **bold** / 列表 / 引用 / 表格 / ---。
    不追求完美，能让笔记可读。"""
    lines = text.split("\n")
    out = []
    in_table = False
    in_list = False

    def _inline(s: str) -> str:
        s = html_lib.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    for ln in lines:
        if not ln.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            if in_table:
                out.append("</table>")
                in_table = False
            out.append("<br/>")
            continue
        if ln.startswith("# "):
            out.append(f"<h1>{_inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{_inline(ln[3:])}</h2>")
        elif ln.startswith("### "):
            out.append(f"<h3>{_inline(ln[4:])}</h3>")
        elif ln.startswith("> "):
            out.append(f'<blockquote>{_inline(ln[2:])}</blockquote>')
        elif ln.startswith("---"):
            out.append("<hr/>")
        elif re.match(r"^\s*-\s", ln):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(re.sub(r'^\\s*-\\s*','',ln))}</li>")
        elif re.match(r"^\s*\d+\.\s", ln):
            if not in_list:
                out.append("<ol>")
                in_list = True
            out.append(f"<li>{_inline(re.sub(r'^\\s*\\d+\\.\\s*','',ln))}</li>")
        elif ln.startswith("|") and ln.endswith("|"):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if not in_table:
                out.append('<table class="tbl"><thead><tr>')
                out.append("".join(f"<th>{_inline(c)}</th>" for c in cells))
                out.append("</tr></thead><tbody>")
                in_table = True
            elif re.match(r"^[|\s:-]+$", ln):
                continue
            else:
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
        else:
            if in_list:
                out.append("</ul>" if out[-1] == "<ul>" or "<ul>" in out[-10:] else "</ol>")
                in_list = False
            if in_table:
                out.append("</tbody></table>")
                in_table = False
            out.append(f"<p>{_inline(ln)}</p>")

    if in_list: out.append("</ul>")
    if in_table: out.append("</tbody></table>")
    return "\n".join(out)


def _chapter_nav(root: Path, book_id: str, meta_id: str) -> dict:
    """计算上下章导航 + 总数 + 书入口相对路径。"""
    nav = {
        "total": 0, "index": 0,
        "prev_id": "", "prev_label": "",
        "next_id": "", "next_label": "",
        "home_href": "../../index.html",   # chapter_XX/site/ → 书入口
        "book_title": "",
    }
    try:
        from lib.book_config import load_books
        books = load_books(root / "config" / "books.yaml")
        book = next((b for b in books if b["id"] == book_id), None)
        if not book:
            return nav
        chapters = book.get("chapters") or []
        ids = [str(c["id"]) for c in chapters]
        nav["total"] = len(ids)
        nav["book_title"] = book.get("title", "")
        if meta_id in ids:
            i = ids.index(meta_id)
            nav["index"] = i + 1
            if i > 0:
                nav["prev_id"] = ids[i - 1]
                nav["prev_label"] = chapters[i - 1].get("label", "")
            if i < len(ids) - 1:
                nav["next_id"] = ids[i + 1]
                nav["next_label"] = chapters[i + 1].get("label", "")
    except Exception as e:
        print(f"   ⚠ 导航计算失败：{e}")
    return nav


def build_chapter_site(chapter_dir: Path, codes_root: Path | None = None) -> Path:
    import yaml as _yaml
    meta_id = chapter_dir.name.replace("chapter_", "")
    meta_path = chapter_dir / f"chapter_{meta_id}.yaml"
    meta = _yaml.safe_load(meta_path.read_text(encoding="utf-8"))

    # 上下章导航（需要 codes_root 才能读 books.yaml）
    nav = {"total": 0, "index": 0, "prev_id": "", "prev_label": "",
           "next_id": "", "next_label": "", "home_href": "../../index.html", "book_title": ""}
    if codes_root is not None:
        try:
            nav = _chapter_nav(codes_root, meta.get("book_id", ""), meta_id)
        except Exception as e:
            print(f"   ⚠ 导航生成失败：{e}")
    nav_bar_html = _render_nav_bar(nav, meta)
    # 原书原文（置顶展示用）
    raw_text_html = _render_raw_text(chapter_dir, meta_id, meta)
    notes_path = chapter_dir / "notes" / "notes.json"
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {}
    overview_path = chapter_dir / "overview" / "overview.md"
    overview = overview_path.read_text(encoding="utf-8") if overview_path.exists() else ""
    glossary_path = chapter_dir / "glossary" / "glossary.md"
    glossary = glossary_path.read_text(encoding="utf-8") if glossary_path.exists() else ""
    socrates_path = chapter_dir / "socrates" / "socrates.md"
    socrates = socrates_path.read_text(encoding="utf-8") if socrates_path.exists() else ""
    graph_mmd_path = chapter_dir / "graph" / "graph.mmd"
    graph_mmd = graph_mmd_path.read_text(encoding="utf-8") if graph_mmd_path.exists() else ""
    chapter_full_path = chapter_dir / f"chapter_{meta_id}.txt"
    chapter_full = chapter_full_path.read_text(encoding="utf-8") if chapter_full_path.exists() else ""

    figures = sorted((chapter_dir / "figures").glob("*.png")) if (chapter_dir / "figures").exists() else []
    MAX_FIGURES_DISPLAY = 12   # 限制显示数，避免装饰图过多拖慢 HTML
    fig_html = ""
    if figures:
        if len(figures) > MAX_FIGURES_DISPLAY:
            note = f'<p class="meta">本章节共 {len(figures)} 张原图；前 {MAX_FIGURES_DISPLAY} 张展示如下，其余在 PNG 文件里。</p>'
        else:
            note = f'<p class="meta">本章节共 {len(figures)} 张原图。</p>'
        fig_html = '<h2>📷 插图（点击看大图）</h2>' + note + '<div class="figures">'
        for f in figures[:MAX_FIGURES_DISPLAY]:
            fig_html += f'<a href="figures/{f.name}" target="_blank"><img src="figures/{f.name}" alt="{f.name}" loading="lazy"/></a>'
        fig_html += "</div>"

    notes_html = build_notes_html(notes)

    # 用 .format 会和 CSS/JS 的 {} 冲突，改成手动 replace
    html = HTML_TEMPLATE
    replacements = {
        "{title}": html_lib.escape(f"《{meta['book_title']}》{meta['chapter_label']} · 伴读"),
        "{book}": html_lib.escape(meta["book_title"]),
        "{author}": html_lib.escape(meta["author"]),
        "{chap_label}": html_lib.escape(meta["chapter_label"]),
        "{chap_part}": html_lib.escape(meta.get("part", "")),
        "{chap_id}": meta_id,
        "{hook}": html_lib.escape(meta.get("hook", "")),
        "{__hook_present__}": html_lib.escape(meta.get("hook", "")),
        "{overview_html}": md_to_html(overview),
        "{graph_mmd}": graph_mmd,
        "{notes_html}": notes_html,
        "{socrates_html}": md_to_html(socrates),
        "{glossary_html}": _glossary_to_html(glossary),
        "{figures_html}": fig_html,
        "{chapter_full_text}": html_lib.escape(chapter_full[:6000]),
        "__WRONGS_STORE__": f"book_{meta.get('book_id', 'book')}_chapter_{meta_id}_wrongs",
        "{nav_bar}": nav_bar_html,
        "{raw_text}": raw_text_html,
        "{prev_href}": f"../chapter_{nav['prev_id']}/site/index.html" if nav["prev_id"] else "",
        "{next_href}": f"../chapter_{nav['next_id']}/site/index.html" if nav["next_id"] else "",
        "{prev_label}": html_lib.escape(nav["prev_label"]),
        "{next_label}": html_lib.escape(nav["next_label"]),
        "{chapter_pos}": f"{nav['index']}/{nav['total']}" if nav["total"] else "",
    }
    for k, v in replacements.items():
        html = html.replace(k, v)

    site_dir = chapter_dir / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    if figures:
        # 软链接或复制 figures
        import shutil
        tgt = site_dir / "figures"
        if tgt.exists():
            shutil.rmtree(tgt, ignore_errors=True)
        shutil.copytree(chapter_dir / "figures", tgt)
    out = site_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def _render_nav_bar(nav: dict, meta: dict) -> str:
    """顶部固定阅读导航：← 目录 | 第 N/总 章 | 上一章 · 下一章。"""
    home = nav.get("home_href", "../../index.html")
    total, idx = nav.get("total", 0), nav.get("index", 0)
    pos = f"第 {idx}/{total} 章" if total else ""

    prev_html = (f'<a class="nav-btn" href="../chapter_{nav["prev_id"]}/site/index.html"'
                 f' title="{html_lib.escape(nav["prev_label"])}">← 上一章</a>'
                 if nav.get("prev_id") else '<span class="nav-btn disabled">← 上一章</span>')
    next_html = (f'<a class="nav-btn" href="../chapter_{nav["next_id"]}/site/index.html"'
                 f' title="{html_lib.escape(nav["next_label"])}">下一章 →</a>'
                 if nav.get("next_id") else '<span class="nav-btn disabled">下一章 →</span>')

    return f'''<nav class="readbar">
  <a class="nav-home" href="{home}">☰ 目录</a>
  <span class="nav-pos">{html_lib.escape(pos)}</span>
  <span class="nav-spacer"></span>
  {prev_html}
  {next_html}
</nav>'''


def _render_raw_text(chapter_dir: Path, meta_id: str, meta: dict) -> str:
    """原文置顶区：让读者第一屏就读到原文。"""
    pages = sorted((chapter_dir / "pages").glob("p*.txt")) if (chapter_dir / "pages").exists() else []
    body = ""
    if pages:
        body = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in pages).strip()
    if not body:
        p = chapter_dir / f"chapter_{meta_id}.txt"
        if p.exists():
            body = p.read_text(encoding="utf-8")
    if not body:
        return ""

    # 去掉章节标题行、来源说明、页标记，只留正文
    import re
    lines = []
    for ln in body.split("\n"):
        s = ln.strip()
        if not s:
            lines.append("")
            continue
        if s.startswith("# ") or s.startswith("_（源自") or s == "---":
            continue
        if re.match(r"^##\s*\[第\s*\d+\s*[章页]\]$", s):
            continue
        lines.append(s)
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if not text:
        return ""

    # 按空行分段，段落间留白
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    body_html = "\n".join(f"<p>{html_lib.escape(p)}</p>" for p in paras)

    return f'''<section id="raw" class="raw-section">
  <h2 class="raw-title">📜 原文</h2>
  <div class="raw-body">{body_html}</div>
</section>'''


def _glossary_to_html(glossary_md: str) -> str:
    """术语表：桌面用表格 + 手机用卡片（同一份数据双形态）。"""
    table_html = md_to_html(glossary_md)
    # 解析 markdown 表格行，生成卡片版
    rows = []
    for ln in glossary_md.split("\n"):
        s = ln.strip()
        if not s.startswith("|"):
            continue
        if "L0 一句话" in s or re.match(r"^\|[\s\-:|]+\|\s*$", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 5 or not cells[0]:
            continue
        rows.append(cells[:5])

    if not rows:
        return f'<div class="glossary-wrap">{table_html}</div>'

    cards = ['<div class="glossary-card">']
    for c in rows:
        term, l0, l1, l2, l3 = c
        cards.append(f'''<div class="gcard">
  <h4 class="gcard-term">{html_lib.escape(term)}</h4>
  <div class="gcard-row l0"><span class="gcard-k">L0</span><span class="gcard-v">{html_lib.escape(l0)}</span></div>
  <div class="gcard-row"><span class="gcard-k">L1</span><span class="gcard-v">{html_lib.escape(l1)}</span></div>
  <div class="gcard-row"><span class="gcard-k">L2</span><span class="gcard-v">{html_lib.escape(l2)}</span></div>
  <div class="gcard-row"><span class="gcard-k">L3</span><span class="gcard-v">{html_lib.escape(l3)}</span></div>
</div>''')
    cards.append("</div>")

    return f'<div class="glossary-wrap">{table_html}{"".join(cards)}</div>'


def build_notes_html(notes: dict) -> str:
    """把笔记 JSON 转成可读 html 区段。"""
    blocks = []

    if notes.get("chapter_role"):
        blocks.append(f'<div class="callout"><strong>章节主旨：</strong>{html_lib.escape(notes["chapter_role"][:600])}</div>')

    if notes.get("core_propositions"):
        blocks.append("<h3>📌 核心命题</h3><ol>")
        for p in notes["core_propositions"][:30]:
            blocks.append(f"<li>{html_lib.escape(str(p))}</li>")
        if len(notes["core_propositions"]) > 30:
            blocks.append(f"<li><em>... 共 {len(notes['core_propositions'])} 条</em></li>")
        blocks.append("</ol>")

    if notes.get("key_arguments"):
        blocks.append("<h3>🔑 关键论据</h3><ol>")
        for p in notes["key_arguments"][:20]:
            blocks.append(f"<li>{html_lib.escape(str(p))}</li>")
        blocks.append("</ol>")

    if notes.get("cases"):
        from lib.normalize import cases_of
        blocks.append("<h3>📚 案例</h3>")
        for c in cases_of(notes)[:15]:
            blocks.append(f'<details><summary><strong>{html_lib.escape(c["name"])}</strong></summary><div class="case-body">{html_lib.escape(c["desc"][:600])}</div></details>')
        # 兼容无 name 的原始字符串案例
        for c in notes["cases"][:15]:
            if isinstance(c, str):
                blocks.append(f"<p>{html_lib.escape(c)}</p>")

    if notes.get("new_concepts"):
        from lib.normalize import concepts_of
        blocks.append("<h3>💡 新概念</h3>")
        for c in concepts_of(notes)[:25]:
            blocks.append(f'<details><summary><strong>{html_lib.escape(c["name"])}</strong></summary><div class="case-body">{html_lib.escape(c["explain"][:500])}</div></details>')

    if notes.get("cross_chapter_hints"):
        blocks.append("<h3>🔗 跨章链接</h3><ul>")
        for p in notes["cross_chapter_hints"][:15]:
            blocks.append(f"<li>{html_lib.escape(str(p))}</li>")
        blocks.append("</ul>")

    return "\n".join(blocks)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({startOnLoad: true, theme: 'default', securityLevel: 'loose'});</script>
<style>
  :root {
    --fg: #1f2937;
    --bg: #fdfbf6;
    --accent: #b08c4e;
    --card: #fff8e7;
    --border: #e5d8b6;
    --muted: #6b7280;
  }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    line-height: 1.7; color: var(--fg); background: var(--bg); margin: 0;
    max-width: 880px; margin: 0 auto; padding: 24px 18px 80px; }
  h1 { font-size: 26px; margin: 0 0 6px; }
  h2 { font-size: 20px; color: var(--accent); border-bottom: 2px solid var(--border); padding-bottom: 6px; margin-top: 36px; }
  h3 { font-size: 17px; margin-top: 24px; }
  .meta { color: var(--muted); font-size: 14px; margin-bottom: 18px; }
  .hook { font-size: 18px; color: var(--accent); font-style: italic; border-left: 4px solid var(--accent); padding: 8px 14px; margin: 18px 0; background: var(--card); }
  .callout { background: var(--card); padding: 12px 16px; border-left: 4px solid var(--accent); margin: 14px 0; border-radius: 6px; }
  details { background: #fff; border: 1px solid var(--border); padding: 6px 12px; border-radius: 6px; margin: 6px 0; }
  summary { cursor: pointer; padding: 4px 0; }
  .case-body { padding: 8px 0; color: #444; }
  ol, ul { padding-left: 24px; }
  li { margin: 6px 0; }
  table.tbl { border-collapse: collapse; width: 100%; font-size: 14px; }
  table.tbl th, table.tbl td { border: 1px solid var(--border); padding: 8px 10px; text-align: left; vertical-align: top; }
  table.tbl th { background: var(--card); }
  blockquote { border-left: 3px solid var(--border); padding: 4px 12px; color: #555; margin: 10px 0; }
  hr { border: none; border-top: 1px dashed var(--border); margin: 28px 0; }
  .nav { position: sticky; top: 0; background: var(--bg); padding: 8px 0; margin: -24px -18px 12px; padding: 8px 18px; border-bottom: 1px solid var(--border); z-index: 10; }
  .nav a { margin-right: 12px; color: var(--accent); text-decoration: none; }
  .nav a:hover { text-decoration: underline; }
  .figures { display: flex; flex-wrap: wrap; gap: 8px; }
  .figures img { max-width: 180px; max-height: 180px; border: 1px solid var(--border); border-radius: 4px; }
  .prompt-card { background: #f7f4eb; padding: 12px 14px; border-radius: 6px; margin: 8px 0; }
  .prompt-card pre { white-space: pre-wrap; word-break: break-word; background: #fff; padding: 8px; border-radius: 4px; font-family: inherit; }
  .copy-btn { background: var(--accent); color: #fff; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 13px; }
  .copy-btn:hover { background: #96764e; }
  .wrong-mark { margin-left: 8px; padding: 2px 8px; font-size: 12px; background: #f0e6d2; border: none; border-radius: 3px; cursor: pointer; }
  .wrong-list { background: #fff7e0; padding: 10px; border-left: 3px solid #d49a3d; margin: 8px 0; }
  .wrong-list li { font-size: 14px; }
  .graph-wrap { background: #fff; padding: 16px; border-radius: 6px; overflow: auto; border: 1px solid var(--border); }
  .mermaid { text-align: center; }

  /* ===== 阅读导航条（固定顶部） ===== */
  .readbar {
    position: sticky; top: 0; z-index: 100;
    display: flex; align-items: center; gap: 10px;
    background: rgba(253,251,246,.96); backdrop-filter: blur(8px);
    margin: -24px -18px 18px; padding: 10px 18px;
    border-bottom: 1px solid var(--border); font-size: 14px;
  }
  .readbar a, .readbar .nav-btn {
    color: var(--accent); text-decoration: none; padding: 4px 10px;
    border: 1px solid var(--border); border-radius: 6px; background: #fff;
    white-space: nowrap; transition: .15s;
  }
  .readbar a:hover { background: var(--card); }
  .readbar .nav-btn.disabled { color: #c8c2b4; background: transparent; border-color: transparent; cursor: default; }
  .readbar .nav-home { font-weight: 500; }
  .readbar .nav-pos { color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
  .readbar .nav-spacer { flex: 1; }

  /* ===== 原文置顶区 ===== */
  .raw-section {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 20px 24px; margin: 0 0 28px;
  }
  .raw-title { font-size: 15px; color: var(--accent); margin: 0 0 14px; font-weight: 500;
    letter-spacing: .08em; border: none; padding: 0; }
  .raw-body {
    font-family: "Songti SC", "STSong", "SimSun", Georgia, serif;
    font-size: 19px; line-height: 2.05; color: #2b2823; letter-spacing: .04em;
  }
  .raw-body p { margin: 0 0 12px; text-indent: 0; }
  .raw-body p:last-child { margin-bottom: 0; }

  /* ===== 术语表：桌面表格 / 手机卡片 ===== */
  .glossary-wrap .tbl { font-size: 14px; }
  .glossary-card { display: none; }

  @media (max-width: 720px) {
    body { padding: 14px 12px 70px; }
    h1 { font-size: 22px; }
    .figures img { max-width: 120px; }
    .readbar { margin: -14px -12px 16px; padding: 9px 12px; gap: 6px; font-size: 13px; }
    .readbar a, .readbar .nav-btn { padding: 4px 8px; font-size: 12.5px; }
    .readbar .nav-pos { display: none; }
    .raw-section { padding: 16px 16px; margin-bottom: 22px; }
    .raw-body { font-size: 17.5px; line-height: 1.95; letter-spacing: .02em; }

    /* 术语表：表格隐藏，改卡片 */
    .glossary-wrap .tbl { display: none; }
    .glossary-card { display: block; margin-bottom: 14px; }
    .gcard-term {
      font-family: "Songti SC", "STSong", serif; font-size: 17px;
      color: var(--accent); margin: 0 0 8px; padding-bottom: 6px;
      border-bottom: 1px solid var(--border);
    }
    .gcard-row { display: flex; gap: 8px; margin: 6px 0; font-size: 13.5px; line-height: 1.75; }
    .gcard-k {
      flex: 0 0 30px; font-weight: 600; color: var(--muted);
      font-size: 11.5px; letter-spacing: .04em; padding-top: 3px;
    }
    .gcard-v { flex: 1; color: #3a352c; }
    .gcard-row.l0 .gcard-v { color: #1f2937; }
  }
</style>
</head>
<body>

{nav_bar}

<h1>《{book}》</h1>
<div class="meta">
  {author} 著 · {chap_part} · {chap_label}
</div>
<div class="hook">“{__hook_present__}”</div>

{raw_text}

<div class="nav">
  <a href="#overview">📖 四步导读</a>
  <a href="#graph">🕸 知识图谱</a>
  <a href="#notes">📝 笔记</a>
  <a href="#socrates">🗣 苏格拉底</a>
  <a href="#glossary">📚 术语表</a>
  <a href="#wrongs">❓ 错题</a>
  <a href="#figures">🖼 插图</a>
</div>

<h2 id="overview">📖 四步导读</h2>
{overview_html}

<h2 id="graph">🕸 知识图谱</h2>
<p class="meta">鼠标拖动可看全图；点节点查看详情。</p>
<div class="graph-wrap">
<pre class="mermaid">
{graph_mmd}
</pre>
</div>

<h2 id="notes">📝 结构化笔记</h2>
{notes_html}

<h2 id="socrates">🗣 苏格拉底对话（章末）</h2>
<p class="meta">复制 prompt → 粘到任意对话 AI（workbuddy 也行）。你试完后点 "<b>这个我没答好</b>" 自动入错题本。</p>
<div id="socrates-list">
{socrates_html}
</div>
<div id="wrongs-section">
  <h2 id="wrongs">❓ 我的错题本</h2>
  <ul id="wrongs-list"></ul>
</div>

<h2 id="glossary">📚 术语表（L0-L3）</h2>
<p class="meta">L0 一句话 / L1 教材级 / L2 学术级 / L3 哲学反思</p>
{glossary_html}

<h2 id="figures">🖼 插图与原书页</h2>
{figures_html}

<hr/>
<details>
<summary><strong>📄 这章原始文本（前 6000 字）</strong></summary>
<pre style="white-space: pre-wrap; background: #fff; padding: 12px; border: 1px solid var(--border); border-radius: 4px; font-size: 13px;">{chapter_full_text}</pre>
</details>

<p class="meta" style="margin-top:36px;">
生成于 WorkBuddy 伴读系统 · 模型白名单：deepseek-v4-flash（推理强）+ doubao-seed-2.1-lite + glm-5.3 + kimi-k3 + MiniMax-M3。
禁用：任何 WorkBuddy 推荐/官方模型。
</p>

<script>
const STORE = '__WRONGS_STORE__';
function loadWrongs() {{
  try {{
    return JSON.parse(localStorage.getItem(STORE) || '[]');
  }} catch (e) {{ return []; }}
}}
function saveWrongs(arr) {{
  localStorage.setItem(STORE, JSON.stringify(arr));
  renderWrongs();
}}
function escapeHtml(s) {{
  return (s+'').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}
function renderWrongs() {{
  const arr = loadWrongs();
  const ul = document.getElementById('wrongs-list');
  if (arr.length === 0) {{
    ul.innerHTML = '<li style="color:#888;">还没有错题。</li>';
    return;
  }}
  ul.innerHTML = arr.map((w, i) =>
    '<li><strong>[' + (i+1) + ']</strong> ' +
    escapeHtml(w.text.slice(0, 200)) +
    ' <button class="copy-btn" data-i="' + i + '" style="background:#aaa;font-size:11px;padding:2px 6px;">删</button></li>'
  ).join('');
  ul.querySelectorAll('button[data-i]').forEach(b => {{
    b.onclick = () => {{ const a = loadWrongs(); a.splice(parseInt(b.dataset.i), 1); saveWrongs(a); }};
  }});
}}
function addWrong(text) {{
  const arr = loadWrongs();
  arr.push({{text: String(text).slice(0, 1000), ts: new Date().toISOString()}});
  saveWrongs(arr);
}}
window.addEventListener('DOMContentLoaded', () => {{
  renderWrongs();
  // 给苏格拉底区每个 prompt-card 加按钮（容错：没有时不报错）
  document.querySelectorAll('.prompt-card').forEach((card) => {{
    if (card.dataset.btnAttached) return;
    card.dataset.btnAttached = '1';
    const c = document.createElement('button');
    c.className = 'copy-btn';
    c.textContent = '复制 prompt';
    c.style.marginRight = '6px';
    c.onclick = () => {{
      const t = (card.querySelector('pre') && card.querySelector('pre').innerText) || card.innerText;
      navigator.clipboard.writeText(t).then(() => {{
        const old = c.textContent; c.textContent = '已复制 ✓';
        setTimeout(() => c.textContent = old, 1500);
      }});
    }};
    card.prepend(c);
    const w = document.createElement('button');
    w.className = 'wrong-mark';
    w.textContent = '我没答好';
    w.onclick = () => addWrong(card.innerText.replace('复制 prompt', '').trim());
    card.appendChild(w);
  }});
  document.querySelectorAll('#socrates-list li').forEach((li) => {{
    if (li.dataset.btnAttached) return;
    li.dataset.btnAttached = '1';
    const w = document.createElement('button');
    w.className = 'wrong-mark';
    w.textContent = '我没答好';
    w.onclick = () => addWrong(li.innerText.trim());
    li.appendChild(w);
  }});
}});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    chapter_dir = root / "outputs" / args.book / f"chapter_{args.chapter}"
    if not chapter_dir.exists():
        raise SystemExit(f"先跑 D1-D6：{chapter_dir}")

    out = build_chapter_site(chapter_dir, codes_root=root)
    print(f"✅ 单页 HTML：{out}")
    print()
    print("=" * 60)
    print("  🎉 个人马上可用 PoC v1 完成")
    print("=" * 60)
    print()
    print(f"👉 双击打开：")
    print(f"   {out}")
    print()
    print(f"📌 5 分钟自测：")
    print(f"   1) 进去导航到 '🕸 知识图谱'，对小白能 1 分钟说出'这章讲什么'")
    print(f"   2) 滚动到 '🗣 苏格拉底'，任选一个问题 → '复制 prompt' → 贴给我或别的 AI 试答")
    print(f"   3) 答不好就点 '我没答好' → 自动入错题本")
    print(f"   4) 看 '📚 术语表'，挑 2 个陌生概念看 L0 → 顺得下就 OK")


if __name__ == "__main__":
    main()
