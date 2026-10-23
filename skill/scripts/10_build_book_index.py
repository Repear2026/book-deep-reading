"""10_build_book_index.py — 生成书的总入口页。

输入：books.yaml + outputs/<book>/chapter_XX/notes.json + graph.mmd
输出：outputs/<book>/index.html（书的 cover + 14 章卡片 + 全书统计 + 跨章知识图谱）

页面要素：
- 顶部：书名/作者/章数/总笔记/总节点
- 全书知识图谱（合并 14 章去重）
- 章节卡片网格（14 张，每张：标题 + 笔记数 + 节点数 + 链接）
- 全书关键词云（汇总所有 new_concepts 高频）
- 全书人物 / 案例 一览
- 进度条（localStorage，跟踪每章完成度）
- 全书错题（localStorage，跨章汇总）
"""
from __future__ import annotations
import argparse, html as html_lib, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.book_config import load_books


def aggregate_chapter_stats(chapter_dir: Path) -> dict:
    """从一个章目录里抽取 stats：笔记条目数、节点数、关键概念、人物、案例。"""
    stats = {
        "note_count": 0,
        "node_count": 0,
        "concepts": [],
        "authors": [],
        "cases": [],
    }
    # notes
    np = chapter_dir / "notes" / "notes.json"
    if np.exists():
        nd = json.loads(np.read_text(encoding="utf-8"))
        stats["note_count"] = sum([
            len(nd.get("core_propositions") or []),
            len(nd.get("key_arguments") or []),
            len(nd.get("cases") or []),
            len(nd.get("new_concepts") or []),
            len(nd.get("cross_chapter_hints") or []),
            len(nd.get("suggested_socratic_questions") or []),
        ])
        from lib.normalize import concepts_of, cases_of
        for c in concepts_of(nd):
            if c["name"]:
                stats["concepts"].append(c["name"])
        for c in cases_of(nd):
            if c["name"]:
                stats["cases"].append(c["name"])
    # graph
    gp = chapter_dir / "graph" / "graph.mmd"
    if gp.exists():
        mmd = gp.read_text(encoding="utf-8")
        stats["node_count"] = len(re.findall(r"^\s*[\w_]+[\[\(\{]", mmd, flags=re.M))
        # 抓作者节点：a_<name> 或带括号的"人物"节点
        for m in re.findall(r"^\s*(\w+)\s*[\[\(\{]\s*[\(\"']?([^\"'\(\)]+)", mmd, flags=re.M):
            nid, label = m
            if nid.startswith("a_"):
                stats["authors"].append(label.strip())
    return stats


def aggregate_book_graph(chapter_dirs: list[Path], max_nodes: int = 50, max_edges: int = 100) -> str:
    """合并 14 章的 Mermaid 节点去重，输出限流后的全书 Mermaid 图。

    排序：按"被多少条边引用"降序，取 top max_nodes 节点；只保留这些节点之间的边。
    避免图过大渲染卡。
    """
    seen_nodes = {}    # id -> label
    seen_edges = set() # (src, label, dst) 去重

    for cd in chapter_dirs:
        gp = cd / "graph" / "graph.mmd"
        if not gp.exists():
            continue
        mmd = gp.read_text(encoding="utf-8")
        for line in mmd.split("\n"):
            line = line.rstrip()
            m = re.match(r"^\s*(\w+)\s*[\[\(\{]\s*[\(\"']?([^\"'\(\)]+)\s*[\"'\)\]\}]?", line)
            if m and not line.strip().startswith("flowchart") and "-->" not in line and "|" not in line:
                nid, label = m.group(1), m.group(2).strip()
                if nid in seen_nodes:
                    continue
                seen_nodes[nid] = label
            em = re.match(r"^\s*(\w+)\s*-->\|(\w+)\|\s*(\w+)\s*$", line)
            if em:
                src, lbl, dst = em.group(1), em.group(2), em.group(3)
                seen_edges.add((src, lbl, dst))

    # 计算每个节点的连接度（出+入）
    degree: dict[str, int] = {nid: 0 for nid in seen_nodes}
    for src, _, dst in seen_edges:
        if src in degree: degree[src] += 1
        if dst in degree: degree[dst] += 1

    # 取 top N 节点
    top_nodes = sorted(degree.items(), key=lambda x: -x[1])[:max_nodes]
    keep_set = {nid for nid, _ in top_nodes}

    # 只保留 keep 集合内的边
    keep_edges = [(s, l, d) for s, l, d in seen_edges if s in keep_set and d in keep_set]
    keep_edges = keep_edges[:max_edges]

    out = ["flowchart LR"]
    for nid, _ in top_nodes:
        label = seen_nodes[nid]
        out.append(f'    {nid}["{label}"]')
    out.append("")
    for src, lbl, dst in keep_edges:
        out.append(f"    {src} -->|{lbl}| {dst}")
    out.append("")
    out.append(f"%% Top {len(top_nodes)} 节点（按连接度） · {len(keep_edges)} 边")
    return "\n".join(out) + "\n"


