# -*- coding: utf-8 -*-
"""模型管理面板：模型列表 + 添加 / 编辑 / 删除对话框。

从 ui.py 拆分而来；入口 show_manager(app)，app 为 ui.App 实例。
"""

from __future__ import annotations
import threading
import tkinter as tk
from tkinter import ttk

import config
from i18n import t as _t
import theme


def show_manager(app):
    """模型管理窗口：列表 + 添加 / 编辑 / 删除。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    _make_modal = ui._make_modal

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.model_mgmt"))
    win.geometry("640x420")
    win.transient(app.root)

    tk.Label(win, text=_t("mm.list_title"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 6))

    listbox = tk.Listbox(win, font=(FONT_MONO, 10),
               bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0, selectbackground=theme.ACCENT_SOFT, selectforeground=theme.TEXT, activestyle="dotbox",
                         selectmode="single")
    listbox.pack(fill="both", expand=True, padx=16)

    def _reload_list():
        listbox.delete(0, "end")
        for m in app.models:
            cur = "  ✓" if (app.current_model and m.key == app.current_model.key) else ""
            listbox.insert("end", f"{m.display_name}{cur}    [{m.key}  {m.base_url}]")

    def _selected_key():
        sel = listbox.curselection()
        if not sel:
            return None
        return app.models[sel[0]].key if sel[0] < len(app.models) else None

    _reload_list()

    def _after_change(status):
        app._refresh_models()
        _reload_list()
        app._set_status(status)

    def _add():
        _add_dialog(app, win, _after_change)

    def _edit():
        key = _selected_key()
        if not key:
            app._set_status(_t("mm.pick_first"))
            return
        m = app.model_map.get(key)
        if m:
            _edit_dialog(app, win, m, _after_change)

    def _delete():
        key = _selected_key()
        if not key:
            app._set_status(_t("mm.pick_first"))
            return
        m = app.model_map.get(key)
        if m is None:
            return
        from tkinter import messagebox
        if not messagebox.askyesno(_t("mm.del_title"),
                                   _t("mm.del_confirm",
                                      name=m.display_name),
                                   parent=win):
            return
        if config.remove_model(key):
            _after_change(_t("mm.deleted", name=m.display_name))
        else:
            app._set_status(_t("mm.del_missing"))

    def _use():
        key = _selected_key()
        if key:
            app._select_model(key)
            _reload_list()

    listbox.bind("<Double-Button-1>", lambda e: _use())

    bar = tk.Frame(win)
    bar.pack(pady=12)
    tk.Button(bar, text=_t("mm.add"), command=_add, width=10).pack(side="left", padx=6)
    tk.Button(bar, text=_t("mm.edit"), command=_edit, width=10).pack(side="left", padx=6)
    tk.Button(bar, text=_t("mm.delete"), command=_delete, width=10).pack(side="left", padx=6)
    tk.Button(bar, text=_t("btn.close"), command=win.destroy, width=10).pack(side="left", padx=6)
    _make_modal(win, app.root)


def _add_dialog(app, parent, on_done):
    """添加模型：一个端点 + 密钥 + 多个模型 ID（每行一个）。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    REASONING_CHOICES = ui.REASONING_CHOICES
    _fetch_openai_models = ui._fetch_openai_models
    _make_modal = ui._make_modal

    win = tk.Toplevel(parent)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.add_model"))
    win.geometry("560x480")
    win.transient(parent)

    tk.Label(win, text=_t("add.base_url"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(12, 2))
    url_entry = tk.Entry(win, font=(FONT_MONO, 10))
    url_entry.pack(fill="x", padx=16)
    url_entry.insert(0, "https://api.deepseek.com/v1")

    tk.Label(win, text=_t("add.api_key"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(10, 2))
    key_entry = tk.Entry(win, font=(FONT_MONO, 10), show="*")
    key_entry.pack(fill="x", padx=16)

    tk.Label(win, text=_t("add.ids"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(10, 2))
    ids_text = tk.Text(win, height=6, font=(FONT_MONO, 10), wrap="none")
    ids_text.pack(fill="both", expand=True, padx=16)
    ids_text.insert("1.0", "deepseek-v4-flash\ndeepseek-v4-pro")

    vision_var = tk.BooleanVar(value=False)
    tk.Checkbutton(win, text=_t("add.vision"),
                   variable=vision_var,
                   font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(8, 0))

    reasoning_var = tk.StringVar(value="")
    tk.Label(win, text=_t("add.reasoning"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(8, 0))
    ttk.Combobox(win, textvariable=reasoning_var, values=REASONING_CHOICES,
                 state="readonly", font=(FONT_UI, 10)).pack(fill="x", padx=16)
    tk.Label(win, text=_t("add.reasoning_hint"),
             font=(FONT_UI, 9), fg="#666666").pack(anchor="w", padx=16)

    msg = tk.Label(win, text="", font=(FONT_UI, 9), fg="red")
    msg.pack(anchor="w", padx=16)

    def _fetch():
        """调用端点 /models 获取支持的模型列表，自动填入下方文本框。"""
        base_url = url_entry.get().strip().rstrip("/")
        api_key = key_entry.get().strip()
        if not base_url:
            msg.config(text=_t("add.base_first"), fg="red")
            return
        msg.config(text=_t("add.fetching"), fg="#2563eb")
        btn_fetch.config(state="disabled")

        def _worker():
            try:
                ids = _fetch_openai_models(base_url, api_key)
            except Exception as e:              # noqa: BLE001
                def _fail():
                    btn_fetch.config(state="normal")
                    msg.config(text=_t("fetch.fail", e=e), fg="red")
                win.after(0, _fail)
                return

            def _ok():
                btn_fetch.config(state="normal")
                ids_text.delete("1.0", "end")
                ids_text.insert("1.0", "\n".join(ids))
                msg.config(text=_t("add.filled", n=len(ids)), fg="#16a34a")
            win.after(0, _ok)

        threading.Thread(target=_worker, daemon=True).start()

    btn_fetch = tk.Button(win, text=_t("add.fetch"),
                          command=_fetch, width=26)
    btn_fetch.pack(pady=(8, 0))

    def _save():
        base_url = url_entry.get().strip().rstrip("/")
        api_key = key_entry.get().strip()
        model_ids = [l for l in ids_text.get("1.0", "end").splitlines() if l.strip()]
        if not base_url or not model_ids:
            msg.config(text=_t("add.require"))
            return
        try:
            added = config.add_custom_model(
                model_ids, base_url, api_key,
                vision=vision_var.get(),
                reasoning_effort=reasoning_var.get().strip())
            on_done(_t("add.done", n=len(added), url=base_url))
            win.destroy()
        except Exception as e:  # noqa: BLE001
            msg.config(text=_t("add.fail", e=e))

    tk.Button(win, text=_t("btn.save"), command=_save, width=12).pack(pady=12)
    _make_modal(win, parent)


def _edit_dialog(app, parent, m, on_done):
    """编辑已有模型：显示名称 / 模型 ID / 端点 / 密钥。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    REASONING_CHOICES = ui.REASONING_CHOICES
    _fetch_openai_models = ui._fetch_openai_models
    _make_modal = ui._make_modal

    win = tk.Toplevel(parent)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.edit_model", name=m.display_name))
    win.geometry("560x440")
    win.transient(parent)

    def _row(label, initial, row, show=None):
        tk.Label(win, text=label, font=(FONT_UI, 10)).grid(
            row=row, column=0, sticky="w", padx=(16, 4), pady=6)
        e = tk.Entry(win, font=(FONT_MONO, 10), show=show)
        e.grid(row=row, column=1, sticky="ew", padx=(0, 16))
        e.insert(0, initial)
        return e

    win.grid_columnconfigure(1, weight=1)
    name_entry = _row(_t("edit.name"), m.display_name, 0)
    id_entry = _row(_t("edit.id"), m.model_id, 1)
    url_entry = _row(_t("edit.base_url"), m.base_url, 2)
    key_entry = _row(_t("edit.api_key"), m.api_key
                     if m.api_key != "local-noauth" else "", 3, show="*")

    vision_var = tk.BooleanVar(value=m.vision)
    tk.Checkbutton(win, text=_t("edit.vision"),
                   variable=vision_var,
                   font=(FONT_UI, 10)).grid(
        row=4, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 0))

    reasoning_var = tk.StringVar(value=m.reasoning_effort)
    tk.Label(win, text=_t("edit.reasoning"),
             font=(FONT_UI, 10)).grid(
        row=5, column=0, sticky="w", padx=(16, 4), pady=(4, 0))
    ttk.Combobox(win, textvariable=reasoning_var, values=REASONING_CHOICES,
                 state="readonly", font=(FONT_UI, 10), width=24).grid(
        row=5, column=1, sticky="w", padx=(0, 16))
    tk.Label(win, text=_t("edit.reasoning_hint"),
             font=(FONT_UI, 9), fg="#666666").grid(
        row=6, column=1, sticky="w", padx=(0, 16), pady=(2, 0))

    msg = tk.Label(win, text="", font=(FONT_UI, 9), fg="red")
    msg.grid(row=7, column=0, columnspan=2, sticky="w", padx=16)

    def _fetch():
        """获取当前端点的模型列表：补齐 provider 缺失项，并弹出列表点选。"""
        base_url = url_entry.get().strip().rstrip("/")
        api_key = key_entry.get().strip() or (
            m.api_key if m.api_key != "local-noauth" else "")
        if not base_url:
            msg.config(text=_t("add.base_first"), fg="red")
            return
        msg.config(text=_t("edit.fetching"), fg="#2563eb")
        fetch_btn.config(state="disabled")

        def _worker():
            try:
                ids = _fetch_openai_models(base_url, api_key)
            except Exception as e:              # noqa: BLE001
                def _fail():
                    fetch_btn.config(state="normal")
                    msg.config(text=_t("fetch.fail", e=e), fg="red")
                win.after(0, _fail)
                return
            pid = m.key.split("/", 1)[0]
            try:
                added = config.augment_provider_models(pid, ids)
            except Exception:                   # noqa: BLE001
                added = 0

            def _show():
                fetch_btn.config(state="normal")
                msg.config(
                    text=_t("add.got", n=len(ids))
                         + (_t("add.got_new", a=added) if added else ""),
                    fg="#16a34a")
                if not ids:
                    return
                sel = tk.Toplevel(win)
                sel.configure(bg=theme.PANEL)
                sel.title(_t("dlg.fetch_models"))
                sel.geometry("420x320")
                ui._make_modal(sel, win)
                tk.Label(sel, text=_t("add.pick_hint"),
                         font=(FONT_UI, 10)).pack(anchor="w", padx=12, pady=(10, 2))
                lb = tk.Listbox(sel, font=(FONT_MONO, 10),
               bg=theme.PANEL, fg=theme.TEXT, relief="flat", highlightthickness=0, selectbackground=theme.ACCENT_SOFT, selectforeground=theme.TEXT, activestyle="dotbox")
                lb.pack(fill="both", expand=True, padx=12, pady=8)
                for i in ids:
                    lb.insert("end", i)

                def _use():
                    s = lb.curselection()
                    if s:
                        id_entry.delete(0, "end")
                        id_entry.insert(0, ids[s[0]])
                    sel.destroy()

                def _use_all():
                    sel.destroy()

                def _double(_e):
                    _use()

                lb.bind("<Double-Button-1>", _double)
                tk.Button(sel, text=_t("add.fill_id"), command=_use, width=14
                          ).pack(side="left", padx=(12, 4), pady=10)
                tk.Button(sel, text=_t("btn.close"), command=_use_all, width=10
                          ).pack(side="left", padx=4, pady=10)
            win.after(0, _show)

        threading.Thread(target=_worker, daemon=True).start()

    fetch_btn = tk.Button(win, text=_t("edit.fetch"),
                          command=_fetch, width=24)
    fetch_btn.grid(row=6, column=0, columnspan=2, sticky="w", padx=16,
                   pady=(2, 0))

    def _save():
        try:
            old_key = m.key
            mc = config.update_model(
                old_key,
                base_url=url_entry.get().strip().rstrip("/"),
                api_key=key_entry.get().strip(),
                model_id=id_entry.get().strip(),
                display_name=name_entry.get().strip(),
                vision=vision_var.get(),
                reasoning_effort=reasoning_var.get().strip())
            if mc is None:
                msg.config(text=_t("edit.missing"))
                return
            # 保持当前模型指向更新后的配置
            if app.current_model and app.current_model.key == old_key:
                app.current_model = mc
            on_done(_t("edit.done", name=mc.display_name))
            win.destroy()
        except Exception as e:  # noqa: BLE001
            msg.config(text=_t("edit.fail", e=e))

    tk.Button(win, text=_t("btn.save"), command=_save, width=12).grid(
        row=8, column=0, columnspan=2, pady=14)
    _make_modal(win, parent)
