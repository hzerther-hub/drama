# -*- coding: utf-8 -*-
"""cache.py：后端读写/过期/清理 + 高层 LLM/工具缓存接口。"""

import pytest

import cache


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch, tmp_path):
    """每个用例拿到干净的缓存状态：重定向 config.CONFIG_DIR + 公开 reset()。"""
    monkeypatch.setattr(cache.config, "CONFIG_DIR", str(tmp_path))
    cache.reset()
    yield tmp_path
    cache.reset()


class TestMemoryBackend:
    def test_put_get(self):
        cache.save_settings(backend="memory")
        cache.put("k1", "v1", ttl=60)
        assert cache.get("k1") == "v1"

    def test_missing_key(self):
        cache.save_settings(backend="memory")
        assert cache.get("absent") is None

    def test_expired_entry_returns_none(self):
        cache.save_settings(backend="memory")
        cache.put("k2", "v2", ttl=-1)          # 立即过期
        assert cache.get("k2") is None

    def test_clear(self):
        cache.save_settings(backend="memory")
        cache.put("k3", "v3", ttl=60)
        assert cache.clear() is True
        assert cache.get("k3") is None

    def test_eviction_keeps_within_cap(self, monkeypatch):
        monkeypatch.setattr(cache, "_MEM_MAX", 10)
        cache.save_settings(backend="memory")
        for i in range(20):
            cache.put(f"key{i}", "v", ttl=60)
        assert len(cache._mem_store) <= 20
        assert cache.stats()["entries"] == len(cache._mem_store)


class TestSqliteBackend:
    def test_put_get_persistent(self, fresh_cache):
        db = str(fresh_cache / "c.db")
        cache.save_settings(backend="sqlite", sqlite_path=db)
        assert cache.backend_name() == "sqlite"
        cache.put("sk", "sv", ttl=60)
        assert cache.get("sk") == "sv"
        assert cache.stats()["entries"] == 1

    def test_expired_deleted_lazily(self, fresh_cache):
        db = str(fresh_cache / "c2.db")
        cache.save_settings(backend="sqlite", sqlite_path=db)
        cache.put("gone", "x", ttl=-1)
        assert cache.get("gone") is None
        assert cache.stats()["entries"] == 0


class TestBackendResolution:
    def test_auto_uses_sqlite_when_available(self, fresh_cache):
        cache.save_settings(backend="auto",
                            sqlite_path=str(fresh_cache / "auto.db"))
        assert cache.backend_name() == "sqlite"

    def test_auto_falls_back_to_memory_without_sqlite(self, fresh_cache):
        # sqlite 路径为空 → auto 退到内存，绝不报异常
        cache.save_settings(backend="auto", sqlite_path="")
        assert cache.backend_name() == "memory"

    def test_legacy_redis_backend_treated_as_auto(self, fresh_cache):
        # 旧配置文件里遗留 backend="redis"（后端已移除）→ 按 auto 处理
        cache.save_settings(backend="redis",
                            sqlite_path=str(fresh_cache / "legacy.db"))
        assert cache.backend_name() == "sqlite"


class TestHighLevel:
    def test_llm_roundtrip(self):
        cache.save_settings(backend="memory")
        msgs = [{"role": "user", "content": "你好"}]
        events = [{"type": "text", "delta": "hi"}]
        assert cache.get_llm("m1", msgs, None) is None
        cache.put_llm("m1", msgs, None, events)
        assert cache.get_llm("m1", msgs, None) == events
        # 消息变了键就变了
        assert cache.get_llm("m1", msgs + [{"role": "user", "content": "x"}],
                             None) is None

    def test_tool_roundtrip_scoped_by_workspace(self):
        cache.save_settings(backend="memory")
        cache.put_tool("read_file", {"path": "a"}, "/ws1", "result-1")
        assert cache.get_tool("read_file", {"path": "a"}, "/ws1") == "result-1"
        assert cache.get_tool("read_file", {"path": "a"}, "/ws2") is None

    def test_zero_ttl_disables_cache(self):
        cache.save_settings(backend="memory", llm_ttl=0, tool_ttl=0)
        cache.put_llm("m", [], None, [{"type": "text", "delta": "x"}])
        cache.put_tool("t", {}, "w", "r")
        assert cache.get_llm("m", [], None) is None
        assert cache.get_tool("t", {}, "w") is None

    def test_save_settings_ignores_unknown_keys(self):
        s = cache.save_settings(backend="memory", no_such_key=1)
        assert "no_such_key" not in s


class TestIsolation:
    def test_config_dir_redirect_gives_fresh_state(self, monkeypatch, tmp_path):
        """重定向 config.CONFIG_DIR + reset() = 完全独立的缓存实例。"""
        cache.save_settings(backend="memory")
        cache.put("shared-key", "v", ttl=60)

        other = tmp_path / "instance2"
        other.mkdir()
        monkeypatch.setattr(cache.config, "CONFIG_DIR", str(other))
        cache.reset()
        # 新实例读不到旧实例的设置文件，回到默认 backend=auto
        assert cache.load_settings()["backend"] == "auto"

    def test_reset_clears_memory_store(self):
        cache.save_settings(backend="memory")
        cache.put("k", "v", ttl=60)
        cache.reset()
        assert cache.stats()["entries"] == 0
