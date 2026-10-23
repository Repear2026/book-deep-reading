"""normalize.py — 归一化 LLM 输出的不统一字段名。

背景：不同章、不同模型、不同 prompt 版本下，LLM 对「概念」这类对象会输出
9 种以上不同的键名组合：
    ('concept','explanation') / ('term','explanation') / ('term','plain')
    ('concept','plain') / ('name','explanation') / ('term','explain')
    ('concept','plain_explanation') / ('term','白话解释') / 纯字符串

这里提供统一的读取入口，调用方不再关心具体键名。

用法：
    from lib.normalize import concept_name, concept_explain, case_name, case_desc
"""
from __future__ import annotations
from typing import Any

# 概念名可能的键（按优先级）
_NAME_KEYS = ("concept", "term", "name", "概念", "术语", "名称")
# 解释可能的键
_EXPLAIN_KEYS = ("explanation", "plain", "explain", "plain_explanation",
                 "白话解释", "解释", "说明", "description")
# 案例名
_CASE_NAME_KEYS = ("name", "case", "title", "案例", "名称")
_CASE_DESC_KEYS = ("description", "desc", "detail", "explanation", "内容", "详情")


def _pick(d: dict, keys: tuple[str, ...]) -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def concept_name(item: Any) -> str:
    """从任意形态的概念条目里取名字。"""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return _pick(item, _NAME_KEYS)
    return ""


def concept_explain(item: Any) -> str:
    """从任意形态的概念条目里取解释。"""
    if isinstance(item, dict):
        return _pick(item, _EXPLAIN_KEYS)
    return ""


def case_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()[:60]
    if isinstance(item, dict):
        n = _pick(item, _CASE_NAME_KEYS)
        if n:
            return n
        # 退化：取描述前 30 字作为名字
        d = _pick(item, _CASE_DESC_KEYS)
        return d[:30] if d else ""
    return ""


def case_desc(item: Any) -> str:
    if isinstance(item, dict):
        return _pick(item, _CASE_DESC_KEYS)
    return ""


def concepts_of(notes: dict) -> list[dict]:
    """统一返回 [{name, explain}]，丢弃无名条目。"""
    out = []
    for item in (notes.get("new_concepts") or []):
        n = concept_name(item)
        if n:
            out.append({"name": n, "explain": concept_explain(item)})
    return out


def cases_of(notes: dict) -> list[dict]:
    out = []
    for item in (notes.get("cases") or []):
        n = case_name(item)
        if n:
            out.append({"name": n, "desc": case_desc(item)})
    return out
