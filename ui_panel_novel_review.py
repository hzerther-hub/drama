# -*- coding: utf-8 -*-
"""小说流水线阶段审阅 modal：在 pipeline_paused 时弹出。

设计：
- 模块级函数 show(app, parent, *, stage_name, state_text, on_choice)，无 class。
- 窗体只读展示当前阶段产物 + 三按钮：通过 / 调定 / 跳过。
- 通过回调 `on_choice("ok")` / `on_choice("adjust", feedback)` /
  `on_choice("skip")` 把用户选择回传给 App 层（由 App 决定要不要调
  _novel_ok / _novel_adjust）。
- 单例锁：再次调用前先关已存在的同款窗（用 _review_pop 标记，
  避免生命周期失控导致叠加多个 modal）。
- Esc 与 WM_DELETE_WINDOW 都走「跳过」语义：关窗即视为本次不操作。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext

import ui as _ui
import theme

from i18n import t as _t


_REVIEW_POP_ATTR = "_review_pop"   # 在 Toplevel 上标记，便于下次调用前识别清理


def _close_existing(parent):
    """先关闭已开着的同款审阅窗，避免叠加。"""
    for child in list(parent.winfo_children()):
        if isinstance(child, tk.Toplevel) and getattr(child, _REVIEW_POP_ATTR, False):
            try:
                child.destroy()
            except Exception:                       # noqa: BLE001
                pass


def show(app, parent, *, stage_name: str, state_text: str,
         on_choice) -> tk.Toplevel | None:
    """打开阶段审阅窗。

    入参：
      app         App
      parent      通常 app.root
      stage_name  当前阶段的人类标签（如「设定」「世界观」）
      state_text  当前阶段产物文本（已截好 2400 字以内）
      on_choice   函数 (choice: str, feedback: str = "") -> None，
                  choice ∈ {"ok","adjust","skip"}
    返回 Toplevel 句柄（主要用于测试断言）；失败返回 None。
    """
    _close_existing(parent)

    win = tk.Toplevel(parent)
    win.title(_t("novel.review_title", stage=stage_name))
    win.configure(bg=theme.PANEL)
    win.geometry("720x540")
    setattr(win, _REVIEW_POP_ATTR, True)
    # 真正模态：transient + 等可见再 grab（Win 上 grab 在未 map 时静默失败）
    try:
        _ui._make_modal(win, parent)
    except Exception:                           # noqa: BLE001
        win.transient(parent)

    # 顶部说明
    body_font = (_ui.FONT_UI, 10)
    body = tk.Label(
        win,
        text=_t("novel.review_body", stage=stage_name),
        bg=theme.PANEL, fg=theme.TEXT, font=body_font,
        anchor="w", justify="left", padx=14,
    )
    body.pack(fill="x", pady=(14, 8))

    # 中部：只读展示当前阶段产物
    text_frame = tk.Frame(win, bg=theme.PANEL)
    text_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))
    box = scrolledtext.ScrolledText(
        text_frame, wrap="word", font=(_ui.FONT_MONO, 10),
        relief="flat", padx=12, pady=10,
        background=theme.PANEL, foreground=theme.TEXT,
        highlightthickness=1, highlightbackground=theme.BORDER,
    )
    box.insert("1.0", state_text or "(空)")
    box.config(state="disabled")
    box.pack(fill="both", expand=True)

    # 调定区：默认折叠。点「调定」按钮展开输入框
    adjust_frame = tk.Frame(win, bg=theme.PANEL)
    hint = tk.Label(
        adjust_frame, text=_t("novel.review_adjust_hint"),
        bg=theme.PANEL, fg=theme.MUTED, font=(_ui.FONT_UI, 9),
        anchor="w", justify="left",
    )
    feedback_text = tk.Text(
        adjust_frame, height=3, font=(_ui.FONT_UI, 10),
        relief="flat", padx=10, pady=8,
        background=theme.BG, foreground=theme.TEXT,
        highlightthickness=1, highlightbackground=theme.BORDER,
        insertbackground=theme.TEXT,
    )
    submit_btn = _ui._flat_button(
        adjust_frame, text=_t("novel.review_submit"), width=10,
        command=lambda: _fire_adjust(),
    )
    hint.pack(side="top", anchor="w", pady=(0, 4))
    feedback_text.pack(side="top", fill="x")
    submit_btn.pack(side="right", pady=(6, 0))
    adjust_frame.pack_forget()                       # 默认折叠

    def _fire_adjust():
        fb = feedback_text.get("1.0", "end").strip()
        if not fb:
            feedback_text.focus_set()
            return
        try:
            on_choice("adjust", fb)
        finally:
            _safe_close(win)

    # 底部按钮栏
    bar = tk.Frame(win, bg=theme.PANEL)
    bar.pack(fill="x", padx=14, pady=(4, 14))

    def _open_adjust():
        adjust_frame.pack(fill="x", padx=14, pady=(0, 6), before=bar)
        feedback_text.focus_set()
        ok_btn.pack_forget()
        adjust_btn.pack_forget()
        skip_btn.pack_forget()

    def _fire_ok():
        try:
            on_choice("ok")
        finally:
            _safe_close(win)

    def _fire_skip():
        try:
            on_choice("skip")
        finally:
            _safe_close(win)

    ok_btn = _ui._flat_button(
        bar, text=_t("novel.review_ok"), width=10,
        command=_fire_ok,
    )
    adjust_btn = _ui._flat_button(
        bar, text=_t("novel.review_adjust"), width=18,
        command=_open_adjust,
    )
    skip_btn = _ui._flat_button(
        bar, text=_t("novel.review_skip"), width=8,
        command=_fire_skip,
    )
    ok_btn.pack(side="left")
    adjust_btn.pack(side="left", padx=8)
    skip_btn.pack(side="right")

    # 关闭语义：Esc / X / 关窗 → 等同「跳过」
    win.bind("<Escape>", lambda _e: _fire_skip())
    win.protocol("WM_DELETE_WINDOW", _fire_skip)

    return win


def _safe_close(win):
    """destroy + 清掉单例标记。"""
    try:
        setattr(win, _REVIEW_POP_ATTR, False)
        win.destroy()
    except Exception:                           # noqa: BLE001
        pass