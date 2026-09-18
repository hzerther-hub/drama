# -*- coding: utf-8 -*-
"""首次确认风格：/novel drama * 第一次跑时弹出风格确认窗（Default 高亮）。

设计：每本书弹一次——用户确认（默认/选下/预设）后记 state["drama_style"]
+ state["_ch_style_picked"]=True，下次同书不弹。run 路径检查 picked：
已选则静默；未选则弹窗（模态，block 到用户确认）。
"""

from __future__ import annotations

import json
import os
import re
import tkinter as tk
from tkinter import ttk

import dramavideo
from i18n import t as _t
import theme


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
    """首次/未选时弹出风格确认。返回 True 表示已选（用户已交互）；False=被取消。"""
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

    win = tk.Toplevel(parent)
    win.title(_t("sp.title"))
    win.configure(bg=theme.BG)
    win.geometry("560x340")
    import ui
    ui._make_modal(win, parent)

    tk.Label(win, text=_t("sp.pick_hint"),
             font=(ui.FONT_UI, 10), bg=theme.BG,
             fg=theme.MUTED, wraplength=520, justify="left"
             ).pack(anchor="w", padx=16, pady=(14, 8))

    preset = tk.StringVar(value=cur if cur in presets
                          else (presets[0] if presets else cur))
    box = ttk.Combobox(win, textvariable=preset, width=60,
                       values=(presets + [cur]) if cur not in presets
                       else presets,
                       font=(ui.FONT_UI, 10))
    box.pack(padx=16, fill="x")

    custom = tk.StringVar()
    tk.Entry(win, textvariable=custom, font=(ui.FONT_UI, 10),
             relief="flat", bg="white", fg=theme.TEXT).pack(
        padx=16, pady=(8, 4), fill="x")
    tk.Label(win, text=_t("sp.pick_or_custom"),
             font=(ui.FONT_UI, 8), bg=theme.BG, fg=theme.MUTED
             ).pack(anchor="w", padx=16)

    def _ok():
        v = (custom.get() or preset.get() or cur).strip()
        if not v:
            return
        picked["ok"] = True
        picked["value"] = v
        win.destroy()

    def _skip():
        # 「用 Default」也视为确认，记下来后下次不再弹
        picked["ok"] = True
        picked["value"] = cur
        win.destroy()

    bar = tk.Frame(win, bg=theme.BG)
    bar.pack(pady=14)
    ui._flat_button(bar, text=_t("sp.use_default"), width=12,
                    font=(ui.FONT_UI, 10), command=_skip).pack(side="left", padx=6)
    ui._flat_button(bar, text=_t("btn.save"), width=12,
                    font=(ui.FONT_UI, 10), command=_ok).pack(side="left", padx=6)

    parent.wait_window(win)
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