# -*- coding: utf-8 -*-
"""模型派发设置面板：总开关 / 智排开关、本地大脑（dispatch_model）下拉
（带 ●/◐/○ 状态点）、三个云端目标（简单 / 高性能 / 识图）下拉、生效状态。

从 ui.py 拆分而来；入口 show(app)，app 为 ui.App 实例。
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk

import config
import localmodels
from i18n import t as _t
import theme


def _dot_of(name: str, cache: dict) -> str:
    """本地模型状态点：● 运行健康 / ◐ 启动中 / ○ 未运行。"""
    state, healthy = cache.get(name, ("unknown", False))
    return "●" if healthy else ("◐" if state == "activating" else "○")


def show(app):
    import ui  # 延迟导入：读最新字体/共享 helper，避免循环依赖
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.dispatch"))
    win.geometry("620x440")
    ui._make_modal(win, app.root)

    cfg = config.get_dispatch_config()
    all_models = list(app.models)

    # ---- 开关行 ----
    sw_frame = tk.Frame(win)
    sw_frame.pack(anchor="w", padx=16, pady=(12, 2))
    master_var = tk.BooleanVar(value=cfg["model_dispatch"])
    smart_var = tk.BooleanVar(value=cfg["dispatch_smart"])
    tk.Checkbutton(sw_frame, text=_t("dispatch.master"), variable=master_var,
                   font=(FONT_UI, 10, "bold")).pack(anchor="w")
    tk.Checkbutton(sw_frame, text=_t("dispatch.smart"), variable=smart_var,
                   font=(FONT_UI, 10)).pack(anchor="w")

    # ---- 本地大脑（dispatch_model）：本地模型下拉 + 状态点 ----
    tk.Label(win, text=_t("dispatch.brain"),
             font=(FONT_UI, 11, "bold")).pack(anchor="w", padx=16, pady=(10, 2))

    # 候选：gpulocal 注册表优先（带实时状态点），不可用时回退已同步的 gpulocal 模型
    brain_items = []            # [(显示文本, model key)]
    status_cache = {}           # 显示名 → (state, healthy)
    if localmodels and localmodels.available():
        for name, lcfg in localmodels.list_models().items():
            try:
                state, healthy = localmodels.status_of(lcfg)
            except Exception:
                state, healthy = "unknown", False
            status_cache[name] = (state, healthy)
            brain_items.append((f"{_dot_of(name, status_cache)} {name}"
                                f"  [:{lcfg.get('port', '?')}]",
                                localmodels.key_of(name)))
    if not brain_items:
        for m in all_models:
            if m.key.startswith("gpulocal"):
                brain_items.append((f"○ {m.display_name}", m.key))
    if not brain_items:
        brain_items.append(("○ " + _t("dispatch.none_local"), ""))

    brain_frame = tk.Frame(win)
    brain_frame.pack(anchor="w", padx=16)
    brain_var = tk.StringVar()
    brain_combo = ttk.Combobox(brain_frame, textvariable=brain_var, state="readonly",
                               width=44, font=(FONT_UI, 10), values=[t for t, _ in brain_items])
    brain_combo.pack(side="left")
    cur_brain_key = cfg["dispatch_model"]
    cur = next((t for t, k in brain_items if k == cur_brain_key), None)
    if cur is None and cur_brain_key:
        m = config.find_model(cur_brain_key)
        cur = f"○ {m.display_name if m else cur_brain_key}"
        brain_items.insert(0, (cur, cur_brain_key))
        brain_combo["values"] = [t for t, _ in brain_items]
    brain_combo.set(cur or brain_items[0][0])

    def _brain_key() -> str:
        t = brain_var.get()
        return next((k for tt, k in brain_items if tt == t), "")

    # 生效状态行：开关开 + 本地大脑在跑健康 → 生效（call_model 工具可用）
    status_lbl = tk.Label(win, font=(FONT_UI, 10), anchor="w", justify="left")
    status_lbl.pack(anchor="w", padx=16, pady=(4, 0))

    def _refresh_status():
        key = _brain_key()
        # 状态点在打开/刷新时实时重读
        if localmodels and localmodels.available():
            for n, lcfg in localmodels.list_models().items():
                try:
                    status_cache[n] = localmodels.status_of(lcfg)
                except Exception:
                    status_cache[n] = ("unknown", False)
        healthy = False
        if key and localmodels and localmodels.available():
            for n, lcfg in localmodels.list_models().items():
                if localmodels.key_of(n) == key:
                    healthy = status_cache.get(n, ("", False))[1]
                    dot = _dot_of(n, status_cache)
                    # 更新下拉项里的点
                    for i, (t, k) in enumerate(brain_items):
                        if k == key:
                            new_t = f"{dot} {n}  [:{lcfg.get('port', '?')}]"
                            brain_items[i] = (new_t, k)
                            brain_combo["values"] = [t for t, _ in brain_items]
                            brain_combo.set(new_t)
                    break
        # localmodels 不可用时无法验证运行状态，按未生效显示
        if not master_var.get():
            status_lbl.config(text=_t("dispatch.off"), fg="#94a3b8")
        elif not key:
            status_lbl.config(text=_t("dispatch.no_brain"), fg="#dc2626")
        elif healthy:
            status_lbl.config(text=_t("dispatch.active"), fg="#16a34a")
        else:
            status_lbl.config(text=_t("dispatch.inactive"), fg="#d97706")

    master_var.trace_add("write", lambda *_: _refresh_status())
    _refresh_status()

    # ---- 云端目标：三个下拉（简单 / 复杂 / 识图），可随模型列表变化重建 ----
    # 简单/复杂：全部云端模型（带 👁/🧠 能力图标，便于区分）；
    # 识图：只列 vision:true 的模型（必选，选了不带识图的会拦截）。
    tk.Label(win, text=_t("dispatch.cloud"),
             font=(FONT_UI, 11, "bold")).pack(anchor="w", padx=16, pady=(10, 2))

    def _cap(m) -> str:
        s = ""
        if m.vision:
            s += "👁"
        if getattr(m, "reasoning", False):
            s += "🧠"
        return (s + " ") if s else ""

    # 每行：{label, var, combo, items, vision_only}
    cloud_rows = []

    def _make_row(label, vision_only):
        row = tk.Frame(win)
        row.pack(anchor="w", padx=16, pady=2)
        tk.Label(row, text=label, font=(FONT_UI, 10), width=12,
                 anchor="w").pack(side="left")
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, state="readonly", width=36,
                             font=(FONT_UI, 10))
        combo.pack(side="left")
        info = {"label": label, "var": var, "combo": combo,
                "items": [], "vision_only": vision_only}
        cloud_rows.append(info)
        return info

    row_flash = _make_row(_t("dispatch.flash"), False)
    row_pro = _make_row(_t("dispatch.pro"), False)
    row_vision = _make_row(_t("dispatch.vision"), True)

    def _rebuild_rows(initial=False):
        """按最新模型列表重建三个下拉（新增/删除模型后点刷新即可重新选择）。

        initial=True 时按当前配置选中；否则保留用户已选（列表里还在的话）。
        """
        try:
            models, _def = config.load_models()      # 返回 (models, default)，须解包
        except Exception:
            models = all_models
        fresh = [m for m in models if not m.key.startswith("gpulocal")]
        for info in cloud_rows:
            pool = ([m for m in fresh if m.vision] if info["vision_only"]
                    else fresh)
            items = [(f"{_cap(m)}{m.display_name}", m.key) for m in pool]
            keep = info["var"].get()
            if info["vision_only"] and not items:
                items = [(_t("dispatch.no_vision_models"), "")]
            info["items"] = items
            info["combo"]["values"] = [t for t, _ in items]
            if initial:
                cur_key = cfg[_FIELD_OF[id(info)]]
                cur_t = next((t for t, k in items if k == cur_key), "")
                if cur_t:
                    info["combo"].set(cur_t)
                # 配置里的 key 不在候选里（如未标 vision）→ 附加为当前项
                elif cur_key:
                    m = config.find_model(cur_key)
                    items.insert(0, (f"{_cap(m) if m else ''}"
                                     f"{m.display_name if m else cur_key}", cur_key))
                    info["items"] = items
                    info["combo"]["values"] = [t for t, _ in items]
                    info["combo"].set(items[0][0])
                elif items:
                    info["combo"].set(items[0][0])
            else:
                # 保留已选；不在新列表则选第一项
                if keep in [t for t, _ in items] or keep == "":
                    pass
                if not any(t == keep for t, _ in items):
                    info["combo"].set(items[0][0] if items else "")

    _FIELD_OF = {id(row_flash): "dispatch_flash",
                 id(row_pro): "dispatch_pro",
                 id(row_vision): "dispatch_vision"}

    def _row_key(info) -> str:
        return next((k for t, k in info["items"] if t == info["var"].get()), "")

    _rebuild_rows(initial=True)

    hint = tk.Label(win, font=(FONT_UI, 9), fg="#64748b", anchor="w",
                    justify="left", text=_t("dispatch.hint"))
    hint.pack(anchor="w", padx=16, pady=(8, 0))

    msg = tk.Label(win, font=(FONT_UI, 9), fg="red", anchor="w")
    msg.pack(anchor="w", padx=16, pady=(6, 0))

    def _brain_running() -> bool:
        """本地大脑当前是否运行健康（面板打开时实时检查）。"""
        key = _brain_key()
        if not key or not (localmodels and localmodels.available()):
            return False
        for n, lcfg in localmodels.list_models().items():
            if localmodels.key_of(n) == key:
                try:
                    _, healthy = localmodels.status_of(lcfg)
                except Exception:
                    return False
                return bool(healthy)
        return False

    # ---- 按钮 ----
    bar = tk.Frame(win)
    bar.pack(side="bottom", pady=12)

    def _save():
        from tkinter import messagebox
        vision_key = _row_key(row_vision)
        if not vision_key:
            msg.config(text=_t("dispatch.vision_required"), fg="red")
            return
        vm = config.find_model(vision_key)
        if vm and not vm.vision:
            msg.config(text=_t("dispatch.vision_not_vision",
                               model=vm.display_name), fg="red")
            return
        # 确定保存前检查本地大脑是否已启动（不会自动拉起，只提醒）
        if master_var.get() and not _brain_running():
            key = _brain_key()
            name = next((t for t, k in brain_items if k == key), key or "?")
            if not messagebox.askyesno(
                    win, _t("dispatch.brain_not_running_q", brain=name)):
                msg.config(text=_t("dispatch.brain_not_running",
                                   brain=name), fg="#d97706")
                return
        # 写配置：异常则提示原因、不关闭
        try:
            config.set_model_dispatch(master_var.get())
            config.set_dispatch_smart(smart_var.get())
            config.set_dispatch_model(_brain_key())
            config.set_dispatch_flash(_row_key(row_flash))
            config.set_dispatch_pro(_row_key(row_pro))
            config.set_dispatch_vision(vision_key)
        except Exception as e:       # noqa: BLE001
            msg.config(text="⚠ " + _t("dispatch.save_fail", e=e), fg="red")
            return
        msg.config(text="✅ " + _t("dispatch.saved"), fg="#16a34a")
        app._set_status(_t("dispatch.saved"))
        if hasattr(app, "_update_dispatch_btn"):
            app._update_dispatch_btn()
        _refresh_status()
        # 保存成功即自动关闭（失败分支已 return，不会走到这）
        try:
            win.after(700, win.destroy)
        except Exception:            # noqa: BLE001
            pass

    def _refresh():
        # 重读模型列表（云端下拉重建）+ 本地状态点 + 生效状态
        _rebuild_rows(initial=False)
        for n, lcfg in (localmodels.list_models().items()
                        if localmodels and localmodels.available() else []):
            try:
                status_cache[n] = localmodels.status_of(lcfg)
            except Exception:
                status_cache[n] = ("unknown", False)
        _refresh_status()

    tk.Button(bar, text=_t("btn.save"), command=_save, width=10
              ).pack(side="left", padx=6)
    tk.Button(bar, text=_t("dispatch.refresh"), command=_refresh, width=10
              ).pack(side="left", padx=6)
    tk.Button(bar, text=_t("btn.close"), command=win.destroy, width=10
              ).pack(side="left", padx=6)