def aggregate_top_concepts(all_chapters: list[dict], top_n: int = 30) -> list[tuple[str, int]]:
    """高频概念 top N。"""
    counter: dict[str, int] = {}
    for c in all_chapters:
        for term in c["stats"]["concepts"]:
            if not term:
                continue
            counter[term] = counter.get(term, 0) + 1
    return sorted(counter.items(), key=lambda x: -x[1])[:top_n]


def aggregate_top_authors(all_chapters: list[dict], top_n: int = 30) -> list[tuple[str, int]]:
    counter: dict[str, int] = {}
    for c in all_chapters:
        for name in c["stats"]["authors"]:
            if not name:
                continue
            counter[name] = counter.get(name, 0) + 1
    return sorted(counter.items(), key=lambda x: -x[1])[:top_n]


def build_index(book: dict, codes_root: Path) -> Path:
    book_id = book["id"]
    book_dir = codes_root / "outputs" / book_id
    chapter_dirs = sorted(book_dir.glob("chapter_*"), key=lambda p: p.name)

    # 收集每章 stats
    chap_data = []
    for cd in chapter_dirs:
        cid = cd.name.replace("chapter_", "")
        meta_path = cd / f"chapter_{cid}.yaml"
        chap_meta = {}
        if meta_path.exists():
            import yaml as _yaml
            chap_meta = _yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        stats = aggregate_chapter_stats(cd)
        chap_data.append({
            "id": cid,
            "label": chap_meta.get("chapter_label", f"第 {cid} 章"),
            "part": chap_meta.get("part", ""),
            "hook": chap_meta.get("hook", ""),
            "stats": stats,
            "url": f"chapter_{cid}/site/index.html",
            "site_exists": (cd / "site" / "index.html").exists(),
            "review_verdict": "",
        })
        # 读 review
        rj = cd / "review.json"
        if rj.exists():
            chap_data[-1]["review_verdict"] = json.loads(rj.read_text(encoding="utf-8")).get("verdict", "")

    # 聚合
    total_notes = sum(c["stats"]["note_count"] for c in chap_data)
    total_nodes = sum(c["stats"]["node_count"] for c in chap_data)
    top_concepts = aggregate_top_concepts(chap_data, top_n=30)
    top_authors = aggregate_top_authors(chap_data, top_n=30)
    full_graph = aggregate_book_graph(chapter_dirs)

    # 计算 book 的本地绝对路径（Windows 路径 → file:// URL）
    book_abs = book_dir.resolve()
    book_file_url = _to_file_url(book_abs)
    book_rel_to_html = ""  # 同目录，相对路径用空
    # 数据属性：JSON 化 chapter 卡片链接表，给 JS 用
    chap_links = [{"id": c["id"], "rel": c["url"], "abs": _to_file_url((book_dir / c["url"]).resolve())} for c in chap_data if c["site_exists"]]

    # HTML
    pass_count = sum(1 for c in chap_data if c["review_verdict"] == "PASS")
    html = HTML_TEMPLATE.format(
        title=f"《{book['title']}》 · 伴读总入口",
        book_title=html_lib.escape(book["title"]),
        author=html_lib.escape(book.get("author", "")),
        chapter_count=len(chap_data),
        total_notes=total_notes,
        total_nodes=total_nodes,
        pass_count=pass_count,
        pass_pct=int(pass_count * 100 / max(len(chap_data), 1)),
        chapter_cards_html=_render_chapter_cards(chap_data),
        top_concepts_html=_render_concept_cloud(top_concepts),
        top_authors_html=_render_author_list(top_authors),
        full_graph=full_graph,
        book_file_url=book_file_url,
        chap_links_json=json.dumps(chap_links, ensure_ascii=False),
    )

    out_path = book_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def _to_file_url(abs_path: Path) -> str:
    """Windows 路径 → file:/// URL（正向斜杠，drive letter 小写）。"""
    s = str(abs_path).replace("\\", "/")
    if not s.startswith("/"):
        s = "/" + s
    # drive letter 小写：/C:/... → /c:/...
    if len(s) >= 3 and s[1].isalpha() and s[2] == ":":
        s = s[0] + s[1].lower() + s[2:]
    return "file://" + s


