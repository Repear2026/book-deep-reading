"""12_build_library.py — 生成"私人图书馆"总入口（多本书书架）。

输入：
  - config/books.yaml（所有书 + 分类/标签/简介，字段可选）
  - outputs/<book_id>/chapter_XX/（实际产物，用来算完成度）
  - outputs/<book_id>/index.html（书入口，存在则可点）

输出：outputs/index.html（书架页）

设计：
  - 学科分类 tab（按 yaml 的 category，缺省归"未分类"）
  - 每本书：书脊色块 + 书名 + 作者 + 章数/笔记/节点 + 完成度环 + 继续阅读
  - 三视图：网格 / 列表 / 时间线
  - 全局搜索（书名/作者/标签）
  - 深色模式（localStorage 记忆）
  - 跨书阅读进度（localStorage：book_<id>_last_chapter）
"""
from __future__ import annotations
import argparse, hashlib, html as html_lib, json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.book_config import load_books

# 预设书脊色板（纸质书调性：赭石/靛青/苔绿/绛紫/墨蓝/赤陶/橄榄/暗金）
SPINE_PALETTE = [
    "#8B6F47",  # 赭石
    "#3D5A80",  # 靛青
    "#5A7D5A",  # 苔绿
    "#7D4E57",  # 绛紫
    "#2E4756",  # 墨蓝
    "#A9673C",  # 赤陶
    "#6B7B48",  # 橄榄
    "#9C8148",  # 暗金
]


def pick_color(book: dict) -> str:
    """书脊色：yaml 指定优先，否则按 id hash 从色板取。"""
    if book.get("cover_color"):
        return book["cover_color"]
    h = int(hashlib.md5(book["id"].encode("utf-8")).hexdigest(), 16)
    return SPINE_PALETTE[h % len(SPINE_PALETTE)]


def scan_book_progress(book_dir: Path, chapter_total: int) -> dict:
    """扫一本书的实际产物，算完成度。"""
    stats = {
        "chapters_done": 0,
        "notes_total": 0,
        "nodes_total": 0,
        "has_index": (book_dir / "index.html").exists(),
        "figures_total": 0,
    }
    if not book_dir.exists():
        return stats

    for cd in sorted(book_dir.glob("chapter_*")):
        site_ok = (cd / "site" / "index.html").exists()
        if site_ok:
            stats["chapters_done"] += 1
        nj = cd / "notes" / "notes.json"
        if nj.exists():
            try:
                nd = json.loads(nj.read_text(encoding="utf-8"))
                stats["notes_total"] += sum(
                    len(nd.get(k) or [])
                    for k in [
                        "core_propositions", "key_arguments", "cases",
                        "new_concepts", "cross_chapter_hints", "suggested_socratic_questions",
                    ]
                )
            except Exception:
                pass
        gj = cd / "graph" / "graph.mmd"
        if gj.exists():
            stats["nodes_total"] += len(
                re.findall(r"^\s*[\w_]+[\[\(\{]", gj.read_text(encoding="utf-8"), flags=re.M)
            )
        figs = cd / "figures"
        if figs.exists():
            stats["figures_total"] += len(list(figs.glob("*.png")))
    return stats


def collect_books(books: list[dict], bookstore: Path) -> list[dict]:
    """把 yaml + 实际产物合并成书架数据。"""
    out = []
    for b in books:
        bid = b["id"]
        bdir = bookstore / bid
        chapters_total = len(b.get("chapters") or [])
        prog = scan_book_progress(bdir, chapters_total)
        # 完成度（按有 index.html 的章节数 / 总章数）
        pct = int(round(prog["chapters_done"] * 100 / chapters_total)) if chapters_total else 0
        out.append({
            "id": bid,
            "title": b.get("title", bid),
            "author": b.get("author", ""),
            "publisher": b.get("publisher", ""),
            "year": b.get("year", ""),
            "category": b.get("category", "未分类"),
            "tags": b.get("tags") or [],
            "description": b.get("description", ""),
            "color": pick_color(b),
            "chapters_total": chapters_total,
            "chapters_done": prog["chapters_done"],
            "notes_total": prog["notes_total"],
            "nodes_total": prog["nodes_total"],
            "figures_total": prog["figures_total"],
            "pct": pct,
            "has_index": prog["has_index"],
            "url": f"{bid}/index.html" if prog["has_index"] else "",
            "status": "done" if (chapters_total and prog["chapters_done"] >= chapters_total) else ("wip" if prog["chapters_done"] > 0 else "todo"),
        })
    # 排序：已完工 → 进行中 → 待处理；同状态按书名字数/拼音
    order = {"done": 0, "wip": 1, "todo": 2}
    out.sort(key=lambda x: (order.get(x["status"], 9), x["title"]))
    return out


