"""09_reaggregate.py — 重聚合所有 review.json 输出 _aggregate_report。

后 07_run_all.py 跑完后立即调用，确保聚合报告反映最新 review 状态。

用法:
    python scripts/09_reaggregate.py --book daodejing
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--codes-root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    root = Path(args.codes_root)
    book_dir = root / "outputs" / args.book
    if not book_dir.exists():
        raise SystemExit(f"找不到 {book_dir}")

    # 扫所有 chapter_XX/review.json
    chapter_dirs = sorted([p for p in book_dir.glob("chapter_*") if p.is_dir()])
    print(f"📚 {args.book}：发现 {len(chapter_dirs)} 章")

    rows = []
    for cdir in chapter_dirs:
        chap_id = cdir.name.replace("chapter_", "")
        rj = cdir / "review.json"
        sj_index_html = (cdir / "site" / "index.html").exists()
        files_ok = (cdir / "notes" / "notes.json").exists() and (cdir / "graph" / "graph.mmd").exists() and sj_index_html

        if rj.exists():
            v = json.loads(rj.read_text(encoding="utf-8"))
            verdict = v.get("verdict", "?")
            issues = len(v.get("issues", []))
            warns = len(v.get("warnings", []))
        else:
            verdict = "NO_REVIEW"
            issues = 0
            warns = 0
        rows.append({"chapter_id": chap_id, "verdict": verdict, "issues": issues, "warns": warns, "files_ok": files_ok})

    passes = sum(1 for r in rows if r["verdict"] == "PASS")
    warns_n = sum(1 for r in rows if r["verdict"] == "WARN")
    fails_n = sum(1 for r in rows if r["verdict"] == "FAIL")
    no_review = sum(1 for r in rows if r["verdict"] == "NO_REVIEW")
    files_missing = [r["chapter_id"] for r in rows if not r["files_ok"]]

    # 重写 _aggregate_report.md
    # 书名友好显示
    BOOK_DISPLAY = {
        "daodejing": "《道德经》（王弼本）",
    }
    title = BOOK_DISPLAY.get(args.book, f"《{args.book}》")
    out = [
        f"# 📚 {title} · {len(rows)} 章全流程聚合报告",
        "",
        f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- PASS：{passes} · WARN：{warns_n} · FAIL：{fails_n} · NO_REVIEW：{no_review}",
        f"- 文件齐全：{len(rows) - len(files_missing)} / {len(rows)}" + ("（✅ 全部齐全）" if not files_missing else f"（❗ 缺：{', '.join(files_missing)}）"),
        "",
        "## 详细（按章排序）",
        "",
        "| 章 | verdict | 致命问题 | 警告 | HTML | 笔记 | 图谱 | 笔记数 | 节点 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    # 排序：按 chapter_id
    rows.sort(key=lambda r: r["chapter_id"])

    for r in rows:
        cid = r["chapter_id"]
        cdir = book_dir / f"chapter_{cid}"
        notes = "✅" if (cdir / "notes" / "notes.json").exists() else "❌"
        mmd = "✅" if (cdir / "graph" / "graph.mmd").exists() else "❌"
        html = "✅" if (cdir / "site" / "index.html").exists() else "❌"

        # 笔记条目数（图节点数）
        notes_count = "?"
        nodes_count = "?"
        try:
            nj = cdir / "notes" / "notes.json"
            if nj.exists():
                nd = json.loads(nj.read_text(encoding="utf-8"))
                notes_count = sum([
                    len(nd.get("core_propositions") or []),
                    len(nd.get("key_arguments") or []),
                    len(nd.get("cases") or []),
                    len(nd.get("new_concepts") or []),
                    len(nd.get("cross_chapter_hints") or []),
                    len(nd.get("suggested_socratic_questions") or []),
                ])
            mj = cdir / "graph" / "graph.mmd"
            if mj.exists():
                import re
                # 认 3 种节点语法：节点[…] / 节点(…) / 节点{{…}}
                nodes_count = len(re.findall(r"^\s*[\w_]+[\[\(\{]", mj.read_text(encoding="utf-8"), flags=re.M))
        except Exception:
            pass

        sym = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "NO_REVIEW": "❓"}.get(r["verdict"], "❓")
        out.append(f"| {cid} | {sym} {r['verdict']} | {r['issues']} | {r['warns']} | {html} | {notes} | {mmd} | {notes_count} | {nodes_count} |")

    out.append("")
    out.append("## 合订本导航")
    out.append(f"所有 {len(rows)} 章 HTML 在 `outputs/{args.book}/chapter_XX/site/index.html` 下，双击即开。")
    out.append("")
    out.append("## 失败章节补救")
    if fails_n or no_review or files_missing:
        out.append("以下章节 FAIL/缺文件——可单独跑：")
        for r in rows:
            if r["verdict"] != "PASS" or not r["files_ok"]:
                out.append(f"- 第 {r['chapter_id']} 章：`python scripts/06_run_one_chapter.py --book {args.book} --chapter {r['chapter_id']}`")
    else:
        out.append("✅ 无失败章节，全书 PASS。")
    out.append("")
    out.append(f"## 整章笔记统计")
    total_props = 0
    for r in rows:
        cdir = book_dir / f"chapter_{r['chapter_id']}"
        nj = cdir / "notes" / "notes.json"
        if nj.exists():
            nd = json.loads(nj.read_text(encoding="utf-8"))
            total_props += sum([
                len(nd.get("core_propositions") or []),
                len(nd.get("key_arguments") or []),
                len(nd.get("cases") or []),
                len(nd.get("new_concepts") or []),
                len(nd.get("cross_chapter_hints") or []),
                len(nd.get("suggested_socratic_questions") or []),
            ])
    out.append(f"全书共 **{total_props}** 条结构化笔记条目（命题+论据+案例+概念+跨章+苏格拉底问题）")
    out.append("")

    report = "\n".join(out)
    (book_dir / "_aggregate_report.md").write_text(report, encoding="utf-8")
    (book_dir / "_aggregate_report.json").write_text(
        json.dumps({"rows": rows, "totals": {"PASS": passes, "WARN": warns_n, "FAIL": fails_n, "NO_REVIEW": no_review, "files_missing": files_missing}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ 报告: {book_dir / '_aggregate_report.md'}")
    print()
    print("=" * 60)
    print(report)
    print("=" * 60)


if __name__ == "__main__":
    main()
