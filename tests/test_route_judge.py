"""LLM 路由判官单元测试：判档解析 / 缓存 / 失败回退 / 协议过滤 / 开关。"""
from types import SimpleNamespace

import pytest

import config
import route_judge


def _mc(api_type="openai_compatible", base_url="https://api.test/v1"):
    return SimpleNamespace(base_url=base_url, api_key="k", model_id="m",
                           api_type=api_type)


def _fake_chat(sequence):
    """按次序返回预设回复的 _chat_once 替身；记录调用次数与入参。"""
    calls = {"n": 0, "texts": []}

    def fake(mc, text, timeout_s):
        i = min(calls["n"], len(sequence) - 1)
        calls["n"] += 1
        calls["texts"].append(text)
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
    """回复含 pro / fast 关键词时分别判对（大小写与多余文字容忍）。"""
    fake = _fake_chat(["pro", "The answer is FAST."])
    monkeypatch.setattr(route_judge, "_chat_once", fake)
    assert route_judge.judge_tier("帮我重构整个模块", model_config=_mc()) == "pro"
    assert route_judge.judge_tier("今天天气不错", model_config=_mc()) == "fast"
    assert fake.calls["n"] == 2


def test_judge_tier_caches_same_text(monkeypatch):
    """同一句话只问一次判官（会话级缓存）。"""
    fake = _fake_chat(["pro"])
    monkeypatch.setattr(route_judge, "_chat_once", fake)
    assert route_judge.judge_tier("复杂任务", model_config=_mc()) == "pro"
    assert route_judge.judge_tier("复杂任务", model_config=_mc()) == "pro"
    assert fake.calls["n"] == 1


def test_judge_tier_network_error_returns_none(monkeypatch):
    """网络失败返回 None（路由回退关键词），不抛异常。"""
    fake = _fake_chat([ConnectionError("down")])
    monkeypatch.setattr(route_judge, "_chat_once", fake)
    assert route_judge.judge_tier("任意指令", model_config=_mc()) is None


def test_judge_tier_bad_reply_returns_none(monkeypatch):
    """回复不含 fast/pro 两个合法词时判不了 → None。"""
    fake = _fake_chat(["我觉得还可以", ""])
    monkeypatch.setattr(route_judge, "_chat_once", fake)
    assert route_judge.judge_tier("a", model_config=_mc()) is None
    assert route_judge.judge_tier("b", model_config=_mc()) is None


def test_judge_tier_filters_anthropic_and_empty(monkeypatch):
    """anthropic 协议的 flash 目标不判；空文本/空配置不发请求。"""
    fake = _fake_chat([])
    monkeypatch.setattr(route_judge, "_chat_once", fake)
    assert route_judge.judge_tier("x", model_config=_mc(api_type="anthropic")) is None
    assert route_judge.judge_tier("", model_config=_mc()) is None
    assert route_judge.judge_tier("x", model_config=None) is None
    assert fake.calls["n"] == 0


def test_chat_once_rejects_bad_scheme():
    """端点协议非 http(s) 时 _chat_once 直接拒绝。"""
    bad = _mc(base_url="ftp://x/v1")
    with pytest.raises(ValueError):
        route_judge._chat_once(bad, "hi", 1.0)


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
