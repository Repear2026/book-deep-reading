---
name: book-deep-reading
description: 把任何书（PDF，上下册/单册均可）拆成"5 步流水线"单页深度伴读：拆页抽图→结构化笔记→Mermaid 知识图谱→4 步导读→多难度术语表→双击即开的本地 HTML 单页。当用户说"伴读《XX》""深读《XX》""拆《XX》""把《XX》做出来""跑书的流水线""换一本书做"时使用。触发词：拆书、深读、伴读、读书笔记、知识图谱、book reading pipeline、second book、下本书。
agent_created: true
---

# 深读伴书 · Book Deep Reading Pipeline

把任何 PDF 书做成"每章双击即可看的伴读 HTML"，跨学科都适用（哲学/历史/数学/技术/经济/认知）。

## 何时用

- 用户给一本 PDF（上/下册或单册），希望逐章节深读
- 想要"结构化笔记 + 知识图谱 + 苏格拉底对话 + L0-L3 术语表"，本地双击就能用
- 想覆盖多本书（这是 skill 的核心价值：**换书只改 1 行 yaml**）

## 不适用

- 教辅/儿童绘本/纯小说——拆书流水线是"非虚构/学术/通识"取向
- 上线/Web/小程序要立刻做——这是 *个人马上能用版*。上线/合规延后到 `v4` 阶段

## 核心做法（一句话）

**YAML 配书目 + 5 步流水线（D1 拆页 → D2 笔记 → D3 图谱 → D4 草稿 → D5 前端）+ per-章 review 自我审视**。

跑出来的产物是 `book_outputs/<book_id>/chapter_XX/site/index.html`，双击即开。每次跑都会写 `review.md`（PASS/WARN/FAIL + 致命/警告清单）。最终 `book_outputs/<book_id>/_aggregate_report.md` 看全书总报告。

---

## 一次性环境准备（首次使用）

```bash
# 用 WorkBuddy 自带的 venv
"<venv>/Scripts/python.exe" -m pip install pymupdf pyyaml json-repair -q
```

`<venv>` 指你本地 Python 虚拟环境的解释器路径（Windows 上形如 `C:/path/to/venv/Scripts/python.exe`，macOS/Linux 形如 `/path/to/venv/bin/python`）。用系统 Python 也可以，只要装好依赖。

> 后续运行不要求用户每次执行依赖装。一次装好后续跑无痛点。

---

## "换书即换配置"（这是核心价值）

### A. PDF 书（默认）

1. 把书 PDF 放到 `inputs/`：
   ```bash
   cp "《XX》上.pdf"   inputs/<book_id>_shang.pdf
   cp "《XX》下.pdf"   inputs/<book_id>_xia.pdf
   ```
2. 复制一份书目配置模板，改 `id / title / author / chapters`：
   ```bash
   cp templates/books.yaml.example config/books.yaml
   ```
3. 跑（见下文"跑批"）。

### B. 文本型书（公版书推荐：道德经/论语/庄子…）

1. 准备 JSON：`inputs/<book_id>.json`
   ```json
   {"meta": {"title":"道德经","author":"老子","version":"王弼本"},
    "chapters": {"01": "道可道，非常道。…", "02": "…", ...}}
   ```
2. books.yaml 里只需极简配置（81 章自动展开）：
   ```yaml
   - id: daodejing
     title: "道德经"
     author: 老子
     source_type: text
     text_source: daodejing.json
     auto_chapters: 81
     auto_label_format: "第 {n} 章"
     category: 国学
     tags: [道家, 先秦哲学, 经典, 公版]
     cover_color: "#2E4756"
   ```
3. 跑批（`06` 会自动识别 `source_type: text` 并改用 `01b_split_text_book.py`）。

> **公版书是合规策略的关键**：原文过了版权保护期，注释/解析是你自己的，可以公开发布和收费。
> 版权期内的书（出版未满 50 年）只能个人使用，不可公开发布。开源示例请用公版书。

## 跑批

```bash
cd "<skill 目录>/scripts"
"<venv>" 06_run_one_chapter.py --book <id> --chapter 01        # 单章验收
"<venv>" 07_run_all.py          --book <id>                     # 顺序全跑
"<venv>" 13_run_parallel.py     --book <id> --workers 4         # 并行全跑（推荐）
```

**并行跑快 10 倍**：道德经 81 章从 2.5 小时降到 17 分钟。
并行时 `06` 用 `--no-library` 避免多进程抢写书架，`13` 在全部完成后统一刷一次。
中断可安全重跑——`06` 会自动跳过已完成的 D 步。

