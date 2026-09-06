# -*- coding: utf-8 -*-
"""帮助面板：无边框模态帮助窗口（可拖动、随主窗）。

从 ui.py 拆分而来；入口 show(app)，app 为 ui.App 实例。
"""

from __future__ import annotations
import tkinter as tk
from tkinter import scrolledtext

from i18n import t as _t
import theme


def show(app):
    """帮助窗口（无边框模态：去三按钮，随主窗、可拖动、不至主窗外）。"""
    import ui
    FONT_UI = ui.FONT_UI

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title("")
    try:
        win.overrideredirect(True)     # 无系统标题栏/三按钮
    except Exception:                # noqa: BLE001
        pass
    win.transient(app.root)
    # 居中于主窗口
    win.geometry("620x560")
    win.update_idletasks()
    mw, mh = app.root.winfo_width(), app.root.winfo_height()
    tx, ty = app.root.winfo_rootx(), app.root.winfo_rooty()
    gx = tx + max(0, (mw - 620) // 2)
    gy = ty + max(0, (mh - 560) // 2)
    win.geometry("620x560+%d+%d" % (gx, gy))
    # 无边框 + transient 的窗口容易开在主窗后面（看起来像点击没反应）：
    # 先抬到主窗之上并抢焦点，再模态锁定
    win.update_idletasks()
    win.lift(app.root)
    win.focus_force()
    ui._make_modal(win, app.root)
    # 顶部拖动条
    grip = tk.Frame(win, bg=theme.BORDER, height=26)
    grip.pack(fill="x")
    grip.pack_propagate(False)
    grip.bind("<ButtonPress-1>", lambda e: setattr(app, "_hdrag", (e.x, e.y)))
    grip.bind("<B1-Motion>", lambda e: _drag(app, win, e))
    tk.Label(grip, text="📖 " + _t("help.title"), bg=theme.BORDER, fg=theme.TEXT,
             font=(FONT_UI, 9)).pack(side="left", padx=8)
    xb = tk.Label(grip, text="✕", bg=theme.BORDER, fg=theme.MUTED, cursor="hand2",
                  font=(FONT_UI, 11, "bold"))
    xb.pack(side="right", padx=8)
    xb.bind("<Button-1>", lambda e: win.destroy())

    box = scrolledtext.ScrolledText(win, wrap="word", font=(FONT_UI, 10),
                                    relief="flat", padx=14, pady=12)
    box.insert("1.0", _t("help.text"))
    # 斜杠命令清单：从 app._COMMANDS 动态生成，新增命令自动出现在帮助里
    box.insert("end", "\n\n" + _t("help.cmds_title") + "\n")
    for cmd, dkey, _k in getattr(app, "_COMMANDS", []):
        box.insert("end", "  %s   %s\n" % (cmd, _t(dkey)))
    # 版权 / 开发者信息（GitHub 链接可点击）
    box.insert("end", "\n" + _t("help.copyright_title") + "\n")
    box.insert("end", _t("help.copyright") + "\n")
    repo_url = "https://github.com/hzerther-hub/drama"
    ltag = "cprlink"
    box.tag_config(ltag, foreground="#2563eb", underline=True)
    box.insert("end", repo_url + "\n", ltag)
    box.tag_bind(ltag, "<Button-1>", lambda _e: ui._open_url(repo_url))
    box.tag_bind(ltag, "<Enter>",
                 lambda e: box.config(cursor="hand2"))
    box.tag_bind(ltag, "<Leave>",
                 lambda e: box.config(cursor=""))
    box.config(state="disabled")
    ui._enable_text_copy(box)
    box.pack(fill="both", expand=True, padx=12, pady=(12, 0))

    tk.Button(win, text=_t("btn.close"), command=win.destroy, width=10
              ).pack(pady=12)
    win.bind("<Escape>", lambda e: win.destroy())


def _drag(app, win, e):
    try:
        dx, dy = getattr(app, "_hdrag", (0, 0))
        x = win.winfo_x() + (e.x - dx)
        y = win.winfo_y() + (e.y - dy)
        mw, mh = app.root.winfo_width(), app.root.winfo_height()
        tx, ty = app.root.winfo_rootx(), app.root.winfo_rooty()
        ww, wh = win.winfo_width(), win.winfo_height()
        x = min(max(x, tx - 10), tx + mw - ww + 10)
        y = min(max(y, ty - 10), ty + mh - wh + 10)
        win.geometry("+%d+%d" % (x, y))
    except Exception:                # noqa: BLE001
        pass
