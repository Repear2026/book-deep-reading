"""D2 脚本：调用白名单里的 deepseek-v4-flash，对每页做结构化笔记。

输入：chapter_01/pages/p*.txt
输出：chapter_01/notes/
  - notes.json  （全章整体：命题/论据/案例/概念/跨章链接）
  - per_page/p{NN}.json  （每页一段笔记）

prompt 模板明确禁止幻觉（一切判断必须基于本页文本）。
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.book_config import load_books
from lib.llm import call, ALLOWED, assert_allowed


SYSTEM_PROMPT = """你是《世界的逻辑》伴读系统的笔记员。要求：
1. 你只能基于【当前章节正文】做笔记，不得补充书上没有的概念或"幻觉"出原文没有出现的内容。
2. 输出必须是**单个 JSON object**，不要 ``` 代码块，不要任何前后文。
3. 字段：core_propositions（核心命题，每条一句话）、key_arguments（关键论据，每条引用书中一句原文）、cases（案例，标出"金字塔工人"/"希帕索斯"等类型）、new_concepts（本章新提出的概念，附"白话解释 1 句"）、cross_chapter_hints（点出可能在第 N 章继续的内容）。
4. 如果某字段在正文中为空，输出空列表。
5. JSON 字符串里如果需要双引号，用转义 \\\"。
"""


def make_user_prompt(chapter_label: str, page_num: int, page_text: str) -> str:
    return f"""章节：{chapter_label}
当前是第 {page_num} 页文本：
---
{page_text[:5500]}
---
请输出本页笔记（只输出单个 JSON object，不带 ```）。"""


def per_page_note(model_id: str, chapter_label: str, page_num: int, page_text: str, retry: int = 4) -> dict:
    last_err = None
    # reasoning 模型会先烧 tokens 在思考链上；max_tokens 必须给余量
    for attempt in range(retry + 1):
        try:
            raw = call(
                model_id,
                make_user_prompt(chapter_label, page_num, page_text),
                system=SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=8000,  # 大幅留余量
                timeout=180,
            )
            if not raw or not raw.strip():
                raise ValueError("LLM 返回空字符串")
            data = _extract_json(raw)
            data["_page"] = page_num
            data["_model_used"] = model_id
            return data
        except Exception as e:
            last_err = e
            if attempt < retry:
                wait = 1.5 + attempt * 1.0
                print(f"   ⚠ p{page_num} LLM 失败 (try {attempt+1}/{retry+1}): {str(e)[:100]}")
                time.sleep(wait)
    raise RuntimeError(f"第 {page_num} 页反复失败: {last_err}")


def _extract_json(raw: str) -> dict:
    """宽容地从 LLM 输出里抠 JSON：
    1. 剥 ``` 代码块包裹
    2. 直接 json.loads
    3. 截取首 { 到末 } 区间
    4. 还不行就用 json_repair 兜底
    """
    raw = raw.strip()
    if "```" in raw:
        parts = raw.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{") and p.endswith("}"):
                raw = p
                break
    try:
        return json.loads(raw)
    except Exception:
        pass
    s, e = raw.find("{"), raw.rfind("}")
    if s >= 0 and e > s:
        cand = raw[s:e + 1]
        try:
            return json.loads(cand)
        except Exception:
            pass
        # 最后用 json_repair 挽救
        try:
            from json_repair import repair_json
            fixed = repair_json(cand, return_objects=True)
            if isinstance(fixed, dict):
                return fixed
        except Exception:
            pass
    raise ValueError(f"无法从 LLM 输出抠出 JSON；长度 {len(raw)}，首 200 字符：{raw[:200]!r}")