---

## 5 步流水线（核心）

| 步 | 做什么 | 产出 | 何时人工介入 |
|---|---|---|---|
| D1 拆页 | **PDF 书**：PyMuPDF 按页号抽文字 + 抽位图；**文本书**（道德经等）：`01b_split_text_book.py` 按章切 JSON | `pages/p*.txt`、`figures/*.png`、`chapter_XX.txt`、`chapter_XX.yaml` | 极少，除非 PDF 是扫描版需要 OCR |
| D2 笔记 | 调 LLM：每页做 "core_propositions/key_arguments/cases/new_concepts/cross_chapter_hints"；最后整章 rollup 一份 +5 个苏格拉底问题 | `notes/per_page/p*.json`、`notes/notes.json` | per_page 30+ 条以上要花 5-10 分钟，不需要人工 |
| D3 图谱 | 调 LLM 输出 Mermaid `flowchart LR`；节点类型限 P/C/K/A/E，边类型 supports/instance_of/relates_to；节点 ≤40 边 ≤60 | `graph/graph.mmd`、`graph/graph.md` | 节点偏少或偏多要调 prompt |
| D4 草稿 | 三个 LLM 调用：导读四步卡（书概览/多问题/跨作者/精读）、L0-L3 术语表、苏格拉底 4 类 prompt + 5-7 新手引导问题 | `overview/overview.md`、`glossary/glossary.md`、`socrates/socrates.md` | — |
| D5 前端 | markdown 渲染到 HTML；Mermaid.js 通过 CDN 渲染图谱；copy/WrongMark 按钮挂载；localStorage 错题本 | `site/index.html`（双击即用）+ `site/figures/` | — |

**两类书源**：
- `source_type: pdf`（默认）→ D1 用 `01_split_chapter.py`，需 `volumes[].path` 指向 PDF
- `source_type: text` → D1 用 `01b_split_text_book.py`，需 `text_source` 指向 JSON（`{"chapters": {"01": "原文", ...}}`）+ `auto_chapters: N` 自动展开章列表

`06_run_one_chapter.py` 会读 books.yaml 自动选对 D1 脚本，无需手动干预。

LLM 默认走白名单里的 `deepseek-v4-flash`（reasoning effort=low）做主力；切到其他模型只改 `config/books.yaml` 的 `model_routing`。

---

## 自检（review.py 跑 8 项校验）

**门槛按章长自适应**：正文 < 2000 字 → 短章标准（《道德经》这类），否则长章标准。

| 项 | 长章门槛 | 短章门槛 | 不通过的代价 |
|---|---|---|---|
| 6 个产物文件齐全 | 都存在 | 都存在 | FAIL |
| 笔记命题数 | ≥8 | ≥3 | WARN |
| 论据数 | ≥5 | ≥2 | WARN |
| 案例数 | ≥2 | ≥0 | WARN |
| 新概念数 | ≥8 | ≥3 | WARN |
| 跨章提示数 | ≥3 | ≥0 | WARN |
| 苏格拉底问题数 | ≥4 | ≥3 | WARN |
| Mermaid 节点 | 10-50 | 6-50 | 太少 WARN / 太多 FAIL |
| L0-L3 术语表行数 | ≥6 | ≥3 | WARN |
| 关键词覆盖 | ≥40% | 仅对配置了关键词的书检查 | WARN |
| HTML 渲染正常 | 体积 > 8KB + 含 mermaid / prompt-card | 同左 | FAIL |

关键词表按书隔离：`CHAPTER_KEYWORDS[book_id][chapter_id]`。未配置的书跳过该项（不算警告）。

致命错 → 跳过该章继续下章；警告 → 继续跑。

---

## 模型白名单（硬约束）

`scripts/lib/llm.py` 自动从 `~/.workbuddy/models.json` 加载 5 个 id：
- `deepseek-v4-flash`（推理强，reasoning effort=low）
- `doubao-seed-2.1-lite`（多模态/图）
- `glm-5.3`（方舟）
- `kimi-k3`（方舟/多模态）
- `MiniMax-M3`（1M 上下文，我本人）

调用前 `assert_allowed()` 断言；任何"WorkBuddy 推荐/官方"模型（DeepSeek-V3/R1、GLM-4.x、Qwen3、ERNIE-4.x、Doubao-pro、Kimi 公版 等）一律 raise 拒绝。

不要扩展白名单。如果非要扩展，去 `~/.workbuddy/models.json` 加——这是头哥（用户）的私人决定。

---

## 已知坑与对应处理

