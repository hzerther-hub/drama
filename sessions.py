# -*- coding: utf-8 -*-
"""多会话管理：保存 / 加载 / 切换 / 删除对话。

会话存于 SQLite（config.CONFIG_DIR/sessions.db），messages 以 JSON 文本存储。
保留原有公开 API（save/load/delete/list_sessions/new_id/make_title），
并在首次使用时把旧的 sessions/*.json 会话自动迁移进 SQLite。
"""

from __future__ import annotations
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

import config

# SQLite 会话库
_DB = os.path.join(config.CONFIG_DIR, "sessions.db")
# 旧版 JSON 会话目录（迁移来源）
_LEGACY_DIR = os.path.join(config.CONFIG_DIR, "sessions")

_lock = threading.RLock()
# 已迁移的旧版目录（目录变化时重新探测，避免多配置/测试环境误判）
_migrated_for = None
# 线程本地连接缓存：避免每次 save/load 都新建连接并重复执行 PRAGMA
_local = threading.local()


def _connect() -> sqlite3.Connection:
    """返回当前线程的 SQLite 连接（按需创建并复用，_DB 变化时自动重建）。"""
    conn = getattr(_local, "conn", None)
    if conn is not None and getattr(_local, "db", None) == _DB:
        try:
            conn.execute("SELECT 1")          # 健康检查：连接可能被外部 close
            return conn
        except sqlite3.Error:
            try:
                conn.close()
            except sqlite3.Error:
                pass
    elif conn is not None:
        # 数据库路径已变化（如测试 monkeypatch），关闭旧连接
        try:
            conn.close()
        except sqlite3.Error:
            pass

    os.makedirs(config.CONFIG_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _local.conn = conn
    _local.db = _DB
    return conn


def _init_db(conn: sqlite3.Connection):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        " id TEXT PRIMARY KEY,"
        " title TEXT NOT NULL,"
        " created REAL NOT NULL,"
        " updated REAL NOT NULL,"
        " workspace TEXT DEFAULT '',"
        " messages TEXT NOT NULL)")
    # 加速按目录过滤 / 按更新时间排序 / 全局倒序列表
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_workspace_updated"
        " ON sessions(workspace, updated)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_updated"
        " ON sessions(updated)")


def _migrate_legacy(conn: sqlite3.Connection):
    """把旧的 sessions/*.json 一次性导入 SQLite（已存在记录不覆盖）。"""
    global _migrated_for
    if _migrated_for == _LEGACY_DIR:
        return
    try:
        names = os.listdir(_LEGACY_DIR)
    except OSError:
        _migrated_for = _LEGACY_DIR    # 目录不存在：无需反复探测
        return
    for name in names:
        if not name.endswith(".json"):
            continue
        sid = name[:-5]
        try:
            with open(os.path.join(_LEGACY_DIR, name), "r", encoding="utf-8") as f:
                d = json.load(f)
            messages = d.get("messages") or []
            _upsert(conn, sid, d.get("title", "（无标题）"), messages,
                    created=d.get("created"), updated=d.get("updated"),
                    workspace=d.get("workspace", ""), overwrite_if_newer=False,
                    notes=d.get("notes") or [])
        except (json.JSONDecodeError, OSError):
            continue
    _migrated_for = _LEGACY_DIR


