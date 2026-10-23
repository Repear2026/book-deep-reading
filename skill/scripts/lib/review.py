"""review.py — 单章校对 + 自测。

校验：
1. 结构性（schema、文件存在）
2. 数量门槛（命题数 / 论据数 / 案例数 / 概念数 / 跨章链接 / 苏格拉底问数 / 图谱节点）
3. 关键词覆盖（每章预设）
4. 页码一致性（notes 引用页必须在 chapter pages_range 内）

产出：chapter_XX/review.md  +  chapter_XX/review.json（机器可读 verdict）
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from typing import Any


# 章节关键词清单（按书隔离：{book_id: {chapter_id: [关键词]}}）
# 只对已配置的书做关键词覆盖检查；未配置的书跳过（不算警告）
CHAPTER_KEYWORDS = {
    "shijie_deluoji": {
        "01": ["语言", "智人", "维特根斯坦", "尼安德特", "文字", "大规模合作", "基因"],
        "02": ["宗教", "上帝", "信仰", "确定性", "救赎", "僧侣", "教义", "仪式"],
        "03": ["古希腊", "智者", "柏拉图", "亚里士多德", "苏格拉底", "理性", "形而上学"],
        "04": ["逻辑", "三段论", "亚里士多德", "演绎", "归纳", "推理", "有效性"],
        "05": ["理性", "宇宙", "俯视", "上帝", "形而上学", "黑格尔", "思辨"],
        "06": ["实践", "经验", "实验", "培根", "观察", "方法"],
        "07": ["数学危机", "无理数", "贝克莱", "罗素", "集合论", "无穷", "公理"],
        "08": ["不完备", "哥德尔", "图灵", "机器", "公理化", "递归"],
        "09": ["直觉", "认知", "无意识", "判断", "经验"],
        "10": ["AI", "图灵", "智能", "机器学习", "算法", "人工"],
        "11": ["混沌", "蝴蝶效应", "非线性", "洛伦兹", "确定性", "初始条件"],
        "12": ["概率", "贝叶斯", "频率", "条件概率", "分布", "统计", "不确定性"],
        "13": ["量子", "叠加", "观察者", "互补", "玻尔", "海森堡", "量子逻辑"],
        "14": ["务实", "解决问题", "有效", "实践", "工程", "范式"],
    },
    # 《道德经》不设关键词：81 章主题各异，逐章枚举意义不大，且短章本就信息密度低
}


# 自测标准（长章：一本书里 10+ 页的章节）
DEFAULT_CRITERIA = {
    "core_propositions": {"min": 8},
    "key_arguments": {"min": 5},
    "cases": {"min": 2},
    "new_concepts": {"min": 8},
    "cross_chapter_hints": {"min": 3},
    "socrates_questions": {"min": 4},
    "mermaid_nodes": {"min": 10, "max": 50},
    "glossary_rows": {"min": 6},
}

# 短章标准（文本型书籍：一章几十到几百字，如《道德经》）
SHORT_CHAPTER_CRITERIA = {
    "core_propositions": {"min": 3},
    "key_arguments": {"min": 2},
    "cases": {"min": 0},
    "new_concepts": {"min": 3},
    "cross_chapter_hints": {"min": 0},
    "socrates_questions": {"min": 3},
    "mermaid_nodes": {"min": 6, "max": 50},
    "glossary_rows": {"min": 3},
}

SHORT_CHAPTER_THRESHOLD = 2000   # 正文字数低于此值 → 用短章标准


def _chapter_char_count(chapter_dir: Path, chap_id: str) -> int:
    """读章节正文字数，用来判断长章/短章。"""
    p = chapter_dir / f"chapter_{chap_id}.txt"
    if p.exists():
        return len(p.read_text(encoding="utf-8"))
    pages = sorted((chapter_dir / "pages").glob("p*.txt")) if (chapter_dir / "pages").exists() else []
    return sum(len(f.read_text(encoding="utf-8")) for f in pages)


def review_chapter(chapter_dir: Path, book_id: str | None = None) -> dict:
    """跑 8 项校验，返回 verdict dict；同时写 review.md / review.json。

    book_id 缺省时从路径推断（outputs/<book_id>/chapter_XX）。
    """
    chap_id = chapter_dir.name.replace("chapter_", "")
    if book_id is None:
        book_id = chapter_dir.parent.name if chapter_dir.parent.name else ""

    # 按正文字数自适应门槛：短章（文本型书籍，如道德经）用宽松标准
    char_count = _chapter_char_count(chapter_dir, chap_id)
    is_short = char_count < SHORT_CHAPTER_THRESHOLD
    criteria = SHORT_CHAPTER_CRITERIA if is_short else DEFAULT_CRITERIA

    out: dict[str, Any] = {
        "chapter_id": chap_id,
        "book_id": book_id,
        "char_count": char_count,
        "mode": "short" if is_short else "long",
        "checks": {},
        "verdict": "PASS",
        "issues": [],
        "warnings": [],
    }

    # 1. 文件存在
    notes_path = chapter_dir / "notes" / "notes.json"
    graph_mmd_path = chapter_dir / "graph" / "graph.mmd"
    overview_path = chapter_dir / "overview" / "overview.md"
    glossary_path = chapter_dir / "glossary" / "glossary.md"
    socrates_path = chapter_dir / "socrates" / "socrates.md"
    html_path = chapter_dir / "site" / "index.html"

    missing = [p.name for p in [notes_path, graph_mmd_path, overview_path, glossary_path, socrates_path, html_path] if not p.exists()]
    out["checks"]["files_exist"] = {"missing": missing, "ok": not missing}
    if missing:
        out["verdict"] = "FAIL"
        out["issues"].extend([f"缺失产物文件：{m}" for m in missing])

    # 2. notes.json 字段与数量
    notes = {}
    if notes_path.exists():
        notes = json.loads(notes_path.read_text(encoding="utf-8"))
        from lib.normalize import concepts_of, cases_of
        # 概念/案例要用归一化后的有效条目数（LLM 字段名不统一，直接 len() 会虚高）
        effective = {
            "new_concepts": len(concepts_of(notes)),
            "cases": len(cases_of(notes)),
        }
        for field, rule in criteria.items():
            if field in {"mermaid_nodes", "glossary_rows", "socrates_questions"}:
                continue   # 后面单独查
            n = effective.get(field, len(notes.get(field) or []))
            ok = n >= rule["min"]
            out["checks"][field] = {"count": n, "min": rule["min"], "ok": ok}
            if not ok:
                out["warnings"].append(f"{field} 仅 {n} 条（要求 ≥ {rule['min']}）")

    # 3. 苏格拉底问题数
    socrates_q = 0
    if notes:
        socrates_q = len(notes.get("suggested_socratic_questions") or [])
    out["checks"]["socrates_questions"] = {"count": socrates_q, "min": criteria["socrates_questions"]["min"], "ok": socrates_q >= criteria["socrates_questions"]["min"]}
    if socrates_q < criteria["socrates_questions"]["min"]:
        out["verdict"] = "WARN" if out["verdict"] == "PASS" else out["verdict"]
        out["warnings"].append(f"苏格拉底引导问题仅 {socrates_q} 个（建议 ≥ {criteria['socrates_questions']['min']}）")

    # 4. Mermaid 节点数（认 3 种节点语法：节点[…]/节点(…)/节点{{…}}）
    if graph_mmd_path.exists():
        mmd = graph_mmd_path.read_text(encoding="utf-8")
        nodes = re.findall(r"^\s*[\w_]+[\[\(\{]", mmd, flags=re.M)
        node_count = len(nodes)
        ok = criteria["mermaid_nodes"]["min"] <= node_count <= criteria["mermaid_nodes"]["max"]
        out["checks"]["mermaid_nodes"] = {"count": node_count, "min": criteria["mermaid_nodes"]["min"], "max": criteria["mermaid_nodes"]["max"], "ok": ok}
        if not ok:
            if node_count < criteria["mermaid_nodes"]["min"]:
                out["warnings"].append(f"图谱节点 {node_count}，偏少（建议 ≥ {criteria['mermaid_nodes']['min']}）")
            else:
                out["verdict"] = "FAIL"
                out["issues"].append(f"图谱节点 {node_count} 超上限 {criteria['mermaid_nodes']['max']}")

    # 5. 术语表行数（按 markdown 表格列：含 L0 / 术语 / --- / 中文标点风格的表头都排除；剩下的就是数据行）
    glossary_rows = 0
    if glossary_path.exists():
        for ln in glossary_path.read_text(encoding="utf-8").split("\n"):
            ln = ln.strip()
            # 是 | 开头行；不是表头（含 L0 一句话的 cell）；不是分隔线
            if ln.startswith("|") and "L0 一句话" not in ln and not re.match(r"^\|[\s\-:|]+\|\s*$", ln):
                glossary_rows += 1
    out["checks"]["glossary_rows"] = {"count": glossary_rows, "min": criteria["glossary_rows"]["min"], "ok": glossary_rows >= criteria["glossary_rows"]["min"]}
    if glossary_rows < criteria["glossary_rows"]["min"]:
        out["warnings"].append(f"术语表仅 {glossary_rows} 行（建议 ≥ {criteria['glossary_rows']['min']}）")

    # 6. 关键词覆盖（按 book 隔离；未配置的书跳过，不算警告）
    kws = (CHAPTER_KEYWORDS.get(book_id) or {}).get(chap_id, [])
    if kws:
        text_blob = (notes_path.read_text(encoding="utf-8") if notes_path.exists() else "") + " " + (graph_mmd_path.read_text(encoding="utf-8") if graph_mmd_path.exists() else "")
        hits = [k for k in kws if k in text_blob]
        coverage = len(hits) / len(kws)
        out["checks"]["keyword_coverage"] = {"hits": hits, "total_keywords": len(kws), "ratio": round(coverage, 2)}
        if coverage < 0.4:
            out["verdict"] = "WARN" if out["verdict"] == "PASS" else out["verdict"]
            out["warnings"].append(f"关键词覆盖 {coverage*100:.0f}%（建议 ≥ 40%）。命中: {hits}")
        # 也写进 review

    # 7. HTML 渲染
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        size = len(html)
        ok = size > 8000 and "mermaid" in html and "prompt-card" in html
        out["checks"]["html_render"] = {"size_kb": size // 1024, "ok": ok}
        if not ok:
            out["verdict"] = "FAIL"
            out["issues"].append(f"HTML 渲染异常（{size//1024} KB）")
    else:
        out["checks"]["html_render"] = {"ok": False}
        out["verdict"] = "FAIL"
        out["issues"].append("HTML 未生成")

    # verdict 状态
    if out["verdict"] != "FAIL" and out["warnings"]:
        out["verdict"] = "WARN"

    # 写产出
    review_dir = chapter_dir
    (review_dir / "review.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    md = _to_review_md(out, chapter_dir)
    (review_dir / "review.md").write_text(md, encoding="utf-8")
    return out


def _to_review_md(verdict: dict, chapter_dir: Path) -> str:
    sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(verdict["verdict"], "?")
    out = [f"# 第 {verdict['chapter_id']} 章 · 校对 & 自测报告  {sym}",
           "",
           f"**verdict**：{verdict['verdict']}"]
    if verdict["issues"]:
        out.append("\n## ❗ 致命问题（必须修）")
        for i in verdict["issues"]:
            out.append(f"- {i}")
    if verdict["warnings"]:
        out.append("\n## ⚠️ 警告（建议修）")
        for w in verdict["warnings"]:
            out.append(f"- {w}")

    out.append("\n## 校验详情")
    for k, v in verdict["checks"].items():
        if isinstance(v, dict):
            if "ok" in v:
                mark = "✓" if v["ok"] else "✗"
                extra = " / ".join(f"{kk}={vv}" for kk, vv in v.items() if kk not in ("ok",))
                out.append(f"- {mark} `{k}`  {extra}")
            else:
                out.append(f"- `{k}`  {v}")

    if "keyword_coverage" in verdict["checks"]:
        k = verdict["checks"]["keyword_coverage"]
        out.append("\n## 🔑 关键词覆盖")
        out.append(f"- 命中 {k['ratio']*100:.0f}% ({len(k['hits'])}/{k['total_keywords']})")
        out.append(f"- 关键词：{', '.join(k['hits'])}")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python -m lib.review <book_id> <chapter_id>")
        sys.exit(1)
    book_id, chap_id = sys.argv[1], sys.argv[2]
    base = Path(__file__).resolve().parent.parent / "outputs" / book_id / f"chapter_{chap_id}"
    v = review_chapter(base)
    print(f"verdict: {v['verdict']}, issues: {len(v['issues'])}, warnings: {len(v['warnings'])}")
