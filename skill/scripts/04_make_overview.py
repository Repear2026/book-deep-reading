"""D4 导读四步卡 + D5 苏格拉底 prompt + D6 多难度术语表。

输入：chapter_01/notes/notes.json
输出：
  - chapter_01/overview/overview.md     （四步导读：①书概览 ②多问题意识 ③跨作者碰撞 ④精读推荐）
  - chapter_01/glossary/glossary.md     （L0-L3 四层翻译）
  - chapter_01/socrates/socrates.md     （4 类 prompt 模板 + 5-7 新手引导问题）
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.llm import call


SYSTEM = """你是深度伴读系统的导师，精通哲学、思想史、语言学与认知科学。

分层原则（重要）：
- **L0/L1/L2、导读、苏格拉底问题**：严格基于本章笔记与原文，不得编造书中未出现的内容、情节或论点。
- **L3 思想史层**：允许（且要求）引用公共学术常识——历代注家、不同学派、现代研究者的代表性说法。这不算"幻觉"，属于标准的思想史背景知识。但必须写清是谁的说法，不得张冠李戴、不得编造不存在的著作名。

输出纯 markdown，不加任何前后解释。"""


def get_overview(label: str, notes: dict) -> str:
    notes_brief = {
        "title": notes.get("title"),
        "chapter_role": notes.get("chapter_role"),
        "core_propositions": (notes.get("core_propositions") or [])[:8],
        "key_arguments": (notes.get("key_arguments") or [])[:6],
        "cases": (notes.get("cases") or [])[:6],
        "new_concepts": (notes.get("new_concepts") or [])[:8],
        "cross_chapter_hints": (notes.get("cross_chapter_hints") or [])[:5],
    }
    user = """章节：{label}
笔记：
{notes}

请按下面格式输出**一段完整 markdown**（不要代码块包装）：

# 《{label}》四步导读

## ①书概览（5 分钟，建立全貌）
> 一段话让小白读者明白：这章讲什么 / 为什么有趣 / 最重要收获是哪个。用不超过 200 字。

## ②多问题意识关联
> 用 3 个"如果...会..."的发问，让读者自己代入。每个问题一两句，不超过 80 字。

## ③其他作者观点碰撞
> 至少 3 位其他思想家对该主题的回应（可来自维特根斯坦/福柯/罗素/涂尔干/吉登斯等，或中国古代名家如荀子、韩非、王阳明）。每条一两句。

## ④精读推荐（小白怎么读这章）
> 三段：
> （1）第一遍（速览）: 给你 3 个关注点
> （2）第二遍（细抠）: 给你 2 个必看的论证
> （3）第三遍（思辨）: 给你 1 个该追问的开放问题

不要任何前后解释，仅输出 markdown。
""".format(label=label, notes=json.dumps(notes_brief, ensure_ascii=False, indent=2))
    raw = call("deepseek-v4-flash", user, system=SYSTEM, temperature=0.35, max_tokens=20000, timeout=300)
    return _trim(raw)


def get_glossary(label: str, notes: dict) -> str:
    """L0-L3 四层翻译。
       L0 白话，L1 教材，L2 学术，L3 哲学反思。
    """
    concepts = notes.get("new_concepts") or []
    # 归一化字段名（LLM 会输出 concept/term/name/plain 等 9 种组合）
    from lib.normalize import concepts_of
    norm_concepts = concepts_of(notes)
    if not norm_concepts:
        return "（本章无新概念）"
    user = """章节：{label}
本章新概念（按 notes 顺序）：
{concepts}

请对每一个概念输出 L0 / L1 / L2 / L3 四层翻译，输出 markdown 表：

| 术语 | L0 一句话（普通人能懂） | L1 教材级别（中文百科） | L2 学术级别（引用原学术语） | L3 哲学/思想史反思（不同流派怎么理解） |

## L3 栏的硬要求（最容易写空，务必照做）

L3 **必须给出至少 2 个具体流派/思想家的实际说法**，不得写"笔记未提供""不作补充"这类回避。

可用的思想史素材（这是公共学术常识，不属于"幻觉"，可以放心引用）：
- 注家传统：王弼（贵无）、河上公（养生）、郭象（独化）、成玄英（重玄）、苏辙、王夫之（气化）
- 道家内部：庄子（齐物/逍遥）、列子、黄老学派、道教内丹
- 对照外部：儒家（孔孟荀）、法家（韩非）、佛学（中观缘起、禅宗无心）、西方（海德格尔的存在、维特根斯坦的语言界限、怀特海的过程）
- 现代研究：陈鼓应、楼宇烈、刘笑敢、葛兆光等的代表性判断

