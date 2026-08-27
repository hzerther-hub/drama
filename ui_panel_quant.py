# -*- coding: utf-8 -*-
"""策略互转面板（量化产品）：聚宽/PTrade/掘金/QMT 互转 + 校验报告 + QMT 探活。

入口 show(app)，app 为 ui.App 实例（与 ui_panel_cache 等同一模式）。
本节在 v1.5 基础上做 UI 打磨：
  - 扁平化：代码区去立体边框、按钮去浮雕，系统浅色扁平风
  - 语法着色：左右两个代码区复用 ui 的浅色 Python 高亮引擎
  - 模态 + 尺寸 = 主窗口 90%
  - 同平台互转在界面上直接禁掉（源=目标时目标项灰掉并自动避开）
确定性互转在前台即时完成；勾选「LLM 兜底」后遇手写策略会走
llm_parse（RAG），在后台线程跑避免冻 UI。
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
import config as _cfg

from i18n import t as _t
import theme

_PLATFORMS = (("joinquant", "聚宽"), ("ptrade", "PTrade"),
              ("gm", "掘金"), ("qmt", "QMT"))

# 扁平风配色（浅色）
_BG_CODE = "#ffffff"
_BORDER = "#cbd5e1"
_TEXT = "#0f172a"
_SECOND_BG = "#f1f5f9"
_SECOND_FG = "#334155"
_SECOND_ACTIVE = "#e2e8f0"
_SEL_BG = "#dbeafe"
_SEL_FG = "#1d4ed8"
_LOCKED_FG = "#94a3b8"


def show(app):
    import ui  # 延迟导入：读最新字体/模态助手，避免循环依赖
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    from products.quant import qmt
    from products.quant.emitters import emit
    from products.quant.ir import demo_etf_rotation, demo_ma_cross
    from products.quant.parsers import ParseError
    from products.quant.translate import translate

    root = app.root
    win = tk.Toplevel(root)
    win.configure(bg=theme.PANEL)
    win.title(_t("quant.panel.title"))
    # 尺寸 = 主窗口的 90%（未映射时回退屏幕尺寸）
    pw, ph = root.winfo_width(), root.winfo_height()
    if pw <= 1:
        pw = root.winfo_screenwidth()
    if ph <= 1:
        ph = root.winfo_screenheight()
    win.geometry(f"{int(pw * 0.9)}x{int(ph * 0.9)}")
    win.transient(root)

    # ---- 代码区语法高亮（复用 ui 浅色引擎；失败不阻断功能）----
    def _apply_hl(txt):
        txt._lang = "python"
        try:
            app._editor_hl_config(txt)
            txt.tag_configure("def", font=(FONT_MONO, 10, "bold"))
            app._editor_hl_apply(txt)
        except Exception:                     # noqa: BLE001 —— 高亮失败仅降级为纯文本
            pass

    def _code_widget(parent, undo=False):
        box = scrolledtext.ScrolledText(
            parent, wrap="none", undo=undo, font=(FONT_MONO, 10),
            relief="flat", borderwidth=0, padx=12, pady=10,
            highlightthickness=1, highlightbackground=_BORDER,
            highlightcolor=_SEL_FG, bg=_BG_CODE, fg=_TEXT)
        return box

    # ---- 控制行：源/目标平台 + LLM 兜底 ----
    ctrl = tk.Frame(win)
    ctrl.pack(fill="x", padx=16, pady=(14, 6))

    src_var = tk.StringVar(value="joinquant")
    dst_var = tk.StringVar(value="ptrade")
    llm_var = tk.BooleanVar(value=False)
    _example_var = tk.StringVar(value="")

    dst_radios: dict[str, "tk.Radiobutton"] = {}

    def _refresh_title():
        """窗口标题随当前 源/目标 平台联动刷新（不再写死 聚宽↔PTrade）。"""
        src = dict(_PLATFORMS).get(src_var.get(), src_var.get())
        dst = dict(_PLATFORMS).get(dst_var.get(), dst_var.get())
        win.title(_t("quant.panel.title_fmt", src=src, dst=dst))

    src_var.trace_add("write", lambda *a: _refresh_title())
    dst_var.trace_add("write", lambda *a: _refresh_title())

    def _lock_platforms():
        """同平台互转直接禁掉：目标里高亮源平台，选中已锁定时自动避开。"""
        src = src_var.get()
        for val, rb in dst_radios.items():
            locked = (val == src)
            rb.config(state="disabled" if locked else "normal",
                      fg=_LOCKED_FG if locked else _TEXT,
                      selectcolor=_SECOND_ACTIVE if locked else _SEL_BG)
            if locked and dst_var.get() == src:
                dst_var.set(next(v for v, _ in _PLATFORMS if v != src))

    def _seg_button(parent, val, label, var):
        """扁平分段按钮式 Radio：indicatoron=0 去掉圆点，选中走浅蓝底。"""
        rb = tk.Radiobutton(
            parent, text=label, value=val, variable=var,
            font=(FONT_UI, 10), indicatoron=0, relief="flat", bd=0,
            cursor="hand2", fg=_TEXT, selectcolor=_SEL_BG,
            activebackground="#e0e7ff", activeforeground=_TEXT)
        return rb

    tk.Label(ctrl, text=_t("quant.src"), font=(FONT_UI, 10, "bold"),
             fg=_TEXT).pack(side="left", padx=(0, 6))
    # 源平台切换时联动锁定目标（同平台禁掉）
    for val, label in _PLATFORMS:
        rb = _seg_button(ctrl, val, label, src_var)
        rb.config(command=_lock_platforms)
        rb.pack(side="left", padx=(3, 6))
    tk.Label(ctrl, text=_t("quant.dst"), font=(FONT_UI, 10, "bold"),
             fg=_TEXT).pack(side="left", padx=(14, 6))
    for val, label in _PLATFORMS:
        rb = _seg_button(ctrl, val, label, dst_var)
        rb.pack(side="left", padx=(3, 6))
        dst_radios[val] = rb

    tk.Checkbutton(ctrl, text=_t("quant.use_llm"), variable=llm_var,
                   font=(FONT_UI, 10), cursor="hand2",
                   bg=ctrl.cget("bg"), activebackground=ctrl.cget("bg"),
                   activeforeground=_TEXT, fg=_TEXT).pack(side="left",
                                                          padx=(16, 0))

    # LLM 兜底模型下拉：选择即写入配置（config.quant_llm_model）
    tk.Label(ctrl, text=_t("quant.llm_model"), font=(FONT_UI, 10),
             bg=ctrl.cget("bg"), fg=_TEXT).pack(side="left", padx=(16, 0))
    llm_model_var = tk.StringVar(value="")

    def _llm_model_items():
        items = []
        for _m in getattr(app, "models", []) or []:
            if getattr(_m, "key", ""):
                items.append("%s  ·  %s" % (_m.key, getattr(_m, "display_name", "")))
        return items

    def _llm_model_key(label: str) -> str:
        return label.split("  ·  ")[0].strip() if label else ""

    def _llm_model_pick(_e=None):
        try:
            key = _llm_model_key(llm_model_var.get())
            if hasattr(_cfg, "set_quant_llm_model"):
                _cfg.set_quant_llm_model(key)
        except Exception:            # noqa: BLE001
            pass

    llm_model_combo = ttk.Combobox(ctrl, textvariable=llm_model_var,
                                   font=(FONT_MONO, 9), width=30, state="readonly")
    llm_model_combo.bind("<<ComboboxSelected>>", _llm_model_pick)
    llm_model_combo.pack(side="left", padx=(4, 0))
    try:
        _items = _llm_model_items()
        _cur = (_cfg.get_quant_llm_model() if hasattr(_cfg, "get_quant_llm_model") else "") \
               or (_cfg.get_dispatch_pro() if hasattr(_cfg, "get_dispatch_pro") else "") \
               or _cfg.load_models()[1]
        llm_model_combo["values"] = _items
        _sel = next((i for i in _items if _llm_model_key(i) == _cur), _items[0] if _items else "")
        if _sel:
            llm_model_var.set(_sel)
    except Exception:            # noqa: BLE001
        pass

    # ---- 代码区：左源右结果，扁平 + 语法高亮 ----
    paned = tk.PanedWindow(win, orient="horizontal", sashwidth=3,
                           sashrelief="flat", bd=0, background=_BORDER)
    paned.pack(fill="both", expand=True, padx=16, pady=6)
    src_text = _code_widget(paned, undo=True)
    dst_text = _code_widget(paned)
    paned.add(src_text, minsize=320, stretch="always")
    paned.add(dst_text, minsize=320, stretch="always")
    # 编辑/粘贴后重新着色（量小，逐键着色开销可忽略）
    src_text.bind("<KeyRelease>", lambda e: _apply_hl(src_text))

    # ---- 报告行 + 转换等待指示 ----
    status_row = tk.Frame(win)
    status_row.pack(fill="x", padx=16)
    report = tk.Label(status_row, text=_t("quant.report.idle"), anchor="w",
                      justify="left", font=(FONT_MONO, 9), fg="#64748b")
    report.pack(side="left", fill="x", expand=True)
    spin = tk.Label(status_row, text="", font=(FONT_UI, 11), fg="#2563eb")
    spin.pack(side="right")

    # ---- 按钮行 ----
    btns = tk.Frame(win)
    btns.pack(fill="x", padx=16, pady=8)

    def _flat(parent, text, command, font=(FONT_UI, 10)):
        b = tk.Button(parent, text=text, command=command, font=font,
                      relief="flat", cursor="hand2", bd=0,
                      highlightthickness=0, padx=14, pady=6)
        return b

    def _set_result(code: str):
        dst_text.delete("1.0", "end")
        dst_text.insert("1.0", code)
        _apply_hl(dst_text)

    # ---- 转换等待效果：滚动指示器 + 禁用主按钮 + 沙漏光标 ----
    _conv = {"on": False, "after": None, "idx": 0}
    _SPINNER = "◐◓◑◒"

    def _spin_tick():
        if not _conv["on"]:
            return
        _conv["idx"] = (_conv["idx"] + 1) % len(_SPINNER)
        spin.config(text=_SPINNER[_conv["idx"]])
        _conv["after"] = win.after(120, _spin_tick)

    def _set_converting(on: bool, msg: str | None = None):
        """进入/退出转换状态：spinner + 禁用主按钮 + 沙漏光标。"""
        _conv["on"] = on
        if on:
            win.configure(cursor="watch")
            primary.config(state="disabled", cursor="watch")
            report.config(fg="#2563eb",
                          text=msg or _t("quant.report.converting"))
            _spin_tick()
        else:
            if _conv["after"] is not None:
                win.after_cancel(_conv["after"])
                _conv["after"] = None
            spin.config(text="")
            win.configure(cursor="")
            primary.config(state="normal", cursor="hand2")

    def _done_parse_fail(e, use_llm):
        _set_converting(False)
        if use_llm:
            report.config(fg="#dc2626", text=f"❌ LLM 兜底失败：{e}")
        else:
            report.config(fg="#dc2626", text=_t("quant.report.parse_fail", e=e))

    def _done_error(e):
        _set_converting(False)
        report.config(fg="#dc2626", text=f"❌ {type(e).__name__}: {e}")

    def _done_success(r, use_llm):
        _set_converting(False)
        _set_result(r["code"])
        v = r["validation"]
        if v.ok:
            key = "quant.report.ok_llm" if use_llm else "quant.report.ok"
            report.config(fg="#16a34a", text=_t(key, name=r["ir"].name))
        else:
            report.config(fg="#dc2626", text="❌ " + "；".join(v.errors))

    def _do_translate():
        source = src_text.get("1.0", "end-1c").strip()
        if not source:
            report.config(text=_t("quant.report.empty"), fg="#d97706")
            return
        src, dst = src_var.get(), dst_var.get()
        if src == dst:
            report.config(text=_t("quant.report.same"), fg="#d97706")
            return
        # 统一走后台线程：确定性解析毫秒级、LLM 兜底秒级；期间展示等待效果，避免冻 UI。
        use_llm = llm_var.get()
        _set_converting(True,
                        (_t("quant.report.llm_running") if use_llm else None))

        def worker():
            try:
                r = translate(source, src, dst,
                              chat_fn=True if use_llm else None)
            except ParseError as e:
                win.after(0, lambda e=e: _done_parse_fail(e, use_llm))
                return
            except Exception as e:              # noqa: BLE001
                win.after(0, lambda e=e: _done_error(e))
                return
            win.after(0, lambda: _done_success(r, use_llm))

        threading.Thread(target=worker, daemon=True).start()

    def _load_example():
        # 示例下拉选择：双均线（可确定性互转）/ ETF轮动（四平台）/ 小市值（LLM兜底）
        name = _example_var.get()
        if name == _t("quant.example.smallcap"):
            _read_smallcap_code(src_text)
            src_var.set("joinquant")                  # 小市值示例为聚宽源码
            _lock_platforms()
            report.config(fg="#2563eb", text=_t("quant.report.smallcap_loaded"))
            return
        if name == _t("quant.example.etf"):
            code = emit(demo_etf_rotation(), src_var.get())
            report.config(fg="#16a34a", text=_t("quant.report.etf_loaded"))
        else:
            code = emit(demo_ma_cross(), src_var.get())
            report.config(fg="#64748b", text=_t("quant.report.demo_loaded"))
        _set_result("")
        src_text.delete("1.0", "end")
        src_text.insert("1.0", code)
        _apply_hl(src_text)

    def _read_smallcap_code(txt):
        """把 examples/早小市值.py（干净版，无八星）读入编辑框。"""
        p = os.path.join(os.path.dirname(__file__), "products", "quant",
                         "examples", "早小市值.py")
        try:
            with open(p, encoding="utf-8") as f:
                code = f.read()
        except OSError as e:
            report.config(fg="#dc2626", text=f"❌ 小市值示例缺失：{e}")
            return
        _set_result("")
        txt.delete("1.0", "end")
        txt.insert("1.0", code)
        _apply_hl(txt)

    def _copy():
        app.root.clipboard_clear()
        app.root.clipboard_append(dst_text.get("1.0", "end-1c"))
        app._set_status(_t("quant.copied"))

    # 主按钮（蓝色扁平）
    primary = _flat(btns, _t("quant.btn.translate"), _do_translate,
                    font=(FONT_UI, 10, "bold"))
    primary.config(bg="#2563eb", fg="white", activebackground="#1d4ed8",
                   activeforeground="white")
    primary.pack(side="left")

    # 次按钮（浅灰扁平）：示例下拉 + 载入所选示例 + 复制结果
    _EXAMPLES = (_t("quant.example.ma"), _t("quant.example.etf"),
                 _t("quant.example.smallcap"))
    ex_menu = tk.OptionMenu(btns, _example_var, *_EXAMPLES)
    ex_menu.config(font=(FONT_UI, 10), relief="flat", bd=0, bg=_SECOND_BG,
                   fg=_SECOND_FG, activebackground=_SECOND_ACTIVE,
                   activeforeground=_TEXT, highlightthickness=0, cursor="hand2")
    ex_menu["menu"].config(font=(FONT_UI, 10), bg="white", fg=_TEXT,
                           activebackground=_SEL_BG, activeforeground=_SEL_FG)
    ex_menu.pack(side="left", padx=(8, 0))
    _example_var.set(_t("quant.example.ma"))

    for text, cmd in ((_t("quant.btn.load_example"), _load_example),
                      (_t("quant.btn.copy"), _copy)):
        b = _flat(btns, text, cmd)
        b.config(bg=_SECOND_BG, fg=_SECOND_FG, activebackground=_SECOND_ACTIVE,
                 activeforeground=_TEXT)
        b.pack(side="left", padx=(8, 0))

    # ---- QMT 探活 ----
    qmt_row = tk.Frame(win)
    qmt_row.pack(fill="x", padx=16, pady=(4, 12))
    tk.Label(qmt_row, text=_t("quant.qmt.label"),
             font=(FONT_UI, 10, "bold"), fg=_TEXT).pack(side="left")
    qmt_var = tk.StringVar(value="…")
    tk.Label(qmt_row, textvariable=qmt_var, font=(FONT_MONO, 9),
             fg="#64748b", anchor="w").pack(side="left", padx=8)

    def _probe():
        qmt_var.set("…")

        def worker():
            r = qmt.probe()
            win.after(0, lambda: qmt_var.set(
                ("🟢 " if r["terminal_running"] else "⚪ ") + r["detail"]))

        threading.Thread(target=worker, daemon=True).start()

    refresh = _flat(qmt_row, _t("quant.qmt.refresh"), _probe, font=(FONT_UI, 9))
    refresh.config(bg=_SECOND_BG, fg=_SECOND_FG, activebackground=_SECOND_ACTIVE,
                   activeforeground=_TEXT, padx=10, pady=3)
    refresh.pack(side="right")

    # 启动状态
    _lock_platforms()
    _refresh_title()
    _probe()
    _load_example()

    # 模态：等窗口可见再 grab，避免 Windows 上 grab 静默失效
    ui._make_modal(win, root)
    win.bind("<Escape>", lambda e: win.destroy())
