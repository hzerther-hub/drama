# -*- coding: utf-8 -*-
"""会话面板：全局会话搜索 + 全部会话列表。

从 ui.py 拆分而来；入口 show_search(app) / show_all(app)，app 为 ui.App 实例。
"""

from __future__ import annotations
import tkinter as tk

import sessions as sess_mod
from i18n import t as _t
import theme


def show_search(app):
    """全局会话搜索：关键词匹配标题或对话内容。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("sess.search_title"))
    win.geometry("560x420")
    ui._make_modal(win, app.root)

    top = tk.Frame(win)
    top.pack(fill="x", padx=12, pady=(12, 6))
    entry = tk.Entry(top, font=(FONT_MONO, 10))
    entry.pack(side="left", fill="x", expand=True)
    entry.focus_set()
    tk.Button(top, text=_t("sess.btn_search"), width=8).pack(side="left", padx=(8, 0))

    listbox = tk.Listbox(win, font=(FONT_MONO, 10),
               bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0, selectbackground=theme.ACCENT_SOFT, selectforeground=theme.TEXT, activestyle="dotbox")
    listbox.pack(fill="both", expand=True, padx=12)

    def _do_search(_e=None):
        q = entry.get().strip()
        listbox.delete(0, "end")
        if not q:
            return
        import time as _time
        app._search_results = sess_mod.list_sessions(limit=30, query=q)
        for it in app._search_results:
            when = _time.strftime("%m-%d %H:%M", _time.localtime(it["updated"]))
            ws_name = it.get("workspace", "") or _t("sess.unknown_ws")
            listbox.insert("end", f"{it['title'][:24]}  {when}  [{ws_name}]")

    def _open(_e=None):
        sel = listbox.curselection()
        if sel and hasattr(app, "_search_results"):
            it = app._search_results[sel[0]]
            win.destroy()
            app._load_session(it["id"])

    entry.bind("<Return>", _do_search)
    listbox.bind("<Double-Button-1>", _open)
    btn = [w for w in top.winfo_children() if isinstance(w, tk.Button)][0]
    btn.config(command=_do_search)

    def _delete(_e=None):
        """删除搜索列表里选中的某一条会话。"""
        sel = listbox.curselection()
        if not sel or not hasattr(app, "_search_results"):
            return
        it = app._search_results[sel[0]]
        from tkinter import messagebox
        if not messagebox.askyesno(_t("sess.del_title"),
                                   _t("sess.del_confirm", t=it["title"]),
                                   parent=win):
            return
        sess_mod.delete(it["id"])
        app._search_results.pop(sel[0])
        listbox.delete(sel[0])
        app._set_status(_t("sess.deleted"))

    bar = tk.Frame(win)
    bar.pack(fill="x", padx=12, pady=8)
    tk.Button(bar, text=_t("sess.del_btn"), command=_delete, width=16
              ).pack(side="right")

    tk.Label(win, text=_t("sess.search_hint"),
             font=(FONT_UI, 9), fg="#64748b").pack(pady=(0, 10))


def show_all(app):
    """列出全部会话（跨目录）。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("sess.all_title"))
    win.geometry("600x440")
    ui._make_modal(win, app.root)
    items = sess_mod.list_sessions(limit=50)
    listbox = tk.Listbox(win, font=(FONT_MONO, 10),
               bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0, selectbackground=theme.ACCENT_SOFT, selectforeground=theme.TEXT, activestyle="dotbox")
    listbox.pack(fill="both", expand=True, padx=12, pady=12)
    import time as _time
    for it in items:
        when = _time.strftime("%m-%d %H:%M", _time.localtime(it["updated"]))
        ws_name = it.get("workspace", "") or _t("sess.unknown_ws")
        listbox.insert("end", f"{it['title'][:24]}  {when}  [{ws_name}]")
    listbox.focus_set()

    def _open(_e=None):
        sel = listbox.curselection()
        if sel:
            win.destroy()
            app._load_session(items[sel[0]]["id"])

    def _delete(_e=None):
        """删除全部列表里选中的某一条会话。"""
        sel = listbox.curselection()
        if not sel:
            return
        it = items[sel[0]]
        from tkinter import messagebox
        if not messagebox.askyesno(_t("sess.del_title"),
                                   _t("sess.del_confirm", t=it["title"]),
                                   parent=win):
            return
        sess_mod.delete(it["id"])
        items.pop(sel[0])
        listbox.delete(sel[0])
        app._set_status(_t("sess.deleted"))

    bar = tk.Frame(win)
    bar.pack(fill="x", padx=12, pady=8)
    tk.Button(bar, text=_t("sess.del_btn"), command=_delete, width=16
              ).pack(side="right")

    listbox.bind("<Double-Button-1>", _open)
    tk.Label(win, text=_t("sess.all_hint"),
             font=(FONT_UI, 9), fg="#64748b").pack(pady=(0, 10))