def _search_blob(c: dict) -> str:
    """构造搜索索引：章号 + 章标题 + 概念名 + 命题片段（小写，供前端 includes 匹配）。"""
    parts = [c.get("id", ""), c.get("label", "")]
    parts.extend((c["stats"].get("concepts") or [])[:20])
    parts.extend((c["stats"].get("cases") or [])[:10])
    blob = " ".join(str(p) for p in parts if p)
    # 章号也支持"第8章"搜索
    try:
        parts.append(f"第{int(c.get('id', 0))}章")
    except Exception:
        pass
    return blob.lower()[:800]


def _render_chapter_cards(chap_data: list[dict]) -> str:
    parts = {}
    out = []
    for c in chap_data:
        part = c["part"] or "其他"
        parts.setdefault(part, []).append(c)

    for part, items in parts.items():
        out.append(f'<h3 class="part-head">📂 {html_lib.escape(part)}</h3>')
        out.append('<div class="cards">')
        for c in items:
            sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "": "❓"}.get(c["review_verdict"], "❓")
            note_n = c["stats"]["note_count"]
            node_n = c["stats"]["node_count"]
            if c["site_exists"]:
                link = f'<a href="{c["url"]}" data-chap="{c["id"]}" target="_blank">进入 →</a>'
            else:
                link = '<em style="color:#aaa">未生成</em>'
            hook = f'<blockquote class="hook">{html_lib.escape(c["hook"])}</blockquote>' if c["hook"] else ''
            out.append(f'''<div class="card" data-chapter="{c["id"]}"
     data-search="{html_lib.escape(_search_blob(c))}">
  <div class="card-title"><span class="status">{sym}</span> {html_lib.escape(c["label"])}</div>
  {hook}
  <div class="stats-row">
    <span>📝 {note_n} 笔记</span>
    <span>🕸 {node_n} 节点</span>
  </div>
  <div class="card-link">{link}</div>
  <button class="mark-read" data-chap="{c["id"]}">标记已读</button>
</div>''')
        out.append("</div>")
    return "\n".join(out)


def _render_concept_cloud(items: list[tuple[str, int]]) -> str:
    if not items:
        return "<p class='meta'>（本书暂无新概念统计）</p>"
    out = ['<div class="cloud">']
    for term, cnt in items:
        out.append(f'<span class="chip" title="出现 {cnt} 次">{html_lib.escape(term)}<i>{cnt}</i></span>')
    out.append("</div>")
    return "\n".join(out)


def _render_author_list(items: list[tuple[str, int]]) -> str:
    if not items:
        return "<p class='meta'>（本书暂无人物统计）</p>"
    out = ['<ul class="people-list">']
    for name, cnt in items:
        out.append(f"<li><strong>{html_lib.escape(name)}</strong> · 出现 {cnt} 次</li>")
    out.append("</ul>")
    return "\n".join(out)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad: true, theme: 'default', securityLevel: 'loose'}});</script>
