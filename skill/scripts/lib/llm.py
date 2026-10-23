"""
伴读系统的 LLM 调用层。

模型清单按以下顺序查找（找到第一个即用）：
  1. 环境变量 BOOKDR_MODELS_FILE 指定的路径
  2. 项目根目录的 config/models.json
  3. ~/.workbuddy/models.json（WorkBuddy 用户的自定义模型清单）

models.json 格式（数组）：
    [{"id": "deepseek-v4-flash",
      "name": "DeepSeek-V4 Flash",
      "url": "https://api.deepseek.com/chat/completions",
      "apiKey": "sk-xxx",
      "supportsReasoning": true}]

调用方用法：
    from lib.llm import call, ALLOWED
    call("deepseek-v4-flash", "...", system="...")
"""
from __future__ import annotations
import json, os, re, sys, urllib.request, urllib.error
from pathlib import Path

# 项目根 = scripts/lib/ 向上两级
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

MODEL_FILE_CANDIDATES = [
    Path(os.environ["BOOKDR_MODELS_FILE"]) if os.environ.get("BOOKDR_MODELS_FILE") else None,
    _PROJECT_ROOT / "config" / "models.json",
    Path.home() / ".workbuddy" / "models.json",
]
MODEL_FILE_CANDIDATES = [p for p in MODEL_FILE_CANDIDATES if p is not None]

# 向后兼容：保留原名指向最终命中的文件
WORKBUDDY_MODELS_FILE = next((p for p in MODEL_FILE_CANDIDATES if p.exists()),
                              MODEL_FILE_CANDIDATES[0])

# WorkBuddy "推荐/官方" 模型黑名单（凡是 list_installed_plugins / mcp clist_models
# 暴露的非白名单模型都属于"推荐"——直接当公版拒绝）
WB_OFFICIAL_DENY = re.compile(
    r"(deepseek[\-_]?(v3|v3[.]\d|r1)(?!\-flash)|"
    r"glm[\-_]?4(\.\d+)?(?!\.\d\d{2,3}$)|"
    r"qwen[\-_]?3[\-_]?(max|plus|turbo|omni)|"
    r"ernie[\-_]?4(\.\d+)?|"
    r"doubao[\-_]?(1\.5[\-_]?pro|pro|seed[\-_]1[\-_]?)|"
    r"kimi[\-_]?(k1\.5|k2)(?!\d{2,3}$)|"
    r"hunyuan[\-_]?(pro|std)|"
    r"spark[\-_]?(v[3-9]|4))",
    re.IGNORECASE,
)


def _load_workbuddy_models() -> list[dict]:
    """按 MODEL_FILE_CANDIDATES 顺序查找模型清单。"""
    for p in MODEL_FILE_CANDIDATES:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    return data
            except Exception as e:
                raise RuntimeError(f"{p} 解析失败: {e}")
    raise FileNotFoundError(
        "找不到模型配置文件。请任选其一：\n"
        f"  ① 在 {_PROJECT_ROOT / 'config' / 'models.json'} 放一份模型清单\n"
        "  ② 设置环境变量 BOOKDR_MODELS_FILE 指向你的 models.json\n"
        "  ③ 使用 WorkBuddy 时它会自动读取 ~/.workbuddy/models.json"
    )


def _index_workbuddy_models() -> dict[str, dict]:
    """返回 {id: model_entry}，id 已经做大小写归一化（下划线和连字符等价）。"""
    raw = _load_workbuddy_models()
    idx = {}
    for m in raw:
        m_id = m.get("id", "").strip()
        if not m_id:
            continue
        idx[m_id] = m
        # 兼容 alias：把 "-" 和 "_" 互换
        idx[m_id.replace("-", "_")] = m
        idx[m_id.replace("_", "-")] = m
    return idx


# 启动时一次加载
WB_INDEX = _index_workbuddy_models()

# 程序内统一别名（路径规范）：只保留原 5 个 id
ALLOWED = {m["id"]: m for m in _load_workbuddy_models() if m.get("id")}
# 兼容 dash / underscore 互转
ALLOWED_ALIAS = dict(WB_INDEX)


def is_allowed(model_id: str) -> bool:
    """白名单检查：返回 True 表示是 WorkBuddy 自定义清单里的 id，否则 False。"""
    return model_id in ALLOWED_ALIAS


def is_workbuddy_official(model_id: str) -> bool:
    """判断是否 WorkBuddy 官方/推荐模型（必须禁用）。"""
    return bool(WB_OFFICIAL_DENY.search(model_id or ""))


def assert_allowed(model_id: str) -> dict:
    """强校验：不在白名单 → 直接抛错。

    返回 workbuddy 原 entry（含 url/apiKey）。
    """
    if not is_allowed(model_id):
        if is_workbuddy_official(model_id):
            raise PermissionError(
                f"❌ 模型 {model_id!r} 是 WorkBuddy 官方/推荐模型，**不允许调用**。"
                f"白名单: {sorted(ALLOWED.keys())}"
            )
        raise ValueError(
            f"❌ 模型 {model_id!r} 不在 ~/.workbuddy/models.json 自定义清单里。"
            f"白名单: {sorted(ALLOWED.keys())}"
        )
    return ALLOWED_ALIAS[model_id]


def call(
    model_id: str,
    prompt: str,
    system: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int = 120,
) -> str:
    """统一的 LLM 调用入口。

    自动用 model_id 在白名单里找到 endpoint 与 apiKey。
    """
    entry = assert_allowed(model_id)
    url = entry["url"]
    api_key = entry.get("apiKey", "")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body: dict = {"model": model_id, "messages": []}
    if system:
        body["messages"].append({"role": "system", "content": system})
    body["messages"].append({"role": "user", "content": prompt})
    if temperature is not None:
        body["temperature"] = temperature
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    # 抑制 reasoning 占用 —— reasoning 模型需要"低 effort"或"关闭"才能把 tokens 留给 content
    if entry.get("supportsReasoning"):
        body["reasoning_effort"] = "low"

    req = urllib.request.Request(url, headers=headers, data=json.dumps(body).encode("utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        # 把远端错误原样转回
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM 调用失败 {e.code}: {body[:400]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM 无法连接 {url}: {e}") from e


if __name__ == "__main__":
    # 自检：打印当前白名单 + 触发一段黑名单检测
    print("✅ WorkBuddy 自定义模型白名单（~/.workbuddy/models.json）:")
    for m in WB_INDEX.values():
        print(f"  - id={m.get('id'):<28} vendor={m.get('vendor'):<10} reasoning={m.get('supportsReasoning')}")
    print()
    print("🔒 黑名单检测（必须返回 False）：")
    for test in ["DeepSeek-V3", "GLM-4.5", "Qwen3-Max", "ERNIE-4.5", "Doubao-pro", "kimi-k2", "deepseek-v4-flash"]:
        official = is_workbuddy_official(test)
        allowed = is_allowed(test)
        print(f"  {test:<25} → official={official}  allowed={allowed}")
