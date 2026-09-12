# -*- coding: utf-8 -*-
"""ui.py 派发守护 + (B) 收敛回归（不启动 Tk，仅测纯逻辑路径）。

(B) 收敛后派发只剩云端腿：配置只有 model_dispatch / dispatch_smart /
dispatch_flash / dispatch_pro；没有本地大脑、dispatch_vision 字段与 call_model 工具。
"""

import io

import pytest

import config
import ui


def _cfg():
    """默认派发配置（与 config._DISPATCH_DEFAULTS 对齐）。"""
    return {"model_dispatch": True, "dispatch_smart": True,
            "auto_cloud_fallback": True,
            "dispatch_flash": "deepseek/deepseek-v4-flash",
            "dispatch_pro": "deepseek/deepseek-v4-pro"}


def _mc(key):
    return config.ModelConfig(key=key, provider_name="p",
                              model_id=key.split("/")[-1], display_name=key,
                              base_url="https://api.example.com/v1", api_key="sk")


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """隔离配置目录 + 派发配置，避免读到真实 models.json。"""
    monkeypatch.setattr(config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(config, "get_dispatch_config", _cfg)
    yield


class TestDispatchCloudOk:
    """_dispatch_cloud_ok 只按云端目标探测（同一端点只探一次）。"""

    def _app_like(self, monkeypatch, results):
        monkeypatch.setattr(ui, "_fetch_openai_models",
                            lambda url, key: (_ for _ in ()).throw(
                                results[url]) if results.get(url) is False
                            else ["m1"])
        return object.__new__(ui.App)

    def test_all_ok(self, monkeypatch):
        app = self._app_like(monkeypatch, {})
        monkeypatch.setattr(config, "find_model", _mc)
        ok, bad = ui.App._dispatch_cloud_ok(app)
        assert ok and bad == ""

    def test_some_bad(self, monkeypatch):
        app = self._app_like(
            monkeypatch, {"https://api.example.com/v1": False})
        monkeypatch.setattr(config, "find_model", _mc)
        ok, bad = ui.App._dispatch_cloud_ok(app)
        assert not ok and bad

    def test_no_targets_does_not_raise(self, monkeypatch):
        """旧实现硬取 cfg["dispatch_vision"] → KeyError；现在返回「无可探测」。"""
        monkeypatch.setattr(config, "get_dispatch_config", lambda: {})
        monkeypatch.setattr(config, "find_model", lambda k: None)
        app = self._app_like(monkeypatch, {})
        ok, bad = ui.App._dispatch_cloud_ok(app)
        assert ok is True and bad == ""


class TestTargetsReady:
    """_dispatch_targets_ready：顶栏/面板共用的零成本生效判据。"""

    def test_ready_with_defaults(self):
        assert ui.App._dispatch_targets_ready(object.__new__(ui.App)) is True

    def test_not_ready_without_targets(self, monkeypatch):
        monkeypatch.setattr(config, "get_dispatch_config",
                            lambda: {"dispatch_pro": "", "dispatch_flash": ""})
        assert ui.App._dispatch_targets_ready(object.__new__(ui.App)) is False


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


class TestRetiredApis:
    """回归：(B) 收敛删掉的 API 不得再出现在 ui.py（否则启动/发送即崩）。"""

    # 按「调用形态」匹配（带左括号）：注释/文档串里提到名字不算回归。
    RETIRED = ("tools.brain_healthy(", "tools._is_local_key(",
               "tools.resolve_dispatch_vision_key(",
               "config.get_dispatch_model(", "config.set_dispatch_model(",
               "config.get_dispatch_vision(", "config.set_dispatch_vision(")

    def test_ui_source_has_no_retired_calls(self):
        src = io.open(ui.__file__, encoding="utf-8").read()
        assert [p for p in self.RETIRED if p in src] == []