1. **reasoning 模型吃光 tokens**：已默认 `reasoning_effort=low` + `max_tokens=20000`。如果还有截断，把脚本里 `max_tokens` 调更大。
2. **JSON 输出不严谨**：已用 `json_repair` 兜底 + 截取首 `{` 末 `}` + 多重 retry（4 次）。
3. **⚠️ LLM 字段名不统一（最常见坑）**：`new_concepts` 的条目键名会出现 9 种以上组合——
   `concept/term/name` × `explanation/plain/explain/plain_explanation/白话解释`，还有纯字符串。
   **必须用 `lib/normalize.py` 的 `concepts_of()/cases_of()` 读取**，直接 `c.get("concept")` 会拿到 None，
   导致术语表生成"本章概念列表为空"、前端概念区空白、review 误报数量。
4. **图谱抽出过多装饰图**：PDF 书可能抽出背景图，前端已限制每章显示前 12 张。
5. **HTML `.format()` 与 CSS/JS 的 `{}` 冲突**：脚本用 `replace()` 而非 `format()`。
6. **yaml `id: 01` 被解析成 int**：`find_chapter()` 用 `str(c["id"]) == str(chapter_id)` 兼容。
7. **`_which_done` 判定 D4 要查三个文件**：`overview.md` + `glossary.md` + `socrates.md` 齐全才算完成，
   否则中断重跑会跳过 D4 留下缺文件的章。
8. **短章会被长章门槛误判**：`review.py` 按正文字数 < 2000 自动切短章标准；
   关键词表按书隔离（`CHAPTER_KEYWORDS[book_id]`），未配置的书跳过该项。
9. **改了 04 的 prompt 后要重刷 glossary**：旧 glossary 是旧 prompt 产物，
   用 `14_refresh_glossary.py --book <id> [--chapters xx,yy]` 只重跑术语表（不动 notes/graph），成本低。

## L3 术语表的设计（重要）

`04_make_overview.py` 的 SYSTEM 采用**分层原则**：

- **L0/L1/L2、导读、苏格拉底问题** → 严格基于本章笔记与原文，不得编造。
- **L3 思想史层** → 允许且**要求**引用公共学术常识：历代注家（王弼/河上公/郭象/成玄英/苏辙/王夫之/裴頠）、
  不同学派（庄列、孔孟荀、韩非、中观、海德格尔、维特根斯坦）、现代研究（陈鼓应/楼宇烈/刘笑敢/葛兆光）。

如果 SYSTEM 写成"一律不得补充书上没有的内容"，L3 会退化成"笔记未提供，不作补充"——L3 就废了。
这是踩过的坑，别改回去。

---

## 与其它辅助文件的关系

- `scripts/01_split_chapter.py` ~ `05_build_frontend.py` 五个 D 步独立可调
- `scripts/06_run_one_chapter.py` 一键跑 1 章（含 review）
- `scripts/07_run_all.py` 顺序跑全部章节 + 写 `_aggregate_report.md`
- `scripts/08_fix_html.py` 修复 HTML 缺失（早期 bug）
- `scripts/lib/llm.py` 白名单 + LLM 调用
- `scripts/lib/pdf_tools.py` PyMuPDF 工具
- `scripts/lib/book_config.py` 读 books.yaml
- `scripts/lib/review.py` per-章节校对 + 自测
- `templates/books.yaml.example` 书目配置模板
- `references/books-yaml-schema.md` 配置字段详细文档
- `references/prompt-templates.md` 5 个 D 步的 prompt 模板
- `references/review-criteria.md` 自测 8 项标准详解
- `references/per-chapter-keywords.md` 每章关键概念清单

---

## 跑一轮的端到端示例（公版书《道德经》81 章）

```bash
cd "<本 skill 目录>/scripts"
"<venv>/Scripts/python.exe" 06_run_one_chapter.py --book daodejing --chapter 01
# 验收第 1 章 OK →
"<venv>/Scripts/python.exe" 07_run_all.py --book daodejing --start 02 --end 81
# 跑完后看
open ../../outputs/daodejing/_aggregate_report.md
```

跑出来的 `outputs/daodejing/chapter_XX/site/index.html` 都是双击即用，不需要后端，不需要联网（首次 Mermaid CDN 后可离线）。

---

## 跑完之后还可以做

- 把整套 `outputs/<book>/` 复制到一个长期库（你的"读书库"）
- 把 `site/index.html` 串成一本"合订本"：`python scripts/lib/<tbd>_combine_books.py` （v2.0）
- 上线：包到云函数 + 公众号（v4）

