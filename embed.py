# -*- coding: utf-8 -*-
"""OpenAI-compatible embeddings 客户端（企业代码知识库的可选增强）。

用 stdlib `urllib.request` 直接 POST `/v1/embeddings`——本地 llama.cpp 与云端
OpenAI-compatible 接口都兼容，延续「无 SDK、stdlib-only」的哲学。失败返回 None，
不影响主流程（codera 自动退回纯 TF-IDF）。
"""

from __future__ import annotations

import json
import urllib.request

DEFAULT_TIMEOUT = 30
_MAX_TEXT = 6000          # 单条文本截断字符数（防超长 token 上限）


def embed(model_cfg, texts: list[str]) -> list[list[float]] | None:
    """把 texts 编码为向量；任何失败（网络/端点/格式）返回 None。

    model_cfg: config.ModelConfig（用其 base_url / api_key / model_id）。
    texts:   非空字符串列表。返回与输入同长度的向量列表；texts 为空返回 []。
    """
    if not texts:
        return []
    base = (getattr(model_cfg, "base_url", "") or "").rstrip("/")
    if not base:
        return None
    url = base + "/embeddings"
    payload = {"model": getattr(model_cfg, "model_id", ""),
               "input": [t[:_MAX_TEXT] for t in texts]}
    headers = {"Content-Type": "application/json"}
    api_key = getattr(model_cfg, "api_key", "")
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:                    # noqa: BLE001  网络/端点异常 → 退回纯 TF-IDF
        return None
    items = (data.get("data") or [])
    items = sorted(items, key=lambda x: x.get("index", 0))
    vecs = [(it.get("embedding") or []) for it in items]
    if len(vecs) != len(texts):
        return None
    out = []
    for v in vecs:
        try:
            out.append([float(x) for x in v])
        except (TypeError, ValueError):
            return None
    return out
