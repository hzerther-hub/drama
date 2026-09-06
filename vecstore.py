# -*- coding: utf-8 -*-
"""向量检索：Qdrant REST（stdlib urllib 直连）+ 无服务降级内存检索。

配置（环境变量，均可选）：
- LAS_QDRANT_URL       Qdrant 服务地址（如 http://127.0.0.1:6333）→ 启用持久向量库
- LAS_QDRANT_API_KEY   Qdrant API Key（云服务用，本地可空）
- LAS_EMBED_BASE_URL / LAS_EMBED_MODEL / LAS_EMBED_API_KEY
                       OpenAI 兼容 /embeddings 端点 → 语义向量；
                       未配置 → 本地词袋哈希向量（256 维，确定性，语义弱但零依赖）

降级链：Qdrant 未配置或不可达 → 进程内 dict 检索（本次运行有效）；
embedding 未配置 → 词袋向量。任何失败都不抛出中断业务。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request

DIM = 256                      # 本地词袋向量维度
_CHUNK = 500                   # 章节切块字符数


class VecError(Exception):
    pass


# ---------------- 配置 ----------------

def qdrant_url() -> str:
    return os.environ.get("LAS_QDRANT_URL", "").strip().rstrip("/")


def qdrant_key() -> str:
    return os.environ.get("LAS_QDRANT_API_KEY", "")


def embed_base() -> str:
    return os.environ.get("LAS_EMBED_BASE_URL", "").strip().rstrip("/")


def embed_model() -> str:
    return os.environ.get("LAS_EMBED_MODEL", "")


def embed_key() -> str:
    return os.environ.get("LAS_EMBED_API_KEY",
                          os.environ.get("LAS_OPENAI_API_KEY", ""))


def rag_enabled() -> bool:
    """是否具备向量检索条件（Qdrant 或至少内存模式都可工作；这里指 Qdrant）。"""
    return bool(qdrant_url())


# ---------------- HTTP ----------------

def _req(method: str, url: str, body: dict | None = None, key: str = "",
         timeout: int = 30) -> dict:
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("api-key", key)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ---------------- embedding ----------------

def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化：OpenAI 兼容 /embeddings 优先，缺失走本地词袋向量。"""
    if embed_base() and embed_model():
        out = _req("POST", f"{embed_base()}/embeddings",
                   {"model": embed_model(), "input": texts}, embed_key())
        return [d["embedding"] for d in out["data"]]
    return [_lex(t) for t in texts]


def _lex(text: str, dim: int = DIM) -> list[float]:
    """本地确定性向量：CJK 双字组 + ASCII 词的哈希词袋，L2 归一化。"""
    v = [0.0] * dim
    toks = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]", text or "")
    grams = toks + ["".join(p) for p in zip(toks, toks[1:])]
    for g in grams:
        v[int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16) % dim] += 1.0
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / n for x in v]


def chunk_text(text: str, size: int = _CHUNK) -> list[str]:
    """按段落聚合成 ~size 字符的块。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    if not paras:
        paras = [text or ""]
    out, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) + 1 > size:
            out.append(cur)
            cur = p
        else:
            cur = f"{cur}\n{p}" if cur else p
    if cur:
        out.append(cur)
    return out


# ---------------- Qdrant / 内存统一接口 ----------------

def ensure_collection(name: str, dim: int = DIM):
    """集合不存在则创建；Qdrant 不可用则准备内存桶。"""
    if not qdrant_url():
        _MEM.setdefault(name, [])
        return
    try:
        _req("GET", f"{qdrant_url()}/collections/{name}", key=qdrant_key(), timeout=10)
        return
    except Exception:             # noqa: BLE001  404/网络错误 → 尝试创建
        pass
    try:
        _req("PUT", f"{qdrant_url()}/collections/{name}",
             {"vectors": {"size": dim, "distance": "Cosine"}},
             key=qdrant_key())
    except Exception as e:        # noqa: BLE001
        raise VecError(f"Qdrant 创建集合失败：{e}") from e


def upsert(name: str, ids: list[int], vectors: list[list[float]],
           payloads: list[dict]):
    if qdrant_url():
        points = [{"id": i, "vector": v, "payload": p}
                  for i, v, p in zip(ids, vectors, payloads)]
        _req("PUT", f"{qdrant_url()}/collections/{name}/points?wait=true",
             {"points": points}, key=qdrant_key())
        return
    bucket = _MEM.setdefault(name, [])
    for i, v, p in zip(ids, vectors, payloads):
        bucket.append({"id": i, "vector": v, "payload": p})


def search(name: str, vector: list[float], top_k: int = 4) -> list[dict]:
    """返回 [{score, payload}]，按相似度降序；两端实现统一形状。"""
    if qdrant_url():
        out = _req("POST", f"{qdrant_url()}/collections/{name}/points/search",
                   {"vector": vector, "limit": top_k, "with_payload": True},
                   key=qdrant_key())
        return [{"score": h.get("score", 0.0),
                 "payload": h.get("payload") or {}}
                for h in (out.get("result") or [])]
    bucket = _MEM.get(name) or []
    scored = []
    for item in bucket:
        v = item["vector"]
        score = sum(a * b for a, b in zip(vector, v))
        scored.append({"score": score, "payload": item["payload"]})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]


def reset_memory():
    """清空进程内降级桶（测试用）。"""
    _MEM.clear()


# 内存降级桶（模块级）
_MEM: dict[str, list[dict]] = {}
