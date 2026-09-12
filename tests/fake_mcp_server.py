# -*- coding: utf-8 -*-
"""测试用最小 MCP stdio 服务器（JSON-RPC 2.0 按行收发）。

只实现 initialize / tools/list / tools/call，供 test_mcp.py 起真子进程端到端。
文件名不以 test_ 开头，pytest 不会收集。
"""
import json
import sys

TOOLS = [{"name": "echo", "description": "回显",
          "inputSchema": {"type": "object",
                          "properties": {"text": {"type": "string"}},
                          "required": ["text"]}}]


def _reply(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if "id" not in msg:                       # 通知：按协议不需回
            continue
        method = msg.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "serverInfo": {"name": "fake"},
                      "capabilities": {"tools": {}}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            args = (msg.get("params") or {}).get("arguments") or {}
            if args.get("text") == "boom":
                result = {"isError": True,
                          "content": [{"type": "text", "text": "故意失败"}]}
            else:
                result = {"content": [{"type": "text",
                                       "text": "echo:" + str(args.get("text", ""))}]}
        else:
            _reply({"jsonrpc": "2.0", "id": msg["id"],
                    "error": {"code": -32601, "message": "method not found"}})
            continue
        _reply({"jsonrpc": "2.0", "id": msg["id"], "result": result})


if __name__ == "__main__":
    main()
