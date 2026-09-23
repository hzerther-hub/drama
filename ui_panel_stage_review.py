# -*- coding: utf-8 -*-
"""小说阶段产物编辑面板（嵌入聊天区样式，与 _make_approval_bar 同款）。

设计：仿 _make_approval_bar —— 嵌入 chat 区的横条、顶部标题 + 按钮组 +
产物摘要（只读，最多 8 行）+ 意见输入框。不用 Toplevel，不破坏用户既有的
阅读节奏（聊天区往上滚看到产物，向下看按钮）。

按钮：
  - 「确认」：锁定当前产物，pipeline 继续。
  - 「重新生成」：删除产物，调 _novel_ok 重跑当前阶段。
  - 「按意见重试」：保留原产物作参照，调 _novel_adjust 重写（与 /novel adjust 等价）。
  - 「下一阶段配置」：调起中央配置面板，让用户在放行前调 novel_config。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext

import novel_chain
import theme
from i18n import t as _t


def _enable_text_copy(text):
    """让只读 Text 仍可 ⌘/Ctrl+C 复制。"""
    def _copy():
        try:
            sel = text.tag_ranges("sel")
            if sel:
                content = text.get(*sel)
            else:
                content = text.get("1.0", "end").rstrip("\n")
            text.clipboard_clear()
            text.clipboard_append(content)
        except Exception:                # noqa: BLE001
            pass
    text.bind("<Control-c>", lambda _e: _copy())
    text.bind("<Command-c>", lambda _e: _copy())


def show(app, parent, p, stage: str, on_action=None) -> dict:
    """内嵌阶段产物审批条；用户点按钮 → 调 on_action(action, value, feedback)。

    - 不弹独立窗口、不阻塞用户阅读
    - 嵌入 chat 区（stat_frame 下方），与权限审批条同款样式
    - 用户点按钮 / 输入回车 / Esc 后立即销毁并回调 on_action
    """
    import ui

    state = p.state
    key = novel_chain.STAGE_STATE_KEYS.get(stage)
    if not key:
        return {"action": "cancel"}
    content = state.get(key, "") or ""
    label = novel_chain.STAGE_LABELS.get(stage, stage)
    closed = [False]

    bar = tk.Frame(parent, bg=theme.PANEL,
                   highlightthickness=1, highlightbackground=theme.ACCENT)
    head = tk.Frame(bar, bg=theme.PANEL)
    head.pack(fill="x", padx=10, pady=(6, 2))

    def _btn(text, bg, fg, hbg, cmd, **kw):
        """细长按钮：padx=8, pady=2, 字号 9。"""
        b = tk.Button(head, text=text, command=cmd, bd=0,
                      relief="flat", cursor="hand2", padx=8, pady=2,
                      font=(ui.FONT_UI, 9), bg=bg, fg=fg,
                      activebackground=hbg, highlightthickness=0, **kw)
        b.bind("<Enter>", lambda _e: b.config(bg=hbg))
        b.bind("<Leave>", lambda _e: b.config(bg=bg))
        return b

    def _trigger(action, value=content, feedback=""):
        if closed[0]:
            return
        closed[0] = True
        try:
            bar.destroy()
        except tk.TclError:
            pass
        if on_action:
            on_action(action, value, feedback)

    # 标题 + 4 个动作按钮（语义用颜色区分）
    tk.Label(head, text="📝 " + _t("sr.bar_title",
                                    stage=label, t=p.title or '（无标题）'),
             font=(ui.FONT_UI, 10, "bold"), fg=theme.TEXT, bg=theme.PANEL
             ).pack(side="left")

    # [确认] → 推进流水线（绿色强调，确认即走）
    _btn("✓ 确认", "#10b981", "#ffffff", "#059669",
         lambda: _trigger("ok")).pack(side="right", padx=(4, 0))
    # [下一阶段配置] → 调配置（灰色低频）
    _btn("⚙ 配置", theme.BG, theme.MUTED, theme.BORDER,
         lambda: _trigger("config")).pack(side="right", padx=4)
    # [按意见重试] → 重做该阶段（accent 蓝色，提示需要文字输入）
    _btn("✎ 按意见", theme.ACCENT, "#ffffff", "#1d4ed8",
         lambda: _trigger("adjust", content,
                          fb_text.get("1.0", "end").rstrip("\n"))).pack(side="right", padx=4)
    # [重新生成] → 删产物重跑（红色警示，会丢当前产物）
    _btn("↻ 重生成", "#fee2e2", "#b91c1c", "#fecaca",
         lambda: _trigger("regen")).pack(side="right", padx=4)

    # 产物摘要（只读，最多 8 行，可滚动/复制）
    lines = content.count("\n") + 1
    box = scrolledtext.ScrolledText(
        bar, wrap="word", font=(ui.FONT_UI, 9),
        height=max(3, min(8, lines)),
        relief="flat", borderwidth=0,
        background=theme.PANEL, foreground=theme.TEXT,
        highlightthickness=1, highlightbackground=theme.BORDER)
    preview = content[:4000] + ("\n...（已截断，全文用 /novel ledger 或文件浏览器查看）"
                                if len(content) > 4000 else "")
    box.insert("1.0", preview)
    box.config(state="disabled")
    _enable_text_copy(box)
    box.pack(fill="x", padx=10, pady=(0, 6))

    # 意见输入行 —— 加高到 3 行 + 明显边框，让用户能看见
    fb_box = tk.LabelFrame(bar, text="💬 你的修改意见（按 Cmd/Ctrl+Enter 提交）",
                           bg=theme.PANEL, fg=theme.TEXT,
                           font=(ui.FONT_UI, 9, "bold"),
                           padx=6, pady=4)
    fb_box.pack(fill="x", padx=10, pady=(0, 6))
    fb_text = tk.Text(fb_box, height=3, font=(ui.FONT_UI, 9), wrap="word",
                      relief="flat", borderwidth=1,
                      background="white", foreground=theme.TEXT,
                      highlightthickness=2,
                      highlightbackground=theme.ACCENT,
                      insertwidth=2)
    fb_text.pack(fill="x", padx=2, pady=2)
    # placeholder 提示
    fb_text.insert("1.0", "例如：节奏太快，请扩写到 2000 字；人物性格 OOC…")
    fb_text.config(fg=theme.MUTED)

    def _on_focus_in(_e):
        if fb_text.get("1.0", "end").strip().startswith("例如："):
            fb_text.delete("1.0", "end")
            fb_text.config(fg=theme.TEXT)

    def _on_focus_out(_e):
        if not fb_text.get("1.0", "end").strip():
            fb_text.insert("1.0", "例如：节奏太快，请扩写到 2000 字；人物性格 OOC…")
            fb_text.config(fg=theme.MUTED)

    fb_text.bind("<FocusIn>", _on_focus_in)
    fb_text.bind("<FocusOut>", _on_focus_out)

    # 键盘：Cmd/Ctrl+Enter 触发「按意见重试」
    def _ctrl_enter(_e):
        _finish_with_value("adjust")
        return "break"
    fb_text.bind("<Control-Return>", _ctrl_enter)
    fb_text.bind("<Command-Return>", _ctrl_enter)

    bar.pack(fill="x", padx=16, pady=(0, 4), after=app.stat_frame)
    return result