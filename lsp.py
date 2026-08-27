# -*- coding: utf-8 -*-
"""轻量 LSP 客户端（标准库实现，JSON-RPC over stdio）——多语言智能提示。

为本地 AI Studio 提供三块能力：
1. 编辑器「真语义」补全 / 签名提示（按文件扩展名选语言服务器）；
2. 诊断（错误/警告）收集：编辑器底栏显示 ✗/⚠ 计数，工具 lsp_diagnostics
   可把诊断交给模型（改代码前先查错）；
3. 启动预热：App 启动时探测工作区主要开发语言，提前拉起对应服务器
   （打开文件首次补全不再卡顿）。

支持语言（服务器存在才启用，缺失自动跳过）：
python/js/ts/jsx/vue/html/css/json/go/rust/c/cpp/java/cs/ruby/kotlin/
swift/php/dart/bash/erlang/yaml。

用法：
    client = lsp.LSPClient.for_file(path)        # None 表示无对应服务器
    client.did_open(content)                     # 打开文件（LSP 必须先 didOpen）
    items = client.complete(content, line, char) # 返回 [{"label":…, "detail":…}]
    diags = client.diag(content)                 # 返回诊断列表
    langs = lsp.probe_workspace(ws)              # 工作区语言探测（按文件数排序）
    lsp.warm(lang, ws)                           # 启动预热一个语言服务器
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from collections import Counter

# 语言 -> 服务器命令（列表；首元素为可执行名，缺失则为 None）
_SERVERS = {
    "python": ["pyright-langserver", "--stdio"],
    "js": ["typescript-language-server", "--stdio"],
    "ts": ["typescript-language-server", "--stdio"],
    "vue": ["typescript-language-server", "--stdio"],
    "html": ["vscode-html-language-server", "--stdio"],
    "css": ["vscode-css-language-server", "--stdio"],
    "json": ["vscode-json-languageserver", "--stdio"],
    "go": ["gopls"],
    "rust": ["rust-analyzer"],
    "c": ["clangd"],
    "cpp": ["clangd"],
    "java": ["jdtls"],
    "cs": ["OmniSharp", "-lsp"],
    "ruby": ["solargraph", "stdio"],
    "kotlin": ["kotlin-language-server"],
    "swift": ["sourcekit-lsp"],
    "dart": ["dart", "language-server"],
    "php": ["php-language-server"],
    "bash": ["bash-language-server", "start"],
    "sh": ["bash-language-server", "start"],
    "erlang": ["erlang_ls"],
    "yaml": ["yaml-language-server", "--stdio"],
}

_LANG_ID = {
    "python": "python", "js": "javascript", "ts": "typescript", "vue": "vue",
    "html": "html", "css": "css", "json": "json", "go": "go", "rust": "rust",
    "c": "c", "cpp": "cpp", "java": "java", "cs": "csharp", "ruby": "ruby",
    "kotlin": "kotlin", "swift": "swift", "dart": "dart", "php": "php",
    "sh": "shellscript", "bash": "shellscript", "erlang": "erlang",
    "yaml": "yaml",
}

# 后缀 -> 语言（多语言探测 + 单文件识别共用）
_EXT_LANG = {
    ".py": "python", ".pyw": "python", ".pyi": "python",
    ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js",
    ".ts": "ts", ".tsx": "ts", ".mts": "ts",
    ".vue": "vue", ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".less": "css",
    ".json": "json", ".jsonc": "json",
    ".go": "go", ".rs": "rust",
    ".c": "c", ".h": "cpp", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hh": "cpp",
    ".java": "java", ".cs": "cs", ".rb": "ruby",
    ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift",
    ".dart": "dart", ".php": "php",
    ".sh": "sh", ".bash": "sh", ".erl": "erlang", ".hrl": "erlang",
    ".escript": "erlang",
    ".yaml": "yaml", ".yml": "yaml",
}

# 工作区语言探测时跳过的目录（生成物/依赖，不代表项目语言）
_PROBE_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", "venv", ".venv",
    "env", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", "target",
    ".idea", ".vscode", ".next", ".nuxt", "vendor", "bower_components",
    "media", ".cache", "coverage", "out", "bin", "obj",
}

# 诊断严重级别 -> 标记（LSP: 1=Error 2=Warning 3=Info 4=Hint）
_SEV_MARK = {1: "✗", 2: "⚠", 3: "ℹ", 4: "·"}


def available_for(lang: str) -> bool:
    """该语言是否有可执行的 LSP 服务器。"""
    cmd = _SERVERS.get(lang)
    return bool(cmd and shutil.which(cmd[0]))


def language_of(path: str) -> str:
    """文件路径 -> 语言标识（无对应语言返回空串）。"""
    return _EXT_LANG.get(os.path.splitext(path)[1].lower(), "")


def lang_id_of(lang: str) -> str:
    """内部语言键 -> LSP languageId。"""
    return _LANG_ID.get(lang, "plaintext")


def probe_workspace(ws: str, max_files: int = 5000) -> list[str]:
    """探测工作区开发语言：按源码文件数降序返回语言键列表。

    只统计有可用语言服务器的语言；扫描上限 max_files 个文件防大仓库卡顿。
    """
    if not ws or not os.path.isdir(ws):
        return []
    counts, n = Counter(), 0
    for root, dirs, files in os.walk(ws):
        dirs[:] = [d for d in dirs if d not in _PROBE_SKIP_DIRS]
        for f in files:
            n += 1
            if n > max_files:
                return [l for l, _ in counts.most_common()
                        if available_for(l)]
            lang = _EXT_LANG.get(os.path.splitext(f)[1].lower())
            if lang:
                counts[lang] += 1
    return [l for l, _ in counts.most_common() if available_for(l)]


def warm(lang: str, workspace: str) -> bool:
    """启动预热一个语言服务器（initialize 即可，不绑定文件）。

    打开文件首次补全不再等服务器冷启动（pyright/node 类启动最慢）。
    返回是否成功启动。
    """
    if not available_for(lang):
        return False
    try:
        c = LSPClient(_SERVERS[lang], workspace, None, lang=lang)
        c.start()
        c.close()
        return True
    except Exception:            # noqa: BLE001  预热失败无碍，打开文件再懒启动
        return False


class LSPClient:
    def __init__(self, cmd: str, workspace: str, path: str, lang: str = ""):
        self._path = os.path.abspath(path) if path else None
        self._workspace = workspace or (
            os.path.dirname(self._path) if self._path else os.getcwd())
        self._uri = ("file://" + self._path) if self._path else \
                    ("file://" + os.path.abspath(self._workspace))
        self._langid = lang_id_of(lang) if lang else (
            lang_id_of(language_of(path)) if path else "plaintext")
        self._id = 0
        self._lock = threading.Lock()
        self._cmd = cmd
        self._proc = None
        self._started = False
        self.diagnostics = []          # 最新一次 publishDiagnostics 结果

    # ---- 底层收发 ----
    def _send(self, obj):
        payload = json.dumps(obj, ensure_ascii=False)
        b = payload.encode("utf-8")
        self._proc.stdin.write(f"Content-Length: {len(b)}\r\n\r\n".encode("utf-8"))
        self._proc.stdin.write(b)
        self._proc.stdin.write(b"\n")
        self._proc.stdin.flush()

    def _read(self, timeout: float):
        """读一条消息，返回 dict；超时/EOF 返回 None。

        publishDiagnostics 等通知顺带存入 self.diagnostics。
        """
        import select
        if not select.select([self._proc.stdout], [], [], timeout)[0]:
            return None
        # 读头部
        headers = {}
        while True:
            line = self._proc.stdout.readline()
            if not line or line in (b"\r\n", b"\n"):
                break
            try:
                k, v = line.decode("utf-8", "replace").strip().split(":", 1)
                headers[k.strip().lower()] = v.strip()
            except ValueError:
                pass
        n = int(headers.get("content-length", "0") or 0)
        if n <= 0:
            return None
        try:
            body = self._proc.stdout.read(n).decode("utf-8", "replace")
            msg = json.loads(body)
            self._take_notice(msg)
            return msg
        except Exception:           # noqa: BLE001
            return None

    def _take_notice(self, msg):
        """处理服务器推送的通知（诊断等），随读随存。"""
        try:
            if msg.get("method") == "textDocument/publishDiagnostics":
                params = msg.get("params") or {}
                uri = params.get("uri", "")
                if not self._path or uri == self._uri:
                    self.diagnostics = params.get("items") or []
        except Exception:           # noqa: BLE001
            pass

    # ---- 生命周期 ----
    def start(self):
        if self._started:
            return
        if self._proc is None:
            self._proc = subprocess.Popen(
                self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)
        init = {"jsonrpc": "2.0", "id": 0, "method": "initialize",
                "params": {"processId": os.getpid(),
                           "rootUri": "file://" + os.path.abspath(self._workspace),
                           "capabilities": {}}}
        self._id = 1
        self._send(init)
        self._read(5.0)                      # 等 initialize 响应（冷启动可慢）
        self._send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        # 打开当前文件（LSP 必须先 didOpen 才能补全；预热模式无文件则跳过）
        if self._path:
            self.did_open(self._read_current())
        self._started = True

    def _read_current(self):
        try:
            with open(self._path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:           # noqa: BLE001
            return ""

    def did_open(self, text: str):
        self._send({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                    "params": {"textDocument": {
                        "uri": self._uri, "languageId": self._langid,
                        "version": 1, "text": text}}})
        self._read(0.6)                       # 吞掉发布诊断等通知

    def did_change(self, text: str):
        self._send({"jsonrpc": "2.0", "method": "textDocument/didChange",
                    "params": {"textDocument": {"uri": self._uri, "version": 2},
                               "contentChanges": [{"text": text}]}})
        self._read(0.4)

    def _request(self, method, params, timeout):
        if not self._started:
            self.start()
        with self._lock:
            self._id += 1
            rid = self._id
            self._send({"jsonrpc": "2.0", "method": method, "id": rid, "params": params})
            deadline = time.time() + timeout
            while time.time() < deadline:
                msg = self._read(timeout)
                if msg is None:
                    break
                if msg.get("id") == rid:
                    return msg.get("result")
        return None

    def complete(self, text, line, char):
        result = self._request("textDocument/completion", {
            "textDocument": {"uri": self._uri},
            "position": {"line": line, "character": char}}, 2.5)
        if isinstance(result, dict):
            result = result.get("items") or []
        items = []
        for it in result or []:
            label = it.get("label", "")
            detail = it.get("detail") or " ".join(
                it.get("documentation", "").split()) if isinstance(
                    it.get("documentation"), str) else (it.get("detail") or "")
            items.append({"label": label, "detail": (detail or "").strip()})
        return items

    def signature(self, text, line, char):
        result = self._request("textDocument/signatureHelp", {
            "textDocument": {"uri": self._uri},
            "position": {"line": line, "character": char}}, 2.0)
        try:
            sigs = result.get("signatures") if isinstance(result, dict) else None
            if sigs:
                return sigs[0].get("label", "")
        except Exception:           # noqa: BLE001
            pass
        return None

    def diag(self, text: str, wait: float = 1.2) -> list:
        """同步最新内容并拉取诊断。返回 [{line, mark, msg}]（行号从 1 起）。"""
        if not self._started:
            self.start()
        with self._lock:
            self._send({"jsonrpc": "2.0", "method": "textDocument/didChange",
                        "params": {"textDocument": {"uri": self._uri, "version": 2},
                                   "contentChanges": [{"text": text}]}})
            # 诊断是服务器异步推送的：等一小会儿收通知
            self.diagnostics = []
            deadline = time.time() + wait
            while time.time() < deadline:
                if self._read(0.2) is None and self.diagnostics:
                    break                      # 已收到且通道静默 → 收工
        return format_diags(self.diagnostics)

    def close(self):
        try:
            self._send({"jsonrpc": "2.0", "method": "shutdown", "params": None})
            self._read(0.5)
        except Exception:           # noqa: BLE001
            pass
        try:
            self._proc.kill()
        except Exception:           # noqa: BLE001
            pass

    @classmethod
    def for_file(cls, path):
        lang = language_of(path)
        if not lang:
            return None
        cmd = _SERVERS.get(lang)
        if not cmd or not shutil.which(cmd[0]):
            return None
        try:
            return cls(cmd, os.path.dirname(os.path.abspath(path)), path, lang=lang)
        except Exception:           # noqa: BLE001
            return None


def format_diags(items: list) -> list:
    """LSP 诊断项 -> 紧凑列表 [{line, mark, msg}]（纯函数，便于测试）。"""
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not it.get("message"):
            continue
        try:
            pos = (it.get("range") or {}).get("start") or {}
            line = int(pos.get("line", 0)) + 1
            sev = int(it.get("severity") or 3)
            msg = (it.get("message") or "").strip().splitlines()
            out.append({"line": line, "mark": _SEV_MARK.get(sev, "ℹ"),
                        "msg": (msg[0] if msg else "")[:200]})
        except Exception:           # noqa: BLE001
            continue
    return out