<style>
  :root {{
    --fg: #1f2937;
    --bg: #fdfbf6;
    --accent: #b08c4e;
    --card: #fff8e7;
    --border: #e5d8b6;
    --muted: #6b7280;
    --good: #16a34a;
  }}
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    line-height: 1.7; color: var(--fg); background: var(--bg); margin: 0;
    max-width: 980px; margin: 0 auto; padding: 24px 18px 80px; }}
  header.book {{ background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 24px 28px; margin-bottom: 24px; }}
  h1 {{ font-size: 28px; margin: 0 0 6px; color: #10263c; }}
  h2 {{ font-size: 22px; color: var(--accent); border-bottom: 2px solid var(--border);
    padding-bottom: 6px; margin-top: 36px; }}
  h3.part-head {{ font-size: 16px; color: var(--muted); margin-top: 18px; font-weight: 500; }}
  .meta {{ color: var(--muted); font-size: 14px; margin: 4px 0; }}
  .badges {{ display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }}
  .badge {{ background: #fff; border: 1px solid var(--border);
    border-radius: 6px; padding: 6px 12px; font-size: 14px; }}
  .badge b {{ color: var(--accent); font-size: 18px; margin-right: 4px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px; margin: 14px 0; }}
  .card {{ background: #fff; border: 1px solid var(--border);
    border-radius: 8px; padding: 12px 16px; transition: 0.2s; }}
  .card:hover {{ box-shadow: 0 4px 14px rgba(0,0,0,0.05); transform: translateY(-1px); }}
  .card.read {{ background: #f0fdf4; border-left: 3px solid var(--good); }}
  .card-title {{ font-size: 15px; font-weight: 500; margin-bottom: 4px; }}
  .ch-filter {{ display: flex; align-items: center; gap: 12px; margin: 10px 0 4px; flex-wrap: wrap; }}
  .ch-filter input {{
    flex: 1; min-width: 200px; max-width: 420px; padding: 8px 14px;
    border: 1px solid var(--border); border-radius: 20px; background: #fff;
    color: var(--fg); font-size: 14px; outline: none; transition: .2s;
  }}
  .ch-filter input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px rgba(176,140,78,.1); }}
  .status {{ margin-right: 4px; }}
  .card blockquote.hook {{ font-size: 13px; color: #555; font-style: italic;
    border-left: 3px solid var(--border); margin: 8px 0; padding: 4px 10px; }}
  .stats-row {{ font-size: 12px; color: var(--muted); display: flex; gap: 14px; margin: 6px 0; }}
  .card-link a {{ color: var(--accent); text-decoration: none; font-size: 14px; }}
  .card-link a:hover {{ text-decoration: underline; }}
  .preview-banner {{ background: #fff7e0; border: 1px solid #e5c97a; border-radius: 8px;
    padding: 12px 16px; margin-bottom: 18px; font-size: 14px; line-height: 1.8; }}
  .preview-banner code {{ background: #fff; padding: 2px 6px; border-radius: 3px;
    font-size: 12px; word-break: break-all; }}
  .mark-read {{ float: right; background: transparent; border: 1px solid var(--border);
    color: var(--muted); padding: 2px 8px; font-size: 12px; border-radius: 3px;
    cursor: pointer; }}
  .mark-read:hover {{ background: var(--good); color: #fff; border-color: var(--good); }}
  .cloud {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .chip {{ display: inline-flex; align-items: center; gap: 4px;
    background: var(--card); border: 1px solid var(--border); border-radius: 14px;
    padding: 3px 10px; font-size: 13px; }}
  .chip i {{ color: var(--accent); font-style: normal; font-size: 11px; font-weight: 600; }}
  .people-list {{ list-style: none; padding: 0; column-count: 3; column-gap: 24px; }}
  .people-list li {{ padding: 4px 0; font-size: 14px; break-inside: avoid; }}
  .progress-wrap {{ background: #fff; border: 1px solid var(--border);
    border-radius: 6px; padding: 14px 18px; margin: 18px 0; }}
  .progress-bar {{ height: 12px; background: var(--border); border-radius: 6px;
    overflow: hidden; margin: 6px 0; }}
  .progress-fill {{ height: 100%; background: var(--good);
    transition: width 0.4s; }}
  .graph-wrap {{ background: #fff; padding: 16px; border-radius: 6px;
    overflow: auto; border: 1px solid var(--border); max-height: 600px; }}
  .mermaid {{ text-align: center; }}
  .nav {{ position: sticky; top: 0; background: var(--bg); padding: 8px 0;
    margin: -24px -18px 12px; padding: 8px 18px; border-bottom: 1px solid var(--border);
    z-index: 10; font-size: 14px; }}
  .nav a {{ margin-right: 12px; color: var(--accent); text-decoration: none; }}
  .nav a:hover {{ text-decoration: underline; }}
  hr {{ border: none; border-top: 1px dashed var(--border); margin: 28px 0; }}
  @media (max-width: 600px) {{
    body {{ padding: 14px 10px; }}
    h1 {{ font-size: 22px; }}
    .people-list {{ column-count: 1; }}
  }}
</style>
</head>
<body>

<div class="nav">
  <a href="#chapter-list">📚 章节</a>
  <a href="#full-graph">🕸 全书图谱</a>
  <a href="#concepts">💡 概念云</a>
  <a href="#people">👥 人物</a>
  <a href="#wrongs">❓ 错题</a>
</div>

<header class="book">
  <h1>📖 {book_title}</h1>
  <p class="meta">{author} 著</p>
  <div class="badges">
    <div class="badge"><b>{chapter_count}</b>章</div>
    <div class="badge"><b>{total_notes}</b>条笔记</div>
    <div class="badge"><b>{total_nodes}</b>节点</div>
    <div class="badge" style="background:#dcfce7;border-color:#86efac"><b>{pass_count}/{chapter_count}</b> PASS · {pass_pct}%</div>
  </div>
</header>

<div class="progress-wrap">
  <div class="meta">📖 阅读进度（本地存储，可点"标记已读"累加）</div>
  <div class="progress-bar"><div class="progress-fill" id="prog-fill" style="width:0%"></div></div>
  <p class="meta"><span id="prog-text">0 / {chapter_count} 章已读</span></p>
</div>

<h2 id="chapter-list">📚 章节列表</h2>
<div class="ch-filter">
  <input id="ch-search" type="search" placeholder="搜章号或关键词（如 水 / 无为 / 8），按 / 聚焦" autocomplete="off"/>
  <span id="ch-count" class="meta"></span>
</div>
{chapter_cards_html}

<h2 id="full-graph">🕸 全书知识图谱（合并）</h2>
<p class="meta">14 章 Mermaid 节点去重合并。节点数 = 合并去重后的唯一节点。边去重后保留。</p>
<div class="graph-wrap">
<pre class="mermaid">
{full_graph}
</pre>
</div>

<h2 id="concepts">💡 全书关键概念云</h2>
<p class="meta">概念后数字 = 跨章出现次数。点击不放高亮。</p>
{top_concepts_html}

<h2 id="people">👥 全书人物 / 案例</h2>
{top_authors_html}

<h2 id="wrongs">❓ 全书错题本</h2>
<p class="meta">localStorage 跨章汇总。</p>
<ul id="wrongs-list"></ul>

<hr/>
<p class="meta">
本书总入口页 · 模型白名单：deepseek-v4-flash（推理强）+ doubao-seed-2.1-lite + glm-5.3 + kimi-k3 + MiniMax-M3。
禁用：任何 WorkBuddy 推荐/官方模型。
</p>

<script>
const BOOK_ID = '{title}';
const STORE_PROG = BOOK_ID + '_progress';
const STORE_WRONG = BOOK_ID + '_wrongs';

function loadProgress() {{
  try {{ return JSON.parse(localStorage.getItem(STORE_PROG) || '{{}}'); }} catch (e) {{ return {{}}; }}
}}
function saveProgress(p) {{ localStorage.setItem(STORE_PROG, JSON.stringify(p)); renderProgress(); }}
function renderProgress() {{
  const p = loadProgress();
  const done = Object.values(p).filter(Boolean).length;
  const total = document.querySelectorAll('.card').length;
  const pct = total ? Math.round(done * 100 / total) : 0;
  document.getElementById('prog-fill').style.width = pct + '%';
  document.getElementById('prog-text').textContent = done + ' / ' + total + ' 章已读（' + pct + '%）';
  document.querySelectorAll('.card').forEach(c => {{
    const cid = c.dataset.chapter;
    if (p[cid]) c.classList.add('read');
    else c.classList.remove('read');
  }});
}}
function loadWrongs() {{
  try {{ return JSON.parse(localStorage.getItem(STORE_WRONG) || '[]'); }} catch (e) {{ return []; }}
}}
function saveWrongs(arr) {{ localStorage.setItem(STORE_WRONG, JSON.stringify(arr)); renderWrongs(); }}
function renderWrongs() {{
  const arr = loadWrongs();
  const ul = document.getElementById('wrongs-list');
  if (arr.length === 0) {{
    ul.innerHTML = '<li style="color:#888">还没有错题。</li>';
    return;
  }}
  ul.innerHTML = arr.map((w, i) =>
    '<li><strong>[' + (i+1) + ']</strong> ' + escapeHtml(w.text.slice(0, 200)) +
    ' <em style="color:#888">(' + (w.chap || '?') + ')</em>' +
    ' <button data-i="' + i + '" style="background:#aaa;font-size:11px;padding:2px 6px;">删</button></li>'
  ).join('');
  ul.querySelectorAll('button[data-i]').forEach(b => {{
    b.onclick = () => {{ const a = loadWrongs(); a.splice(parseInt(b.dataset.i), 1); saveWrongs(a); }};
  }});
}}
function escapeHtml(s) {{
  return (s+'').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}
// 跨协议链接路由：workbuddy preview 面板（http://）点不开 file:// 之外的相对路径
// 链接策略：
//   ① 本地双击（file://）→ 相对路径天然可用
//   ② 本地 http server → 相对路径可用
//   ③ WorkBuddy 单文件预览（http://127.0.0.1:.../static-html/<hash>/）→ 相对路径解析不到，浏览器也禁止 http→file
//      → 只能提示用户改用 ①②
const CHAP_LINKS = {chap_links_json};
const BOOK_FILE_URL = '{book_file_url}';

window.addEventListener('DOMContentLoaded', () => {{
  renderProgress();
  renderWrongs();

  // ===== 章节搜索 =====
  const chSearch = document.getElementById('ch-search');
  const chCount = document.getElementById('ch-count');
  const allCards = Array.from(document.querySelectorAll('.card'));
  function applyChFilter() {{
    const q = (chSearch.value || '').trim().toLowerCase();
    let shown = 0;
    allCards.forEach(c => {{
      const hit = !q || (c.dataset.search || '').includes(q);
      c.style.display = hit ? '' : 'none';
      if (hit) shown++;
    }});
    // 部分标题（部分组）无可见卡片时隐藏
    document.querySelectorAll('.part-head').forEach(h => {{
      let sib = h.nextElementSibling, any = false;
      while (sib && (sib.classList.contains('cards'))) {{
        if (Array.from(sib.querySelectorAll('.card')).some(x => x.style.display !== 'none')) any = true;
        sib = sib.nextElementSibling;
      }}
      h.style.display = (q && !any) ? 'none' : '';
    }});
    chCount.textContent = q ? ('匹配 ' + shown + ' / ' + allCards.length + ' 章') : ('共 ' + allCards.length + ' 章');
  }}
  if (chSearch) {{
    chSearch.addEventListener('input', applyChFilter);
    applyChFilter();
    document.addEventListener('keydown', e => {{
      if (e.key === '/' && document.activeElement !== chSearch) {{ e.preventDefault(); chSearch.focus(); }}
      if (e.key === 'Escape' && document.activeElement === chSearch) {{
        chSearch.value = ''; applyChFilter(); chSearch.blur();
      }}
    }});
  }}

  document.querySelectorAll('.mark-read').forEach(b => {{
    b.onclick = () => {{
      const cid = b.dataset.chap;
      const p = loadProgress();
      p[cid] = !p[cid];
      saveProgress(p);
    }};
  }});
  // 章节卡链接：显式标目标章节 id（提示用）
  document.querySelectorAll('.card-link a[data-chap]').forEach(a => {{
    const cid = a.dataset.chap;
    const target = CHAP_LINKS.find(c => c.id === cid);
    if (target) a.title = '打开：' + target.rel;
  }});
  // WorkBuddy 单文件预览：相对路径失效，给引导
  const isStaticHtmlPreview = /\\/static-html\\//.test(location.pathname);
  if (isStaticHtmlPreview) {{
    const banner = document.createElement('div');
    banner.className = 'preview-banner';
    banner.innerHTML =
      '<strong>📌 当前是 WorkBuddy 单文件预览，章节链接在此环境无法跳转</strong><br/>' +
      '请任选其一：<br/>' +
      '① 浏览器打开本地服务器：<code id="srv-url">启动中…</code><br/>' +
      '② 或直接双击本地文件：<code>' + BOOK_FILE_URL + '/index.html</code>';
    document.body.insertBefore(banner, document.body.firstChild);
    // 探测常见的本地服务器端口
    ['8123', '8000', '8080'].forEach(p => {{
      fetch('http://127.0.0.1:' + p + '/index.html', {{method: 'HEAD'}})
        .then(r => {{ if (r.ok) {{ const el = document.getElementById('srv-url'); if (el) el.textContent = 'http://127.0.0.1:' + p + '/index.html'; }} }})
        .catch(() => {{}});
    }});
  }}
}});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    books = load_books(root / "config" / "books.yaml")
    book = next((b for b in books if b["id"] == args.book), None)
    if book is None:
        raise SystemExit(f"找不到书 id={args.book}")

    out = build_index(book, root)
    print(f"✅ 书的总入口页：{out}")


if __name__ == "__main__":
    main()
