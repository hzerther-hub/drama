# -*- coding: utf-8 -*-
"""风格管理面板：风格库 CRUD，默认风格，影响后续所有资产生成。

入口 show(app)：输入框（自由录入）+ 列表（预设/自定义）+ 类别标签
（3D/2D/真人/自定义）+ 「应用到此书」持久化 state["drama_style"]，
「保存为预设」→ 持久化到 models.json["globals"]["drama_styles"]（跨书可用）。
"""

from __future__ import annotations

import json
import os
import re
import tkinter as tk
from tkinter import ttk

import dramavideo
from i18n import t as _t
import theme


def _globals_path() -> str:
    return os.path.join(os.environ.get("APPDATA", "")
                        if os.name == "nt" else os.path.expanduser("~"),
                        "local-ai-studio")


def _book_state(app):
    """当前书 state；没有就从最近一本载入。"""
    import novel_chain
    p = getattr(app, "_novel_pipe", None)
    if p is None:
        p, _ = app._novel_pick("")
    if p is None:
        return None, None
    return p, novel_chain._book_dir(p.state)


def _load_globals():
    """统一风格库（dramavideo.load_style_lib）：没有就播种全部预设。"""
    styles, default, data, path = dramavideo.load_style_lib()
    glb = data.setdefault("globals", {})
    glb["drama_styles"] = styles
    glb.setdefault("default_drama_style", default)
    return data, path


def _save_globals(data, path):
    dramavideo.save_style_lib(data, path)


