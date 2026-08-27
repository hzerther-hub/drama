# -*- coding: utf-8 -*-
"""量化知识库（RAG 的 R）：加载 + 轻量检索。

知识构成：
  1. api_maps/joinquant_ptrade.md —— 平台 API 对照表（映射/白名单/语料三用）
  2. few-shot 策略对 —— 从 benchmark.BENCHMARKS 动态生成
     （已知正确的 代码 ↔ IR 对，永远与发射器/解析器同步，不存静态副本）
  3. kb/*.md —— 手写量化知识（随时往里丢，自动纳入检索）

检索：库小，用关键词重叠打分（诚实轻量，不上 embedding）。
将来语料变大或微调启动（v2.0）时再换向量检索。
"""

from __future__ import annotations

import os
import re

from .emitters import emit

QUANT_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(QUANT_DIR, "kb")
API_MAPS_DIR = os.path.join(QUANT_DIR, "api_maps")

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[一-鿿]+")


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_documents() -> list[dict]:
    """全部知识文档：[{"id", "text", "kind"}]。每次调用现读（库小，免去缓存失效问题）。"""
    docs: list[dict] = []
    if os.path.isdir(API_MAPS_DIR):
        for fn in sorted(os.listdir(API_MAPS_DIR)):
            if fn.endswith(".md"):
                docs.append({"id": f"api_map:{fn}", "kind": "api_map",
                             "text": _read(os.path.join(API_MAPS_DIR, fn))})
    # few-shot：5 基准策略 × 4 平台代码 ↔ IR
    from .benchmark import BENCHMARKS, PLATFORMS     # noqa: PLC0415 防循环导入
    for ir in BENCHMARKS:
        for platform in PLATFORMS:
            docs.append({
                "id": f"fewshot:{ir.signals[0].kind}:{platform}",
                "kind": "fewshot",
                "text": (f"# 示例（{platform}）：{ir.name}\n"
                         f"```python\n{emit(ir, platform)}```\n"
                         f"对应 IR：\n```json\n{ir.to_json()}\n```"),
            })
    if os.path.isdir(KB_DIR):
        for fn in sorted(os.listdir(KB_DIR)):
            if fn.endswith(".md"):
                docs.append({"id": f"kb:{fn}", "kind": "kb",
                             "text": _read(os.path.join(KB_DIR, fn))})
    return docs


_SNIPPET_MAX = 3000   # 大文档（官方 API 镜像 ~300KB）只取关键词邻域片段


def _snippet(text: str, q: set[str]) -> str:
    """大文档截取：找到命中查询词最多的一段窗口，首尾留上下文。"""
    if len(text) <= _SNIPPET_MAX:
        return text
    # 以段落为单位打分，取最高分段落的邻域
    paras = text.split("\n\n")
    best_i, best_score = 0, -1
    for i, para in enumerate(paras):
        score = len(q & _tokens(para))
        if score > best_score:
            best_i, best_score = i, score
    out, total = [], 0
    i = best_i
    while i < len(paras) and total < _SNIPPET_MAX:
        out.append(paras[i])
        total += len(paras[i])
        i += 1
    return "[片段截取自完整文档]\n" + "\n\n".join(out)


def retrieve(query: str, k: int = 3, kind: str | None = None,
             snippet: bool = False) -> list[dict]:
    """按关键词重叠取 top-k 文档。kind 可限定 'fewshot'/'kb'/'api_map'。
    snippet=True 时大文档只返回关键词邻域片段（喂 LLM 用）。"""
    q = _tokens(query)
    scored = []
    for d in load_documents():
        if kind and d["kind"] != kind:
            continue
        score = len(q & _tokens(d["text"]))
        if score:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, d in scored[:k]:
        if snippet:
            d = {**d, "text": _snippet(d["text"], q)}
        out.append(d)
    return out
