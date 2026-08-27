# -*- coding: utf-8 -*-
"""MCP（Model Context Protocol）客户端。

支持两种传输，按配置自动选择：
- stdio：本地服务器作为子进程启动，JSON-RPC 2.0 按行传输（配置 command/args）。
- streamable HTTP：远程服务器用 POST 收发，响应兼容纯 JSON 与 SSE（配置 url/headers）。

共同流程：initialize 握手 → tools/list 发现工具 → 合并进模型 tools 参数。
工具名加前缀 mcp_<server>_<tool>，避免与内置工具冲突。
服务器配置存于 config.CONFIG_DIR/mcp.json，可在界面里管理。

零第三方依赖（仅标准库）。
"""

from __future__ import annotations
import base64
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

import config

# JSON-RPC / MCP 常量
PROTOCOL_VERSION = "2024-11-05"
INIT_TIMEOUT = 20           # 启动握手超时（秒）
CALL_TIMEOUT = 120          # 单次工具调用超时（秒）


class MCPError(Exception):
    pass


class _MCPClientBase:
    """MCP 客户端公共逻辑：握手、工具发现、调用结果归一化。

    传输细节由子类实现：_open() / request() / notify() / stop() / is_alive()。
    """

    def __init__(self, name: str):
        self.name = name
        self.tools: list[dict] = []
        self.last_error: str = ""

    # ---------- 生命周期 ----------

    def start(self):
        """建立传输 → initialize 握手 → 工具发现，返回服务器自报名称。"""
        self._open()
        # initialize 握手（带 capabilities，便于服务器按需降级）
        resp = self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "local-ai-studio", "version": "1.0"},
        }, timeout=INIT_TIMEOUT)
        server_info = (resp.get("serverInfo") or {}).get("name", "")
        self._on_initialized(resp)
        self.notify("notifications/initialized")
        # 工具发现
        result = self.request("tools/list", {}, timeout=INIT_TIMEOUT)
        self.tools = result.get("tools") or [] if isinstance(result, dict) else []
        return server_info

    def _open(self):
        """建立底层传输；stdio 起子进程，HTTP 只做校验。"""

    def _on_initialized(self, resp: dict):
        """握手响应回调，供子类记录协议版本等信息。"""

    # ---- 以下由子类实现 ----

    def request(self, method: str, params: dict,
                timeout: float = CALL_TIMEOUT) -> dict:
        raise NotImplementedError

    def notify(self, method: str, params: dict | None = None):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def is_alive(self) -> bool:
        raise NotImplementedError

    # ---------- 工具 ----------

    def call_tool(self, tool: str, arguments: dict,
                  timeout: float = CALL_TIMEOUT) -> dict:
        """调用工具，返回归一化结果 {"text": str, "media": [文件路径]}。

        content 里的 image 部分落盘到 config.MEDIA_DIR，路径放进 media
        列表（供 UI 内嵌显示）。
        """
        result = self.request("tools/call", {"name": tool,
                                             "arguments": arguments},
                              timeout=timeout)
        if result.get("isError"):
            texts = [c.get("text", "") for c in result.get("content", [])
                     if isinstance(c, dict) and c.get("type") == "text"]
            raise MCPError("；".join(t for t in texts if t) or "工具返回错误")

        texts, media = [], []
        for part in result.get("content", []):
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                texts.append(part.get("text", ""))
            elif ptype == "image":
                path = _save_image(part.get("data", ""),
                                   part.get("mimeType", "image/png"))
                if path:
                    media.append(path)
                    texts.append(f"[图片已保存: {path}]")
            elif ptype == "resource":
                res = part.get("resource") or {}
                if res.get("uri", "").startswith("data:image"):
                    header, _, b64 = res.get("uri", "").partition(",")
                    mime = "image/png"
                    if "jpeg" in header or "jpg" in header:
                        mime = "image/jpeg"
                    elif "gif" in header:
                        mime = "image/gif"
                    path = _save_image(b64, mime)
                    if path:
                        media.append(path)
                        texts.append(f"[图片已保存: {path}]")
                else:
                    texts.append(str(res.get("text", res.get("uri", ""))))
        return {"text": "\n".join(t for t in texts if t) or "(无输出)",
                "media": media}


