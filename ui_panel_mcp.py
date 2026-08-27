# -*- coding: utf-8 -*-
"""MCP 服务器管理面板：列表 + 添加/删除 + 启用/只读开关 + 重连。

从 ui.py 拆分而来；入口 show(app)，app 为 ui.App 实例。
"""

from __future__ import annotations
import json as _json
import threading
import tkinter as tk

import config
import mcp
from i18n import t as _t
import theme


def show(app):
    """MCP 服务器管理窗口：列表 + 添加/删除 + 启用/只读开关 + 重连。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    _flat_button = ui._flat_button

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("mcp.title"))
    win.geometry("640x520")
    ui._make_modal(win, app.root)

    listbox = tk.Listbox(win, font=(FONT_MONO, 10),
               bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0, selectbackground=theme.ACCENT_SOFT, selectforeground=theme.TEXT, activestyle="dotbox")
    listbox.pack(fill="both", expand=True, padx=12, pady=(12, 6))

    state = {"data": None}

    def _servers() -> dict:
        return state["data"].get("servers") or {}

    def _reload():
        data = config.load_mcp_servers()
        servers = data.get("servers") or {}
        listbox.delete(0, "end")
        mgr = mcp.get_manager()
        for name, cfg in servers.items():
            flags = [_t("mcp.enabled" if cfg.get("enabled", True) else "mcp.disabled"),
                     _t("mcp.readonly" if cfg.get("readonly") else "mcp.writable")]
            st = mgr.status.get(name, "")
            url = cfg.get("url", "")
            if url:
                transport = url[:40]
            else:
                transport = " ".join([cfg.get("command", "")]
                                     + (cfg.get("args") or []))
            listbox.insert(
                "end", f"{name}［{'/'.join(flags)}］ {transport[:44]}"
                       + (f"  → {st[:40]}" if st else ""))
        return data

    state["data"] = _reload()

    form = tk.Frame(win)
    form.pack(fill="x", padx=12)
    entries = {}
    for row, (key, label, w) in enumerate([
            ("name", _t("mcp.col.name"), 10),
            ("command", _t("mcp.col.command"), 20),
            ("url", _t("mcp.col.url"), 26),
            ("headers", _t("mcp.col.headers"), 24),
            ("args", _t("mcp.col.args"), 22)]):
        tk.Label(form, text=label, font=(FONT_UI, 9)).grid(
            row=row, column=0, sticky="w", pady=2)
        e = tk.Entry(form, font=(FONT_MONO, 10), width=w)
        e.grid(row=row, column=1, sticky="we", pady=2, padx=(6, 0))
        entries[key] = e

    def _selected():
        sel = listbox.curselection()
        names = list(_servers())
        return names[sel[0]] if sel and sel[0] < len(names) else None

    def _set_entry(key, value):
        entries[key].delete(0, "end")
        entries[key].insert(0, value)

    def _load_form():
        name = _selected()
        if not name:
            return
        cfg = state["data"]["servers"][name]
        _set_entry("name", name)
        _set_entry("command", cfg.get("command", ""))
        _set_entry("url", cfg.get("url", ""))
        _set_entry("headers", _json.dumps(cfg.get("headers") or {},
                                           ensure_ascii=False))
        _set_entry("args", _json.dumps(cfg.get("args") or [],
                                       ensure_ascii=False))

    def _save_server():
        name = entries["name"].get().strip()
        command = entries["command"].get().strip()
        url = entries["url"].get().strip()
        if not name:
            app._set_status(_t("mcp.name_req"))
            return
        if not command and not url:
            app._set_status(_t("mcp.cmd_req"))
            return
        try:
            args = _json.loads(entries["args"].get().strip() or "[]")
            headers = _json.loads(entries["headers"].get().strip() or "{}")
        except _json.JSONDecodeError:
            app._set_status(_t("mcp.json_req"))
            return
        if not isinstance(args, list) or not isinstance(headers, dict):
            app._set_status(_t("mcp.json_req"))
            return
        servers = state["data"].setdefault("servers", {})
        old_name = _selected()
        old = servers.get(old_name, {}) if old_name else {}
        # 基于旧配置合并，保留 env / cwd 等未在表单里编辑的字段
        cfg = dict(old)
        cfg.update({"command": command, "args": args})
        cfg.setdefault("enabled", True)
        cfg.setdefault("readonly", False)
        if url:
            cfg["url"] = url
            if headers:
                cfg["headers"] = headers
            else:
                cfg.pop("headers", None)
        else:
            cfg.pop("url", None)       # 清空 URL 时一并清掉旧的远程配置
            cfg.pop("headers", None)
        # 改名：移除旧条目，避免残留孤儿配置
        if old_name and old_name != name:
            servers.pop(old_name, None)
        servers[name] = cfg
        config.save_mcp_servers(state["data"])
        state["data"] = _reload()
        app._set_status(_t("mcp.saved", name=name))

    def _delete():
        name = _selected()
        if not name:
            return
        del state["data"]["servers"][name]
        config.save_mcp_servers(state["data"])
        state["data"] = _reload()
        app._set_status(_t("mcp.deleted", name=name))

    def _toggle(key):
        name = _selected()
        if not name:
            return
        cfg = state["data"]["servers"][name]
        # enabled 缺省 True、readonly 缺省 False
        cfg[key] = not cfg.get(key, key == "enabled")
        config.save_mcp_servers(state["data"])
        state["data"] = _reload()

    def _reconnect():
        def worker():
            mcp.get_manager().stop_all()
            mcp.reset_manager()
            mgr = mcp.get_manager()
            ok = mgr.connect(on_log=lambda m: app._set_status(m))
            app._set_status(
                _t("mcp.reconn", n=len(mgr.tool_map))
                + ("" if ok else _t("mcp.reconn_none")))

            def _apply():
                try:
                    state.update({"data": _reload()})
                except tk.TclError:     # 窗口已关闭
                    pass
            app.root.after(0, _apply)
        threading.Thread(target=worker, daemon=True).start()

    btns = tk.Frame(win)
    btns.pack(fill="x", padx=12, pady=(6, 12))
    for text, cmd in [(_t("mcp.save"), _save_server),
                      (_t("mm.delete"), _delete),
                      (_t("mcp.toggle_en"), lambda: _toggle("enabled")),
                      (_t("mcp.toggle_ro"), lambda: _toggle("readonly")),
                      (_t("mcp.reconnect"), _reconnect)]:
        _flat_button(btns, text=text, command=cmd,
                     font=(FONT_UI, 9)).pack(side="left", padx=(0, 6))
    listbox.bind("<<ListboxSelect>>", lambda e: _load_form())
    tk.Label(win, text=_t("mcp.hint"),
             font=(FONT_UI, 9), fg="#64748b").pack(pady=(0, 8))
