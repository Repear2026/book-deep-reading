"""D3：知识图谱（Mermaid）。

输入：chapter_01/notes/notes.json + chapter_01/chapter_01.txt
输出：chapter_01/graph/
  - graph.mmd        （Mermaid 源码，给前端直接 <embed> 渲染）
  - graph.md         （文字版：节点列表 + 边列表）

prompt 要求：
- 节点类型限：Proposition / Concept / Case / Author(人物) / Event(事件)
- 边类型限：supports(论据→命题) / instance_of(案例→命题) / introduces(页→概念) / relates_to(同位关系)
- 节点总数 ≤ 40，图结构层次清楚不超过 4 层
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.llm import call, assert_allowed
from lib.book_config import load_books


GRAPH_SYSTEM = """你是知识图谱工程师。任务：基于章节笔记画**一张** Mermaid 图。

约束：
1. 图用 Mermaid `flowchart` 语法（不要 `graph TD/RD`，用 `flowchart LR`）。
2. 节点类型限定：Proposition(命题) / Concept(概念) / Case(案例) / Author(人物) / Event(事件)。
3. 节点标签统一用双引号，转义用 \\\"。
4. 边的类型：supports（论据→命题）、instance_of（案例→命题）、introduces（页面→概念，可省）、relates_to（同位关系）。
5. **全部节点 ≤ 40 个**，边 ≤ 60 条；不允许出现意义重复节点。
6. **只输出 Mermaid 源码**（从 `flowchart LR` 开头），不要 markdown 代码块包装，不要任何前后解释。
7. 节点 ID 用拼音或英文短词，标签中写中文。
"""

GRAPH_USER_TEMPLATE = """章节：{label}
原始笔记 JSON：
{notes_json}

请严格按字数约束输出 Mermaid 图。"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    chapter_dir = root / "outputs" / args.book / f"chapter_{args.chapter}"
    notes_dir = chapter_dir / "notes"
    graph_dir = chapter_dir / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)

    notes_file = notes_dir / "notes.json"
    if not notes_file.exists():
        raise SystemExit(f"先跑 D2：{notes_file}")
    notes = json.loads(notes_file.read_text(encoding="utf-8"))

    # import yaml as _yaml
    import yaml as _yaml
    meta = _yaml.safe_load((chapter_dir / f"chapter_{args.chapter}.yaml").read_text(encoding="utf-8"))

    # 截短给 LLM，避免 reasoning 烧光
    brief_notes = {
        "title": notes.get("title"),
        "chapter_role": notes.get("chapter_role"),
        # 每类最多 12 条，截短
        "core_propositions": (notes.get("core_propositions") or [])[:12],
        "key_arguments": (notes.get("key_arguments") or [])[:12],
        "cases": (notes.get("cases") or [])[:10],
        "new_concepts": (notes.get("new_concepts") or [])[:14],
        "cross_chapter_hints": (notes.get("cross_chapter_hints") or [])[:6],
    }
    print(f"📖 图谱：{meta['chapter_label']}（节点 ≤40）")
    print(f"   模型：{args.model}（白名单）")

    user = GRAPH_USER_TEMPLATE.format(label=meta["chapter_label"], notes_json=json.dumps(brief_notes, ensure_ascii=False, indent=2))
    last_err = None
    mmd = ""
    for attempt in range(3):
        try:
            raw = call(args.model, user, system=GRAPH_SYSTEM, temperature=0.3, max_tokens=20000, timeout=300)
            mmd = _strip_to_mermaid(raw)
            assert "flowchart" in mmd and len(mmd) > 100, f"图谱过短/格式异常：{mmd[:200]}"
            break
        except Exception as e:
            last_err = e
            print(f"   ⚠ 第 {attempt+1} 次失败: {str(e)[:200]}")
            time.sleep(2)
    else:
        raise RuntimeError(f"图谱反复失败: {last_err}")

    (graph_dir / "graph.mmd").write_text(mmd, encoding="utf-8")
    print(f"✅ Mermaid 图：{graph_dir / 'graph.mmd'}")

    # 文字版
    text = notes_to_text_graph(notes)
    (graph_dir / "graph.md").write_text(text, encoding="utf-8")
    print(f"✅ 文字版：{graph_dir / 'graph.md'}")


def _strip_to_mermaid(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        # 剥代码块
        parts = raw.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("mermaid") or p.startswith("flowchart"):
                return p[len("mermaid"):].strip() if p.startswith("mermaid") else p
        return raw.replace("```", "")
    return raw


def notes_to_text_graph(notes: dict) -> str:
    out = [f"# {notes.get('title', '章节')} 知识图谱（文字版）", ""]
    out.append("## 🎯 章节主旨")
    out.append(f"> {notes.get('chapter_role', '')[:400]}")
    out.append("")
    out.append("## 📌 核心命题")
    for i, p in enumerate((notes.get("core_propositions") or [])[:10], 1):
        out.append(f"{i}. {p}")
    if len(notes.get("core_propositions") or []) > 10:
        out.append(f"_... 共 {len(notes['core_propositions'])} 条_")
    out.append("")
    out.append("## 🔑 关键论据")
    for i, p in enumerate((notes.get("key_arguments") or [])[:10], 1):
        out.append(f"{i}. {p}")
    out.append("")
    out.append("## 🗂 案例")
    for c in (notes.get("cases") or [])[:8]:
        if isinstance(c, dict):
            out.append(f"- **{c.get('name', '')}** · {c.get('type', '')}")
            out.append(f"  > {c.get('description', '')[:200]}")
        else:
            out.append(f"- {c}")
    out.append("")
    out.append("## 💡 概念（新提出）")
    for c in (notes.get("new_concepts") or [])[:12]:
        if isinstance(c, dict):
            out.append(f"- **{c.get('concept', '')}**：{c.get('explanation', '')[:160]}")
        else:
            out.append(f"- {c}")
    out.append("")
    out.append("## 🔗 跨章链接提示")
    for c in (notes.get("cross_chapter_hints") or [])[:6]:
        out.append(f"- {c}")
    return "\n".join(out)


if __name__ == "__main__":
    main()
