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


def _fmt_tokens(n) -> str:
    """token 数 → 紧凑显示：262144 → 256K；0/空 → -。"""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "-"
    if n <= 0:
        return "-"
    if n >= 1000:
        v = n / 1000
        return f"{v:.0f}K" if v == int(v) else f"{v:.1f}K"
    return str(n)


def _add_provider_dialog(app, parent, on_done):
    """新建 provider：id + name + 可选的 base_url/api_key/api_type。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    _make_modal = ui._make_modal

    win = tk.Toplevel(parent)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.add_provider"))
    win.geometry("520x460")
    win.transient(parent)

    win.grid_columnconfigure(1, weight=1)

    def _row(label, initial, row, show=None, hint=None):
        tk.Label(win, text=label, font=(FONT_UI, 10)).grid(
            row=row, column=0, sticky="w", padx=(16, 4), pady=6)
        e = tk.Entry(win, font=(FONT_MONO, 10), show=show)
        e.grid(row=row, column=1, sticky="ew", padx=(0, 16))
        if initial:
            e.insert(0, initial)
        if hint:
            tk.Label(win, text=hint, font=(FONT_UI, 9), fg="#666666").grid(
                row=row + 1, column=1, sticky="w", padx=(0, 16), pady=(0, 4))
        return e

    id_entry = _row(_t("add_provider.id"), "custom", 0,
                    hint=_t("add_provider.id_hint"))
    name_entry = _row(_t("add_provider.name"), "自定义", 2,
                      hint=_t("add_provider.name_hint"))
    url_entry = _row(_t("add_provider.base_url"), "", 4)
    key_entry = _row(_t("add_provider.api_key"), "", 6, show="*")

    api_type_var = tk.StringVar(value="openai_compatible")
    tk.Label(win, text=_t("add_provider.api_type"),
             font=(FONT_UI, 10)).grid(row=8, column=0, sticky="w",
                                      padx=(16, 4), pady=6)
    ttk.Combobox(win, textvariable=api_type_var,
                 values=("openai_compatible", "anthropic"),
                 state="readonly", font=(FONT_UI, 10)).grid(
        row=8, column=1, sticky="ew", padx=(0, 16))

    msg = tk.Label(win, text="", font=(FONT_UI, 9), fg="red")
    msg.grid(row=10, column=0, columnspan=2, sticky="w", padx=16)

    def _save():
        err = config.add_provider(
            id_entry.get().strip(),
            name_entry.get().strip(),
            base_url=url_entry.get().strip(),
            api_key=key_entry.get().strip(),
            api_type=api_type_var.get().strip() or "openai_compatible")
        if err:
            msg.config(text=err)
            return
        on_done(_t("add_provider.done",
                   name=name_entry.get().strip() or id_entry.get().strip()))
        win.destroy()

    tk.Button(win, text=_t("btn.save"), command=_save, width=12).grid(
        row=11, column=0, columnspan=2, pady=14)
    _make_modal(win, parent)


def _edit_provider_dialog(app, parent, pid: str, on_done):
    """编辑 provider：显示名 / base_url / API Key / API 类型。"""
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    _make_modal = ui._make_modal

    prov = config.get_provider(pid) or {}
    win = tk.Toplevel(parent)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.edit_provider", id=pid))
    win.geometry("520x340")
    win.transient(parent)

    win.grid_columnconfigure(1, weight=1)

    def _row(label, initial, row, show=None):
        tk.Label(win, text=label, font=(FONT_UI, 10)).grid(
            row=row, column=0, sticky="w", padx=(16, 4), pady=6)
        e = tk.Entry(win, font=(FONT_MONO, 10), show=show)
        e.grid(row=row, column=1, sticky="ew", padx=(0, 16))
        if initial:
            e.insert(0, initial)
        return e

    tk.Label(win, text="id", font=(FONT_UI, 10)).grid(
        row=0, column=0, sticky="w", padx=(16, 4), pady=(12, 6))
    tk.Label(win, text=pid, font=(FONT_MONO, 10), fg="#666666").grid(
        row=0, column=1, sticky="w", padx=(0, 16), pady=(12, 6))

    name_entry = _row(_t("add_provider.name"), prov.get("name", ""), 1)
    url_entry = _row(_t("add_provider.base_url"), prov.get("base_url", ""), 2)
    key_entry = _row(_t("add_provider.api_key"), prov.get("api_key", ""), 3,
                     show="*")

    api_type_var = tk.StringVar(
        value=prov.get("api_type") or "openai_compatible")
    tk.Label(win, text=_t("add_provider.api_type"),
             font=(FONT_UI, 10)).grid(row=4, column=0, sticky="w",
                                      padx=(16, 4), pady=6)
    ttk.Combobox(win, textvariable=api_type_var,
                 values=("openai_compatible", "anthropic"),
                 state="readonly", font=(FONT_UI, 10)).grid(
        row=4, column=1, sticky="ew", padx=(0, 16))

    msg = tk.Label(win, text="", font=(FONT_UI, 9), fg="red")
    msg.grid(row=5, column=0, columnspan=2, sticky="w", padx=16)

    def _save():
        err = config.update_provider(
            pid,
            name=name_entry.get(),
            base_url=url_entry.get(),
            api_key=key_entry.get(),
            api_type=api_type_var.get().strip() or "openai_compatible")
        if err:
            msg.config(text=err)
            return
        on_done(_t("edit_provider.done",
                   name=name_entry.get().strip() or pid))
        win.destroy()

    tk.Button(win, text=_t("btn.save"), command=_save, width=12).grid(
        row=6, column=0, columnspan=2, pady=14)
    _make_modal(win, parent)


def show_manager(app):
    """模型管理窗口：左 Provider 列表 + 右 Models 列表，按钮按上下文启用。

    - 左侧：所有 provider；当前 provider 标 ✓
    - 右侧：当前选中 provider 的所有模型；当前 model 标 ✓
    """
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    _make_modal = ui._make_modal

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.model_mgmt"))
    win.geometry("900x600")
    win.transient(app.root)

    # ============== 顶部说明 ==============
    tk.Label(win, text=_t("mm.list_title"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 6))

    # ============== 底部按钮栏（先于内容 pack 到底部：空间不足时压缩
    #              上方树列表，而不是把按钮挤出窗口外） ==============
    bar = tk.Frame(win, bg=theme.PANEL)
    bar.pack(side="bottom", pady=12, fill="x")

    # 左侧按钮：provider 操作
    add_p_btn = tk.Button(bar, text=_t("mm.add_provider"),
                          command=lambda: _add_provider_dialog(app, win, _after_change),
                          width=14)
    add_p_btn.pack(side="left", padx=4)
    rename_p_btn = tk.Button(bar, text=_t("mm.edit_provider"),
                             command=lambda: _edit_provider(),
                             width=14)
    rename_p_btn.pack(side="left", padx=4)
    del_p_btn = tk.Button(bar, text=_t("mm.del_provider"),
                          command=lambda: _del_provider(),
                          width=14)
    del_p_btn.pack(side="left", padx=4)

    # 中间：model 操作
    add_m_btn = tk.Button(bar, text=_t("mm.add"),
                          command=lambda: _add_model(),
                          width=10)
    add_m_btn.pack(side="left", padx=(20, 4))
    edit_m_btn = tk.Button(bar, text=_t("mm.edit"),
                           command=lambda: _edit_model(),
                           width=10)
    edit_m_btn.pack(side="left", padx=4)
    del_m_btn = tk.Button(bar, text=_t("mm.delete"),
                          command=lambda: _del_model(),
                          width=10)
    del_m_btn.pack(side="left", padx=4)

    tk.Button(bar, text=_t("btn.close"), command=win.destroy,
              width=10).pack(side="right", padx=4)

    # ============== 双栏 ==============
    body = tk.Frame(win, bg=theme.PANEL)
    body.pack(fill="both", expand=True, padx=16)

    # 左侧：providers
    left = tk.Frame(body, bg=theme.PANEL)
    left.pack(side="left", fill="both", expand=False)
    tk.Label(left, text=_t("mm.providers"), font=(FONT_UI, 10, "bold"),
             bg=theme.PANEL, fg=theme.TEXT).pack(anchor="w", pady=(0, 4))
    prov_tree = ttk.Treeview(left, columns=("name", "n"), show="headings",
                             selectmode="browse", height=13)
    prov_tree.heading("name", text=_t("mm.providers"))
    prov_tree.heading("n", text="n")
    prov_tree.column("name", width=200, anchor="w")
    prov_tree.column("n", width=40, anchor="e")
    prov_tree.pack(fill="both", expand=True, side="left")

    prov_sb = ttk.Scrollbar(left, orient="vertical", command=prov_tree.yview)
    prov_sb.pack(side="right", fill="y")
    prov_tree.configure(yscrollcommand=prov_sb.set)

    # 中间分隔
    tk.Frame(body, bg=theme.PANEL, width=12).pack(side="left")

    # 右侧：models
    right = tk.Frame(body, bg=theme.PANEL)
    right.pack(side="left", fill="both", expand=True)
    tk.Label(right, text=_t("mm.models"), font=(FONT_UI, 10, "bold"),
             bg=theme.PANEL, fg=theme.TEXT).pack(anchor="w", pady=(0, 4))
    model_tree = ttk.Treeview(right, columns=("name", "mid", "ctx", "out"),
                              show="headings", selectmode="browse", height=13)
    model_tree.heading("name", text=_t("mm.models"))
    model_tree.heading("mid", text=_t("edit.id"))
    model_tree.heading("ctx", text=_t("mm.col_ctx"))
    model_tree.heading("out", text=_t("mm.col_out"))
    model_tree.column("name", width=230, anchor="w")
    model_tree.column("mid", width=200, anchor="w")
    model_tree.column("ctx", width=80, anchor="e")
    model_tree.column("out", width=80, anchor="e")
    model_tree.pack(fill="both", expand=True, side="left")

    model_sb = ttk.Scrollbar(right, orient="vertical", command=model_tree.yview)
    model_sb.pack(side="right", fill="y")
    model_tree.configure(yscrollcommand=model_sb.set)

    # ============== 状态 ==============
    state = {"selected_pid": None, "selected_model_key": None}

    def _selected_pid():
        sel = prov_tree.selection()
        if not sel:
            return None
        # iid 是 "pid::name" 编码回原 id
        return sel[0].split("::", 1)[0]

    def _selected_model_key():
        sel = model_tree.selection()
        if not sel:
            return None
        return sel[0]                # iid 就是 model.key

    def _reload_providers():
        prov_tree.delete(*prov_tree.get_children())
        cur_pid = (app.current_model.key.split("/", 1)[0]
                   if app.current_model else "")
        # 读取持久化的 provider 列表
        data = config._load_models_data()
        providers = data.get("providers", [])
        # 按字母排序；当前 provider 提前
        def _sort_key(p):
            return (p.get("id") != cur_pid, (p.get("name") or p.get("id", "")).lower())
        providers = sorted(providers, key=_sort_key)
        for p in providers:
            pid = p.get("id", "")
            pname = p.get("name", "") or pid
            mark = " ✓" if pid == cur_pid else ""
            display = f"{pname}{mark}"
            n = len(p.get("models", []))
            iid = f"{pid}::{pname}"
            prov_tree.insert("", "end", iid=iid,
                             values=(display, str(n)))
        # 还原选择
        if state["selected_pid"]:
            for child in prov_tree.get_children():
                if child.split("::", 1)[0] == state["selected_pid"]:
                    prov_tree.selection_set(child)
                    prov_tree.see(child)
                    break
        _reload_models()

    def _reload_models():
        model_tree.delete(*model_tree.get_children())
        pid = state["selected_pid"]
        if not pid:
            return
        for m in app.models:
            if m.key.split("/", 1)[0] != pid:
                continue
            mark = " ✓" if (app.current_model and m.key == app.current_model.key) else ""
            caps = ""
            if m.vision:
                caps += " 👁"
            if getattr(m, "reasoning", False):
                caps += " 🧠"
            display = f"{m.display_name}{caps}{mark}"
            model_tree.insert("", "end", iid=m.key,
                              values=(display, m.model_id,
                                      _fmt_tokens(getattr(m, "context_window", 0)),
                                      _fmt_tokens(getattr(m, "max_tokens", 0))))
        if state["selected_model_key"]:
            if model_tree.exists(state["selected_model_key"]):
                model_tree.selection_set(state["selected_model_key"])
                model_tree.see(state["selected_model_key"])

    def _after_change(status):
        app._refresh_models()
        prev_pid = state["selected_pid"]
        prev_key = state["selected_model_key"]
        _reload_providers()
        # 优先保持当前 provider 选择；如果旧 pid 被删了，选第一个
        if prev_pid and not any(c.split("::", 1)[0] == prev_pid
                                for c in prov_tree.get_children()):
            children = prov_tree.get_children()
            state["selected_pid"] = (children[0].split("::", 1)[0]
                                     if children else None)
        else:
            state["selected_pid"] = prev_pid
        # model 选择：可能不存在
        state["selected_model_key"] = prev_key \
            if prev_key and model_tree.exists(prev_key) else None
        _update_button_state()
        if status:
            app._set_status(status)

    def _update_button_state():
        pid = state["selected_pid"]
        rename_p_btn.config(
            text=_t("mm.edit_provider"),
            state=("normal" if pid else "disabled"))
        del_p_btn.config(state=("normal" if pid else "disabled"))
        add_m_btn.config(state=("normal" if pid else "disabled"))
        edit_m_btn.config(state=("normal" if state["selected_model_key"]
                                  else "disabled"))
        del_m_btn.config(state=("normal" if state["selected_model_key"]
                                else "disabled"))

    def _on_select_provider(_event):
        sel = prov_tree.selection()
        if not sel:
            return
        state["selected_pid"] = sel[0].split("::", 1)[0]
        state["selected_model_key"] = None
        _reload_models()
        _update_button_state()

    def _on_select_model(_event):
        sel = model_tree.selection()
        if not sel:
            return
        state["selected_model_key"] = sel[0]
        _update_button_state()

    def _on_double_model(_event):
        # 双击 = 切换到该模型
        key = _selected_model_key()
        if key:
            app._select_model(key)
            _reload_models()
            _update_button_state()

    prov_tree.bind("<<TreeviewSelect>>", _on_select_provider)
    model_tree.bind("<<TreeviewSelect>>", _on_select_model)
    model_tree.bind("<Double-Button-1>", _on_double_model)

    # 双击 provider = 编辑；右键 provider / model = 上下文菜单
    prov_tree.bind("<Double-Button-1>", lambda _e: _edit_provider())

    def _prov_menu(event):
        # 右键：先选中光标下的行，再弹菜单
        iid = prov_tree.identify_row(event.y)
        if not iid:
            return
        prov_tree.selection_set(iid)
        prov_tree.focus(iid)
        menu = tk.Menu(win, tearoff=0, font=(FONT_UI, 10))
        menu.add_command(label=_t("mm.edit_provider"), command=_edit_provider)
        menu.add_command(label=_t("mm.add"), command=_add_model)
        menu.add_command(label=_t("mm.delete"), command=_del_provider)
        menu.tk_popup(event.x_root, event.y_root)

    def _model_menu(event):
        iid = model_tree.identify_row(event.y)
        if not iid:
            return
        model_tree.selection_set(iid)
        model_tree.focus(iid)
        menu = tk.Menu(win, tearoff=0, font=(FONT_UI, 10))
        is_cur = (app.current_model and app.current_model.key == iid)
        menu.add_command(label=_t("mm.use") if not is_cur else _t("mm.in_use"),
                         command=_on_double_model,
                         state=("disabled" if is_cur else "normal"))
        menu.add_command(label=_t("mm.edit"), command=_edit_model)
        menu.add_command(label=_t("mm.delete"), command=_del_model)
        menu.tk_popup(event.x_root, event.y_root)

    prov_tree.bind("<Button-3>", _prov_menu)
    model_tree.bind("<Button-3>", _model_menu)

    # ============== 按钮动作 ==============
    def _edit_provider():
        pid = state["selected_pid"]
        if not pid:
            app._set_status(_t("mm.pick_provider"))
            return
        _edit_provider_dialog(app, win, pid, _after_change)

    def _del_provider():
        from tkinter import messagebox
        pid = state["selected_pid"]
        if not pid:
            app._set_status(_t("mm.pick_provider"))
            return
        # 找到该 provider 的模型数
        data = config._load_models_data()
        prov = next((p for p in data.get("providers", [])
                     if p.get("id") == pid), None)
        if prov is None:
            app._set_status(_t("del_provider.missing", id=pid))
            return
        n_models = len(prov.get("models", []))
        pname = prov.get("name", "") or pid
        if not messagebox.askyesno(
                _t("mm.del_title"),
                _t("del_provider.confirm", name=pname, n=n_models),
                parent=win):
            return
        if config.delete_provider(pid):
            state["selected_pid"] = None
            state["selected_model_key"] = None
            _after_change(_t("del_provider.deleted", name=pname))
        else:
            app._set_status(_t("del_provider.missing", id=pid))

    def _add_model():
        pid = state["selected_pid"]
        if not pid:
            app._set_status(_t("mm.pick_provider"))
            return
        _add_dialog(app, win, _after_change, target_pid=pid)

    def _edit_model():
        key = state["selected_model_key"]
        if not key:
            app._set_status(_t("mm.pick_model"))
            return
        m = app.model_map.get(key)
        if m:
            _edit_dialog(app, win, m, _after_change)

    def _del_model():
        from tkinter import messagebox
        key = state["selected_model_key"]
        if not key:
            app._set_status(_t("mm.pick_model"))
            return
        m = app.model_map.get(key)
        if m is None:
            return
        if not messagebox.askyesno(_t("mm.del_title"),
                                   _t("mm.del_confirm",
                                      name=m.display_name),
                                   parent=win):
            return
        if config.remove_model(key):
            state["selected_model_key"] = None
            _after_change(_t("mm.deleted", name=m.display_name))
        else:
            app._set_status(_t("mm.del_missing"))

    # 默认选中：当前 model 所属的 provider
    if app.current_model:
        state["selected_pid"] = app.current_model.key.split("/", 1)[0]
        state["selected_model_key"] = app.current_model.key
    _reload_providers()
    _update_button_state()
    _make_modal(win, app.root)


def _add_dialog(app, parent, on_done, target_pid: str = "custom"):
    """添加模型：一个端点 + 密钥 + 多个模型 ID（每行一个）。

    target_pid: 新模型归属的 provider id；默认 "custom"。
                 当 target_pid 已有 provider 时，端点/密钥/类型随 provider
                 （只显示灰色提示条，不再重复出现输入框）。
    """
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    REASONING_CHOICES = ui.REASONING_CHOICES
    _fetch_openai_models = ui._fetch_openai_models
    _make_modal = ui._make_modal

    # 目标 provider 已存在 → 端点/密钥/类型固定为 provider 的值
    provider = (config.get_provider(target_pid)
                if target_pid and target_pid != "custom" else None)

    # 找目标 provider 的预填值（provider dict 优先，app.models 兜底）；
    # 无任何来源时留空——不预填示例端点，避免误导
    prefill_url = ""
    prefill_key = ""
    prefill_api_type = "openai_compatible"
    if provider:
        prefill_url = (provider.get("base_url") or "").rstrip("/")
        prefill_key = provider.get("api_key") or ""
        prefill_api_type = provider.get("api_type") or prefill_api_type
    else:
        for m in app.models:
            if m.key.split("/", 1)[0] == target_pid:
                prefill_url = m.base_url or ""
                prefill_key = m.api_key if m.api_key != "local-noauth" else ""
                prefill_api_type = getattr(m, "api_type", "openai_compatible") \
                    or "openai_compatible"
                break

    win = tk.Toplevel(parent)
    win.configure(bg=theme.PANEL)
    title = _t("dlg.add_model")
    if target_pid != "custom":
        title = f"{title} — {target_pid}"
    win.title(title)
    win.geometry("600x560" if provider else "600x680")
    win.transient(parent)

    url_entry = None
    key_entry = None
    if provider:
        # 已有 provider：端点/密钥/类型不重复出现，只读提示条代替
        tk.Label(win, text=_t("add.endpoint_fixed",
                              url=prefill_url, api=prefill_api_type),
                 font=(FONT_UI, 9), fg="#666666", wraplength=560,
                 justify="left").pack(anchor="w", padx=16, pady=(12, 2))
    else:
        tk.Label(win, text=_t("add.base_url"),
                 font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(12, 2))
        url_entry = tk.Entry(win, font=(FONT_MONO, 10))
        url_entry.pack(fill="x", padx=16)
        url_entry.insert(0, prefill_url)

        tk.Label(win, text=_t("add.api_key"),
                 font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(10, 2))
        key_entry = tk.Entry(win, font=(FONT_MONO, 10), show="*")
        key_entry.pack(fill="x", padx=16)

    tk.Label(win, text=_t("add.ids"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(10, 2))
    ids_text = tk.Text(win, height=6, font=(FONT_MONO, 10), wrap="none")
    ids_text.pack(fill="both", expand=True, padx=16)

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

    tk.Label(win, text=_t("add.context_window"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(8, 0))
    ctx_entry = tk.Entry(win, font=(FONT_MONO, 10))
    ctx_entry.pack(fill="x", padx=16)

    tk.Label(win, text=_t("add.max_tokens"),
             font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(8, 0))
    mt_entry = tk.Entry(win, font=(FONT_MONO, 10))
    mt_entry.pack(fill="x", padx=16)
    tk.Label(win, text=_t("add.tokens_hint"),
             font=(FONT_UI, 9), fg="#666666").pack(anchor="w", padx=16)

    api_type_var = tk.StringVar(value=prefill_api_type)
    if not provider:
        tk.Label(win, text=_t("add.api_type"),
                 font=(FONT_UI, 10)).pack(anchor="w", padx=16, pady=(8, 0))
        ttk.Combobox(win, textvariable=api_type_var,
                     values=("openai_compatible", "anthropic"),
                     state="readonly", font=(FONT_UI, 10)).pack(fill="x",
                                                                padx=16)
        tk.Label(win, text=_t("add.api_type_hint"),
                 font=(FONT_UI, 9), fg="#666666").pack(anchor="w", padx=16)

    msg = tk.Label(win, text="", font=(FONT_UI, 9), fg="red")
    msg.pack(anchor="w", padx=16)

    def _fetch():
        """调用端点 /models 获取支持的模型列表，自动填入下方文本框。"""
        base_url = (url_entry.get().strip().rstrip("/") if url_entry
                    else prefill_url)
        api_key = key_entry.get().strip() if key_entry else prefill_key
        api_type = api_type_var.get().strip() or "openai_compatible"
        if not base_url:
            msg.config(text=_t("add.base_first"), fg="red")
            return
        msg.config(text=_t("add.fetching"), fg="#2563eb")
        btn_fetch.config(state="disabled")

        def _worker():
            try:
                ids = _fetch_openai_models(base_url, api_key, api_type=api_type)
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
    # anthropic 端点也尝试拉取（x-api-key 鉴权；不支持 listing 的端点会报错提示）
    btn_fetch.pack(pady=(8, 0))

    def _save():
        base_url = (url_entry.get().strip().rstrip("/") if url_entry
                    else prefill_url)
        api_key = key_entry.get().strip() if key_entry else prefill_key
        model_ids = [l for l in ids_text.get("1.0", "end").splitlines() if l.strip()]
        if not base_url or not model_ids:
            msg.config(text=_t("add.require"))
            return
        try:
            ctx = int(ctx_entry.get().strip() or 0)
            mt = int(mt_entry.get().strip() or 0)
        except ValueError:
            msg.config(text=_t("add.fail", e="context/max tokens 必须是整数"))
            return
        try:
            added = config.add_custom_model(
                model_ids, base_url, api_key,
                vision=vision_var.get(),
                reasoning_effort=reasoning_var.get().strip(),
                context_window=ctx, max_tokens=mt,
                api_type=api_type_var.get().strip() or "openai_compatible",
                provider_id=target_pid)
            on_done(_t("add.done", n=len(added), url=base_url))
            win.destroy()
        except Exception as e:  # noqa: BLE001
            msg.config(text=_t("add.fail", e=e))

    tk.Button(win, text=_t("btn.save"), command=_save, width=12).pack(pady=12)
    _make_modal(win, parent)


def _edit_dialog(app, parent, m, on_done):
    """编辑已有模型：显示名称 / 模型 ID / 识图 / 推理等级 / 上下文 / 最大输出。

    base_url / API Key / API 类型是 provider 级配置，
    在「编辑 Provider」里改，这里不再出现。
    """
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    REASONING_CHOICES = ui.REASONING_CHOICES
    _fetch_openai_models = ui._fetch_openai_models
    _make_modal = ui._make_modal

    win = tk.Toplevel(parent)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.edit_model", name=m.display_name))
    win.geometry("600x520")
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

    vision_var = tk.BooleanVar(value=m.vision)
    tk.Checkbutton(win, text=_t("edit.vision"),
                   variable=vision_var,
                   font=(FONT_UI, 10)).grid(
        row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 0))

    reasoning_var = tk.StringVar(value=m.reasoning_effort)
    tk.Label(win, text=_t("edit.reasoning"),
             font=(FONT_UI, 10)).grid(
        row=3, column=0, sticky="w", padx=(16, 4), pady=(4, 0))
    ttk.Combobox(win, textvariable=reasoning_var, values=REASONING_CHOICES,
                 state="readonly", font=(FONT_UI, 10), width=24).grid(
        row=3, column=1, sticky="w", padx=(0, 16))
    tk.Label(win, text=_t("edit.reasoning_hint"),
             font=(FONT_UI, 9), fg="#666666").grid(
        row=4, column=1, sticky="w", padx=(0, 16), pady=(2, 0))

    tk.Label(win, text=_t("edit.context_window"),
             font=(FONT_UI, 10)).grid(
        row=5, column=0, sticky="w", padx=(16, 4), pady=(4, 0))
    ctx_entry = tk.Entry(win, font=(FONT_MONO, 10))
    ctx_entry.grid(row=5, column=1, sticky="ew", padx=(0, 16))
    ctx_entry.insert(0, str(m.context_window or 0))

    tk.Label(win, text=_t("edit.max_tokens"),
             font=(FONT_UI, 10)).grid(
        row=6, column=0, sticky="w", padx=(16, 4), pady=(4, 0))
    mt_entry = tk.Entry(win, font=(FONT_MONO, 10))
    mt_entry.grid(row=6, column=1, sticky="ew", padx=(0, 16))
    mt_entry.insert(0, str(m.max_tokens or 0))
    tk.Label(win, text=_t("edit.tokens_hint"),
             font=(FONT_UI, 9), fg="#666666").grid(
        row=7, column=1, sticky="w", padx=(0, 16), pady=(2, 0))

    msg = tk.Label(win, text="", font=(FONT_UI, 9), fg="red")
    msg.grid(row=8, column=0, columnspan=2, sticky="w", padx=16)

    # provider 级端点/密钥：取当前持久化配置（fetch 拉模型列表用）
    prov = config.get_provider(m.key.split("/", 1)[0]) or {}
    prov_url = (prov.get("base_url") or m.base_url or "").strip().rstrip("/")
    prov_key = prov.get("api_key", m.api_key) or ""
    is_anthropic = ((prov.get("api_type")
                     or getattr(m, "api_type", "")
                     or "") == "anthropic")

    def _fetch():
        """获取当前端点的模型列表：补齐 provider 缺失项，并弹出列表点选。"""
        base_url = prov_url
        api_key = prov_key if prov_key != "local-noauth" else ""
        if not base_url:
            msg.config(text=_t("add.base_first"), fg="red")
            return
        msg.config(text=_t("edit.fetching"), fg="#2563eb")
        fetch_btn.config(state="disabled")

        def _worker():
            try:
                ids = _fetch_openai_models(
                    base_url, api_key,
                    api_type="anthropic" if is_anthropic else "openai_compatible")
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
    # anthropic 端点也尝试拉取（x-api-key 鉴权；不支持 listing 的端点会报错提示）
    fetch_btn.grid(row=9, column=0, columnspan=2, sticky="w", padx=16,
                   pady=(8, 0))

    def _save():
        try:
            old_key = m.key
            try:
                ctx = int(ctx_entry.get().strip() or 0)
                mt = int(mt_entry.get().strip() or 0)
            except ValueError:
                msg.config(text="context/max tokens 必须是整数")
                return
            # 端点/密钥/协议是 provider 级配置，这里不动（None = 保持原值）
            mc = config.update_model(
                old_key,
                model_id=id_entry.get().strip(),
                display_name=name_entry.get().strip(),
                vision=vision_var.get(),
                reasoning_effort=reasoning_var.get().strip(),
                context_window=ctx, max_tokens=mt)
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
        row=10, column=0, columnspan=2, pady=14)
    _make_modal(win, parent)
