# -*- coding: utf-8 -*-
"""首次确认风格：/novel drama * 第一次跑时弹出风格确认窗（嵌入聊天区横条样式）。

设计：每本书弹一次——用户确认（默认/选下/预设）后记 state["drama_style"]
+ state["_ch_style_picked"]=True，下次同书不弹。run 路径检查 picked：
已选则静默；未选则弹横条（嵌在 chat 区，不弹独立 Toplevel）。

横条结构：
┌──────────────────────────────────────────────────────────────────┐
│ 🎬 Drama Style · 《书名》                              [取消] [用默认] [保存]│
│ ──────────────────────────────────────────────────────────────── │
│ 预设: [动漫番剧 ┐                                                          │
│       写实电影 ┤                                                          │
│       水墨动画 ┘  (滚动下拉)                                              │
│ 自定义: [___________________________________________]                    │
└──────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import dramavideo
import theme
from i18n import t as _t


def _globals():
    """统一风格库：没有就播种全部预设（dramavideo.load_style_lib）。"""
    styles, default, data, path = dramavideo.load_style_lib()
    return {"globals": {"drama_styles": styles,
                        "default_drama_style": default}}, path


def _book_state(app):
    import novel_chain
    p = getattr(app, "_novel_pipe", None)
    if p is None:
        p, _ = app._novel_pick("")
    if p is None:
        return None, None
    return p, novel_chain._book_dir(p.state)


def ensure_picked(app, parent) -> bool:
    """首次/未选时弹出风格确认（嵌入横条）。

    返回 True 表示已选（用户已交互）；False=被取消。
    与 Toplevel 路径不同：这里 wait_window 改为在主线程同步等待用户按钮回调；
    控件嵌在 chat 区不挡其他视图。
    """
    import ui
    p, _ = _book_state(app)
    if p is None:
        return False
    state = p.state
    if state.get("_ch_style_picked"):
        return True                       # 本书已确认 → 直接放行

    cur = dramavideo.resolve_style(state)
    glb, cfg_path = _globals()
    presets = [s["text"] for s in (glb.get("globals", {})
                                     .get("drama_styles", []) or [])]

    picked = {"ok": False, "value": cur}
    closed = [False]

    bar = tk.Frame(parent, bg=theme.PANEL,
                   highlightthickness=1, highlightbackground=theme.ACCENT)
    head = tk.Frame(bar, bg=theme.PANEL)
    head.pack(fill="x", padx=10, pady=(6, 2))

    def _btn(text, bg, fg, hbg, cmd, side="right"):
        b = tk.Button(head, text=text, command=cmd, width=8, bd=0,
                      relief="flat", cursor="hand2", padx=10, pady=3,
                      font=(ui.FONT_UI, theme.FS_TOOLBAR), bg=bg, fg=fg,
                      activebackground=hbg, highlightthickness=0)
        b.bind("<Enter>", lambda _e: b.config(bg=hbg))
        b.bind("<Leave>", lambda _e: b.config(bg=bg))
        b.pack(side=side, padx=(6, 0))
        return b

    def _destroy():
        if closed[0]:
            return
        closed[0] = True
        try:
            bar.destroy()
        except tk.TclError:
            pass

    tk.Label(head,
             text=f"🎬 Drama Style · 《{p.title or '（无标题）'}》",
             font=(ui.FONT_UI, 10, "bold"), fg=theme.TEXT, bg=theme.PANEL
             ).pack(side="left")

    body = tk.Frame(bar, bg=theme.PANEL)
    body.pack(fill="x", padx=10, pady=(0, 6))
    tk.Label(body, text=_t("sp.pick_hint"),
             font=(ui.FONT_UI, 9), bg=theme.PANEL, fg=theme.MUTED,
             wraplength=720, justify="left").pack(anchor="w")

    preset_var = tk.StringVar(value=cur if cur in presets
                             else (presets[0] if presets else cur))
    box_values = presets + ([cur] if cur not in presets else [])
    tk.Label(body, text="预设：", bg=theme.PANEL, fg=theme.TEXT,
             font=(ui.FONT_UI, 9)).pack(side="left", padx=(0, 4), pady=(4, 0))
    preset_box = ttk.Combobox(body, textvariable=preset_var, width=60,
                              values=box_values, font=(ui.FONT_UI, 9))
    preset_box.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=(4, 0))

    custom_var = tk.StringVar()
    row2 = tk.Frame(bar, bg=theme.PANEL)
    row2.pack(fill="x", padx=10, pady=(0, 8))
    tk.Label(row2, text="自定义：", bg=theme.PANEL, fg=theme.TEXT,
             font=(ui.FONT_UI, 9)).pack(side="left", padx=(0, 4))
    tk.Entry(row2, textvariable=custom_var, font=(ui.FONT_UI, 9),
             relief="flat", bg="white", fg=theme.TEXT, borderwidth=1,
             highlightthickness=1, highlightbackground=theme.BORDER
             ).pack(side="left", fill="x", expand=True)

    def _ok():
        v = (custom_var.get() or preset_var.get() or cur).strip()
        if not v:
            return
        picked["ok"] = True
        picked["value"] = v
        _destroy()

    def _skip():
        picked["ok"] = True
        picked["value"] = cur
        _destroy()

    def _cancel():
        _destroy()

    bar_btn = tk.Frame(bar, bg=theme.PANEL)
    bar_btn.pack(fill="x", padx=10, pady=(0, 8))
    _btn("保存", theme.ACCENT, "#ffffff", "#1d4ed8", _ok, side="right")
    _btn("用默认", theme.BG, theme.TEXT, theme.BORDER, _skip, side="right")
    _btn("取消", theme.BG, theme.TEXT, theme.BORDER, _cancel, side="right")

    bar.pack(fill="x", padx=16, pady=(0, 4), after=app.stat_frame)
    # 同步等待 —— 与原 Toplevel 行为一致，drama 命令需要用户先选风格
    app.root.wait_window(bar)
    if not picked["ok"]:
        return False

    state["drama_style"] = picked["value"]
    state["_ch_style_picked"] = True
    try:
        p.save()
    except Exception:                  # noqa: BLE001
        pass
    app._set_status(_t("sp.applied_book"))
    return True