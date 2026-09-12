# -*- coding: utf-8 -*-
"""ui.App._load_session：坏会话回放不得带崩（不启动 Tk）。

会话正文存在磁盘上（旧版本写入 / 用户手改 / 崩溃半截），tool_calls 的条目
可能缺 function、甚至不是对象，notes 也可能不是列表——旧实现直接取
tc["function"]["name"]、n.get("turn")，切换会话时抛 KeyError / TypeError /
AttributeError，整段历史读不出来。
"""

import sessions
import ui


class _StubBtn:
    def config(self, **_kw):
        pass


class StubApp:
    """只提供 _load_session 依赖的最小接口。"""

    _load_session = ui.App._load_session

    def __init__(self):
        self.session_id = ""
        self.session_title = ""
        self.messages = []
        self.lines = []
        self.sess_btn = _StubBtn()

    def clear(self):
        self.lines = []

    def _append(self, text, tag=None):
        self.lines.append((tag, text))

    def _append_segments(self, segs):
        self.lines.extend((s.get("tag"), s.get("text")) for s in segs)

    def _set_status(self, *_a, **_kw):
        pass

    def _close_all_file_views(self):
        pass

    def _update_workspace_label(self):
        pass

    def _dispatch_targets_ready(self):
        return False


def _load(sid):
    app = StubApp()
    app._load_session(sid)
    return app


def _texts(app):
    return [txt or "" for _tag, txt in app.lines]


def test_tool_call_missing_function_yields_content():
    """条目缺 function（流被截断 / 手改）：旧实现 KeyError。"""
    sessions.save("bad-fn", [{"role": "assistant", "content": "x",
                              "tool_calls": [{"id": "1"}]}], "t")
    app = _load("bad-fn")
    assert app.session_id == "bad-fn"
    assert ("assistant", "x\n") in app.lines


def test_tool_call_entry_not_object():
    """tool_calls 里混进字符串条目：旧实现 TypeError。"""
    sessions.save("bad-str", [{"role": "assistant",
                               "tool_calls": ["read_file"]}], "t")
    assert _load("bad-str").session_id == "bad-str"


def test_tool_calls_not_list():
    """tool_calls 被手改成对象：旧实现遍历出键名再取值 → TypeError。"""
    sessions.save("bad-dict", [{"role": "assistant",
                                "tool_calls": {"a": 1}}], "t")
    assert _load("bad-dict").session_id == "bad-dict"


def test_notes_not_list_ignored():
    """notes 是对象（非列表）：旧实现 n.get("turn") → AttributeError。"""
    sessions.save("bad-notes", [{"role": "user", "content": "hi"}], "t",
                  notes={"turn": 1})
    assert _load("bad-notes").session_id == "bad-notes"


def test_call_model_replay_renders_dispatch_target():
    """历史派发会话仍可读：call_model 已退役，但旧会话要能回放出"派发给谁"。"""
    sessions.save("old-cm", [{"role": "assistant", "tool_calls": [
        {"id": "1", "function": {"name": "call_model",
                                 "arguments": '{"model": "deepseek/x"}'}}]}], "t")
    app = _load("old-cm")
    assert any("派发给" in txt for txt in _texts(app))


def test_call_model_replay_survives_broken_arguments():
    """arguments 被截断（流中断的历史会话）：不得崩，也不显示空的派发行。"""
    sessions.save("old-cm2", [{"role": "assistant", "tool_calls": [
        {"id": "1", "function": {"name": "call_model",
                                 "arguments": '{"model": "deepseek/x",'}}]}], "t")
    app = _load("old-cm2")
    assert not any("派发给" in txt for txt in _texts(app))


def test_call_model_args_not_object():
    """arguments 是合法 JSON 但不是对象（"[1,2]"）→ 旧实现 a.get() AttributeError。"""
    sessions.save("old-cm3", [{"role": "assistant", "tool_calls": [
        {"id": "1", "function": {"name": "call_model",
                                 "arguments": "[1,2]"}}]}], "t")
    app = _load("old-cm3")
    assert not any("派发给" in txt for txt in _texts(app))


def test_normal_session_still_replays_tool_line():
    """正常会话照旧把工具折叠成一行：修复不得把回放内容吞掉。"""
    sessions.save("ok", [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "tool_calls": [
            {"id": "1", "function": {"name": "read_file",
                                     "arguments": '{"path": "a"}'}}]}], "t")
    app = _load("ok")
    assert any("read_file" in txt for txt in _texts(app))
