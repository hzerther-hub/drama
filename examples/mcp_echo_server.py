# -*- coding: utf-8 -*-
"""示例 MCP 服务器（stdio JSON-RPC）：用于测试/演示 MCP 客户端接入。

功能：
  - echo(text)                 原样返回文本
  - add(a, b)                  两数相加
  - show_color(red, green, blue) 生成一张 1x1 PNG 返回（演示图片结果）

手动测试：
  python3 examples/mcp_echo_server.py     # 从 stdin 读 JSON-RPC，往 stdout 写
在应用里接入（~/.config/local-ai-studio/mcp.json）：
  {"servers": {"echo": {
      "command": "python3",
      "args": ["<项目路径>/examples/mcp_echo_server.py"],
      "enabled": true, "readonly": true}}}
"""

from __future__ import annotations
import base64
import json
import struct
import sys
import zlib

TOOLS = [
    {
        "name": "echo",
        "description": "原样返回输入文本（测试用）",
        "inputSchema": {"type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"]},
    },
    {
        "name": "add",
        "description": "两数相加",
        "inputSchema": {"type": "object",
                        "properties": {"a": {"type": "number"},
                                       "b": {"type": "number"}},
                        "required": ["a", "b"]},
    },
    {
        "name": "show_color",
        "description": "生成一张 1x1 PNG 图片（演示图片类工具结果）",
        "inputSchema": {"type": "object",
                        "properties": {"red": {"type": "integer"},
                                       "green": {"type": "integer"},
                                       "blue": {"type": "integer"}},
                        "required": []},
    },
]


def make_png(r: int, g: int, b: int) -> bytes:
    """手搓一张 1x1 RGB PNG（零依赖）。"""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" + bytes((r & 255, g & 255, b & 255)))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", idat) + chunk(b"IEND", b""))


def handle(method, params):
    if method == "initialize":
        return {"protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "echo-server", "version": "1.0"}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "echo":
            return {"content": [{"type": "text",
                                 "text": args.get("text", "")}]}
        if name == "add":
            return {"content": [{"type": "text",
                                 "text": str(args.get("a", 0) + args.get("b", 0))}]}
        if name == "show_color":
            png = make_png(args.get("red", 255), args.get("green", 128),
                           args.get("blue", 0))
            return {"content": [
                {"type": "text", "text": f"这是颜色 RGB({args.get('red', 255)},"
                                         f"{args.get('green', 128)},{args.get('blue', 0)})"},
                {"type": "image", "data": base64.b64encode(png).decode(),
                 "mimeType": "image/png"},
            ]}
    if method == "ping":
        return {}
    raise ValueError(f"未知方法 {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method", "")
        if method == "notifications/initialized":
            continue    # 通知无需响应
        try:
            result = handle(method, req.get("params") or {})
            resp = {"jsonrpc": "2.0", "id": req.get("id"), "result": result}
        except Exception as e:  # noqa: BLE001
            resp = {"jsonrpc": "2.0", "id": req.get("id"),
                    "error": {"code": -32603, "message": str(e)}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