格式示例：`王弼以"无"为本，认为万物由无而生；郭象则主张"独化"，反对有一个更高的本体；海德格尔的"无"是存在之遮蔽，与老子的生成论不同。`

不要任何前后解释。**严格只用 markdown**，不要 ``` 包裹。如果概念太多可保留前 18 个。
""".format(
        label=label,
        concepts=json.dumps(
            [{"concept": c["name"], "explanation": c["explain"]} for c in norm_concepts[:25]],
            ensure_ascii=False, indent=2,
        ),
    )
    raw = call("deepseek-v4-flash", user, system=SYSTEM, temperature=0.3, max_tokens=20000, timeout=300)
    return _trim(raw)


def get_socrates(label: str, notes: dict) -> str:
    """章末苏格拉底：4 类固定 prompt + 5-7 新手引导问题。"""
    user = """章节：{label}

请输出 markdown，包含两个部分：

## 1）4 个固定 prompt 模板（每类 1 个）

- **理解检查**：用户读完一章后，对自己的一段陈述做"主线提取 + 关键概念检查"，让他给出关键点
- **强反驳**：让 AI 扮演最强反方，从相反视角挑战用户对该章的接受度
- **连现实**：用户读完一章，给 3 个真实生活/工作场景让 AI 解释该章思想如何应用
- **深挖**：用户挑出该章最让他兴奋的一句话，AI 围绕这句展开"那这样推下去还有什么？"

每个模板写成可直接复制的 prompt 文本，使用 {{占位符名}} 的形式表示变量。

## 2）5-7 个新手引导问题（按"小白友好"程度排序）

按（适合 0 哲学基础 → 适合 5 年哲学爱好）排序，越简单越靠前。
每条一行 + 一行提示。

不要任何前后解释。
""".format(label=label)
    raw = call("deepseek-v4-flash", user, system=SYSTEM, temperature=0.4, max_tokens=12000, timeout=240)
    return _trim(raw)


def _trim(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("markdown") or p.startswith("md"):
                return p[len("markdown"):].strip() if p.startswith("markdown") else p.strip()
            if "\n" in p and not p.startswith("```"):
                return p.strip()
        return raw.replace("```", "")
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chapter", required=True)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--only", choices=["all", "overview", "glossary", "socrates"], default="all")
    args = ap.parse_args()

    root = Path(args.codes_root)
    chapter_dir = root / "outputs" / args.book / f"chapter_{args.chapter}"
    notes = json.loads((chapter_dir / "notes" / "notes.json").read_text(encoding="utf-8"))
    import yaml as _yaml
    meta = _yaml.safe_load((chapter_dir / f"chapter_{args.chapter}.yaml").read_text(encoding="utf-8"))
    label = meta["chapter_label"]

    out_overview = chapter_dir / "overview"
    out_glossary = chapter_dir / "glossary"
    out_socrates = chapter_dir / "socrates"
    out_overview.mkdir(parents=True, exist_ok=True)
    out_glossary.mkdir(parents=True, exist_ok=True)
    out_socrates.mkdir(parents=True, exist_ok=True)

    print(f"📖 {label}")
    if args.only in ("all", "overview"):
        print("   · D4 导读四步...")
        text = get_overview(label, notes)
        (out_overview / "overview.md").write_text(text, encoding="utf-8")
        print(f"     ✅ {out_overview / 'overview.md'}")
    if args.only in ("all", "glossary"):
        print("   · D6 术语表 L0-L3...")
        text = get_glossary(label, notes)
        (out_glossary / "glossary.md").write_text(text, encoding="utf-8")
        print(f"     ✅ {out_glossary / 'glossary.md'}")
    if args.only in ("all", "socrates"):
        print("   · D5 苏格拉底 prompt + 引导问题...")
        text = get_socrates(label, notes)
        (out_socrates / "socrates.md").write_text(text, encoding="utf-8")
        print(f"     ✅ {out_socrates / 'socrates.md'}")

    meta["status"] = "drafts-done"
    (chapter_dir / f"chapter_{args.chapter}.yaml").write_text(
        _yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print()
    print(f"📌 下一步 (D7)：python scripts/05_build_frontend.py --book {args.book} --chapter {args.chapter}")


if __name__ == "__main__":
    main()
