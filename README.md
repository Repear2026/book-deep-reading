# Book Deep Reading · 把书拆成能被读懂的结构

> 一本 PDF 或纯文本的书，自动拆成：章节 → 结构化笔记 → 知识图谱 → 多难度术语表。
> 每章一个网页，双击就能读，手机适配。

**[在线示例：《道德经》81 章](https://github.com/)** （部署后替换为实际 Pages 地址）

---

## 这个项目解决什么

读一本硬书，卡住人的往往不是字句，而是三件事：

1. **不知道这章在全书里处在什么位置** —— 读到一半失去方向
2. **抓不住作者的论证链条** —— 记住了结论，不知道为什么成立
3. **概念和概念连不起来** —— 读完像捡了一地零件

市面上的 AI 摘要有用，但它把结构磨平了。这个项目做的不是压缩，是**还原结构**：
让你看见命题、论据、案例、概念各自在哪，以及它们怎么连。

## 每章产出什么

一个章节页（`site/index.html`，双击即开）包含：

| 区块 | 内容 |
|---|---|
| 📜 原文 | 置顶显示，衬线字体，第一屏就读到原文 |
| 📖 四步导读 | 书概览 / 问题意识 / 跨作者碰撞 / 精读建议 |
| 🕸 知识图谱 | Mermaid 图：命题 ← 论据，案例 → 命题，概念关联 |
| 📝 结构化笔记 | 核心命题 / 关键论据 / 案例 / 新概念 / 跨章线索 |
| 🗣 苏格拉底追问 | 4 类追问模板 + 5-7 个分层引导问题 |
| 📚 术语表 | 每个概念 L0 白话 / L1 教材 / L2 学术 / L3 思想史；手机端自动卡片化 |
| ❓ 错题本 | 本地存储，答不好的问题可记录回看 |

顶部固定阅读条：`☰ 目录 · 第 N/总 章 · ← 上一章 · 下一章 →`

## 一条流水线，五步

```
D1 拆   PDF 按页抽文字与插图（PyMuPDF） / 纯文本按章切分
D2 记   逐页抽取核心命题、论据、案例、新概念、跨章线索
D3 连   生成 Mermaid 知识图谱（命题/概念/案例/人物 + 支撑与关联边）
D4 译   导读四步卡 + L0-L3 多难度术语表 + 苏格拉底追问模板
D5 读   渲染成单页 HTML（含 Mermaid 渲染、错题本、章间导航、移动端适配）
```

## 实测数据

| 书 | 规模 | 耗时 | 产出 |
|---|---|---|---|
| 《道德经》（王弼本） | 81 章 / 约 5300 字 | **17 分钟**（4 路并行） | 81 章页 · 2000+ 笔记条目 · 1090 图谱节点 |

## 快速开始

```bash
git clone <this-repo>
cd skill/scripts
pip install pymupdf pyyaml json-repair

# 单章试跑（先用示例配置）
cp ../templates/books.yaml.example ../../config/books.yaml   # 或按下方说明自建
python 06_run_one_chapter.py --book daodejing --chapter 01

# 整本并行跑（推荐，快约 10 倍）
python 13_run_parallel.py --book daodejing --workers 4

# 生成书入口页 + 书架
python 10_build_book_index.py --book daodejing
python 12_build_library.py
```

## 支持两类书源

**A. PDF 书**

```yaml
- id: my_book
  title: "书名"
  author: 作者
  volumes:
    - id: shang
      path: my_book_shang.pdf    # 放在 inputs/
      pages: 400
  chapters:
    - id: "01"
      label: "第 1 章 · 章题"
      volume: shang
      pages: [21, 45]            # PDF 页号，含两端
```

**B. 文本型书（公版书推荐）**

```yaml
- id: daodejing
  title: "道德经"
  author: 老子
  source_type: text
  text_source: daodejing.json    # {"chapters": {"01": "原文", ...}}
  auto_chapters: 81              # 81 章自动展开
  auto_label_format: "第 {n} 章"
```

## 目录结构

```
skill/
├── SKILL.md                     # 完整使用说明（含 9 条踩坑清单）
├── scripts/
│   ├── 01_split_chapter.py      # D1 PDF 拆页
│   ├── 01b_split_text_book.py   # D1 文本拆章
│   ├── 02_make_notes.py         # D2 结构化笔记
│   ├── 03_make_graph.py         # D3 知识图谱
│   ├── 04_make_overview.py      # D4 导读/术语表/追问
│   ├── 05_build_frontend.py     # D5 单页 HTML
│   ├── 06_run_one_chapter.py    # 一键跑 1 章（含自检）
│   ├── 07_run_all.py            # 顺序跑全部
│   ├── 13_run_parallel.py       # 并行跑（推荐）
│   ├── 09_reaggregate.py        # 全书聚合报告
│   ├── 10_build_book_index.py   # 书入口页
│   ├── 12_build_library.py      # 多书书架
│   └── lib/
│       ├── llm.py               # LLM 调用（自带白名单校验）
│       ├── pdf_tools.py         # PyMuPDF 封装
│       ├── book_config.py       # books.yaml 解析
│       ├── normalize.py         # LLM 输出字段名归一化
│       └── review.py            # 8 项自动校对
├── references/                  # 详细文档
└── templates/books.yaml.example
docs/                            # GitHub Pages 站点（示例书）
```

## 每章自动自检（8 项）

跑完一章自动检查并给出 PASS / WARN / FAIL：

- 6 个产物文件齐全 → 缺则 FAIL
- 笔记命题数 / 论据数 / 案例数 / 新概念数 / 跨章线索数 → 低于门槛则 WARN
- 苏格拉底问题数 → WARN
- Mermaid 图谱节点数（10-50）→ 太少 WARN、太多 FAIL
- L0-L3 术语表行数 → WARN
- 关键词覆盖（按书配置，未配置则跳过）
- HTML 渲染正常（体积 + 关键区块）→ FAIL

**门槛按章长自适应**：正文 < 2000 字的短章用宽松标准（《道德经》一章才几十字）。

## 关于合规与版权

- **原文**：示例用的是《道德经》王弼通行本，属**公有领域**，可自由公开。
- **解析内容**：由 AI 辅助生成，属加工产物。公开发布时建议明确标注"AI 辅助生成"。
- **版权期内的书**（现代出版物）：建议**仅个人使用**，不要公开分发其原文摘录或大段译文。
  本项目不提供、也不建议绕过版权限制。
- **AI 内容标识**：在中国大陆平台发布 AI 生成内容，须遵守《人工智能生成合成内容标识办法》
  等规定，主动声明并标注。

## 已知限制

- 扫描版 PDF 需要先 OCR（本项目默认用 PyMuPDF 抽文本层）
- LLM 输出字段名不统一，已用 `lib/normalize.py` 兜底，但新增 prompt 时仍需留意
- 知识图谱节点上限 50，超长章节会做裁剪（按连接度排序）
- 苏格拉底追问目前是"复制 prompt 到其他 AI"，未内置对话面板

## License

代码：MIT。示例书内容：原文为公有领域；解析内容由 AI 辅助生成，署名可省略但请标注来源。
