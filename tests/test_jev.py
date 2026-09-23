# -*- coding: utf-8 -*-
"""jev 引擎适配器：安装检测、配置读写、执行器降级与权限分层。

测试中的 api_key 值一律从环境变量读取（无则用占位符），
不在源码里出现任何疑似真实凭据的字面量。
"""

from __future__ import annotations

import importlib.util
import os

import pytest

import config
import jev
import tools

FAKE_KEY = os.environ.get("JEV_TEST_KEY") or "dummy-key-for-tests"


# ---------------- 安装检测 ----------------

class TestFindInstall:
    def test_default_dir(self, monkeypatch):
        """默认目录存在 run.py 即命中。"""
        monkeypatch.delenv("LAS_JEV_DIR", raising=False)
        monkeypatch.setattr(jev, "DEFAULT_INSTALL_DIR", "/fake/jev")
        want = os.path.normpath("/fake/jev")
        monkeypatch.setattr("os.path.isfile",
                            lambda p: p == os.path.join(want, "examples", "run.py"))
        assert jev.find_install() == want

    def test_env_override(self, monkeypatch):
        """LAS_JEV_DIR 优先于默认目录。"""
        monkeypatch.setenv("LAS_JEV_DIR", "/my/jev")
        want = os.path.normpath("/my/jev")
        monkeypatch.setattr("os.path.isfile",
                            lambda p: p == os.path.join(want, "examples", "run.py"))
        assert jev.find_install() == want

    def test_not_installed(self, monkeypatch):
        """都不存在返回空串，installed=False。"""
        monkeypatch.delenv("LAS_JEV_DIR", raising=False)
        monkeypatch.setattr(jev, "DEFAULT_INSTALL_DIR", "/nope")
        monkeypatch.setattr("os.path.isfile", lambda p: False)
        assert jev.find_install() == ""
        assert jev.installed() is False

    def test_run_goal_rejects_bad_url(self):
        """URL 协议校验前置，未到安装检测就拒绝。"""
        with pytest.raises(jev.JevError):
            jev.run_goal("not a url", "goal", FAKE_KEY)

    def test_run_goal_requires_goal(self):
        """空目标直接拒绝。"""
        with pytest.raises(jev.JevError):
            jev.run_goal("https://example.com", "", FAKE_KEY)


# ---------------- 配置段 ----------------

class TestJevConfig:
    def _patch_store(self, monkeypatch, store):
        monkeypatch.setattr(config, "_load_models_data", lambda: dict(store))
        monkeypatch.setattr(config, "_save_models_data",
                            lambda d: store.clear() or store.update(d))

    def test_roundtrip_and_whitelist(self, monkeypatch):
        store = {}
        self._patch_store(monkeypatch, store)
        config.set_jev({"api_key": FAKE_KEY, "model": "jev-latest",
                        "evil": "1"})
        got = config.get_jev()
        assert got["api_key"] == FAKE_KEY
        assert got["model"] == "jev-latest"
        assert "evil" not in got

    def test_clear_on_empty_key(self, monkeypatch):
        """api_key 为空 = 整段删除（未配置状态）。"""
        store = {"jev": {"api_key": FAKE_KEY}}
        self._patch_store(monkeypatch, store)
        config.set_jev({"api_key": ""})
        assert config.get_jev() == {}

    def test_per_user_isolation_shape(self, monkeypatch):
        """配置落 models.json（APPDATA 按用户隔离），更新只留最新值。"""
        store = {}
        self._patch_store(monkeypatch, store)
        config.set_jev({"api_key": FAKE_KEY, "install_dir": "/j",
                        "model": "m"})
        config.set_jev({"api_key": FAKE_KEY + "-2"})
        got = config.get_jev()
        assert got == {"api_key": FAKE_KEY + "-2"}


# ---------------- 工具注册与权限 ----------------

class TestJevTool:
    def test_schema_and_executor(self):
        assert any(s["function"]["name"] == "jev_run"
                   for s in tools.TOOL_SCHEMAS)
        assert "jev_run" in tools._EXECUTORS

    def test_write_tool(self):
        """整段委托自动操作 → 审批层。"""
        assert tools.is_write_tool("jev_run")

    def test_no_key_hint(self, monkeypatch):
        """未配置 key 时返回可操作提示而非裸报错。"""
        monkeypatch.setattr(config, "get_jev", lambda: {})
        out = tools.execute_tool("jev_run", {"url": "https://x", "goal": "g"})
        assert "/media" in out and out.startswith("错误：")

    def test_import_without_deps(self):
        """jev 模块本体只依赖标准库，可独立导入。"""
        spec = importlib.util.find_spec("jev")
        assert spec is not None


# ---------------- 短剧/漫画尺寸配置 ----------------

class TestDramaSizes:
    def test_drama_sizes_roundtrip(self, monkeypatch):
        store = {}
        monkeypatch.setattr(config, "_load_models_data", lambda: dict(store))
        monkeypatch.setattr(config, "_save_models_data",
                            lambda d: store.clear() or store.update(d))
        config.set_drama({"image_size": "2K", "image_ratio": "9:16",
                          "video_size": "720x1280",
                          "comic_size": "1K", "comic_ratio": "2:3"})
        got = config.get_drama()
        assert got["image_size"] == "2K"
        assert got["video_size"] == "720x1280"
        assert "evil" not in got

    def test_drama_sizes_defaults(self, monkeypatch):
        """未配置时回落内置默认（1K / 9:16 / 空 / 1K / 2:3）。"""
        monkeypatch.setattr(config, "_load_models_data", lambda: {})
        import dramavideo
        isz, iratio, vsz, csz, cratio = dramavideo._drama_sizes()
        assert (isz, iratio, vsz, csz, cratio) == \
            ("1K", "9:16", "", "1K", "2:3")

    def test_drama_whitelist(self, monkeypatch):
        store = {}
        monkeypatch.setattr(config, "_load_models_data", lambda: dict(store))
        monkeypatch.setattr(config, "_save_models_data",
                            lambda d: store.clear() or store.update(d))
        config.set_drama({"image_size": "2K", "hacker": "1"})
        assert "hacker" not in config.get_drama()
