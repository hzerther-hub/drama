# -*- coding: utf-8 -*-
"""公司知识库管理面板（企业代码 RAG）：根目录增删、建/重建索引、开关、测试查询。

入口 show(app)，app 为 ui.App 实例（与 ui_panel_quant 等同一模式）。
后台线程跑 codera.build，完事经 root.after 回主线程刷新，避免冻 UI。
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

import config
from i18n import t as _t
import theme


def show(app):
    import ui  # 延迟导入：读最新字体，避免循环依赖
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    import codera

    roots = list(config.get_kb_roots())          # 面板内可编辑副本，Save 写回
    enabled = tk.BooleanVar(value=config.get_kb_enabled())
    inject = tk.BooleanVar(value=config.get_kb_inject())
    auto = tk.BooleanVar(value=config.get_kb_auto())
    top_k_var = tk.IntVar(value=config.get_kb_top_k())
    emb_var = tk.StringVar(value=config.get_kb_embedding())

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("kb.panel.title"))
    win.geometry("860x620")
    ui._make_modal(win, app.root)

    # ---- 根目录列表 ----
    tk.Label(win, text=_t("kb.roots"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 2))
    root_frame = tk.Frame(win)
    root_frame.pack(fill="x", padx=16)
    lb = tk.Listbox(root_frame, font=(FONT_MONO, 10), height=6,
                    bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0, selectbackground=theme.ACCENT_SOFT, selectforeground=theme.TEXT,
                    selectmode="single", exportselection=False)
    lb.pack(side="left", fill="both", expand=True)

    def _refresh_list():
        lb.delete(0, "end")
        for r in roots:
            lb.insert("end", r)
        _refresh_stats()

    def _add_root():
        d = filedialog.askdirectory(title=_t("kb.roots.add"))
        if d and d not in roots:
            roots.append(d)
            _refresh_list()

    def _del_root():
        sel = lb.curselection()
        if not sel:
            return
        del roots[sel[0]]
        _refresh_list()

    btn_col = tk.Frame(root_frame)
    btn_col.pack(side="left", padx=(8, 0))
    ui._flat_button(btn_col, text=_t("kb.roots.add"), command=_add_root,
                    font=(FONT_UI, 9), width=10).pack(fill="x")
    ui._flat_button(btn_col, text=_t("kb.roots.del"), command=_del_root,
                    font=(FONT_UI, 9), width=10).pack(fill="x", pady=(4, 0))

    # ---- 开关 / 参数 ----
    opts = tk.Frame(win)
    opts.pack(anchor="w", padx=16, pady=(10, 0))
    tk.Checkbutton(opts, text=_t("kb.enabled"), variable=enabled,
                   font=(FONT_UI, 10, "bold")).pack(anchor="w")
    tk.Checkbutton(opts, text=_t("kb.inject"), variable=inject,
                   font=(FONT_UI, 10)).pack(anchor="w")
    tk.Checkbutton(opts, text=_t("kb.auto"), variable=auto,
                   font=(FONT_UI, 10)).pack(anchor="w")
    tk.Label(opts, text=_t("kb.top_k"), font=(FONT_UI, 10)).pack(side="left",
                                                                 pady=(6, 0))
    tk.Spinbox(opts, from_=1, to=20, textvariable=top_k_var, width=4,
               font=(FONT_UI, 10)).pack(side="left", padx=(4, 20), pady=(6, 0))
    tk.Label(opts, text=_t("kb.embedding"), font=(FONT_UI, 10)
             ).pack(side="left", pady=(6, 0))
    try:
        models, _def = config.load_models()
    except Exception:                    # noqa: BLE001
        models = []
    emb_items = [(_t("kb.embedding.none"), "")]
    emb_items += [(f"{m.display_name}", m.key) for m in models]
    emb_combo = ttk.Combobox(opts, textvariable=emb_var, state="readonly",
                             width=30, font=(FONT_UI, 10),
                             values=[t for t, _ in emb_items])
    emb_combo.pack(side="left", padx=4, pady=(6, 0))
    cur_t = next((t for t, k in emb_items if k == emb_var.get()), None)
    if cur_t is None and emb_var.get():
        cur_t = emb_var.get()
        emb_items.insert(0, (cur_t, cur_t))
        emb_combo["values"] = [t for t, _ in emb_items]
    emb_combo.set(cur_t or emb_items[0][0])

    # ---- 统计 / 状态 ----
    stats_lbl = tk.Label(win, text=_t("kb.stats.idle"), anchor="w",
                         justify="left", font=(FONT_MONO, 9), fg="#64748b")
    stats_lbl.pack(fill="x", padx=16, pady=(8, 0))

    msg = tk.Label(win, text="", anchor="w", font=(FONT_UI, 9), fg="#64748b")
    msg.pack(fill="x", padx=16, pady=(4, 0))

    def _refresh_stats():
        s = codera.stats(roots)
        if s["db"]:
            stats_lbl.config(text=_t("kb.stats", files=s["files"],
                                     chunks=s["chunks"], db=s["db"]))
        else:
            stats_lbl.config(text=_t("kb.stats.empty"))

    def _do_build():
        if not roots:
            msg.config(text=_t("kb.need_roots"), fg="#d97706")
            return
        msg.config(text=_t("kb.building"), fg="#2563eb")

        def worker():
            try:
                r = codera.build(roots, force=True)
                win.after(0, lambda: _build_done(r, None))
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda: _build_done(None, e))

        def _build_done(r, err):
            _refresh_stats()
            if err is not None:
                msg.config(text=f"❌ {err}", fg="#dc2626")
                return
            msg.config(text=_t("kb.built", files=r["files_indexed"],
                               updated=r["updated"], mode=r["embedding"],
                               sec=r["seconds"]), fg="#16a34a")

        threading.Thread(target=worker, daemon=True).start()

    def _do_refresh():
        """增量更新：只刷变化/删除文件，跳过未变（不动全量重建）。"""
        if not roots:
            msg.config(text=_t("kb.need_roots"), fg="#d97706")
            return
        msg.config(text=_t("kb.building"), fg="#2563eb")

        def worker():
            try:
                r = codera.build(roots, force=False)
                win.after(0, lambda: _refresh_done(r, None))
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda: _refresh_done(None, e))

        def _refresh_done(r, err):
            _refresh_stats()
            if err is not None:
                msg.config(text=f"❌ {err}", fg="#dc2626")
                return
            msg.config(text=_t("kb.refreshed", updated=r["updated"],
                               skipped=r["skipped_unchanged"],
                               mode=r["embedding"], sec=r["seconds"]),
                       fg="#16a34a")

        threading.Thread(target=worker, daemon=True).start()

    # ---- 测试查询 ----
    tk.Label(win, text=_t("kb.test"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(10, 2))
    q_frame = tk.Frame(win)
    q_frame.pack(fill="x", padx=16)
    q_var = tk.StringVar()
    q_entry = tk.Entry(q_frame, textvariable=q_var, font=(FONT_MONO, 10))
    q_entry.pack(side="left", fill="x", expand=True)
    ui._flat_button(q_frame, text=_t("kb.test.run"),
                    command=lambda: _do_test(),
                    font=(FONT_UI, 10), width=10).pack(side="left", padx=(8, 0))
    result = scrolledtext.ScrolledText(win, wrap="none", height=10,
                                       font=(FONT_MONO, 9))
    result.pack(fill="both", expand=True, padx=16, pady=(6, 0))

    def _do_test():
        q = q_var.get().strip()
        if not q:
            return
        if not roots:
            result.delete("1.0", "end")
            result.insert("1.0", _t("kb.need_roots"))
            return
        hits = codera.search(q, top_k=top_k_var.get(), roots=roots)
        result.delete("1.0", "end")
        if not hits:
            result.insert("1.0", _t("kb.test.none"))
            return
        out = []
        for h in hits:
            out.append(f"### [{h['source']} 相关度 {h['score']}] "
                       f"{h['root']}/{h['file']}:{h['start_line']}-{h['end_line']}\n"
                       f"{h['content']}")
        result.insert("1.0", "\n\n".join(out))

    # ---- 按钮 ----
    bar = tk.Frame(win)
    bar.pack(fill="x", padx=16, pady=12)

    def _save():
        emb = next((k for t, k in emb_items if t == emb_var.get()), "")
        config.set_kb_roots(roots)
        config.set_kb_enabled(enabled.get())
        config.set_kb_inject(inject.get())
        config.set_kb_auto(auto.get())
        config.set_kb_top_k(top_k_var.get())
        config.set_kb_embedding(emb)
        msg.config(text="✅ " + _t("kb.saved"), fg="#16a34a")
        app._set_status(_t("kb.saved"))

    ui._flat_button(bar, text=_t("kb.build"), command=_do_build,
                    font=(FONT_UI, 10), width=10).pack(side="left")
    ui._flat_button(bar, text=_t("kb.refresh"), command=_do_refresh,
                    font=(FONT_UI, 10), width=10).pack(side="left", padx=(8, 0))
    ui._flat_button(bar, text=_t("btn.save"), command=_save,
                    font=(FONT_UI, 10), width=10).pack(side="left", padx=(8, 0))
    ui._flat_button(bar, text=_t("btn.close"), command=win.destroy,
                    font=(FONT_UI, 10), width=10).pack(side="left", padx=(8, 0))

    _refresh_list()
