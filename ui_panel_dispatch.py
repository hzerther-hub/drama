# -*- coding: utf-8 -*-
"""模型派发设置面板：总开关 / 智排开关 + 云端目标（简单 / 高性能）下拉 + 生效状态。

(B) 收敛后派发只剩云端路由：没有「本地大脑」配置（dispatch_model 已退役），
也没有 call_model 工具——复杂任务由 ui._route_complex 把本轮换成 dispatch_pro，
识图由 config.resolve_dispatch_vision_key 在已配置目标里挑带识图的模型。

从 ui.py 拆分而来；入口 show(app)，app 为 ui.App 实例。
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk

import config
from i18n import t as _t
import theme


def _cloud_items(models) -> list:
    """云端目标候选 [(显示文本, model key)]。

    跳过 gpulocal 遗留条目（本地功能已移除，不该再当派发目标）；
    带识图/推理能力的模型在显示名前加 👁/🧠，便于一眼区分。
    """
    out = []
    for m in models:
        if m.key.startswith("gpulocal"):
            continue
        caps = ""
        if m.vision:
            caps += "👁"
        if getattr(m, "reasoning", False):
            caps += "🧠"
        out.append((((caps + " ") if caps else "") + m.display_name, m.key))
    return out


def show(app):
    import ui  # 延迟导入：读最新字体/共享 helper，避免循环依赖
    FONT_UI = ui.FONT_UI

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("dlg.dispatch"))
    win.geometry("620x330")
    ui._make_modal(win, app.root)

    cfg = config.get_dispatch_config()

    # ---- 开关行 ----
    sw_frame = tk.Frame(win)
    sw_frame.pack(anchor="w", padx=16, pady=(12, 2))
    master_var = tk.BooleanVar(value=cfg["model_dispatch"])
    smart_var = tk.BooleanVar(value=cfg["dispatch_smart"])
    tk.Checkbutton(sw_frame, text=_t("dispatch.master"), variable=master_var,
                   font=(FONT_UI, 10, "bold")).pack(anchor="w")
    tk.Checkbutton(sw_frame, text=_t("dispatch.smart"), variable=smart_var,
                   font=(FONT_UI, 10)).pack(anchor="w")

    # ---- 云端目标：简单 / 高性能 ----
    tk.Label(win, text=_t("dispatch.cloud"),
             font=(FONT_UI, 11, "bold")).pack(anchor="w", padx=16, pady=(10, 2))

    cloud_rows = []                 # 每行：{label, var, combo, items}

    def _make_row(label):
        row = tk.Frame(win)
        row.pack(anchor="w", padx=16, pady=2)
        tk.Label(row, text=label, font=(FONT_UI, 10), width=12,
                 anchor="w").pack(side="left")
        var = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=var, state="readonly", width=36,
                             font=(FONT_UI, 10))
        combo.pack(side="left")
        info = {"label": label, "var": var, "combo": combo, "items": []}
        cloud_rows.append(info)
        return info

    row_flash = _make_row(_t("dispatch.flash"))
    row_pro = _make_row(_t("dispatch.pro"))

    _FIELD_OF = {id(row_flash): "dispatch_flash",
                 id(row_pro): "dispatch_pro"}

    def _row_key(info) -> str:
        return next((k for t, k in info["items"] if t == info["var"].get()), "")

    def _rebuild_rows(initial=False):
        """按最新模型列表重建下拉（新增/删除模型后点刷新即可重新选择）。

        initial=True 时按当前配置选中；否则保留用户已选（列表里还在的话）。
        """
        try:
            models, _def = config.load_models()      # 返回 (models, default)，须解包
        except Exception:                            # noqa: BLE001
            models = list(app.models)
        items = _cloud_items(models)
        for info in cloud_rows:
            info["items"] = items
            info["combo"]["values"] = [t for t, _ in items]
            keep = info["var"].get()
            if initial:
                cur_key = cfg[_FIELD_OF[id(info)]]
                cur_t = next((t for t, k in items if k == cur_key), "")
                if cur_t:
                    info["combo"].set(cur_t)
                elif cur_key:
                    # 配置里的 key 不在候选里（模型被删/未装）→ 附加为当前项
                    m = config.find_model(cur_key)
                    info["items"] = items + [(m.display_name if m else cur_key,
                                              cur_key)]
                    info["combo"]["values"] = [t for t, _ in info["items"]]
                    info["combo"].set(info["items"][-1][0])
                elif items:
                    info["combo"].set(items[0][0])
            elif not any(t == keep for t, _ in items):
                info["combo"].set(items[0][0] if items else "")

    _rebuild_rows(initial=True)

    # ---- 生效状态行 ----
    status_lbl = tk.Label(win, font=(FONT_UI, 10), anchor="w", justify="left")
    status_lbl.pack(anchor="w", padx=16, pady=(4, 0))

    def _refresh_status():
        """刷新生效状态：纯云端派发，只看总开关（目标由下拉决定路由去向）。"""
        if not master_var.get():
            status_lbl.config(text=_t("dispatch.off"), fg="#94a3b8")
            return
        key = _row_key(row_pro) or _row_key(row_flash)
        mc = config.find_model(key) if key else None
        name = mc.display_name if mc else (key or "?")
        status_lbl.config(text=_t("dispatch.active_cloud", name=name),
                          fg="#16a34a")

    master_var.trace_add("write", lambda *_: _refresh_status())
    _refresh_status()

    hint = tk.Label(win, font=(FONT_UI, 9), fg="#64748b", anchor="w",
                    justify="left", text=_t("dispatch.hint"))
    hint.pack(anchor="w", padx=16, pady=(8, 0))

    msg = tk.Label(win, font=(FONT_UI, 9), fg="red", anchor="w")
    msg.pack(anchor="w", padx=16, pady=(6, 0))

    # ---- 按钮 ----
    bar = tk.Frame(win)
    bar.pack(side="bottom", pady=12)

    def _save():
        """写配置：(B) 收敛后只有 总开关/智排/两个云端目标 四个字段。"""
        try:
            config.set_model_dispatch(master_var.get())
            config.set_dispatch_smart(smart_var.get())
            config.set_dispatch_flash(_row_key(row_flash))
            config.set_dispatch_pro(_row_key(row_pro))
        except Exception as e:       # noqa: BLE001
            msg.config(text="⚠ " + _t("dispatch.save_fail", e=e), fg="red")
            return
        msg.config(text="✅ " + _t("dispatch.saved"), fg="#16a34a")
        app._set_status(_t("dispatch.saved"))
        if hasattr(app, "_update_dispatch_btn"):
            app._update_dispatch_btn()
        _refresh_status()
        try:                         # 保存成功即自动关闭（失败分支已 return）
            win.after(700, win.destroy)
        except Exception:            # noqa: BLE001
            pass

    def _refresh():
        # 重读模型列表（下拉重建）+ 生效状态
        _rebuild_rows(initial=False)
        _refresh_status()

    tk.Button(bar, text=_t("btn.save"), command=_save, width=10
              ).pack(side="left", padx=6)
    tk.Button(bar, text=_t("dispatch.refresh"), command=_refresh, width=10
              ).pack(side="left", padx=6)
    tk.Button(bar, text=_t("btn.close"), command=win.destroy, width=10
              ).pack(side="left", padx=6)