def build_library(books_data: list[dict]) -> str:
    total_books = len(books_data)
    total_notes = sum(b["notes_total"] for b in books_data)
    total_nodes = sum(b["nodes_total"] for b in books_data)
    done_books = sum(1 for b in books_data if b["status"] == "done")
    chapters_all = sum(b["chapters_done"] for b in books_data)

    # 分类 tab
    cats: dict[str, int] = {}
    for b in books_data:
        cats[b["category"]] = cats.get(b["category"], 0) + 1
    # 按数量降序，'未分类' 最后
    cat_list = sorted(cats.items(), key=lambda kv: (kv[0] == "未分类", -kv[1], kv[0]))
    cat_tabs = "".join(
        f'<button class="cat-tab{" active" if i == 0 else ""}" data-cat="{html_lib.escape(c)}">'
        f'{html_lib.escape(c)} <i>{n}</i></button>'
        for i, (c, n) in enumerate([("全部", total_books)] + cat_list)
    )

    cards = "\n".join(_render_book_card(b) for b in books_data)
    empty_hint = ""
    if total_books <= 1:
        empty_hint = """
<div class="add-hint">
  <div class="add-hint-icon">＋</div>
  <div>
    <strong>再加一本书</strong>
    <p>把新书的 PDF 放进 <code>code/inputs/</code>，在 <code>config/books.yaml</code> 加一段配置，跑流水线即可自动出现在这里。</p>
  </div>
</div>"""

    return HTML_TEMPLATE.format(
        total_books=total_books,
        done_books=done_books,
        total_notes=total_notes,
        total_nodes=total_nodes,
        chapters_all=chapters_all,
        cat_tabs=cat_tabs,
        cards=cards,
        empty_hint=empty_hint,
        books_json=json.dumps(books_data, ensure_ascii=False),
        gen_time=time.strftime("%Y-%m-%d %H:%M"),
    )