def _upsert(conn: sqlite3.Connection, sid: str, title: str, messages: list,
            created: float | None = None, updated: float | None = None,
            workspace: str = "", overwrite_if_newer: bool = True,
            notes: list | None = None):
    """插入或更新一条会话；overwrite_if_newer=False 时仅当新数据更新才覆盖。

    created/updated 缺省用当前时间；显式传入时（如旧 JSON 迁移）保留原始时间戳。
    """
    now = time.time()
    created = created if created is not None else now
    updated = updated if updated is not None else now
    payload = json.dumps({"messages": messages, "notes": notes or []},
                         ensure_ascii=False)

    row = conn.execute(
        "SELECT created, updated, workspace FROM sessions WHERE id=?",
        (sid,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO sessions (id, title, created, updated, workspace, messages)"
            " VALUES (?,?,?,?,?,?)",
            (sid, title, created, updated, workspace, payload))
        return

    _old_created, old_updated, old_ws = row
    if overwrite_if_newer or updated > old_updated:
        # 未传 workspace（空串）时保留原工作目录，便于会话目录过滤不丢
        if not workspace:
            workspace = old_ws or ""
        # 保证 updated 单调不减（避免时钟回拨导致排序错乱）
        new_updated = max(updated, old_updated)
        conn.execute(
            "UPDATE sessions SET title=?, updated=?, workspace=?, messages=?"
            " WHERE id=?",
            (title, new_updated, workspace, payload, sid))


@contextmanager
def _tx():
    """统一的事务上下文：取锁、建库/迁移、提交或回滚。连接复用不关闭。"""
    with _lock:
        conn = _connect()
        try:
            _init_db(conn)
            _migrate_legacy(conn)
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def make_title(text: str) -> str:
    """从首条用户消息生成会话标题。"""
    t = " ".join(text.split())          # 压掉换行和多余空格
    return (t[:24] + "…") if len(t) > 24 else (t or "新会话")


def save(session_id: str, messages: list, title: str, workspace: str = "",
         notes: list | None = None):
    """保存（或创建）会话。workspace 记录工作目录（按目录过滤用）。

    notes: 可选，随会话持久化但不发给模型的批注列表（如识图切模型记录）。
    """
    messages = messages or []
    with _tx() as conn:
        _upsert(conn, session_id, title, messages, workspace=workspace,
                notes=notes)


def load(session_id: str):
    """读会话（优先 SQLite，缺失则回退旧 JSON）。不存在/损坏返回 None。"""
    with _tx() as conn:
        row = conn.execute(
            "SELECT title, created, updated, workspace, messages"
            " FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row is not None:
        title, created, updated, workspace, msg_json = row
        try:
            data = json.loads(msg_json)
        except json.JSONDecodeError:
            data = None
        # 兼容新格式（dict: messages+notes）与旧格式（list: 纯 messages）
        if isinstance(data, dict):
            messages, notes = data.get("messages"), data.get("notes") or []
        else:
            messages, notes = data, []
        if isinstance(messages, list):
            return {"id": session_id, "title": title, "created": created,
                    "updated": updated, "workspace": workspace or "",
                    "messages": messages, "notes": notes}
    # 回退：读旧 JSON 文件（尚未迁移时兜底）
    p = os.path.join(_LEGACY_DIR, f"{session_id}.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("messages"), list):
            data.setdefault("notes", [])
            data.setdefault("id", session_id)
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def delete(session_id: str) -> bool:
    """删除会话记录。"""
    with _tx() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        deleted = cur.rowcount > 0
    # 同时清理旧 JSON 文件（如有）
    try:
        os.remove(os.path.join(_LEGACY_DIR, f"{session_id}.json"))
    except OSError:
        pass
    return deleted


def rename(session_id: str, title: str) -> bool:
    """改会话标题。只更新 title，不刷新 updated（不扰动最近列表排序）。

    SQLite 无此记录时回退旧 JSON：读出后整体落库（保留原时间戳）再改标题。
    """
    title = (title or "").strip()
    if not title:
        return False
    with _tx() as conn:
        cur = conn.execute("UPDATE sessions SET title=? WHERE id=?",
                           (title, session_id))
        ok = cur.rowcount > 0
    if not ok:
        data = load(session_id)
        if data is None:
            return False
        with _tx() as conn:
            _upsert(conn, session_id, title, data["messages"],
                    created=data.get("created"), updated=data.get("updated"),
                    workspace=data.get("workspace", ""),
                    notes=data.get("notes"))
    return True


def list_sessions(limit: int = 20, workspace: str | None = None,
                  query: str = "") -> list[dict]:
    """最近会话列表（按更新时间倒序）。

    workspace: 给定则只返回该目录创建的会话（None = 全部）
    query:     标题/内容关键词过滤（跨项目搜索）
    返回 [{id, title, updated, workspace}]
    """
    # 不 SELECT messages：仅当需要 query 过滤时才在 WHERE 里引用该列，
    # 避免每次列表/菜单刷新都拉取全部会话正文。
    sql = "SELECT id, title, updated, workspace FROM sessions"
    conds, params = [], []
    if workspace is not None:
        conds.append("workspace=?")
        params.append(workspace)
    if query:
        q = query.lower()
        conds.append("(lower(title) LIKE ? OR lower(messages) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY updated DESC LIMIT ?"
    params.append(int(limit))

    with _tx() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [{"id": sid, "title": title, "updated": updated,
             "workspace": ws or ""} for sid, title, updated, ws in rows]
