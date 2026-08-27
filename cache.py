# -*- coding: utf-8 -*-
"""LLM 响应 / 工具结果缓存：SQLite / 内存 两种后端。

目的：提速（重复请求秒回）+ 省 tokens（命中即不调后端）。

- 键 = sha256(模型 + 请求内容)，精确匹配
- LLM 回复缓存 TTL 较长（默认 1 小时）
- 工具结果缓存 TTL 较短（默认 5 分钟，文件可能变化）
- backend=auto：优先 SQLite（本机持久化），不可用退回内存

设置持久化在 config.CONFIG_DIR/cache.json，可在界面「管理缓存」修改。
"""

from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import threading
import time

import config

# ---------------- 设置 ----------------
# 路径动态跟随 config.CONFIG_DIR：测试/多实例场景重定向 config 即可整体隔离。

def _settings_file() -> str:
    return os.path.join(config.CONFIG_DIR, "cache.json")


def _default_settings() -> dict:
    return {
        "backend": "auto",                          # auto / sqlite / memory
        "sqlite_path": os.path.join(config.CONFIG_DIR, "cache.db"),
        "llm_ttl": 3600,
        "tool_ttl": 300,
    }

_settings_lock = threading.RLock()   # 可重入：save_settings 内部会调 load_settings
_settings = None


def _cached_settings() -> dict:
    """返回内存中的设置（内部只读，勿改动）。热路径用，避免每次复制 dict。"""
    global _settings
    with _settings_lock:
        if _settings is None:
            data = _default_settings()
            try:
                with open(_settings_file(), "r", encoding="utf-8") as f:
                    saved = json.load(f)
                data.update({k: saved[k] for k in data if k in saved})
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            _settings = data
        return _settings


def load_settings() -> dict:
    """读设置（返回副本），坏文件回退默认。"""
    return dict(_cached_settings())


