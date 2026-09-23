# -*- coding: utf-8 -*-
"""小说生产中央配置面板（嵌入聊天区样式，与权限审批条同款）。

设计：与 ui_panel_stage_review 一致 —— 嵌入 chat 区的横条，不弹独立窗口。
默认状态显示概要：总章数/字数/语气/模型 4 行 + 按钮 [编辑全部][恢复默认][取消][保存]。
点 [编辑全部] 展开完整 13 项编辑面板（沿用旧 Toplevel 实现，单独文件内嵌类）。

入口：/novel config —— 弹横条 + 当前 state["novel_config"] 概要。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
import novel_chain
import theme
from i18n import t as _t


def _all_model_labels() -> list[str]:
    """拉所有可用模型 key，用于 4 个模型下拉。空字符串=跟随全局默认。"""
    models, _ = config.load_models()
    return [""] + [m.key for m in models]


def _summary_lines(cfg: dict) -> list[str]:
    """把配置压成 4 行可读概要。"""
    return [
        f"总章数：{cfg['total_chapters']}    每章字数：{cfg['words_per_chapter']}",
        f"语气：{cfg['tone']}    视角：{cfg['pov']}    主角：{cfg['mc_gender']}/{cfg['mc_age']}",
        f"配角数：{cfg['side_chars']}    自动修：{'开' if cfg['auto_adjust'] else '关'}    "
        f"允许重做：{'开' if cfg['allow_rework'] else '关'}",
        f"默认模型：{cfg['model_default'] or '（用全局 default）'}    "
        f"规划：{cfg['model_planner'] or '—'}    写作：{cfg['model_writer'] or '—'}    "
        f"审校：{cfg['model_reviewer'] or '—'}",
    ]


def show(app, parent, p=None, on_saved=None) -> bool:
    """中央配置面板（嵌入聊天区样式）。

    返回 True=保存了，False=取消/未改。
    on_saved: 保存后回调（可选）。
    """
    import ui

    if p is None:
        p, _ = app._novel_pick("")
    if p is None:
        app._append("⚠ 还没有书，无法编辑配置（先 /novel start <灵感>）\n",
                     "denied")
        return False
    state = p.state
    cfg = novel_chain.get_novel_config(state)
    models = _all_model_labels()
    closed = [False]

    bar = tk.Frame(parent, bg=theme.PANEL,
                   highlightthickness=1, highlightbackground=theme.ACCENT)
    head = tk.Frame(bar, bg=theme.PANEL)
    head.pack(fill="x", padx=10, pady=(6, 2))

    def _btn(text, bg, fg, hbg, cmd, side="right"):
        b = tk.Button(head, text=text, command=cmd, bd=0,
                      relief="flat", cursor="hand2", padx=8, pady=2,
                      font=(ui.FONT_UI, 9), bg=bg, fg=fg,
                      activebackground=hbg, highlightthickness=0)
        b.bind("<Enter>", lambda _e: b.config(bg=hbg))
        b.bind("<Leave>", lambda _e: b.config(bg=bg))
        b.pack(side=side, padx=(4, 0) if side == "right" else 0)
        return b

    def _destroy():
        if closed[0]:
            return
        closed[0] = True
        try:
            bar.destroy()
        except tk.TclError:
            pass

    # 标题
    tk.Label(head,
             text=f"📖 《{p.title or '（无标题）'}》配置（{p.pid}）",
             font=(ui.FONT_UI, 9, "bold"), fg=theme.TEXT, bg=theme.PANEL
             ).pack(side="left")

    # 概要行
    box = tk.Frame(bar, bg=theme.PANEL)
    box.pack(fill="x", padx=10, pady=(0, 6))
    for line in _summary_lines(cfg):
        tk.Label(box, text="  " + line, font=(ui.FONT_MONO, 9),
                 fg=theme.TEXT, bg=theme.PANEL, anchor="w"
                 ).pack(fill="x")

    # 按钮组
    bar_btn = tk.Frame(bar, bg=theme.PANEL)
    bar_btn.pack(fill="x", padx=10, pady=(0, 8))

    def _open_editor():
        """展开全部 13 项编辑器（嵌入聊天区、Canvas 可滚动、可最大化）。"""
        nonlocal closed
        # 标记当前摘要横条已销毁
        closed[0] = True
        try:
            bar.destroy()
        except tk.TclError:
            pass
        _open_full_editor(app, p, cfg, models, on_saved=on_saved)

    def _save_current():
        # 概要模式下没有改动可写 —— 仅作为「确认」按钮的语义
        _destroy()
        app._append(f"✅ 《{p.title or '（无标题）'}》配置已确认\n", "meta")
        app._set_status("配置已确认")

    def _reset_defaults():
        for k, v in novel_chain._DEFAULT_NOVEL_CONFIG.items():
            cfg[k] = v
        novel_chain.set_novel_config(state, **cfg)
        try:
            p.save()
        except Exception:                # noqa: BLE001
            pass
        app._append("🔄 已恢复默认配置\n", "meta")
        _destroy()
        # 重开一条让用户看到默认概要
        show(app, parent, p, on_saved=on_saved)

    def _cancel():
        _destroy()

    # 右排按钮顺序（pack 从右到左）：[保存] → [取消] → [恢复默认] → [编辑全部]
    # 即：保存 在最右，编辑全部 最左（紧贴概要区右侧），保持从右到左的可预期顺序
    _btn("编辑全部…", theme.ACCENT, "#ffffff", "#1d4ed8", _open_editor,
         side="right")
    _btn("恢复默认", theme.BG, theme.TEXT, theme.BORDER, _reset_defaults,
         side="right")
    _btn("取消", theme.BG, theme.TEXT, theme.BORDER, _cancel, side="right")
    _btn("保存", theme.ACCENT, "#ffffff", "#1d4ed8",
         _save_current, side="right")

    bar.pack(fill="x", padx=16, pady=(0, 4), after=app.stat_frame)
    return True


def _open_full_editor(app, p, cfg, models, on_saved=None):
    """展开式 13 项编辑器（嵌入聊天区，Canvas+Scrollbar 滚动，可最大化）。

    不弹独立 Toplevel —— 用户可在 chat 区看完所有字段。
    [⛶ 最大化] 按钮把面板填满 chat 区宽度，[↩ 默认宽] 恢复紧凑。
    """
    import ui

    state = p.state
    closed = [False]
    is_max = [False]                                  # 状态：是否最大化

    # ====== 外层容器（panel）======
    panel = tk.Frame(app.center, bg=theme.PANEL,
                     highlightthickness=1,
                     highlightbackground=theme.ACCENT)
    head = tk.Frame(panel, bg=theme.PANEL)
    head.pack(fill="x", padx=10, pady=(6, 2))
    title_lbl = tk.Label(
        head,
        text=f"📖 《{p.title or '（无标题）'}》配置 · 全部（可滚动）",
        font=(ui.FONT_UI, 10, "bold"), fg=theme.TEXT, bg=theme.PANEL)
    title_lbl.pack(side="left")

    def _btn(text, bg, fg, hbg, cmd, side="right"):
        b = tk.Button(head, text=text, command=cmd, width=8, bd=0,
                      relief="flat", cursor="hand2", padx=10, pady=3,
                      font=(ui.FONT_UI, theme.FS_TOOLBAR), bg=bg, fg=fg,
                      activebackground=hbg, highlightthickness=0)
        b.bind("<Enter>", lambda _e: b.config(bg=hbg))
        b.bind("<Leave>", lambda _e: b.config(bg=bg))
        b.pack(side=side, padx=(6, 0))
        return b

    # ====== Canvas + Scrollbar 容器（让 13 项可滚动）======
    canvas_holder = tk.Frame(panel, bg=theme.PANEL)
    canvas_holder.pack(fill="both", expand=True, padx=10, pady=(0, 6))
    canvas = tk.Canvas(canvas_holder, bg=theme.PANEL,
                       highlightthickness=0, height=420)
    scroll = tk.Scrollbar(canvas_holder, orient="vertical",
                          command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    body = tk.Frame(canvas, bg=theme.PANEL)
    win_id = canvas.create_window((0, 0), window=body, anchor="nw")

    def _on_resize(event):
        # 跟着 canvas 宽度调整 body（最大化时撑满）
        canvas.itemconfigure(win_id, width=event.width)
    canvas.bind("<Configure>", _on_resize)

    def _on_frame_config(_e):
        # 跟着 body 自身大小调整滚动区
        canvas.configure(scrollregion=canvas.bbox("all"))
    body.bind("<Configure>", _on_frame_config)

    # 鼠标滚轮支持
    def _on_wheel(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
    canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_wheel))
    canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

    def section(parent_, title):
        f = tk.LabelFrame(parent_, text=title, bg=theme.PANEL,
                          font=(ui.FONT_UI, 10, "bold"), fg=theme.TEXT)
        f.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        return f

    # ====== 字段填充（与原 Toplevel 一致）======
    f1 = section(body, "基础")
    vars_basic = {}
    row = 0
    tk.Label(f1, text="总章数", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=row, column=0, sticky="w", padx=6, pady=4)
    v = tk.IntVar(value=cfg["total_chapters"])
    tk.Spinbox(f1, from_=3, to=novel_chain._MAX_CHAPTERS, textvariable=v,
               width=6, font=(ui.FONT_UI, 10)).grid(row=row, column=1, sticky="w")
    vars_basic["total_chapters"] = v
    row += 1
    tk.Label(f1, text="每章字数", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=row, column=0, sticky="w", padx=6, pady=4)
    v = tk.IntVar(value=cfg["words_per_chapter"])
    tk.Spinbox(f1, from_=800, to=8000, increment=200, textvariable=v,
               width=6, font=(ui.FONT_UI, 10)).grid(row=row, column=1, sticky="w")
    vars_basic["words_per_chapter"] = v
    row += 1
    tk.Label(f1, text="配角数", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=row, column=0, sticky="w", padx=6, pady=4)
    v = tk.IntVar(value=cfg["side_chars"])
    tk.Spinbox(f1, from_=2, to=5, textvariable=v, width=6,
               font=(ui.FONT_UI, 10)).grid(row=row, column=1, sticky="w")
    vars_basic["side_chars"] = v
    row += 1
    v = tk.BooleanVar(value=cfg["auto_adjust"])
    tk.Checkbutton(f1, text="审校问题自动修复一次", variable=v,
                   bg=theme.PANEL, font=(ui.FONT_UI, 9)
                   ).grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    vars_basic["auto_adjust"] = v
    row += 1
    v = tk.BooleanVar(value=cfg["allow_rework"])
    tk.Checkbutton(f1, text="允许 /novel polish/expand/condense",
                   variable=v, bg=theme.PANEL, font=(ui.FONT_UI, 9)
                   ).grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=2)
    vars_basic["allow_rework"] = v

    f2 = section(body, "风格")
    tk.Label(f2, text="语气", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=0, column=0, sticky="w", padx=6, pady=4)
    tone_var = tk.StringVar(value=cfg["tone"])
    ttk.Combobox(f2, textvariable=tone_var, width=18,
                 values=["neutral", "sweet", "angsty", "dark",
                         "comedic", "epic"], state="readonly",
                 font=(ui.FONT_UI, 9)).grid(row=0, column=1, sticky="w")
    tk.Label(f2, text="视角", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=1, column=0, sticky="w", padx=6, pady=4)
    pov_var = tk.StringVar(value=cfg["pov"])
    ttk.Combobox(f2, textvariable=pov_var, width=18,
                 values=["first", "third_limited", "third_omniscient"],
                 state="readonly", font=(ui.FONT_UI, 9)
                 ).grid(row=1, column=1, sticky="w")
    tk.Label(f2, text="主角性别", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=2, column=0, sticky="w", padx=6, pady=4)
    g_var = tk.StringVar(value=cfg["mc_gender"])
    ttk.Combobox(f2, textvariable=g_var, width=18,
                 values=["any", "male", "female"], state="readonly",
                 font=(ui.FONT_UI, 9)).grid(row=2, column=1, sticky="w")
    tk.Label(f2, text="主角年龄", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=3, column=0, sticky="w", padx=6, pady=4)
    age_var = tk.StringVar(value=cfg["mc_age"])
    ttk.Combobox(f2, textvariable=age_var, width=18,
                 values=["teen", "adult", "middle_aged", "elder"],
                 state="readonly", font=(ui.FONT_UI, 9)
                 ).grid(row=3, column=1, sticky="w")
    tk.Label(f2, text="风格备注", bg=theme.PANEL, font=(ui.FONT_UI, 9)
             ).grid(row=4, column=0, sticky="nw", padx=6, pady=4)
    notes_var = tk.StringVar(value=cfg["style_notes"])
    tk.Entry(f2, textvariable=notes_var, font=(ui.FONT_UI, 9),
             width=30).grid(row=4, column=1, sticky="we", padx=6, pady=4)

    f3 = section(body, "模型（空=全局默认）")
    model_vars = {}
    role_labels = [("model_default", "默认/全部"),
                   ("model_planner", "规划阶段"),
                   ("model_writer", "写作章节"),
                   ("model_reviewer", "审校/复盘")]
    for i, (k, label) in enumerate(role_labels):
        tk.Label(f3, text=label, bg=theme.PANEL, font=(ui.FONT_UI, 9)
                 ).grid(row=i, column=0, sticky="w", padx=6, pady=4)
        v = tk.StringVar(value=cfg.get(k, ""))
        ttk.Combobox(f3, textvariable=v, width=30, values=models,
                     font=(ui.FONT_UI, 9)).grid(row=i, column=1, sticky="we",
                                                  padx=6, pady=4)
        model_vars[k] = v

    picked = {"ok": False, "cfg": None}

    def _destroy():
        if closed[0]:
            return
        closed[0] = True
        try:
            canvas.unbind_all("<MouseWheel>")
            panel.destroy()
        except tk.TclError:
            pass

    def _ok():
        try:
            t = int(vars_basic["total_chapters"].get())
            if not (3 <= t <= novel_chain._MAX_CHAPTERS):
                raise ValueError(f"总章数需在 3~{novel_chain._MAX_CHAPTERS}")
        except (tk.TclError, ValueError) as e:
            from tkinter import messagebox
            messagebox.showerror("参数错", str(e), parent=app.root)
            return
        picked["cfg"] = {
            "total_chapters": t,
            "words_per_chapter": int(vars_basic["words_per_chapter"].get()),
            "side_chars": int(vars_basic["side_chars"].get()),
            "auto_adjust": bool(vars_basic["auto_adjust"].get()),
            "allow_rework": bool(vars_basic["allow_rework"].get()),
            "tone": tone_var.get(),
            "pov": pov_var.get(),
            "mc_gender": g_var.get(),
            "mc_age": age_var.get(),
            "style_notes": notes_var.get().strip(),
            **{k: v.get().strip() for k, v in model_vars.items()},
        }
        picked["ok"] = True
        _destroy()
        # 保存
        new_cfg = picked["cfg"]
        novel_chain.set_novel_config(state, **new_cfg)
        novel_chain.set_novel_config(state, total_chapters=new_cfg["total_chapters"])
        state["total_chapters"] = new_cfg["total_chapters"]
        try:
            p.save()
        except Exception:              # noqa: BLE001
            pass
        app._append(
            f"✅ 配置已保存到 {p.pid}：{len(new_cfg)} 项\n", "meta")
        app._set_status(f"配置已保存 · 总章数 {new_cfg['total_chapters']}")
        if on_saved:
            on_saved(new_cfg)

    def _cancel():
        _destroy()

    def _toggle_max():
        """在「紧凑」和「最大化（撑满 chat 区宽 + 高）」之间切换。"""
        is_max[0] = not is_max[0]
        panel.pack_forget()
        if is_max[0]:
            # 最大化：占满 chat 区可用宽 + 高
            canvas_holder.pack_configure(fill="both", expand=True)
            panel.pack(fill="both", expand=True, padx=16, pady=(0, 4),
                       after=app.stat_frame)
            # 让 canvas 高度自适应（撑到 panel 内部）
            try:
                panel.update_idletasks()
                avail_h = max(280, panel.winfo_height() - 110)
                canvas.config(height=avail_h)
            except Exception:           # noqa: BLE001
                canvas.config(height=520)
            max_btn.config(text="↩ 默认大小")
        else:
            # 紧凑：宽度自然、高度固定 420
            canvas_holder.pack_configure(fill="both", expand=True)
            canvas.config(height=420)
            panel.pack(fill="x", padx=16, pady=(0, 4),
                       after=app.stat_frame)
            max_btn.config(text="⛶ 最大化")

    bar = tk.Frame(panel, bg=theme.PANEL)
    bar.pack(fill="x", padx=10, pady=(0, 8))
    _btn("保存", theme.ACCENT, "#ffffff", "#1d4ed8", _ok, side="right")
    _btn("取消", theme.BG, theme.TEXT, theme.BORDER, _cancel, side="right")
    max_btn = _btn("⛶ 最大化", theme.BG, theme.TEXT, theme.BORDER,
                   _toggle_max, side="right")

    panel.pack(fill="x", padx=16, pady=(0, 4), after=app.stat_frame)