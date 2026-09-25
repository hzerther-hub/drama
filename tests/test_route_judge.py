"""LLM 路由判官单元测试：判档解析 / 缓存 / 失败回退 / 开关。"""
import json

import pytest

import config
import route_judge


def _fake_post(sequence):
    """按次序返回预设响应的 _post 替身；记录调用次数。"""
    calls = {"n": 0}

    def fake(key, body, timeout_s):
        i = min(calls["n"], len(sequence) - 1)
        calls["n"] += 1
        item = sequence[i]
        if isinstance(item, Exception):
            raise item
        return item

    fake.calls = calls
    return fake


@pytest.fixture(autouse=True)
def _clean_cache():
    route_judge.reset_cache()
    yield
    route_judge.reset_cache()


def test_judge_tier_pro_and_fast(monkeypatch):
    """合法 JSON 分别解析出 pro / fast。"""
    monkey_resp = _fake_post([
        {"choices": [{"message": {"content": '{"tier": "pro"}'}}]},
        {"choices": [{"message": {"content": '{"tier": "fast"}'}}]},
    ])
    monkeypatch.setattr(route_judge, "_post", monkey_resp)
    assert route_judge.judge_tier("帮我重构整个模块", api_key="k") == "pro"
    assert route_judge.judge_tier("今天天气不错", api_key="k") == "fast"
    assert monkey_resp.calls["n"] == 2


def test_judge_tier_caches_same_text(monkeypatch):
    """同一句话只问一次判官（会话级缓存）。"""
    monkey_resp = _fake_post([
        {"choices": [{"message": {"content": '{"tier": "pro"}'}}]},
    ])
    monkeypatch.setattr(route_judge, "_post", monkey_resp)
    assert route_judge.judge_tier("复杂任务", api_key="k") == "pro"
    assert route_judge.judge_tier("复杂任务", api_key="k") == "pro"
    assert monkey_resp.calls["n"] == 1


def test_judge_tier_network_error_returns_none(monkeypatch):
    """网络失败返回 None（路由回退关键词），不抛异常。"""
    monkey_resp = _fake_post([ConnectionError("down")])
    monkeypatch.setattr(route_judge, "_post", monkey_resp)
    assert route_judge.judge_tier("任意指令", api_key="k") is None


def test_judge_tier_bad_payload_returns_none(monkeypatch):
    """缺字段 / tier 非法 / 非 JSON 一律 None。"""
    monkey_resp = _fake_post([
        {"choices": [{"message": {"content": "not json"}}]},
        {"choices": [{"message": {"content": '{"tier": "unknown"}'}}]},
        {},
    ])
    monkeypatch.setattr(route_judge, "_post", monkey_resp)
    assert route_judge.judge_tier("a", api_key="k") is None
    assert route_judge.judge_tier("b", api_key="k") is None
    assert route_judge.judge_tier("c", api_key="k") is None


def test_judge_tier_empty_inputs_short_circuit(monkeypatch):
    """空文本 / 空 key 不发请求直接 None。"""
    monkey_resp = _fake_post([])
    monkeypatch.setattr(route_judge, "_post", monkey_resp)
    assert route_judge.judge_tier("", api_key="k") is None
    assert route_judge.judge_tier("指令", api_key="") is None
    assert monkey_resp.calls["n"] == 0


def test_route_judge_config_default_and_toggle(tmp_path, monkeypatch):
    """route_judge 开关默认开，可关可再开（落 models.json）。"""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    import importlib
    importlib.reload(config)
    try:
        assert config.get_route_judge() is True        # 默认开
        config.set_route_judge(False)
        assert config.get_route_judge() is False
        config.set_route_judge(True)
        assert config.get_route_judge() is True
    finally:
        importlib.reload(config)