def _render_book_card(b: dict) -> str:
    status_badge = {
        "done": '<span class="badge badge-done">已完工</span>',
        "wip": f'<span class="badge badge-wip">进行中 {b["chapters_done"]}/{b["chapters_total"]}</span>',
        "todo": '<span class="badge badge-todo">待处理</span>',
    }.get(b["status"], "")

    tags_html = "".join(f'<span class="tag">{html_lib.escape(t)}</span>' for t in b["tags"][:4])
    desc = b["description"] or (f"《{b['title']}》共 {b['chapters_total']} 章，已完成 {b['chapters_done']} 章的结构化解析。")

    # 环形进度 SVG
    r = 16
    circ = 2 * 3.14159 * r
    dash = circ * b["pct"] / 100
    ring = f'''<svg class="ring" viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="{r}" fill="none" stroke="#e8dfc8" stroke-width="4"/>
      <circle cx="20" cy="20" r="{r}" fill="none" stroke="{b["color"]}" stroke-width="4"
        stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-linecap="round"
        transform="rotate(-90 20 20)"/>
      <text x="20" y="24" text-anchor="middle" font-size="11" fill="#5a5245">{b["pct"]}%</text>
    </svg>'''

    if b["has_index"]:
        action = f'<a class="btn-open" href="{b["url"]}">进入阅读 →</a>'
    elif b["chapters_done"] > 0:
        action = '<em class="btn-pending">入口待生成</em>'
    else:
        action = '<em class="btn-pending">尚未解析</em>'

    return f'''<article class="book-card" data-id="{b["id"]}" data-cat="{html_lib.escape(b["category"])}"
  data-search="{html_lib.escape((b["title"] + " " + b["author"] + " " + " ".join(b["tags"])).lower())}"
  style="--spine:{b["color"]}">
  <div class="spine"></div>
  <div class="card-body">
    <div class="card-head">
      <div class="title-wrap">
        <h3>{html_lib.escape(b["title"])}</h3>
        <p class="author">{html_lib.escape(b["author"])}{(" · " + html_lib.escape(b["publisher"])) if b["publisher"] else ""}</p>
      </div>
      {ring}
    </div>
    <div class="badges-row">{status_badge}{tags_html}</div>
    <p class="desc">{html_lib.escape(desc)}</p>
    <div class="metrics">
      <span><b>{b["chapters_done"]}</b>/{b["chapters_total"]} 章</span>
      <span><b>{b["notes_total"]}</b> 笔记</span>
      <span><b>{b["nodes_total"]}</b> 节点</span>
    </div>
    <div class="progress-line"><i style="width:{b["pct"]}%"></i></div>
    <div class="card-foot">
      {action}
      <button class="btn-resume" data-id="{b["id"]}" hidden>继续阅读</button>
    </div>
  </div>
</article>'''


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>我的图书馆 · 深度伴读</title>
<style>
  :root {{
    --bg: #fbf8f1;
    --bg-card: #fffdf8;
    --fg: #2b2823;
    --fg-soft: #5a5245;
    --fg-mute: #8a8172;
    --line: #e8dfc8;
    --line-soft: #f0e9d8;
    --accent: #8B6F47;
    --shadow: 0 1px 2px rgba(120,100,70,.06), 0 8px 24px -12px rgba(120,100,70,.18);
  }}
  html.dark {{
    --bg: #1a1815;
    --bg-card: #24211c;
    --fg: #ebe4d6;
    --fg-soft: #b9ae9a;
    --fg-mute: #8a8172;
    --line: #3a352c;
    --line-soft: #2c2822;
    --accent: #c9a86a;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px -12px rgba(0,0,0,.5);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--fg);
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    line-height: 1.65; -webkit-font-smoothing: antialiased;
    transition: background .3s, color .3s;
  }}
  /* 纸质纹理感（极淡噪点） */
  body::before {{
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image: radial-gradient(rgba(140,120,90,.055) 1px, transparent 1px);
    background-size: 3px 3px; opacity: .6;
  }}
  .wrap {{ position: relative; z-index: 1; max-width: 1080px; margin: 0 auto; padding: 0 20px 80px; }}

  /* ===== 顶部 ===== */
  header.hero {{ padding: 44px 0 20px; }}
  .hero-top {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }}
  h1 {{
    font-family: "Songti SC", "STSong", "SimSun", Georgia, serif;
    font-size: 34px; font-weight: 600; letter-spacing: .06em;
    margin: 0 0 6px; color: var(--fg);
  }}
  .subtitle {{ color: var(--fg-mute); font-size: 14px; letter-spacing: .04em; margin: 0; }}
  .hero-actions {{ display: flex; gap: 8px; }}
  .icon-btn {{
    background: var(--bg-card); border: 1px solid var(--line); color: var(--fg-soft);
    width: 38px; height: 38px; border-radius: 10px; cursor: pointer; font-size: 16px;
    display: grid; place-items: center; transition: .2s;
  }}
  .icon-btn:hover {{ border-color: var(--accent); color: var(--accent); transform: translateY(-1px); }}

  /* 统计条 */
  .stats {{ display: flex; gap: 28px; margin-top: 22px; flex-wrap: wrap; }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat b {{
    font-family: Georgia, serif; font-size: 26px; font-weight: 600; color: var(--accent);
    line-height: 1.1;
  }}
  .stat span {{ font-size: 12px; color: var(--fg-mute); letter-spacing: .08em; }}

  /* ===== 工具条（分类 + 搜索 + 视图） ===== */
  .toolbar {{
    position: sticky; top: 0; z-index: 20;
    display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
    padding: 14px 0; margin: 20px 0 8px;
    background: linear-gradient(to bottom, var(--bg) 78%, transparent);
    border-bottom: 1px solid var(--line-soft);
  }}
  .cat-tabs {{ display: flex; gap: 6px; flex-wrap: wrap; flex: 1; }}
  .cat-tab {{
    background: transparent; border: 1px solid transparent; color: var(--fg-mute);
    padding: 6px 13px; border-radius: 20px; cursor: pointer; font-size: 13.5px;
    transition: .18s; white-space: nowrap;
  }}
  .cat-tab:hover {{ color: var(--fg); background: var(--line-soft); }}
  .cat-tab.active {{ background: var(--fg); color: var(--bg); border-color: var(--fg); }}
  .cat-tab i {{ font-style: normal; opacity: .55; margin-left: 3px; font-size: 11px; }}

  .search-box {{ position: relative; }}
  .search-box input {{
    width: 168px; padding: 7px 12px 7px 32px; border-radius: 20px;
    border: 1px solid var(--line); background: var(--bg-card); color: var(--fg);
    font-size: 13.5px; outline: none; transition: .2s;
  }}
  .search-box input:focus {{ width: 220px; border-color: var(--accent); }}
  .search-box::before {{
    content: "⌕"; position: absolute; left: 12px; top: 50%; transform: translateY(-52%);
    color: var(--fg-mute); font-size: 16px; pointer-events: none;
  }}
  .view-switch {{ display: flex; border: 1px solid var(--line); border-radius: 20px; overflow: hidden; }}
  .view-switch button {{
    background: transparent; border: none; color: var(--fg-mute);
    padding: 6px 11px; cursor: pointer; font-size: 13px; transition: .18s;
  }}
  .view-switch button.active {{ background: var(--fg); color: var(--bg); }}

  /* ===== 书架网格 ===== */
  .shelf {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 18px; margin-top: 22px;
  }}
  .book-card {{
    position: relative; display: flex; background: var(--bg-card);
    border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
    box-shadow: var(--shadow); transition: transform .22s cubic-bezier(.2,.7,.3,1), box-shadow .22s;
  }}
  .book-card:hover {{ transform: translateY(-3px); box-shadow: 0 4px 8px rgba(120,100,70,.08), 0 16px 36px -14px rgba(120,100,70,.3); }}
  .spine {{
    width: 7px; flex: 0 0 7px; background: var(--spine);
    box-shadow: inset -1px 0 0 rgba(0,0,0,.12);
  }}
  .card-body {{ flex: 1; padding: 16px 18px 14px; display: flex; flex-direction: column; min-width: 0; }}
  .card-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
  .title-wrap {{ min-width: 0; }}
  .book-card h3 {{
    font-family: "Songti SC", "STSong", "SimSun", Georgia, serif;
    font-size: 18px; font-weight: 600; margin: 0 0 3px; line-height: 1.35;
    color: var(--fg); letter-spacing: .015em;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }}
  .author {{ margin: 0; font-size: 12.5px; color: var(--fg-mute); }}
  .ring {{ width: 42px; height: 42px; flex: 0 0 42px; }}

  .badges-row {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 10px 0 8px; align-items: center; }}
  .badge {{ font-size: 11px; padding: 2px 8px; border-radius: 4px; letter-spacing: .04em; }}
  .badge-done {{ background: #e6f0e2; color: #3f6b3a; }}
  .badge-wip {{ background: #fdf1dc; color: #8a6320; }}
  .badge-todo {{ background: #f0ece4; color: #7a7266; }}
  html.dark .badge-done {{ background: #2e3d2b; color: #a8c9a0; }}
  html.dark .badge-wip {{ background: #3d3222; color: #d9b979; }}
  html.dark .badge-todo {{ background: #2e2a24; color: #9a9082; }}
  .tag {{ font-size: 11px; color: var(--fg-mute); border: 1px solid var(--line); padding: 1px 7px; border-radius: 4px; }}

  .desc {{
    font-size: 13px; color: var(--fg-soft); margin: 0 0 12px; line-height: 1.6;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }}
  .metrics {{ display: flex; gap: 16px; font-size: 12px; color: var(--fg-mute); margin-bottom: 10px; }}
  .metrics b {{ color: var(--fg-soft); font-weight: 600; }}
  .progress-line {{ height: 3px; background: var(--line-soft); border-radius: 2px; overflow: hidden; margin-bottom: 12px; }}
  .progress-line i {{ display: block; height: 100%; background: var(--spine); border-radius: 2px; transition: width .5s; }}
  .card-foot {{ display: flex; justify-content: space-between; align-items: center; margin-top: auto; }}
  .btn-open {{
    color: var(--accent); text-decoration: none; font-size: 13.5px; font-weight: 500;
    padding: 5px 0; transition: .2s;
  }}
  .btn-open:hover {{ letter-spacing: .03em; }}
  .btn-pending {{ color: var(--fg-mute); font-size: 13px; font-style: normal; }}
  .btn-resume {{
    background: var(--accent); color: #fff; border: none; padding: 5px 12px;
    border-radius: 6px; font-size: 12.5px; cursor: pointer;
  }}

  /* 列表视图 */
  .shelf.list {{ display: flex; flex-direction: column; gap: 10px; }}
  .shelf.list .book-card {{ border-radius: 8px; }}
  .shelf.list .card-body {{ padding: 12px 16px; }}
  .shelf.list .desc, .shelf.list .progress-line, .shelf.list .ring {{ display: none; }}
  .shelf.list .book-card h3 {{ font-size: 16px; -webkit-line-clamp: 1; }}
  .shelf.list .metrics {{ margin-bottom: 0; margin-top: 6px; }}
  .shelf.list .card-foot {{ position: absolute; right: 16px; bottom: 12px; }}
  .shelf.list .badges-row {{ margin: 6px 0 0; }}

  /* 时间线视图 */
  .shelf.timeline {{ display: block; }}
  .shelf.timeline .book-card {{ margin-bottom: 14px; border-left: 3px solid var(--spine); }}

  /* 空态 / 引导 */
  .add-hint {{
    display: flex; gap: 16px; align-items: center; margin-top: 30px;
    border: 1px dashed var(--line); border-radius: 12px; padding: 22px;
    background: var(--bg-card);
  }}
  .add-hint-icon {{
    font-size: 26px; color: var(--accent); width: 52px; height: 52px;
    display: grid; place-items: center; border: 1px solid var(--line); border-radius: 12px;
  }}
  .add-hint strong {{ font-size: 15px; }}
  .add-hint p {{ margin: 4px 0 0; font-size: 13px; color: var(--fg-mute); }}
  .add-hint code {{ background: var(--line-soft); padding: 1px 5px; border-radius: 3px; font-size: 12px; }}

  .no-result {{ text-align: center; color: var(--fg-mute); padding: 60px 0; font-size: 14px; display: none; }}

  footer {{ margin-top: 50px; padding-top: 18px; border-top: 1px solid var(--line-soft);
    font-size: 12px; color: var(--fg-mute); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}

  @media (max-width: 620px) {{
    h1 {{ font-size: 26px; }}
    .hero {{ padding: 28px 0 14px; }}
    .stats {{ gap: 20px; }}
    .stat b {{ font-size: 22px; }}
    .shelf {{ grid-template-columns: 1fr; }}
    .search-box input {{ width: 120px; }}
    .search-box input:focus {{ width: 150px; }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <header class="hero">
    <div class="hero-top">
      <div>
        <h1>我的图书馆</h1>
        <p class="subtitle">深度伴读 · 每本书 14 步结构化拆解</p>
      </div>
      <div class="hero-actions">
        <button class="icon-btn" id="theme-toggle" title="切换深色/浅色">◐</button>
      </div>
    </div>
    <div class="stats">
      <div class="stat"><b>{total_books}</b><span>本书</span></div>
      <div class="stat"><b>{done_books}</b><span>已完工</span></div>
      <div class="stat"><b>{chapters_all}</b><span>章已解析</span></div>
      <div class="stat"><b>{total_notes}</b><span>笔记条目</span></div>
      <div class="stat"><b>{total_nodes}</b><span>知识节点</span></div>
    </div>
  </header>

  <div class="toolbar">
    <div class="cat-tabs">{cat_tabs}</div>
    <div class="search-box"><input id="search" placeholder="搜书名 / 作者 / 标签，/ 聚焦" autocomplete="off"/></div>
    <div class="view-switch">
      <button data-view="grid" class="active" title="网格">▦</button>
      <button data-view="list" title="列表">☰</button>
      <button data-view="timeline" title="时间线">⌛</button>
    </div>
  </div>

  <main class="shelf grid" id="shelf">
{cards}
  </main>
  <div class="no-result" id="no-result">没有匹配的书。</div>
  {empty_hint}

  <footer>
    <span>生成于 {gen_time} · 模型白名单 deepseek-v4-flash 等 5 个</span>
    <span>{total_books} 本书 · 双击本地 index.html 或访问公网链接</span>
  </footer>
</div>

<script>
const BOOKS = {books_json};

/* ---------- 深色模式 ---------- */
const THEME_KEY = 'library_theme';
function applyTheme(t) {{
  document.documentElement.classList.toggle('dark', t === 'dark');
  localStorage.setItem(THEME_KEY, t);
}}
applyTheme(localStorage.getItem(THEME_KEY) || 'light');
document.getElementById('theme-toggle').onclick = () => {{
  applyTheme(document.documentElement.classList.contains('dark') ? 'light' : 'dark');
}};

/* ---------- 分类筛选 ---------- */
let curCat = '全部', curSearch = '';
const shelf = document.getElementById('shelf');
const cards = Array.from(shelf.querySelectorAll('.book-card'));
const noResult = document.getElementById('no-result');

function applyFilter() {{
  let shown = 0;
  cards.forEach(c => {{
    const catOk = curCat === '全部' || c.dataset.cat === curCat;
    const searchOk = !curSearch || (c.dataset.search || '').includes(curSearch);
    const show = catOk && searchOk;
    c.style.display = show ? '' : 'none';
    if (show) shown++;
  }});
  noResult.style.display = shown === 0 ? 'block' : 'none';
}}
document.querySelectorAll('.cat-tab').forEach(t => {{
  t.onclick = () => {{
    document.querySelectorAll('.cat-tab').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    curCat = t.dataset.cat;
    applyFilter();
  }};
}});

/* ---------- 搜索 ---------- */
const searchInput = document.getElementById('search');
searchInput.oninput = () => {{ curSearch = searchInput.value.trim().toLowerCase(); applyFilter(); }};
document.addEventListener('keydown', e => {{
  if (e.key === '/' && document.activeElement !== searchInput) {{ e.preventDefault(); searchInput.focus(); }}
  if (e.key === 'Escape') {{ searchInput.value = ''; curSearch = ''; applyFilter(); searchInput.blur(); }}
}});

/* ---------- 视图切换 ---------- */
document.querySelectorAll('.view-switch button').forEach(b => {{
  b.onclick = () => {{
    document.querySelectorAll('.view-switch button').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    shelf.className = 'shelf ' + b.dataset.view;
  }};
}});

/* ---------- 继续阅读（跨书记忆每本书读到哪章） ---------- */
function lastChapter(bookId) {{
  try {{ return localStorage.getItem('book_' + bookId + '_last_chapter'); }} catch (e) {{ return null; }}
}}
cards.forEach(c => {{
  const bid = c.dataset.id;
  const lc = lastChapter(bid);
  const btn = c.querySelector('.btn-resume');
  if (lc && btn) {{
    btn.hidden = false;
    btn.textContent = '继续读第 ' + lc.replace(/^0/, '') + ' 章';
    btn.onclick = () => {{
      const book = BOOKS.find(b => b.id === bid);
      if (book && book.url) {{
        const base = book.url.replace('index.html', '');
        location.href = base + 'chapter_' + lc + '/site/index.html';
      }}
    }};
  }}
}});
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()
    root = Path(args.codes_root)
    books = load_books(root / "config" / "books.yaml")
    bookstore = root / "outputs"
    data = collect_books(books, bookstore)
    html = build_library(data)
    out = bookstore / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"📚 图书馆总入口：{out}")
    print(f"   共 {len(data)} 本书 · " + " / ".join(f"{b['title'][:12]}…({b['pct']}%)" for b in data))


if __name__ == "__main__":
    main()
