# -*- coding: utf-8 -*-
"""llm.py：SSE 流解析（mock 传输层，不联网）。"""

import pytest

import config
import llm


def _model():
    return config.ModelConfig(key="t/m", provider_name="t", model_id="m",
                              display_name="M", base_url="http://x",
                              api_key="k")


def _run(monkeypatch, objs):
    """用假的 SSE 对象流替换传输层，跑一遍 stream_chat。"""
    monkeypatch.setattr(llm, "_post_stream",
                        lambda model, messages, tools: iter(objs))
    return list(llm.stream_chat(_model(), [{"role": "user", "content": "hi"}]))


class TestStreamChat:
    def test_text_deltas(self, monkeypatch):
        events = _run(monkeypatch, [
            {"choices": [{"delta": {"content": "你"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "好"}, "finish_reason": "stop"}]},
        ])
        texts = [e["delta"] for e in events if e["type"] == "text"]
        assert texts == ["你", "好"]
        assert events[-1] == {"type": "finish", "reason": "stop"}

    def test_reasoning_deltas(self, monkeypatch):
        events = _run(monkeypatch, [
            {"choices": [{"delta": {"reasoning_content": "想一下"},
                          "finish_reason": "stop"}]},
        ])
        assert {"type": "reasoning", "delta": "想一下"} in events

    def test_tool_calls_accumulated_across_chunks(self, monkeypatch):
        events = _run(monkeypatch, [
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "call_1",
                 "function": {"name": "read_file", "arguments": "{\"pa"}}]},
             "finish_reason": None}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": "th\": \"a.txt\"}"}}]},
             "finish_reason": "tool_calls"}]},
        ])
        tc_events = [e for e in events if e["type"] == "tool_calls"]
        assert len(tc_events) == 1
        tc = tc_events[0]["tool_calls"][0]
        assert tc["id"] == "call_1"
        assert tc["function"]["name"] == "read_file"
        assert tc["function"]["arguments"] == '{"path": "a.txt"}'

    def test_usage_emitted_and_usage_only_chunk_skipped(self, monkeypatch):
        events = _run(monkeypatch, [
            {"choices": [{"delta": {"content": "x"}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 10,
                                      "completion_tokens": 5,
                                      "total_tokens": 15}},
        ])
        usage = [e for e in events if e["type"] == "usage"]
        assert usage and usage[0]["usage"]["total_tokens"] == 15
        # usage-only chunk 不产生额外事件
        assert [e["type"] for e in events].count("finish") == 1


class TestParseUsage:
    def test_openai_cached_tokens(self):
        u = {"prompt_tokens": 100, "completion_tokens": 20,
             "prompt_tokens_details": {"cached_tokens": 64}}
        assert llm._parse_usage(u)["cached_tokens"] == 64

    def test_deepseek_format(self):
        u = {"prompt_tokens": 100, "prompt_cache_hit_tokens": 32}
        assert llm._parse_usage(u)["cached_tokens"] == 32

    def test_reasoning_tokens(self):
        u = {"completion_tokens_details": {"reasoning_tokens": 7}}
        assert llm._parse_usage(u)["reasoning_tokens"] == 7

    def test_missing_fields(self):
        assert llm._parse_usage({})["cached_tokens"] is None


class TestErrors:
    def test_http_error_becomes_llmerror(self, monkeypatch):
        def boom(model, messages, tools):
            raise llm.LLMError("HTTP 500: x")
            yield                                        # pragma: no cover
        monkeypatch.setattr(llm, "_post_stream", boom)
        with pytest.raises(llm.LLMError):
            list(llm.stream_chat(_model(), []))
