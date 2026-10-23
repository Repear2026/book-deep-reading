# 5 个 D 步的 prompt 模板

> 这些 prompt 实际在 `scripts/0X_*.py` 里以字符串形式保存。本文是说明文档，方便调整时回看。

## D1 拆页（无 LLM，纯 PyMuPDF）

不需要 prompt。但要避免：**页码是 PDF 物理页号**（PyMuPDF 0-indexed，所以代码里写 `pages[i]` 对应 PDF 页号 `i+1`）。

## D2 笔记（LLM，per-page + rollup）

SYSTEM：
```
你是《{书名}》伴读系统的笔记员。要求：
1. 你只能基于【当前章节正文】做笔记，不得补充书上没有的概念或"幻觉"出原文没有出现的内容。
2. 输出必须是单个 JSON object，不要 ``` 代码块，不要任何前后文。
3. 字段：core_propositions, key_arguments, cases, new_concepts, cross_chapter_hints。
4. 如果某字段在正文中为空，输出空列表。
5. JSON 字符串里如果需要双引号，用转义 \\"。
```

USER（per-page）：
```
章节：{chapter_label}
当前是第 {page_num} 页文本：
---
{page_text[:5500]}
---
请输出本页笔记（只输出单个 JSON object，不带 ```）。
```

调用关键参数：`max_tokens=8000`、`reasoning_effort=low`、`temperature=0.2`、`retry=4`。retry 时输出空字符串也算失败。

整章 rollup prompt 类似但要求输出 `title + chapter_role + suggested_socratic_questions[3-5 个问题]`。

## D3 知识图谱（LLM，Mermaid 输出）

SYSTEM：
```
你是知识图谱工程师。任务：基于章节笔记画一张 Mermaid 图。
约束：
1. 用 Mermaid `flowchart` 语法（用 `flowchart LR`）。
2. 节点类型限定：Proposition / Concept / Case / Author / Event（缩写成 P/C/K/A/E）。
3. 节点标签统一用双引号，转义用 \\"。
4. 边的类型：supports（论据→命题）、instance_of（案例→命题）、relates_to（同位关系）。
5. 全部节点 ≤ 40 个，边 ≤ 60 条；不允许出现意义重复节点。
6. 只输出 Mermaid 源码（从 `flowchart LR` 开头），不要 markdown 代码块包装，不要任何前后解释。
7. 节点 ID 用拼音或英文短词，标签中写中文。
```

USER：传入 `notes_json` 截短版（避免 reasoning 烧光）。

调 `max_tokens=20000`、`reasoning_effort=low`、`temperature=0.3`。

## D4 草稿（3 个 LLM 调用并行/串行）

**导读四步卡**：
- ①书概览（5 分钟）：一段话让小白读者明白这章讲什么 + 为什么有趣 + 最重要收获
- ②多问题意识关联：3 个"如果...会..."的发问
- ③其他作者观点碰撞：3 位其他思想家对该主题的回应
- ④精读推荐：第一遍/第二遍/第三遍

**L0-L3 术语表**：每个新概念分 4 层：
- L0 一句话（普通人能懂）
- L1 教材级（中文百科）
- L2 学术级（引用原文术语）
- L3 哲学/思想史反思

**苏格拉底 prompt**：4 个固定模板 + 5-7 个新手引导问题。
- 理解检查 / 强反驳 / 连现实 / 深挖
- 引导问题按"小白友好 → 5 年哲学爱好"排序

## D5 前端（无 LLM，markdown 渲染）

- 用 HTML 模板（`scripts/05_build_frontend.py` 里的 `HTML_TEMPLATE`）
- Mermaid 渲染走 CDN：`https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js`
- 错题本用 localStorage：`shijie_c01_wrongs`
- "复制 prompt" / "我没答好" 按钮用 JS 注入 `document.querySelectorAll('.prompt-card')`

---

## 调整准则

1. **不要改字段名**：notes JSON 的字段是契约，下游 `build_notes_html()` 依赖这些 key。
2. **改 prompt 时调 temperature**：搜索结果 0.2、整章 rollup 0.3、图谱 0.3、术语表 0.3、苏格拉底 0.4。
3. **加 prompt test**：用 D2 跑单页验证 JSON 解析。
4. **高级调优**：在 `llm.py` 加 `temperature=0.5` 或 `top_p` 探索多样性。
