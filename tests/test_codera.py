# -*- coding: utf-8 -*-
"""公司多根知识库（codera）测试：建索引、代码/文档召回、增量、根哈希隔离、配置。"""

import os

import pytest

import codera
import config


@pytest.fixture
def roots(tmp_path):
    """多根目录：一个代码仓库 + 一个文档目录。"""
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
    (rb / "api.rst").write_text(
        "API 说明\n========\n/health 健康检查\n", encoding="utf-8")
    return [str(ra), str(rb)]


def test_build_and_stats(roots):
    s = codera.stats(roots)
    assert s["chunks"] == 0           # 尚未建
    r = codera.build(roots)
    assert r["files_indexed"] == 4    # app.py utils.py guide.md api.rst
    assert r["updated"] == 4
    s = codera.stats(roots)
    assert s["files"] == 4 and s["chunks"] >= 1
    assert os.path.exists(s["db"])


def test_search_code_identifier(roots):
    codera.build(roots)
    hits = codera.search("calculate_ema", roots=roots)
    assert hits and hits[0]["file"] == "app.py"


def test_search_doc_keyword(roots):
    codera.build(roots)
    hits = codera.search("部署指南 启动服务", roots=roots)
    assert hits and hits[0]["file"] == "guide.md"


def test_search_empty_roots_returns_empty():
    assert codera.search("anything", roots=[]) == []
    assert codera.retrieve_context("anything", roots=[]) == ""


def test_incremental_skip_unchanged(roots):
    codera.build(roots)
    r = codera.build(roots)
    assert r["updated"] == 0


def test_force_rebuild(roots):
    codera.build(roots)
    r = codera.build(roots, force=True)
    assert r["updated"] == 4


def test_root_hash_isolates_dbs(roots):
    ra, rb = roots
    assert codera.roots_hash([ra]) != codera.roots_hash([rb])
    assert codera.roots_hash([ra, rb]) != codera.roots_hash([ra])


def test_ensure_builds_when_empty(roots):
    s1 = codera.ensure(roots)
    assert s1["chunks"] > 0
    s2 = codera.ensure(roots)         # 已建 → 不变
    assert s2 == s1


def test_retrieve_context_includes_locations(roots):
    codera.build(roots)
    ctx = codera.retrieve_context("calculate_ema", roots=roots)
    assert ctx and "app.py" in ctx and "calculate_ema" in ctx


def test_config_roundtrip(roots):
    config.set_kb_roots(roots)
    assert config.get_kb_roots() == sorted(os.path.abspath(r) for r in roots)
    config.set_kb_enabled(True)
    assert config.get_kb_enabled() is True
    config.set_kb_inject(True)
    assert config.get_kb_inject() is True
    config.set_kb_top_k(8)
    assert config.get_kb_top_k() == 8
    config.set_kb_embedding("deepseek/deepseek-chat")
    assert config.get_kb_embedding() == "deepseek/deepseek-chat"
    config.set_kb_auto(True)
    assert config.get_kb_auto() is True
    # 复位，避免影响其它测试
    config.set_kb_roots([])
    config.set_kb_enabled(False)
    config.set_kb_inject(False)
    config.set_kb_auto(False)


def test_maybe_auto_refresh_throttles(roots):
    """自动增量开启时：首次建索引，节流窗口内跳过，过期后走增量（无变化 updated=0）。"""
    config.set_kb_auto(True)
    codera._last_auto_refresh.clear()
    try:
        r1 = codera.maybe_auto_refresh(roots)     # 首次：建索引
        assert r1["updated"] >= 1
        r2 = codera.maybe_auto_refresh(roots)     # 节流内：跳过
        assert r2["updated"] == 0
        codera._last_auto_refresh.clear()          # 清节流 → 到期走增量
        r3 = codera.maybe_auto_refresh(roots)     # 无变化：updated == 0
        assert r3["updated"] == 0
    finally:
        config.set_kb_auto(False)
        codera._last_auto_refresh.clear()
