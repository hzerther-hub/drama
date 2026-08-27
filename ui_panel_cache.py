# -*- coding: utf-8 -*-
"""缓存管理面板：后端选择（SQLite / 自动 / 内存）、TTL、条目统计、清空。

从 ui.py 拆分而来；入口 show(app)，app 为 ui.App 实例。
"""

from __future__ import annotations
import tkinter as tk

import cache as cache_mod
from i18n import t as _t
import theme


def show(app):
    import ui  # 延迟导入：读最新字体/共享 helper，避免循环依赖
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.cache"))
    win.geometry("580x360")
    ui._make_modal(win, app.root)

    settings = cache_mod.load_settings()

    tk.Label(win, text=_t("cache.backend"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 4))
    info = tk.Label(win, font=(FONT_MONO, 9), fg="#64748b", anchor="w",
                    justify="left")
    info.pack(anchor="w", padx=16)

    backend_var = tk.StringVar(value=settings.get("backend", "auto"))
    backend_row = tk.Frame(win)
    backend_row.pack(anchor="w", padx=16, pady=4)
    backend_names = {
        "auto": _t("cache.auto"),
        "sqlite": "SQLite",
        "memory": _t("cache.memory"),
    }
    for val in ("auto", "sqlite", "memory"):
        tk.Radiobutton(backend_row, text=backend_names[val], value=val,
                       variable=backend_var, font=(FONT_UI, 10)
                       ).pack(side="left", padx=(0, 10))

    def _refresh_info():
        s = cache_mod.stats()
        info.config(text=_t("cache.info", b=s['backend'],
                            c=s['configured'], n=s.get('entries', '?')))

    _refresh_info()

    # ---- TTL ----
    tk.Label(win, text=_t("cache.ttl"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(10, 2))
    ttl_row = tk.Frame(win)
    ttl_row.pack(anchor="w", padx=16)
    tk.Label(ttl_row, text=_t("cache.llm_ttl"), font=(FONT_UI, 10)).pack(side="left")
    llm_ttl = tk.Entry(ttl_row, width=8, font=(FONT_MONO, 10))
    llm_ttl.pack(side="left", padx=(4, 14))
    llm_ttl.insert(0, str(settings.get("llm_ttl", 3600)))
    tk.Label(ttl_row, text=_t("cache.tool_ttl"), font=(FONT_UI, 10)).pack(side="left")
    tool_ttl = tk.Entry(ttl_row, width=8, font=(FONT_MONO, 10))
    tool_ttl.pack(side="left", padx=(4, 0))
    tool_ttl.insert(0, str(settings.get("tool_ttl", 300)))

    msg = tk.Label(win, font=(FONT_UI, 9), fg="red", anchor="w")
    msg.pack(anchor="w", padx=16, pady=(8, 0))

    # ---- 按钮 ----
    bar = tk.Frame(win)
    bar.pack(side="bottom", pady=12)

    def _clear():
        if cache_mod.clear():
            _refresh_info()
            app._set_status(_t("cache.cleared"))
        else:
            msg.config(text=_t("cache.clear_fail"))

    def _save():
        try:
            cache_mod.save_settings(
                backend=backend_var.get(),
                llm_ttl=int(llm_ttl.get() or 0),
                tool_ttl=int(tool_ttl.get() or 0),
            )
            _refresh_info()
            app._set_status(_t("cache.saved", b=cache_mod.backend_name()))
            msg.config(text="", fg="#16a34a")
        except ValueError:
            msg.config(text=_t("cache.ttl_int"), fg="red")

    ui._flat_button(bar, text=_t("btn.save"), command=_save, width=10).pack(side="left", padx=6)
    ui._flat_button(bar, text=_t("cache.clear"), command=_clear, width=10).pack(side="left", padx=6)
    ui._flat_button(bar, text=_t("btn.close"), command=win.destroy, width=10).pack(side="left", padx=6)
