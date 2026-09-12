# -*- coding: utf-8 -*-
"""MCP 客户端：传输选择、SSE/JSON 解析、工具前缀路由与权限、失败路径。

含一个真子进程端到端用例（tests/fake_mcp_server.py），覆盖握手 / 工具发现 /
调用 / 错误返回 / 进程收尾。
"""

import base64
import json
import os
import sys

import pytest

import config
import mcp

_FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_mcp_server.py")


class TestCreateClient:
    def test_url_goes_http(self):
        assert isinstance(mcp.create_client("s", {"url": "https://x/mcp"}),
                          mcp.HttpMCPClient)

    def test_http_url_alias(self):
        assert isinstance(mcp.create_client("s", {"httpUrl": "https://x/mcp"}),
                          mcp.HttpMCPClient)

    def test_command_goes_stdio_with_args(self):
        c = mcp.create_client("s", {"command": "npx", "args": ["-y", "pkg"]})
        assert isinstance(c, mcp.StdioMCPClient)
        assert (c.command, c.args) == ("npx", ["-y", "pkg"])

    def test_neither_raises(self):
        with pytest.raises(mcp.MCPError):
            mcp.create_client("s", {})

    def test_http_open_rejects_bad_scheme(self):
        c = mcp.HttpMCPClient("s", "ftp://x")
        with pytest.raises(mcp.MCPError):
            c._open()


class TestParseMessages:
    def test_plain_json_object(self):
        assert mcp.HttpMCPClient._parse_messages("application/json",
                                                b'{"id": 1}') == [{"id": 1}]

    def test_json_array(self):
        raw = json.dumps([{"id": 1}, {"id": 2}]).encode()
        assert len(mcp.HttpMCPClient._parse_messages("application/json", raw)) == 2

    def test_sse_takes_only_data_lines(self):
        raw = (b"event: message\n"
               b'data: {"id": 7, "result": {}}\n\n'
               b"data: [DONE]\n")
        assert mcp.HttpMCPClient._parse_messages(
            "text/event-stream; charset=utf-8", raw) == [{"id": 7, "result": {}}]

    def test_empty_and_garbage(self):
        assert mcp.HttpMCPClient._parse_messages("application/json", b"") == []
        assert mcp.HttpMCPClient._parse_messages("application/json",
                                                b"<html>oops") == []


class TestSafeName:
    @pytest.mark.parametrize("raw,want", [
        ("filesystem", "filesystem"),
        ("my server/tool", "my_server_tool"),
        ("a.b", "a_b"),
        ("已命名", "___"),
    ])
    def test_safe_name(self, raw, want):
        assert mcp._safe_name(raw) == want


def _manager():
    m = mcp.MCPManager()
    m.tool_map["mcp_fs_read"] = ("fs", "read")
    m.tool_map["mcp_net_post"] = ("net", "post")
    m.readonly_servers.add("fs")
    return m


class TestManagerRouting:
    def test_is_write_tool_respects_readonly_server(self):
        m = _manager()
        assert m.has_tool("mcp_fs_read") is True
        assert m.is_write_tool("mcp_fs_read") is False      # readonly 服务器
        assert m.is_write_tool("mcp_net_post") is True
        assert m.is_write_tool("unknown") is False

    def test_call_unknown_tool_returns_text(self):
        out = _manager().call("mcp_nope_x", {})
        assert "未知 MCP 工具" in out["text"] and out["media"] == []

    def test_call_dead_server_returns_text(self):
        m = _manager()
        m.clients["fs"] = mcp.StdioMCPClient("fs", "nope")   # 从未启动
        out = m.call("mcp_fs_read", {})
        assert "未运行" in out["text"]

    def test_tool_schemas_are_prefixed_and_carry_input_schema(self):
        m = mcp.MCPManager()
        client = mcp.HttpMCPClient("net", "https://x")
        client.tools = [{"name": "fetch", "description": "抓页面",
                         "inputSchema": {"type": "object",
                                         "properties": {"url": {"type": "string"}}}}]
        m.clients["net"] = client
        schema = m.tool_schemas()[0]["function"]
        assert schema["name"] == "mcp_net_fetch"
        assert schema["description"].startswith("[MCP:net]")
        assert "url" in schema["parameters"]["properties"]

    def test_tool_schemas_fallback_description_and_schema(self):
        m = mcp.MCPManager()
        client = mcp.HttpMCPClient("s", "https://x")
        client.tools = [{"name": "t"}]
        m.clients["s"] = client
        fn = m.tool_schemas()[0]["function"]
        assert "MCP 工具（s）" in fn["description"]
        assert fn["parameters"] == {"type": "object", "properties": {}}