def save_settings(**kwargs) -> dict:
    """更新并持久化设置，返回新设置。backend/sqlite 路径变化后自动重置连接。"""
    global _settings
    with _settings_lock:
        s = dict(_cached_settings())
        s.update({k: v for k, v in kwargs.items() if k in _default_settings()})
        os.makedirs(config.CONFIG_DIR, exist_ok=True)
        with open(_settings_file(), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
        _settings = s
    _close_sqlite()   # 真正关闭旧连接（而非仅置 None 泄漏句柄）
    return dict(s)


def reset():
    """重置全部缓存状态（设置、后端连接、内存库）。

    测试 / 多实例隔离用：配合 monkeypatch 重定向 config.CONFIG_DIR，
    每个用例即可拿到完全独立的缓存实例。
    """
    global _settings
    with _settings_lock:
        _settings = None
    _close_sqlite()
    with _mem_lock:
        _mem_store.clear()


# ---------------- 键生成 ----------------

def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(
        obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def llm_key(model_id: str, messages: list, tools: list | None) -> str:
    """LLM 回复缓存键：模型 + 完整消息 + 工具 schema。"""
    return "qwenc:llm:" + _hash([model_id, messages, tools or []])


def tool_key(name: str, args: dict, workspace: str) -> str:
    """工具结果缓存键。"""
    return "qwenc:tool:" + _hash([name, args, workspace])


# ---------------- 后端实现 ----------------

_mem_store: dict[str, tuple[float, str]] = {}   # key -> (expire_ts, value)
_mem_lock = threading.Lock()
_MEM_MAX = 500                                   # 内存缓存条目上限
_sqlite: sqlite3.Connection | None = None
_sqlite_lock = threading.RLock()                 # 串行化 SQLite 连接与操作（单连接多线程共享）


def _close_sqlite():
    """关闭并清空 SQLite 连接（线程安全）。"""
    global _sqlite
    with _sqlite_lock:
        if _sqlite is not None:
            try:
                _sqlite.close()
            except Exception:                     # noqa: BLE001
                pass
            _sqlite = None


def _get_sqlite():
    """惰性打开 SQLite（双重检查锁；WAL + NORMAL 同步提速，缓存可接受掉电丢尾）。"""
    global _sqlite
    if _sqlite is not None:
        return _sqlite
    with _sqlite_lock:
        if _sqlite is not None:
            return _sqlite
        path = _cached_settings().get("sqlite_path", "")
        if not path:
            return None
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                "  k TEXT PRIMARY KEY, expire_ts REAL, v TEXT)")
            conn.commit()
            _sqlite = conn
        except Exception:                         # noqa: BLE001
            _sqlite = None
        return _sqlite


def _active_backend() -> str:
    """按设置解析当前实际可用的后端。"""
    backend = _cached_settings().get("backend", "auto")
    if backend == "memory":
        return "memory"
    # auto / sqlite（及旧配置遗留的 "redis"）：优先 SQLite，不可用退内存
    return "sqlite" if _get_sqlite() is not None else "memory"


def _now() -> float:
    return time.time()


def get(key: str) -> str | None:
    """取缓存；过期/不存在返回 None。"""
    backend = _active_backend()
    if backend == "sqlite":
        with _sqlite_lock:
            conn = _sqlite
            if conn is None:
                return None
            try:
                row = conn.execute(
                    "SELECT expire_ts, v FROM kv WHERE k = ?", (key,)).fetchone()
                if row is None:
                    return None
                expire_ts, v = row
                if expire_ts < _now():
                    conn.execute("DELETE FROM kv WHERE k = ?", (key,))
                    conn.commit()
                    return None
                return v
            except Exception:                     # noqa: BLE001
                return None
    # memory
    with _mem_lock:
        item = _mem_store.get(key)
        if item is None:
            return None
        expire_ts, value = item
        if expire_ts < _now():
            _mem_store.pop(key, None)
            return None
        return value


def put(key: str, value: str, ttl: int):
    """写缓存。"""
    backend = _active_backend()
    if backend == "sqlite":
        with _sqlite_lock:
            conn = _sqlite
            if conn is None:
                return
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO kv (k, expire_ts, v) VALUES (?, ?, ?)",
                    (key, _now() + ttl, value))
                conn.commit()
                return
            except Exception:                     # noqa: BLE001
                return
    with _mem_lock:
        if len(_mem_store) >= _MEM_MAX:
            # 淘汰最旧的四分之一
            oldest = sorted(_mem_store.items(), key=lambda kv: kv[1][0])[:_MEM_MAX // 4]
            for k, _ in oldest:
                _mem_store.pop(k, None)
        _mem_store[key] = (_now() + ttl, value)


def clear():
    """清空当前后端的全部缓存。"""
    backend = _active_backend()
    if backend == "sqlite":
        with _sqlite_lock:
            conn = _sqlite
            if conn is None:
                return False
            try:
                conn.execute("DELETE FROM kv")
                conn.commit()
                return True
            except Exception:                     # noqa: BLE001
                return False
    with _mem_lock:
        _mem_store.clear()
        return True


def stats() -> dict:
    """当前后端信息（诊断/管理界面用）。"""
    backend = _active_backend()
    info = {"backend": backend,
            "configured": _cached_settings().get("backend", "auto")}
    if backend == "sqlite":
        with _sqlite_lock:
            conn = _sqlite
            if conn is None:
                info["entries"] = -1
            else:
                try:
                    row = conn.execute("SELECT COUNT(*) FROM kv").fetchone()
                    info["entries"] = row[0]
                except Exception:                 # noqa: BLE001
                    info["entries"] = -1
    else:
        with _mem_lock:
            info["entries"] = len(_mem_store)
    return info


# ---------------- 高层接口 ----------------

def get_llm(model_id: str, messages: list, tools: list | None):
    """返回缓存的回复事件列表（dict 列表），未命中返回 None。"""
    if not _cached_settings().get("llm_ttl"):
        return None
    raw = get(llm_key(model_id, messages, tools))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def put_llm(model_id: str, messages: list, tools: list | None, events: list):
    """缓存一次纯文本回复的事件列表（不含工具调用轮）。"""
    ttl = _cached_settings().get("llm_ttl")
    if not ttl:
        return
    put(llm_key(model_id, messages, tools),
        json.dumps(events, ensure_ascii=False), int(ttl))


def get_tool(name: str, args: dict, workspace: str) -> str | None:
    if not _cached_settings().get("tool_ttl"):
        return None
    return get(tool_key(name, args, workspace))


def put_tool(name: str, args: dict, workspace: str, result: str):
    ttl = _cached_settings().get("tool_ttl")
    if not ttl:
        return
    put(tool_key(name, args, workspace), result, int(ttl))


def backend_name() -> str:
    """当前实际生效的后端。"""
    return _active_backend()
