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
        "dispatch_model": "gpulocal-8097/qwen38-27b-q8",
        "dispatch_flash": "deepseek/deepseek-v4-flash",
        "dispatch_pro": "deepseek/deepseek-v4-pro",
        "dispatch_vision": "deepseek/deepseek-v4-flash-vision-exp",
    }


class TestConfigDispatch:
    def test_defaults_when_missing(self):
        cfg = config.get_dispatch_config()
        assert cfg["model_dispatch"] is True
        assert cfg["dispatch_model"] == "gpulocal-8097/qwen38-27b-q8"
        assert cfg["dispatch_flash"] == "deepseek/deepseek-v4-flash"
        assert cfg["dispatch_pro"] == "deepseek/deepseek-v4-pro"
        # dispatch_vision 必选，默认已给出
        assert cfg["dispatch_vision"] == "deepseek/deepseek-v4-flash-vision-exp"

    def test_dispatch_target_label(self):
        cfg = config.get_dispatch_config()
        assert config.dispatch_target_label(cfg["dispatch_pro"]) == "云端高性能"
        assert config.dispatch_target_label(cfg["dispatch_flash"]) == "云端简单"
        assert config.dispatch_target_label(cfg["dispatch_vision"]) == "云端识图"
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

    def test_set_dispatch_model_roundtrip(self):
        config.set_dispatch_model("gpulocal-8098/qwen3-vl-32b")
        assert config.get_dispatch_model() == "gpulocal-8098/qwen3-vl-32b"

    def test_dispatch_vision_required_default(self):
        # dispatch_vision 必选：即使没显式设置也一定有值
        cfg = config.get_dispatch_config()
        assert cfg["dispatch_vision"]


class TestDispatchTargetValidation:
    @pytest.fixture(autouse=True)
    def _cfg(self, monkeypatch):
        cfg = _dispatch_cfg()
        monkeypatch.setattr(config, "get_dispatch_config", lambda: cfg)

    def test_cloud_target_allowed(self):
        cfg = config.get_dispatch_config()
        ok, err = tools.validate_dispatch_target(cfg["dispatch_pro"])
        assert ok and err is None
        ok, err = tools.validate_dispatch_target(cfg["dispatch_vision"])
        assert ok

    def test_unknown_cloud_rejected(self, monkeypatch):
        monkeypatch.setattr(config, "find_model",
                            lambda k: _mc("deepseek/other") if k == "deepseek/other" else None)
        ok, err = tools.validate_dispatch_target("deepseek/other")
        assert not ok and "白名单" in err

    def test_self_local_rejected(self, monkeypatch):
        cfg = config.get_dispatch_config()
        monkeypatch.setattr(tools.config, "find_model",
                            lambda k: _mc(cfg["dispatch_model"],
                                          "http://127.0.0.1:8097/v1"))
        ok, err = tools.validate_dispatch_target(cfg["dispatch_model"])
        assert not ok and "自身" in err

    def test_other_local_rejected(self, monkeypatch):
        cfg = config.get_dispatch_config()
        other = "gpulocal-8098/qwen3-vl-32b"
        monkeypatch.setattr(tools.config, "find_model",
                            lambda k: _mc(other, "http://127.0.0.1:8098/v1"))
        ok, err = tools.validate_dispatch_target(other)
        assert not ok and "互斥" in err


def _fake_stream(text):
    def stream(model, messages, schemas=None):
        yield {"type": "text", "delta": text}
        yield {"type": "finish", "reason": "stop"}
    return stream