class TestManagerConnect:
    def test_missing_command_reported_not_raised(self, monkeypatch):
        monkeypatch.setattr(config, "load_mcp_servers",
                            lambda: {"servers": {"bad": {"command":
                                                         "no-such-binary-xyz-123"}}})
        m = mcp.MCPManager()
        assert m.connect() is False
        assert "不存在" in m.status["bad"]
        assert m.clients == {}

    def test_disabled_server_skipped(self, monkeypatch):
        monkeypatch.setattr(config, "load_mcp_servers",
                            lambda: {"servers": {"off": {"enabled": False,
                                                         "command": "x"}}})
        m = mcp.MCPManager()
        assert m.connect() is False
        assert m.status["off"] == "已停用"
        assert m.clients == {}

    def test_stop_all_clears_state(self):
        m = _manager()
        m.connected = True
        m.stop_all()
        assert (m.clients, m.tool_map, m.connected) == ({}, {}, False)


class TestStdioRoundTrip:
    """真子进程端到端：握手 → 工具发现 → 调用 → 错误 → 收尾。"""

    def test_full_roundtrip(self):
        c = mcp.StdioMCPClient("fake", sys.executable, [_FAKE])
        try:
            assert c.start() == "fake"
            assert [t["name"] for t in c.tools] == ["echo"]
            assert c.is_alive() is True
            out = c.call_tool("echo", {"text": "hi"})
            assert out["text"] == "echo:hi" and out["media"] == []
        finally:
            c.stop()
        assert c.is_alive() is False

    def test_iserror_becomes_mcperror(self):
        c = mcp.StdioMCPClient("fake", sys.executable, [_FAKE])
        try:
            c.start()
            with pytest.raises(mcp.MCPError) as ei:
                c.call_tool("echo", {"text": "boom"})
            assert "故意失败" in str(ei.value)
        finally:
            c.stop()

    def test_unknown_method_raises(self):
        c = mcp.StdioMCPClient("fake", sys.executable, [_FAKE])
        try:
            c.start()
            with pytest.raises(mcp.MCPError):
                c.request("no/such.method", {}, timeout=10)
        finally:
            c.stop()


class TestTransportGuards:
    def test_stdio_send_without_process_raises(self):
        with pytest.raises(mcp.MCPError):
            mcp.StdioMCPClient("s", "cmd")._send({"jsonrpc": "2.0"})

    def test_stdio_not_alive_before_start(self):
        assert mcp.StdioMCPClient("s", "cmd").is_alive() is False

    def test_http_request_before_start_raises(self):
        with pytest.raises(mcp.MCPError):
            mcp.HttpMCPClient("s", "https://x").request("tools/list", {})


class TestSaveImage:
    def test_writes_under_media_dir(self):
        path = mcp._save_image(base64.b64encode(b"\x89PNG fake").decode(), "image/png")
        assert path and path.endswith(".png")
        assert os.path.dirname(os.path.abspath(path)) == \
            os.path.dirname(os.path.abspath(os.path.join(config.MEDIA_DIR, "x")))
        with open(path, "rb") as f:
            assert f.read() == b"\x89PNG fake"

    def test_unknown_mime_defaults_to_png(self):
        assert mcp._save_image(base64.b64encode(b"x").decode(), "image/tiff").endswith(".png")

    def test_bad_base64_returns_none(self):
        assert mcp._save_image("中文", "image/png") is None


class TestSingleton:
    def test_get_manager_is_stable_and_reset_clears(self):
        assert mcp.get_manager() is mcp.get_manager()
        mcp.reset_manager()
        assert mcp.get_manager() is not None
        mcp.reset_manager()
