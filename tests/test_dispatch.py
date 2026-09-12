# -*- coding: utf-8 -*-
"""模型派发：config 字段 + tools.call_model（白名单/健康校验/结果截断）。"""

import pytest

import config
import llm
import tools


@pytest.fixture(autouse=True)
def _iso_cfg(monkeypatch):
    """把 config 的 models.json 读写换成内存 dict，隔离本模块所有用例。"""
    store: dict = {}

    def _load():
        return dict(store)

    def _save(data):
        store.clear()
        store.update(data)

    monkeypatch.setattr(config, "_load_models_data", _load)
    monkeypatch.setattr(config, "_save_models_data", _save)
    yield store


def _mc(key, base_url="https://api.deepseek.com/v1"):
    return config.ModelConfig(key=key, provider_name="p",
                              model_id=key.split("/")[-1],
                              display_name=key, base_url=base_url, api_key="k")


def _dispatch_cfg():
    return {
        "model_dispatch": True,
        "dispatch_flash": "deepseek/deepseek-v4-flash",
        "dispatch_pro": "deepseek/deepseek-v4-pro",
    }


class TestConfigDispatch:
    def test_defaults_when_missing(self):
        cfg = config.get_dispatch_config()
        assert cfg["model_dispatch"] is True
        assert cfg["dispatch_flash"] == "deepseek/deepseek-v4-flash"
        assert cfg["dispatch_pro"] == "deepseek/deepseek-v4-pro"

    def test_dispatch_target_label(self):
        cfg = config.get_dispatch_config()
        assert config.dispatch_target_label(cfg["dispatch_pro"]) == "云端高性能"
        assert config.dispatch_target_label(cfg["dispatch_flash"]) == "云端简单"
        assert config.dispatch_target_label("other/key") == "other/key"

    def test_dispatch_smart_roundtrip(self):
        assert config.get_dispatch_smart() is True
        config.set_dispatch_smart(False)
        assert config.get_dispatch_smart() is False
        config.set_dispatch_smart(True)
        assert config.get_dispatch_smart() is True

    def test_set_model_dispatch_roundtrip(self):
        config.set_model_dispatch(False)
        assert config.get_model_dispatch() is False
        config.set_model_dispatch(True)
        assert config.get_model_dispatch() is True

class TestCallModelGone:
    """(B) 收敛后合约：call_model 工具及其配置常量已退役。

    不再使用 tools.call_model_schema()/_local_healthy()/_is_local_key()/
    validate_dispatch_target()/resolve_dispatch_vision_key()/_truncate_dispatch/
    _call_model/brain_healthy，也不再用 config.get/set_dispatch_model(vision)；
    派发只剩 _route_complex 按 flash/pro/thinking 路由云端目标。
    """

    def test_call_model_schema_symbol_gone(self):
        with pytest.raises(AttributeError):
            tools.call_model_schema   # noqa: B018  访问即触发

    def test_local_helpers_symbol_gone(self):
        for name in ("_is_local_key", "_local_healthy",
                     "validate_dispatch_target", "resolve_dispatch_vision_key",
                     "_truncate_dispatch", "_call_model",
                     "brain_healthy"):
            with pytest.raises(AttributeError):
                getattr(tools, name)   # noqa: B018

    def test_dispatch_model_config_getters_gone(self):
        for name in ("get_dispatch_model", "set_dispatch_model",
                     "get_dispatch_vision", "set_dispatch_vision"):
            with pytest.raises(AttributeError):
                getattr(config, name)   # noqa: B018

    def test_dispatch_vision_removed_from_defaults(self):
        cfg = config.get_dispatch_config()
        assert "dispatch_vision" not in cfg

    def test_dispatch_model_removed_from_defaults(self):
        cfg = config.get_dispatch_config()
        assert "dispatch_model" not in cfg

    def test_executors_no_call_model(self):
        from tools import _EXECUTORS
        assert "call_model" not in _EXECUTORS

    def test_dispatch_target_label_no_vision_branch(self):
        """dispatch_target_label 不再依赖 dispatch_vision 配置。"""
        # 任意 key 都安全返回（cfg 没有 dispatch_vision 字段也不报错）
        assert config.dispatch_target_label("anything") == "anything"
        cfg = config.get_dispatch_config()
        if cfg.get("dispatch_pro"):
            assert config.dispatch_target_label(cfg["dispatch_pro"]) == "云端高性能"
        if cfg.get("dispatch_flash"):
            assert config.dispatch_target_label(cfg["dispatch_flash"]) == "云端简单"
        if cfg.get("dispatch_thinking"):
            assert config.dispatch_target_label(cfg["dispatch_thinking"]) == "云端思考"
class TestResolveDispatchVisionKey:
    """识图预路由：只在「已配置的云端目标」里挑带识图的模型。

    (B) 收敛删掉了 dispatch_vision 字段，识图目标由已配置目标推导；
    旧实现 tools.resolve_dispatch_vision_key 读 cfg["dispatch_vision"] 会 KeyError。
    """

    PRO = "deepseek/deepseek-v4-pro"
    FLASH = "deepseek/deepseek-v4-flash"

    def _patch(self, monkeypatch, vision_keys):
        def _fm(k):
            if k not in (self.PRO, self.FLASH):
                return None
            return config.ModelConfig(
                key=k, provider_name="p", model_id=k.split("/")[-1],
                display_name=k, base_url="https://api.example.com/v1",
                api_key="k", vision=(k in vision_keys))
        monkeypatch.setattr(config, "find_model", _fm)

    def test_empty_when_no_vision_target(self, monkeypatch):
        self._patch(monkeypatch, set())
        assert config.resolve_dispatch_vision_key() == ""

    def test_prefers_pro(self, monkeypatch):
        self._patch(monkeypatch, {self.PRO, self.FLASH})
        assert config.resolve_dispatch_vision_key() == self.PRO

    def test_falls_back_to_flash(self, monkeypatch):
        self._patch(monkeypatch, {self.FLASH})
        assert config.resolve_dispatch_vision_key() == self.FLASH
