# -*- coding: utf-8 -*-
"""ui.py 派发守护：定时核验 + 自动关掉（不启动 Tk，仅测纯逻辑路径）。"""

import pytest

import config
import ui


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """隔离配置目录 + 会话库，避免污染真实配置。"""
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    yield


class TestDispatchCloudOk:
    def _app_like(self, monkeypatch, results):
        """构造最小 app 替身：只挂 _dispatch_cloud_ok 依赖的行为。"""
        monkeypatch.setattr(ui, "_fetch_openai_models",
                            lambda url, key: (_ for _ in ()).throw(
                                results[url]) if results.get(url) is False
                            else ["m1"])
        app = object.__new__(ui.App)
        return app

    def test_all_ok(self, monkeypatch):
        app = self._app_like(monkeypatch, {})
        # 直接测静态逻辑：全部端点可达
        monkeypatch.setattr(config, "find_model", lambda k: config.ModelConfig(
            key=k, provider_name="p", model_id=k, display_name=k,
            base_url="https://api.example.com/v1", api_key="sk"))
        ok, bad = ui.App._dispatch_cloud_ok(app)
        assert ok and bad == ""

    def test_some_bad(self, monkeypatch):
        app = self._app_like(
            monkeypatch, {"https://api.example.com/v1": False})
        monkeypatch.setattr(config, "find_model", lambda k: config.ModelConfig(
            key=k, provider_name="p", model_id=k, display_name=k,
            base_url="https://api.example.com/v1", api_key="sk"))
        ok, bad = ui.App._dispatch_cloud_ok(app)
        assert not ok and bad


class TestAutoOffGuard:
    def test_auto_off_only_when_on(self, monkeypatch):
        """派发本来就没开时 _dispatch_auto_off 是空操作。"""
        called = []
        monkeypatch.setattr(config, "set_model_dispatch",
                            lambda on: called.append(on))
        monkeypatch.setattr(config, "get_model_dispatch", lambda: False)
        app = object.__new__(ui.App)
        monkeypatch.setattr(ui.App, "_update_dispatch_btn",
                            lambda self: None, raising=False)
        ui.App._dispatch_auto_off(app, "测试原因")
        assert called == []            # 没开 → 不写配置
