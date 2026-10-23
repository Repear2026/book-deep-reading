# books.yaml 字段详解

| 字段 | 必需？ | 类型 | 说明 |
|---|---|---|---|
| `id` | ✓ | str | **字符串加引号**（`"01"` 而非 `01`，否则 YAML 解析成 int）。用作 `outputs/<id>/` 目录名，全局唯一。 |
| `title` | ✓ | str | 显示在每章页头 |
| `author` | ✓ | str | 显示在每章页头 |
| `volumes` | ✓ | list | 多分册；每项 `id` 与 `path` 与 `pages`（PDF 总页数） |
| `chapters` | ✓ | list | 顺序写，pipeline 顺序跑 |
| `preface` | ✗ | list | 引言/序言；可省略 |
| `part` | ✗ | str | 章所属部分标题；用于分组显示 |
| `hook` | ✗ | str | 章首引语（名人名言）—— prompt 提示注入 |
| `status` | ✗ | enum | todo / wip / done（pipeline 不强依赖） |
| `model_whitelist` | ✗ | list | 5 个 id；改 `~/.workbuddy/models.json` 才是真名单 |
| `model_routing` | ✗ | dict | 用途→模型映射；pipeline 会查这张表 |
| `model_blacklist` | ✗ | list | 永远不调（仅记录，pipeline 启用正则 detect `WB_OFFICIAL_DENY`） |

## 常见错误

1. **id 没加引号**：`id: 01` → YAML 解析成 `id: 1`。`find_chapter` 用 `str(c["id"])` 兼容，但脚本里 `args.chapter` 必须传 `"01"`。
2. **PDF 路径写错**：相对路径以 `inputs/` 为基准。
3. **页号写错**：PDF 页号从 1 算。例如第 1 章起始页 39，意味着 PDF 第 39 页是该章首页。
4. **章内的 hook/quote 没写**：`prompt` 会直接用 `chapter_label` 替代，不报错；只是 MD 上不显示引语块。

## 加新书

最简单复制 `templates/books.yaml.example`，填上书的基本信息和分册路径，把 PDF 放到 `inputs/<book_id>_shang.pdf` / `<book_id>_xia.pdf`，跑流水线。

不要复用旧书的 `chapter_XX`，新书自然在 `outputs/<new_book_id>/chapter_YY/`。

## 版本兼容

pipeline 是 v0.1。`books.yaml` 字段 `id / title / author / volumes.path / volumes.pages / chapters[].volume / chapters[].pages` 这 7 项是**契约字段**，别动。其他字段未来加新字段是后向兼容的。

## 多本书并存

把多本书写在同一 `books.yaml` 即可，每本一个 `- id: ...`。`06/07/08` 脚本只接受 `--book <id>` 一个。

