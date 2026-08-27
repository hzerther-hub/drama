# -*- coding: utf-8 -*-
"""codera embedding 增强测试：mock 向量，验证混合评分与纯 TF-IDF 回退（无需网络）。"""

import hashlib

import pytest

import codera


class _DummyModel:
    base_url = "http://127.0.0.1:9/v1"
    api_key = "x"
    model_id = "mock-embed"


def _fake_embed(model_cfg, texts):
    """确定性向量：按文本 md5 前 16 字节映射到 [-1,1]，同文本同向量。"""
    out = []
    for t in texts:
        h = hashlib.md5(t.encode("utf-8")).digest()
        out.append([float((b - 128) / 128.0) for b in h])
    return out


@pytest.fixture
def roots(tmp_path):
    ra = tmp_path / "repo_a"
    rb = tmp_path / "docs_b"
    ra.mkdir()
    rb.mkdir()
    (ra / "app.py").write_text(
        "def calculate_ema(prices, period):\n"
        "    return sum(prices) / period\n", encoding="utf-8")
    (ra / "utils.py").write_text(
        "class DataLoader:\n    pass\n", encoding="utf-8")
    (rb / "guide.md").write_text(
        "## 部署指南\n先安装依赖，再启动服务。\n", encoding="utf-8")
    return [str(ra), str(rb)]


def test_hybrid_source_when_embedding_configured(roots, monkeypatch):
    monkeypatch.setattr(codera, "_embed_model", lambda: _DummyModel())
    import embed as embed_mod
    monkeypatch.setattr(embed_mod, "embed", _fake_embed)
    r = codera.build(roots)
    assert r["embedding"] == "hybrid"
    hits = codera.search("calculate_ema", roots=roots)
    assert hits and all(h["source"] == "hybrid" for h in hits)


def test_pure_tfidf_when_no_embedding(roots, monkeypatch):
    monkeypatch.setattr(codera, "_embed_model", lambda: None)
    r = codera.build(roots)
    assert r["embedding"] == "tfidf"
    hits = codera.search("calculate_ema", roots=roots)
    assert hits and all(h["source"] == "tfidf" for h in hits)


def test_falls_back_when_embed_fails(roots, monkeypatch):
    monkeypatch.setattr(codera, "_embed_model", lambda: _DummyModel())
    import embed as embed_mod
    monkeypatch.setattr(embed_mod, "embed",
                        lambda model_cfg, texts: None)   # 向量失败 → 退回
    r = codera.build(roots)
    assert r["embedding"] == "tfidf"
    hits = codera.search("calculate_ema", roots=roots)
    assert hits and all(h["source"] == "tfidf" for h in hits)


def test_embed_client_roundtrip(monkeypatch):
    """embed.embed 对 mock 端点编码文本并解包向量（patch urlopen，零网络）。"""
    import embed as embed_mod
    import urllib.request

    class _Resp:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=30):
        import json as _json
        payload = _json.loads(req.data.decode("utf-8"))
        texts = payload["input"]
        data = [{"index": i, "embedding": [1.0, 0.0, 0.0]}
                for i in range(len(texts))]
        return _Resp(_json.dumps({"data": data}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    vecs = embed_mod.embed(_DummyModel(), ["hello", "world"])
    assert vecs == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]


def test_embed_client_failure_returns_none(monkeypatch):
    import embed as embed_mod
    import urllib.request

    def _boom(req, timeout=30):
        raise OSError("no network")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert embed_mod.embed(_DummyModel(), ["x"]) is None