def rollup_chapter(model_id: str, chapter_label: str, per_page: list[dict]) -> dict:
    """把 20 页的笔记汇总成整章 notes.json（retry 3 次）。"""
    brief = []
    for n in per_page:
        brief.append(
            f"### p{n['_page']}\n"
            + json.dumps(
                {k: n.get(k) for k in ["core_propositions", "key_arguments", "cases", "new_concepts", "cross_chapter_hints"]},
                ensure_ascii=False,
            )
        )
    brief_text = "\n\n".join(brief)
    user = f"""章节：{chapter_label}

请基于以下 20 页笔记，整合输出整章结构化笔记：
{brief_text}

字段：title, chapter_role、core_propositions、key_arguments、cases、new_concepts、cross_chapter_hints、suggested_socratic_questions（3-5 个问题）。
**重要**：输出**一个** JSON object，**不要** markdown 代码块包裹，**不要**任何前后解释。
"""
    last_err = None
    for attempt in range(3):
        try:
            raw = call(model_id, user, system="你是章节整合员。务必只输出单个 JSON object。", temperature=0.2, max_tokens=20000, timeout=300)
            if not raw or not raw.strip():
                raise ValueError("LLM 返回空")
            return _extract_json(raw)
        except Exception as e:
            last_err = e
            print(f"   ⚠ 整章 rollup 失败 (try {attempt+1}): {str(e)[:200]}")
            time.sleep(2)
    raise RuntimeError(f"整章 rollup 反复失败: {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--model", default="deepseek-v4-flash")
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--per-page-only", action="store_true", help="只做页笔记，不整合整章")
    ap.add_argument("--rollup-only", action="store_true", help="复用已生成的 per-page，只做整章整合")
    args = ap.parse_args()

    root = Path(args.codes_root)
    chapter_dir = root / "outputs" / args.book / f"chapter_{args.chapter}"
    pages_dir = chapter_dir / "pages"
    notes_dir = chapter_dir / "notes"
    per_page_dir = notes_dir / "per_page"
    per_page_dir.mkdir(parents=True, exist_ok=True)

    # 强校验：白名单外（含 WorkBuddy 公版）会直接 raise
    assert_allowed(args.model)

    import yaml as _yaml
    meta = _yaml.safe_load((chapter_dir / f"chapter_{args.chapter}.yaml").read_text(encoding="utf-8"))
    chapter_label = meta["chapter_label"]

    page_files = sorted(pages_dir.glob("p*.txt"))
    if not page_files:
        raise SystemExit(f"未发现任何 p*.txt——先跑 D1")

    print(f"📖 {chapter_label}")
    print(f"   模型：{args.model}（白名单）")
    print(f"   页数：{len(page_files)}")

    per_page = []
    # 若 per_page 已存在完整，跳过 LLM 直接用
    existing = sorted(per_page_dir.glob("p*.json"))
    expected = {int(pf.stem[1:]) for pf in page_files}
    if args.rollup_only and len(existing) == len(expected) and all(int(f.stem[1:]) in expected for f in existing):
        print(f"   · per-page 已存在 {len(existing)} 个，直接复用")
        per_page = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(existing)]
    else:
        for pf in page_files:
            page_num = int(pf.stem[1:])
            text = pf.read_text(encoding="utf-8").strip()
            if not text:
                continue
            print(f"   · 处理 p{page_num:03d}... ", end="", flush=True)
            note = per_page_note(args.model, chapter_label, page_num, text)
            (per_page_dir / pf.name.replace(".txt", ".json")).write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
            per_page.append(note)
            print(f"✓")

    if args.per_page_only:
        print(f"✅ 页笔记完成（仅 per-page）：{per_page_dir}")
        return

    print()
    print(f"🔁 整章整合...")
    chapter_note = rollup_chapter(args.model, chapter_label, per_page)
    (notes_dir / "notes.json").write_text(json.dumps(chapter_note, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 整章笔记：{notes_dir / 'notes.json'}")

    # 更新 meta
    meta["status"] = "notes-done"
    import yaml as _yaml
    (chapter_dir / f"chapter_{args.chapter}.yaml").write_text(
        _yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print()
    print(f"📌 下一步 (D3)：python scripts/03_make_graph.py --book {args.book} --chapter {args.chapter}")


if __name__ == "__main__":
    main()
