# -*- coding: utf-8 -*-
"""agent.py：function-calling 循环 + 权限模式（mock llm 传输层）。"""

import json

import pytest

import agent
import cache
import config
import llm
import tools


MODEL = config.ModelConfig(key="t/m", provider_name="t", model_id="m",
                           display_name="M", base_url="http://x",
                           api_key="k")


@pytest.fixture(autouse=True)
def no_cache(monkeypatch):
    """关掉缓存层，避免用例间串扰。"""
    monkeypatch.setattr(cache, "get_llm", lambda *a, **k: None)
    monkeypatch.setattr(cache, "put_llm", lambda *a, **k: None)
    monkeypatch.setattr(cache, "get_tool", lambda *a, **k: None)
    monkeypatch.setattr(cache, "put_tool", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def workspace(tmp_path):
    old = tools.get_workspace()
    tools.set_workspace(str(tmp_path))
    yield str(tmp_path)
    tools.set_workspace(old)


def _text_stream(text, reason="stop"):
    def stream(model, messages, schemas):
        yield {"type": "text", "delta": text}
        yield {"type": "finish", "reason": reason}
    return stream


class TestBuildUserMessage:
    """用户消息构造：代码片段附件直接内联文件+行号+内容。"""

    def test_snippet_attachment_inlined(self):
        att = {"kind": "snippet", "path": r"D:\x\requirements.php",
               "start_line": 110, "end_line": 135,
               "content": 'array(\n    "name" => "PDO",\n);'}
        m = agent.Agent._build_user_message("请分析这段", [att])
        assert m["role"] == "user"
        texts = [p["text"] for p in m["content"] if p["type"] == "text"]
        assert "requirements.php" in texts[-1] and "110" in texts[-1]
        assert 'array(' in texts[-1]
        assert "请分析这段" in texts[0]


class TestPlainReply:
    def test_text_returned(self, monkeypatch):
        monkeypatch.setattr(llm, "stream_chat", _text_stream("你好，世界"))
        ag = agent.Agent(mode=agent.MODE_ALWAYS, model=MODEL)
        assert ag.run("打个招呼") == "你好，世界"

    def test_reply_appended_to_history(self, monkeypatch):
        monkeypatch.setattr(llm, "stream_chat", _text_stream("回答"))
        ag = agent.Agent(mode=agent.MODE_ALWAYS, model=MODEL)
        ag.run("问题")
        roles = [m["role"] for m in ag.messages]
        assert roles == ["system", "user", "assistant"]
        assert ag.messages[-1]["content"] == "回答"

    def test_empty_stream_warns(self, monkeypatch):
        def empty(model, messages, schemas):
            yield {"type": "finish", "reason": "stop"}
        monkeypatch.setattr(llm, "stream_chat", empty)
        ag = agent.Agent(mode=agent.MODE_ALWAYS, model=MODEL)
        out = ag.run("hi")
        assert "未返回任何内容" in out

    def test_usage_accumulated(self, monkeypatch):
        def stream(model, messages, schemas):
            yield {"type": "text", "delta": "x"}
            yield {"type": "usage", "usage": {"prompt_tokens": 10,
                                              "completion_tokens": 5,
                                              "total_tokens": 15,
                                              "cached_tokens": None,
                                              "reasoning_tokens": None}}
            yield {"type": "finish", "reason": "stop"}
        monkeypatch.setattr(llm, "stream_chat", stream)
        ag = agent.Agent(mode=agent.MODE_ALWAYS, model=MODEL)
        ag.run("hi")
        assert ag.usage_total["total_tokens"] == 15
        assert ag.usage_total["requests"] == 1


class TestToolCalling:
    def _two_round_stream(self, monkeypatch, calls):
        """第一轮返回工具调用，第二轮返回纯文本。"""
        def stream(model, messages, schemas):
            if not calls["done"]:
                calls["done"] = True
                yield {"type": "tool_calls", "tool_calls": [{
                    "id": "call_1", "type": "function",
                    "function": {"name": "read_file",
                                 "arguments": json.dumps({"path": "note.txt"})}}]}
                yield {"type": "finish", "reason": "tool_calls"}
            else:
                yield {"type": "text", "delta": "读完了"}
                yield {"type": "finish", "reason": "stop"}
        monkeypatch.setattr(llm, "stream_chat", stream)

    def test_tool_result_fed_back(self, monkeypatch, workspace):
        with open(f"{workspace}/note.txt", "w", encoding="utf-8") as f:
            f.write("秘密内容ABC")
        self._two_round_stream(monkeypatch, {"done": False})
        ag = agent.Agent(mode=agent.MODE_ALWAYS, model=MODEL)
        assert ag.run("读一下 note.txt") == "读完了"
        tool_msgs = [m for m in ag.messages if m.get("role") == "tool"]
        assert tool_msgs and "秘密内容ABC" in tool_msgs[0]["content"]
        assert tool_msgs[0]["tool_call_id"] == "call_1"

    def test_ask_mode_denial(self, monkeypatch, workspace):
        """ask 模式下拒绝 write_file → 工具不执行，结果反馈给模型。"""
        def stream(model, messages, schemas):
            if not any(m.get("role") == "tool" for m in messages):
                yield {"type": "tool_calls", "tool_calls": [{
                    "id": "c1", "type": "function",
                    "function": {"name": "write_file",
                                 "arguments": json.dumps(
                                     {"path": "evil.txt", "content": "x"})}}]}
                yield {"type": "finish", "reason": "tool_calls"}
            else:
                yield {"type": "text", "delta": "好的，不写了"}
                yield {"type": "finish", "reason": "stop"}
        monkeypatch.setattr(llm, "stream_chat", stream)

        import os
        ag = agent.Agent(mode=agent.MODE_ASK, model=MODEL,
                         on_approval=lambda n, a, s: False)
        out = ag.run("写个文件")
        assert "不写了" in out
        assert not os.path.exists(f"{workspace}/evil.txt")   # 确实没写
        tool_msgs = [m for m in ag.messages if m.get("role") == "tool"]
        assert "拒绝" in tool_msgs[0]["content"]

    def test_readonly_mode_hides_write_tools(self, monkeypatch):
        seen = {}

        def stream(model, messages, schemas):
            seen["names"] = {s["function"]["name"] for s in schemas}
            yield {"type": "text", "delta": "ok"}
            yield {"type": "finish", "reason": "stop"}
        monkeypatch.setattr(llm, "stream_chat", stream)
        ag = agent.Agent(mode=agent.MODE_READONLY, model=MODEL)
        ag.run("hi")
        assert "write_file" not in seen["names"]
        assert "read_file" in seen["names"]

    def test_stop_callback_breaks_loop(self, monkeypatch):
        monkeypatch.setattr(llm, "stream_chat", _text_stream("x"))
        ag = agent.Agent(mode=agent.MODE_ALWAYS, model=MODEL,
                         on_stop=lambda: True)
        out = ag.run("hi")
        assert "已按用户请求停止" in out


LOCAL_MODEL = config.ModelConfig(
    key="gpulocal-8097/qwen38", provider_name="gpulocal-8097",
    model_id="qwen38", display_name="本地Q", base_url="http://127.0.0.1:8097",
    api_key="local-noauth")
CLOUD_MODEL = config.ModelConfig(
    key="deepseek/v4-flash", provider_name="deepseek",
    model_id="v4-flash", display_name="云端D", base_url="http://cloud",
    api_key="sk-x")


class TestLocalCloudFallback:
    """本地模型不可用（加载中/未运行）→ 自动回退云端重发本轮。"""

    def _wire(self, monkeypatch, fail_first):
        """stream_chat 第一次抛 LLMError，之后正常返回云端文本。"""
        calls = []

        def stream(model, messages, schemas):
            calls.append(model.key)
            if len(calls) == 1 and fail_first:
                raise llm.LLMError(
                    'HTTP 503: {"error":{"message":"Loading model"}}')
            yield {"type": "text", "delta": "云端回答"}
            yield {"type": "finish", "reason": "stop"}

        monkeypatch.setattr(llm, "stream_chat", stream)
        return calls

    def _wire_config(self, monkeypatch, fallback=True):
        monkeypatch.setattr(config, "get_auto_cloud_fallback",
                            lambda: fallback)
        monkeypatch.setattr(config, "get_dispatch_config", lambda: {
            "dispatch_flash": "deepseek/v4-flash",
            "dispatch_pro": "deepseek/v4-pro",
            "dispatch_model": LOCAL_MODEL.key})
        monkeypatch.setattr(config, "find_model", lambda key: CLOUD_MODEL)

    def test_503_loading_falls_back_to_cloud(self, monkeypatch):
        self._wire_config(monkeypatch)
        calls = self._wire(monkeypatch, fail_first=True)
        events = []
        ag = agent.Agent(on_event=events.append, model=LOCAL_MODEL)
        out = ag.run("hi")
        assert out == "云端回答"
        assert calls == [LOCAL_MODEL.key, CLOUD_MODEL.key]
        note = "".join(e.get("delta", "") for e in events
                       if e["type"] == "text")
        assert "已自动切换到云端" in note
        # UI 依赖 model_switch 事件把模型按钮切到实际使用的模型
        sw = [e for e in events if e["type"] == "model_switch"]
        assert len(sw) == 1 and sw[0]["to"] is CLOUD_MODEL
        assert sw[0]["from"] == LOCAL_MODEL.display_name

    def test_fallback_disabled_raises(self, monkeypatch):
        self._wire_config(monkeypatch, fallback=False)
        self._wire(monkeypatch, fail_first=True)
        ag = agent.Agent(model=LOCAL_MODEL)
        with pytest.raises(llm.LLMError):
            ag.run("hi")

    def test_no_fallback_model_friendly_error(self, monkeypatch):
        monkeypatch.setattr(config, "get_auto_cloud_fallback", lambda: True)
        monkeypatch.setattr(config, "get_dispatch_config", lambda: {
            "dispatch_flash": "deepseek/v4-flash",
            "dispatch_pro": "deepseek/v4-pro",
            "dispatch_model": LOCAL_MODEL.key})
        monkeypatch.setattr(config, "find_model", lambda key: None)
        self._wire(monkeypatch, fail_first=True)
        ag = agent.Agent(model=LOCAL_MODEL)
        with pytest.raises(llm.LLMError) as ei:
            ag.run("hi")
        assert "没有可用的云端回退模型" in str(ei.value)

    def test_cloud_failure_never_falls_back(self, monkeypatch):
        """云端模型自身失败不回退（避免连环计费）。"""
        self._wire_config(monkeypatch)

        def stream(model, messages, schemas):
            raise llm.LLMError("HTTP 503: Loading model")
            yield  # pragma: no cover

        monkeypatch.setattr(llm, "stream_chat", stream)
        ag = agent.Agent(model=CLOUD_MODEL)
        with pytest.raises(llm.LLMError):
            ag.run("hi")

    def test_connection_refused_falls_back(self, monkeypatch):
        """本地服务没在运行（连接失败）同样回退。"""
        self._wire_config(monkeypatch)
        calls = []

        def stream(model, messages, schemas):
            calls.append(model.key)
            if len(calls) == 1:
                raise llm.LLMError("连接失败: Connection refused")
            yield {"type": "text", "delta": "ok"}
            yield {"type": "finish", "reason": "stop"}

        monkeypatch.setattr(llm, "stream_chat", stream)
        ag = agent.Agent(model=LOCAL_MODEL)
        assert ag.run("hi") == "ok"
        assert calls[-1] == CLOUD_MODEL.key


class TestMidStreamStop:
    """流中协作式停止：半程回复落盘、不进缓存、不误报空流。"""

    def test_stop_mid_stream_keeps_partial(self, monkeypatch):
        state = {"n": 0}

        def stream(model, messages, schemas):
            yield {"type": "text", "delta": "半"}
            state["n"] += 1
            yield {"type": "text", "delta": "截"}
            state["n"] += 1

        monkeypatch.setattr(llm, "stream_chat", stream)
        # 第 2 个事件后 on_stop 开始返回 True → 流终止
        ag = agent.Agent(model=MODEL, on_stop=lambda: state["n"] >= 2)
        out = ag.run("hi")
        assert out == "半截"
        # 半程回复已写入 messages（关窗/停止也能落盘保存）
        assert ag.messages[-1]["role"] == "assistant"
        assert ag.messages[-1]["content"] == "半截"

    def test_stop_mid_stream_no_empty_warning(self, monkeypatch):
        """停止时一个正文都没收到：不报「模型未返回任何内容」。"""
        def stream(model, messages, schemas):
            yield {"type": "finish", "reason": "stop"}  # 无正文事件

        monkeypatch.setattr(llm, "stream_chat", stream)
        ag = agent.Agent(model=MODEL, on_stop=lambda: True)
        out = ag.run("hi")
        assert "未返回任何内容" not in (out or "")


class TestMCPManagerIsolation:
    def test_reset_manager_gives_fresh_instance(self):
        import mcp
        m1 = mcp.get_manager()
        mcp.reset_manager()
        m2 = mcp.get_manager()
        assert m1 is not m2