class TestCallModelTool:
    def test_disabled_returns_error(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: False)
        out = tools.execute_tool("call_model",
                                 {"model": "deepseek/deepseek-v4-pro", "task": "hi"})
        assert "未开启" in out

    def test_missing_params_error(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: True)
        assert "model 与 task" in tools.execute_tool("call_model", {"model": "x"})

    def test_dispatch_returns_text(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: True)
        monkeypatch.setattr(config, "find_model", lambda k: _mc(k))
        monkeypatch.setattr(tools.llm, "stream_chat", _fake_stream("子任务结果"))
        monkeypatch.setattr(tools, "validate_dispatch_target", lambda m: (True, None))
        out = tools.execute_tool("call_model",
                                 {"model": "deepseek/deepseek-v4-pro", "task": "t"})
        assert out == "子任务结果"

    def test_dispatch_truncates_result(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: True)
        monkeypatch.setattr(config, "find_model", lambda k: _mc(k))
        monkeypatch.setattr(tools.llm, "stream_chat",
                            _fake_stream("长" * 10000))
        monkeypatch.setattr(tools, "validate_dispatch_target", lambda m: (True, None))
        out = tools.execute_tool("call_model",
                                 {"model": "deepseek/deepseek-v4-pro", "task": "t"})
        assert len(out) < 10000
        assert "已压缩" in out

    def test_invalid_target_rejected(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: True)
        monkeypatch.setattr(tools, "validate_dispatch_target",
                            lambda m: (False, "错误：派发目标不在白名单内：x"))
        out = tools.execute_tool("call_model", {"model": "x", "task": "t"})
        assert "白名单" in out

    def test_transport_error_returned(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: True)
        monkeypatch.setattr(config, "find_model", lambda k: _mc(k))
        monkeypatch.setattr(tools, "validate_dispatch_target", lambda m: (True, None))

        def boom(model, messages, schemas=None):
            raise llm.LLMError("连接失败")
        monkeypatch.setattr(tools.llm, "stream_chat", boom)
        out = tools.execute_tool("call_model",
                                 {"model": "deepseek/deepseek-v4-pro", "task": "t"})
        assert "派发失败" in out


class TestCallModelSchema:
    def test_requires_enabled_and_healthy(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: True)
        monkeypatch.setattr(config, "get_dispatch_model",
                            lambda: "gpulocal-8097/qwen38-27b-q8")
        # 健康检查失败 → 不暴露
        monkeypatch.setattr(tools, "_local_healthy", lambda k: False)
        assert tools.call_model_schema() == []
        # 健康检查通过 → 暴露
        monkeypatch.setattr(tools, "_local_healthy", lambda k: True)
        assert len(tools.call_model_schema()) == 1

    def test_toggle_off_hides(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: False)
        assert tools.call_model_schema() == []

    def test_schema_fields(self, monkeypatch):
        monkeypatch.setattr(config, "get_model_dispatch", lambda: True)
        monkeypatch.setattr(config, "get_dispatch_model",
                            lambda: "gpulocal-8097/qwen38-27b-q8")
        monkeypatch.setattr(tools, "_local_healthy", lambda k: True)
        s = tools.call_model_schema()[0]["function"]
        assert s["name"] == "call_model"
        assert {"model", "task"} <= set(s["parameters"]["required"])


class TestResolveVision:
    def test_local_vision_brain_first(self, monkeypatch):
        cfg = _dispatch_cfg()
        monkeypatch.setattr(config, "get_dispatch_config", lambda: cfg)
        monkeypatch.setattr(tools, "_is_local_key", lambda k: True)
        monkeypatch.setattr(tools, "_local_healthy", lambda k: True)

        def _find(key):
            mc = _mc(key, "http://127.0.0.1:8097/v1")
            if key == cfg["dispatch_model"]:
                mc = config.ModelConfig(
                    key=key, provider_name="p", model_id=key.split("/")[-1],
                    display_name=key, base_url="http://127.0.0.1:8097/v1",
                    api_key="k", vision=True)
            return mc
        monkeypatch.setattr(config, "find_model", _find)
        # 本地大脑带识图且健康 → 返回本地大脑
        assert tools.resolve_dispatch_vision_key() == cfg["dispatch_model"]

    def test_cloud_fallback_when_local_unhealthy(self, monkeypatch):
        cfg = _dispatch_cfg()
        monkeypatch.setattr(config, "get_dispatch_config", lambda: cfg)
        monkeypatch.setattr(tools, "_is_local_key", lambda k: True)
        monkeypatch.setattr(tools, "_local_healthy", lambda k: False)
        # 本地大脑没在跑 → 回退云端识图
        assert tools.resolve_dispatch_vision_key() == cfg["dispatch_vision"]


class TestLocalHealthy:
    def test_false_when_no_models(self, monkeypatch):
        import localmodels
        monkeypatch.setattr(localmodels, "list_models", lambda: {})
        assert tools._local_healthy("gpulocal-8097/qwen38-27b-q8") is False

    def test_false_when_gpulocal_missing(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "localmodels":
                raise ImportError("no gpulocal")
            return real_import(name, *a, **k)
        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert tools._local_healthy("any/thing") is False