class StdioMCPClient(_MCPClientBase):
    """本地 MCP 服务器：子进程 + JSON-RPC 按行收发。"""

    def __init__(self, name: str, command: str, args=None, env=None,
                 cwd: str | None = None):
        super().__init__(name)
        self.command = command
        self.args = list(args or [])
        self.env = env or {}
        self.cwd = cwd
        self.proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._pending: dict[int, dict] = {}   # id -> {"event", "response"}
        self._reader: threading.Thread | None = None

    # ---------- 生命周期 ----------

    def _open(self):
        """启动子进程并开始后台读取。"""
        env = dict(os.environ)
        env.update({k: str(v) for k, v in self.env.items()})
        try:
            self.proc = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=env, cwd=self.cwd,
            )
        except FileNotFoundError:
            raise MCPError(f"命令不存在：{self.command}")
        except OSError as e:
            raise MCPError(f"启动失败：{e}")

        self._reader = threading.Thread(target=self._read_loop,
                                        name=f"mcp-{self.name}", daemon=True)
        self._reader.start()

    def stop(self):
        """终止子进程（先 SIGTERM，0.5s 后 SIGKILL）。"""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            except OSError:
                pass
        self.proc = None

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # ---------- 传输 ----------

    def _send(self, obj: dict):
        if not self.proc or not self.proc.stdin:
            raise MCPError(f"MCP 服务器 {self.name} 未运行")
        try:
            self.proc.stdin.write(
                json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise MCPError(f"MCP 服务器 {self.name} 写入失败：{e}")

    def _read_loop(self):
        """后台线程：逐行读取服务器响应，按 id 分发。"""
        stream = self.proc.stdout if self.proc else None
        if not stream:
            return
        while True:
            try:
                line = stream.readline()
            except (OSError, ValueError):
                break
            if not line:
                break   # 服务器关闭
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line.decode("utf-8", "replace"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if "id" in msg and (msg.get("result") is not None or
                                msg.get("error") is not None):
                with self._lock:
                    slot = self._pending.pop(msg["id"], None)
                if slot:
                    slot["response"] = msg
                    slot["event"].set()

    def request(self, method: str, params: dict, timeout: float = CALL_TIMEOUT) -> dict:
        """发送 JSON-RPC 请求并等待响应，返回 result。"""
        with self._lock:
            rid = self._next_id
            self._next_id += 1
            slot = {"event": threading.Event(), "response": None}
            self._pending[rid] = slot
        self._send({"jsonrpc": "2.0", "id": rid, "method": method,
                    "params": params})
        if not slot["event"].wait(timeout):
            with self._lock:
                self._pending.pop(rid, None)
            raise MCPError(f"MCP {self.name}.{method} 超时（>{timeout}s）")
        resp = slot["response"]
        if resp.get("error"):
            err = resp["error"]
            raise MCPError(f"MCP 错误 [{err.get('code')}]: {err.get('message')}")
        return resp.get("result") or {}

    def notify(self, method: str, params: dict | None = None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})


class HttpMCPClient(_MCPClientBase):
    """远程 MCP 服务器：streamable HTTP，每次请求一个 POST。

    响应可能是纯 JSON，也可能是 SSE（text/event-stream）——后者要从
    data: 行里挑出 id 匹配的那条。无需后台读线程。
    """

    def __init__(self, name: str, url: str, headers=None):
        super().__init__(name)
        self.url = url
        self.headers = {k: str(v) for k, v in (headers or {}).items()}
        self.session_id = ""            # 服务器可能下发 Mcp-Session-Id
        self.protocol_version = PROTOCOL_VERSION
        self._started = False
        self._lock = threading.Lock()
        self._next_id = 1

    # ---------- 生命周期 ----------

    def _open(self):
        if not self.url.startswith(("http://", "https://")):
            raise MCPError(f"非法 URL：{self.url}")
        self._started = True

    def _on_initialized(self, resp: dict):
        version = resp.get("protocolVersion")
        if isinstance(version, str) and version:
            self.protocol_version = version

    def stop(self):
        # 尽力通知服务器释放会话，失败无所谓
        if self._started and self.session_id:
            try:
                req = urllib.request.Request(
                    self.url, method="DELETE",
                    headers={"Mcp-Session-Id": self.session_id, **self.headers})
                urllib.request.urlopen(req, timeout=5).close()
            except Exception:  # noqa: BLE001
                pass
        self._started = False
        self.session_id = ""

    def is_alive(self) -> bool:
        return self._started

    # ---------- 传输 ----------

    def _post(self, payload: dict, timeout: float) -> tuple[str, bytes]:
        """POST 一条 JSON-RPC 消息，返回 (Content-Type, 响应体)。"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol_version,
        }
        headers.update(self.headers)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(
            self.url, method="POST", headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                session = resp.headers.get("Mcp-Session-Id")
                if session:
                    self.session_id = session
                return (resp.headers.get("Content-Type") or "").lower(), resp.read()
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:200]
            except Exception:  # noqa: BLE001
                pass
            raise MCPError(f"HTTP {e.code} {e.reason}{'：' + detail if detail else ''}")
        except urllib.error.URLError as e:
            raise MCPError(f"连接失败：{e.reason}")
        except OSError as e:
            raise MCPError(f"连接失败：{e}")

    @staticmethod
    def _parse_messages(content_type: str, raw: bytes) -> list[dict]:
        """把响应体解析成 JSON-RPC 消息列表，兼容 SSE 与纯 JSON。"""
        text = raw.decode("utf-8", "replace").strip()
        if not text:
            return []
        if "text/event-stream" in content_type:
            messages = []
            for line in text.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    messages.append(json.loads(payload))
                except json.JSONDecodeError:
                    continue
            return messages
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else [data]

    def request(self, method: str, params: dict,
                timeout: float = CALL_TIMEOUT) -> dict:
        if not self._started:
            raise MCPError(f"MCP 服务器 {self.name} 未运行")
        with self._lock:
            rid = self._next_id
            self._next_id += 1
        content_type, raw = self._post(
            {"jsonrpc": "2.0", "id": rid, "method": method, "params": params},
            timeout)
        for msg in self._parse_messages(content_type, raw):
            if msg.get("id") != rid:
                continue            # 服务器夹带的通知，跳过
            if msg.get("error"):
                err = msg["error"]
                raise MCPError(f"MCP 错误 [{err.get('code')}]: {err.get('message')}")
            return msg.get("result") or {}
        raise MCPError(f"MCP {self.name}.{method} 无有效响应")

    def notify(self, method: str, params: dict | None = None):
        if not self._started:
            return
        try:    # 通知无响应可等，失败不致命
            self._post({"jsonrpc": "2.0", "method": method,
                        "params": params or {}}, timeout=INIT_TIMEOUT)
        except MCPError:
            pass


def create_client(name: str, cfg: dict) -> _MCPClientBase:
    """按配置选择传输：填了 url 走远程 HTTP，否则走 stdio 子进程。"""
    url = (cfg.get("url") or cfg.get("httpUrl") or "").strip()
    if url:
        return HttpMCPClient(name, url, cfg.get("headers"))
    command = (cfg.get("command") or "").strip()
    if not command:
        raise MCPError("未配置 command 或 url")
    return StdioMCPClient(name, command, cfg.get("args"),
                          cfg.get("env"), cfg.get("cwd"))


def _save_image(b64: str, mime: str) -> str | None:
    """把 base64 图片落盘到媒体目录，返回路径；失败返回 None。"""
    try:
        raw = base64.b64decode(b64)
    except Exception:  # noqa: BLE001
        return None
    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
           "image/webp": ".webp"}.get(mime, ".png")
    os.makedirs(config.MEDIA_DIR, exist_ok=True)
    path = os.path.join(config.MEDIA_DIR, f"mcp_{uuid.uuid4().hex[:8]}{ext}")
    with open(path, "wb") as f:
        f.write(raw)
    return path


# ================= 多服务器管理 =================

def _safe_name(s: str) -> str:
    """把服务器/工具名里的非法字符换成下划线（OpenAI 工具名约束）。"""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


class MCPManager:
    """管理所有 MCP 服务器连接；工具发现、路由、权限。"""

    def __init__(self):
        self.clients: dict[str, _MCPClientBase] = {}   # server -> client
        self.tool_map: dict[str, tuple[str, str]] = {}  # 前缀名 -> (server, tool)
        self.readonly_servers: set[str] = set()
        self.status: dict[str, str] = {}             # server -> "ok"/错误信息
        self.connected = False

    def connect(self, on_log=None) -> bool:
        """按 mcp.json 连接所有启用服务器；返回是否有至少一个成功。"""
        def log(msg):
            if on_log:
                on_log(msg)

        data = config.load_mcp_servers()
        ok_any = False
        for name, cfg in (data.get("servers") or {}).items():
            if not cfg.get("enabled", True):
                self.status[name] = "已停用"
                continue
            try:
                client = create_client(name, cfg)
            except MCPError as e:
                self.status[name] = str(e)
                continue
            try:
                server_info = client.start()
                self.clients[name] = client
                if cfg.get("readonly", False):
                    self.readonly_servers.add(name)
                self.status[name] = f"ok（{server_info}，{len(client.tools)} 个工具）"
                ok_any = True
                log(f"MCP 服务器 {name} 已连接：{len(client.tools)} 个工具")
            except MCPError as e:
                self.status[name] = str(e)
                client.stop()
                log(f"MCP 服务器 {name} 连接失败：{e}")
        # 建立前缀 → (server, tool) 映射
        self.tool_map.clear()
        for server, client in self.clients.items():
            for t in client.tools:
                self.tool_map[f"mcp_{_safe_name(server)}_{_safe_name(t['name'])}"] = \
                    (server, t["name"])
        self.connected = True
        return ok_any

    def tool_schemas(self) -> list[dict]:
        """把所有 MCP 工具转成 OpenAI function-calling schema（带前缀）。"""
        schemas = []
        for server, client in self.clients.items():
            for t in client.tools:
                desc = (t.get("description") or "").strip() or f"MCP 工具（{server}）"
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": f"mcp_{_safe_name(server)}_{_safe_name(t['name'])}",
                        "description": f"[MCP:{server}] {desc}"[:4096],
                        "parameters": t.get("inputSchema") or
                                      {"type": "object", "properties": {}},
                    },
                })
        return schemas

    def has_tool(self, name: str) -> bool:
        return name in self.tool_map

    def is_write_tool(self, name: str) -> bool:
        """未标记 readonly 的 MCP 服务器上的工具一律视为可写（需审批）。"""
        if name not in self.tool_map:
            return False
        return self.tool_map[name][0] not in self.readonly_servers

    def call(self, name: str, arguments: dict) -> dict:
        """路由调用：返回 {"text", "media"}；错误也以文本形式返回。"""
        target = self.tool_map.get(name)
        if not target:
            return {"text": f"错误：未知 MCP 工具 {name}", "media": []}
        server, tool = target
        client = self.clients.get(server)
        if client is None or not client.is_alive():
            return {"text": f"错误：MCP 服务器 {server} 未运行", "media": []}
        try:
            return client.call_tool(tool, arguments or {})
        except MCPError as e:
            return {"text": f"错误：{e}", "media": []}

    def stop_all(self):
        for client in self.clients.values():
            client.stop()
        self.clients.clear()
        self.tool_map.clear()
        self.connected = False


# 进程级单例：UI 与 agent 共用同一批子进程连接
_manager: MCPManager | None = None
_manager_lock = threading.Lock()


def get_manager() -> MCPManager:
    """获取/创建全局 MCP 管理器（懒加载，线程安全）。"""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = MCPManager()
        return _manager


def reset_manager():
    """断开全部连接并重置单例（配置变更/界面刷新时用）。"""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.stop_all()
        _manager = None