def show(app):
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO
    p, book = _book_state(app)
    if p is None:
        app._set_status(_t("novel.none"))
        return
    state = p.state

    data, cfg_path = _load_globals()
    glb = data["globals"]
    styles = glb["drama_styles"]                  # [{name,text,category}]
    default = glb["default_drama_style"]

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.BG)
    win.title(_t("sp.title"))
    win.geometry("780x560")
    ui._make_modal(win, app.root)

    # ---- 顶栏：当前书风格显示 + 应用 ----
    top = tk.Frame(win, bg=theme.BG)
    top.pack(fill="x", padx=14, pady=(10, 6))
    tk.Label(top, text=_t("sp.current_book"),
             font=(FONT_UI, 10), bg=theme.BG, fg=theme.MUTED
             ).pack(side="left")
    cur_var = tk.StringVar(value=state.get("drama_style") or default)
    cur_e = tk.Entry(top, textvariable=cur_var, width=44, font=(FONT_UI, 10),
                    relief="flat", bg="white", fg=theme.TEXT)
    cur_e.pack(side="left", padx=6)

    def _apply_to_book():
        v = cur_var.get().strip() or default
        state["drama_style"] = v
        try:
            p.save()
        except Exception:              # noqa: BLE001
            pass
        app._set_status(_t("sp.applied_book"))

    ui._flat_button(top, text=_t("sp.apply_book"), width=12,
                    font=(FONT_UI, 10), command=_apply_to_book
                    ).pack(side="left", padx=4)

    # ---- 列表：左侧分类目录 + 右侧风格 ----
    body = tk.Frame(win, bg=theme.BG)
    body.pack(fill="both", expand=True, padx=14)

    cats = ("全部", "内置", "2D", "3D", "真人", "自定义")
    cat_var = tk.StringVar(value="全部")
    cat_lb = tk.Listbox(body, width=12, font=(FONT_UI, 10), bg=theme.PANEL,
                       fg=theme.TEXT, relief="flat", highlightthickness=1,
                       highlightbackground=theme.BORDER, exportselection=False)
    for c in cats:
        cat_lb.insert("end", c)
    cat_lb.selection_set(0)
    cat_lb.pack(side="left", fill="y", padx=(0, 6))

    lb = tk.Listbox(body, font=(FONT_UI, 10), bg=theme.PANEL, fg=theme.TEXT,
                   relief="flat", highlightthickness=1,
                   highlightbackground=theme.BORDER, exportselection=False,
                   selectmode="extended")
    lb.pack(side="left", fill="both", expand=True)

    def _refresh_list():
        lb.delete(0, "end")
        cat = cat_var.get()
        d = glb.get("default_drama_style", "")
        for s in styles:
            if cat == "全部" or s.get("category", "自定义") == cat:
                star = "★ " if s.get("text") == d else ""
                lb.insert("end",
                          f"{star}{s.get('name','')}（{s.get('category','自定义')}）")

    cat_lb.bind("<<ListboxSelect>>", lambda e: _refresh_list())

    def _on_pick(_e=None):
        sel = lb.curselection()
        if not sel:
            return
        # 把选中项的 text 填到顶部输入框（也可用于「编辑」入口）
        s = _visible_items()[sel[0]]
        cur_var.set(s.get("text", ""))

    lb.bind("<<ListboxSelect>>", lambda e: _on_pick())

    def _visible_items():
        cat = cat_var.get()
        return [s for s in styles
                if cat == "全部" or s.get("category", "自定义") == cat]

    # ---- 底部：新增 / 编辑 / 删除 / 设为默认 ----
    foot = tk.Frame(win, bg=theme.BG)
    foot.pack(fill="x", padx=14, pady=(0, 10))
    name_e = tk.Entry(foot, width=22, font=(FONT_UI, 10),
                     relief="flat", bg="white", fg=theme.TEXT)
    name_e.insert(0, _t("sp.name_ph"))
    name_e.pack(side="left", padx=(0, 4))
    cat_box = ttk.Combobox(foot, values=("2D", "3D", "真人", "自定义"),
                          width=8, state="readonly", font=(FONT_UI, 10))
    cat_box.set("自定义")
    cat_box.pack(side="left", padx=4)
    text_e = tk.Entry(foot, font=(FONT_UI, 10), relief="flat", bg="white",
                     fg=theme.TEXT)
    text_e.insert(0, _t("sp.text_ph"))
    text_e.pack(side="left", fill="x", expand=True, padx=4)

    def _add():
        n = re.sub(r"[\\/:*?\"<>|]+", "", name_e.get().strip())
        t = text_e.get().strip()
        if not n or not t or t == _t("sp.text_ph"):
            app._set_status(_t("sp.empty"))
            return
        for s in styles:
            if s["text"] == t:
                app._set_status(_t("sp.dup"))
                return
        styles.append({"name": n, "text": t, "category": cat_box.get()})
        _save_globals(data, cfg_path)
        _refresh_list()
        app._set_status(_t("sp.added", n=n))

    def _del():
        sel = lb.curselection()
        if not sel:
            return
        # 从末尾往前删，避免下标漂移
        for i in sorted(sel, reverse=True):
            s = _visible_items()[i]
            if s in styles:
                styles.remove(s)
        _save_globals(data, cfg_path)
        _refresh_list()
        app._set_status(_t("sp.deleted", n=len(sel)))

    def _set_default():
        v = cur_var.get().strip()
        if not v:
            return
        glb["default_drama_style"] = v
        _save_globals(data, cfg_path)
        # 全局默认只影响新书——同步应用到当前书，避免「设了默认但本书没变」
        applied = False
        try:
            state["drama_style"] = v
            state["_ch_style_picked"] = True
            p.save()
            applied = True
        except Exception:              # noqa: BLE001
            pass
        _refresh_list()
        key = "sp.default_saved_book" if applied else "sp.default_saved"
        app._set_status(_t(key, n=v[:30]))

    ui._flat_button(foot, text=_t("sp.add"), width=8,
                    font=(FONT_UI, 9), command=_add).pack(side="left", padx=2)
    ui._flat_button(foot, text=_t("sp.delete"), width=8,
                    font=(FONT_UI, 9), command=_del).pack(side="left", padx=2)
    ui._flat_button(foot, text=_t("sp.set_default"), width=10,
                    font=(FONT_UI, 9), command=_set_default).pack(side="left", padx=2)

    _refresh_list()