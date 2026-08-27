# -*- coding: utf-8 -*-
"""工具审批面板：ask 模式下可写工具执行前的确认对话框。

从 ui.py 拆分而来；入口 make_dialog(app, name, summary, result, done)。
样式走 theme.py 设计令牌：白底、顶部主题色条、主色「允许」+ 中性「拒绝」。
"""

from __future__ import annotations
import tkinter as tk
from tkinter import scrolledtext

from i18n import t as _t
import theme


def make_dialog(app, name, summary, result, done):
    """创建审批对话框，返回窗口。result/done 由按钮回调写入。

    用 grid 布局：按钮行固定底部，文本框占据剩余空间。
    （不要用 pack+expand 后置按钮栏——按钮会被挤成 0 高度，根本不渲染。）
    """
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    win = tk.Toplevel(app.root)
    win.title(_t("dlg.approve_tool", name=name))
    win.configure(bg=theme.PANEL)
    ui._make_modal(win, app.root)
    win.grid_columnconfigure(0, weight=1)

    # 顶部主题色细条（3px）：与全局扁平风一致的点缀
    tk.Frame(win, bg=theme.ACCENT, height=3).grid(row=0, column=0, sticky="ew")

    tk.Label(win, text=_t("ui.approve_want", name=name),
             font=(FONT_UI, 13, "bold"), fg=theme.TEXT,
             bg=theme.PANEL).grid(row=1, column=0, padx=16, pady=(14, 8))

    box = scrolledtext.ScrolledText(win, wrap="word", font=(FONT_MONO, 10),
                                    width=74, relief="flat", borderwidth=0,
                                    background=theme.PANEL, foreground=theme.TEXT,
                                    highlightthickness=1,
                                    highlightbackground=theme.BORDER)
    box.insert("1.0", summary)
    box.config(state="disabled")
    ui._enable_text_copy(box)
    box.grid(row=2, column=0, sticky="ew", padx=16, pady=8)

    # 高度自适应内容：按等宽字符宽估算换行后的显示行数，夹在 [3, 18] 行；
    # 超出部分文本框内部滚动，短内容不再撑出一大片空白
    def _fit_height():
        box.update_idletasks()
        if not box.winfo_width():
            box.after(50, _fit_height)
            return
        import tkinter.font as tkfont
        cw = max(tkfont.Font(font=box.cget("font")).measure("0"), 1)
        cpl = max(20, (box.winfo_width() - 4) // cw)
        n = sum(max(1, -(-len(ln) // cpl)) for ln in summary.split("\n"))
        box.config(height=max(3, min(n + 1, 18)))
    box.after(60, _fit_height)

    closed = [False]   # 幂等防护：回车/按钮/关窗可能同时触发

    def _finish(approved: bool):
        """写入审批结果并关闭窗口；只生效一次。"""
        if closed[0]:
            return
        closed[0] = True
        result["approved"] = approved
        try:
            win.destroy()
        except tk.TclError:
            pass          # 窗口已被销毁：忽略
        done.set()

    def _btn(parent, text, bg, fg, hover_bg, hover_fg, cmd):
        """扁平操作按钮：主题底色 + 悬停反馈。"""
        b = tk.Button(parent, text=text, command=cmd, width=10, bd=0,
                      relief="flat", cursor="hand2", padx=12, pady=6,
                      font=(FONT_UI, theme.FS_TOOLBAR), bg=bg, fg=fg,
                      activebackground=hover_bg, activeforeground=hover_fg,
                      highlightthickness=0)
        b.bind("<Enter>", lambda _e: b.config(bg=hover_bg, fg=hover_fg))
        b.bind("<Leave>", lambda _e: b.config(bg=bg, fg=fg))
        return b

    bar = tk.Frame(win, bg=theme.PANEL)
    bar.grid(row=3, column=0, pady=(6, 12))
    # 主操作「允许」用主题色实底；「拒绝」中性浅底，主次分明
    allow_btn = _btn(bar, _t("btn.allow"), theme.ACCENT, "#ffffff",
                     "#1d4ed8", "#ffffff", lambda: _finish(True))
    allow_btn.pack(side="left", padx=6)
    deny_btn = _btn(bar, _t("btn.deny"), theme.BG, theme.TEXT,
                    theme.BORDER, theme.TEXT, lambda: _finish(False))
    deny_btn.pack(side="left", padx=6)

    # 键盘快捷：回车=允许，Esc=拒绝（鼠标无法点击时仍有出路）
    win.bind("<Return>", lambda _e: _finish(True))
    win.bind("<Escape>", lambda _e: _finish(False))
    win.protocol("WM_DELETE_WINDOW", lambda: _finish(False))
    # 焦点给「允许」按钮，回车自然触发；若无按钮（被回收）则给窗口
    try:
        allow_btn.focus_set()
    except tk.TclError:
        pass
    return win
