# review.py 自测 8 项标准详解

`scripts/lib/review.py` 对每个章节产出 `review.md` + `review.json`。本文件说明每项标准的依据与可调整的默认值。

## 校验项目

| 项 | 默认门槛 | 改成什么？ | 为什么会这样定？ |
|---|---|---|---|
| **files_exist** | 6 文件齐全 | 必为存在 | 任何缺文件都是 bug，要求 D1-D5 全成功 |
| **core_propositions** | ≥8 | 长章节（>40 页）调 12；短章节（<20 页）调 5 | 一章平均应有 8-30 条命题 |
| **key_arguments** | ≥5 | 同上 | 论据密度低于命题 |
| **cases** | ≥2 | 0 也行（哲学/理论章节未必有案例） | 案例是非虚构的标志，但不是必须 |
| **new_concepts** | ≥8 | 哲学章调 15；史事章调 5 | 概念密度是知识图谱的输入 |
| **cross_chapter_hints** | ≥3 | 历史/哲学章应有 5-10；技术章节可降到 2 | 跨章提示关联全书的体系 |
| **socrates_questions** | ≥4 | 入门读者章节应有 5-7 | 苏格拉底的核心 |
| **mermaid_nodes** | 10-50 | <10 → FAIL；>50 → FAIL | 太少图谱没价值，太多易乱 |
| **glossary_rows** | ≥6 | 难章节（如量子）调 12 | 术语表是新词索引 |
| **keyword_coverage** | ≥40% | 加严到 60% / 放松到 30% | 通过看 books.yaml 关键词清单 |
| **html_render** | >8KB + 有 mermaid + 有 prompt-card | — | 硬指标 |

## Verdict 等级

- **PASS**：所有都过
- **WARN**：warnings 非空但 issues 空（致命问题为 0、警告 ≥ 1）
- **FAIL**：致命问题 ≥ 1；这种情况 `07_run_all` 会跳过该章继续下章

## 调整标准

如果发现某本书的章节系统性地偏 WARN/FAIL，可以：

1. 在 `scripts/lib/review.py` 改 `DEFAULT_CRITERIA` 字典
2. 在 `scripts/lib/review.py` 改 `CHAPTER_KEYWORDS` 字典（加章节关键词）
3. 直接编辑 review.json / review.md（不推荐，结果不入下一章）

## 用 review 的方式

- **看 review.md**：每章的人工可见报告
- **看 review.json**：机器可读 verdict，便于聚合
- **看 _aggregate_report.md**：14 章总报告（表格）

