# -*- coding: utf-8 -*-
"""媒体生成服务面板：图像 / 视频后端的可视化配置（产品客户入口）。

配置落盘 models.json 的 "media" 段（config.get_media / set_media），
优先级介于环境变量与供应商配置之间。后端协议：
  图像 auto（探测）/ comfyui / a1111 / openai（云端 OpenAI 兼容，含即梦生图）
  视频 auto（探测）/ agnes / ark（火山即梦 Seedance）
入口：/media 命令 → show(app)。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config
from i18n import t as _t
import theme

_IMAGE_KINDS = ("auto", "comfyui", "a1111", "openai")
_VIDEO_KINDS = ("auto", "agnes", "ark")
_FIELDS = ("base_url", "model", "api_key")


def _section(win, title_key: str, section: str, kinds, hints):
    """构建一个后端配置区块，返回 (save, clear, widgets)。"""
    import ui  # 延迟导入：字体与共享 helper
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    cur = config.get_media().get(section) or {}

    tk.Label(win, text=_t(title_key), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 2))

    grid = tk.Frame(win, bg=theme.PANEL)
    grid.pack(anchor="w", padx=16)
    rows = {}
    for i, key in enumerate(_FIELDS):
        tk.Label(grid, text=_t(f"media.{key}"), font=(FONT_UI, 10)
                 ).grid(row=i, column=0, sticky="w", pady=2)
        ent = tk.Entry(grid, width=46, font=(FONT_MONO, 10),
                       show="*" if key == "api_key" else "")
        ent.insert(0, str(cur.get(key, "") or ""))
        ent.grid(row=i, column=1, sticky="w", padx=(8, 0), pady=2)
        rows[key] = ent

    kind_row = tk.Frame(grid, bg=theme.PANEL)
    kind_row.grid(row=len(_FIELDS), column=0, columnspan=2, sticky="w",
                  pady=(4, 0))
    tk.Label(kind_row, text=_t("media.kind"), font=(FONT_UI, 10)
             ).pack(side="left")
    kind_var = tk.StringVar(value=str(cur.get("kind", "") or "auto"))
    box = ttk.Combobox(kind_row, textvariable=kind_var, values=kinds,
                       state="readonly", width=10, font=(FONT_MONO, 10))
    box.pack(side="left", padx=(8, 10))
    tk.Label(kind_row, text=hints, font=(FONT_UI, 9), fg="#64748b"
             ).pack(side="left")

    def save():
        cfg = {k: rows[k].get() for k in _FIELDS}
        cfg["kind"] = "" if kind_var.get() == "auto" else kind_var.get()
        config.set_media(section, cfg)

    def clear():
        for k in _FIELDS:
            rows[k].delete(0, "end")
        kind_var.set("auto")
        config.set_media(section, None)

    return save, clear


def _jev_section(win):
    """浏览器智能体（jev-ultrafast）配置区块，返回 (save, clear)。"""
    import ui  # 延迟导入：字体与共享 helper
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    cur = config.get_jev()

    tk.Label(win, text=_t("media.jev"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 2))
    grid = tk.Frame(win, bg=theme.PANEL)
    grid.pack(anchor="w", padx=16)
    rows = {}
    fields = (("api_key", "media.jev_api_key", True),
              ("install_dir", "media.jev_install_dir", False),
              ("model", "media.jev_model", False))
    for i, (key, label, secret) in enumerate(fields):
        tk.Label(grid, text=_t(label), font=(FONT_UI, 10)
                 ).grid(row=i, column=0, sticky="w", pady=2)
        ent = tk.Entry(grid, width=46, font=(FONT_MONO, 10),
                       show="*" if secret else "")
        ent.insert(0, str(cur.get(key, "") or ""))
        ent.grid(row=i, column=1, sticky="w", padx=(8, 0), pady=2)
        rows[key] = ent
    tk.Label(grid, text=_t("media.jev_hint"), font=(FONT_UI, 9), fg="#64748b"
             ).grid(row=len(rows), column=0, columnspan=2, sticky="w",
                    pady=(4, 0))

    def save():
        cfg = {k: rows[k].get() for k in rows}
        cfg["model"] = cfg["model"] or "jev-latest"
        config.set_jev(cfg)

    def clear():
        for k in rows:
            rows[k].delete(0, "end")
        config.set_jev(None)

    return save, clear


def _browser_section(win):
    """浏览器行为区块：可见窗口 + 代理模式，返回 (save, clear)。"""
    import ui  # 延迟导入：字体与共享 helper
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    cur = config.get_browser()

    tk.Label(win, text=_t("media.browser"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 2))
    grid = tk.Frame(win, bg=theme.PANEL)
    grid.pack(anchor="w", padx=16)

    headed = str(cur.get("headed", "") or "") in ("1", "true", "on")
    var_headed = tk.BooleanVar(value=headed)
    tk.Checkbutton(grid, text=_t("media.headed"), variable=var_headed,
                   font=(FONT_UI, 10), bg=theme.PANEL
                   ).grid(row=0, column=0, columnspan=2, sticky="w", pady=2)

    tk.Label(grid, text=_t("media.proxy"), font=(FONT_UI, 10)
             ).grid(row=1, column=0, sticky="w", pady=2)
    var_proxy = tk.StringVar(
        value=str(cur.get("proxy", "") or "system"))
    box = ttk.Combobox(grid, textvariable=var_proxy,
                       values=("system", "direct"), state="readonly",
                       width=12, font=(FONT_MONO, 10))
    box.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=2)
    tk.Label(grid, text=_t("media.proxy_hint"), font=(FONT_UI, 9),
             fg="#64748b", bg=theme.PANEL
             ).grid(row=1, column=2, sticky="w", padx=(8, 0))

    def save():
        config.set_browser({"headed": "1" if var_headed.get() else "",
                            "proxy": var_proxy.get()})

    def clear():
        var_headed.set(False)
        var_proxy.set("system")
        config.set_browser(None)

    return save, clear


def _drama_section(win):
    """短剧/漫画尺寸区块：全部下拉选框，返回 (save, clear)。"""
    import ui  # 延迟导入：字体与共享 helper
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    cur = config.get_drama()

    tk.Label(win, text=_t("media.drama"), font=(FONT_UI, 11, "bold")
             ).pack(anchor="w", padx=16, pady=(12, 2))
    grid = tk.Frame(win, bg=theme.PANEL)
    grid.pack(anchor="w", padx=16)
    choices = {
        "image_size": ("1K", "2K", "3K", "4K"),
        "image_ratio": ("9:16", "16:9", "1:1", "3:4", "4:3",
                        "2:3", "3:2", "21:9"),
        "video_size": ("", "720x1280", "1080x1920",
                       "1280x720", "1920x1080"),
        "comic_size": ("1K", "2K"),
        "comic_ratio": ("2:3", "3:4", "9:16", "1:1"),
    }
    labels = {"image_size": "media.drama_isz",
              "image_ratio": "media.drama_iratio",
              "video_size": "media.drama_vsize",
              "comic_size": "media.drama_csz",
              "comic_ratio": "media.drama_cratio"}
    rows = {}
    for i, key in enumerate(choices):
        tk.Label(grid, text=_t(labels[key]), font=(FONT_UI, 10)
                 ).grid(row=i, column=0, sticky="w", pady=2)
        var = tk.StringVar(
            value=str(cur.get(key, "") or "") or
            ("9:16" if key == "image_ratio" else
             "2:3" if key == "comic_ratio" else
             "1K" if key in ("image_size", "comic_size") else ""))
        box = ttk.Combobox(grid, textvariable=var, state="readonly",
                           values=choices[key], width=12,
                           font=(FONT_MONO, 10))
        box.grid(row=i, column=1, sticky="w", padx=(8, 0), pady=2)
        rows[key] = var

    def save():
        cfg = {k: v.get() for k, v in rows.items()}
        config.set_drama(cfg)

    def clear():
        for v in rows.values():
            v.set("")
        config.set_drama(None)

    return save, clear


def show(app):
    """媒体服务配置面板入口（/media）。"""
    import ui  # 延迟导入：读最新字体/共享 helper，避免循环依赖
    FONT_UI = ui.FONT_UI

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("media.title"))
    win.geometry("640x780")
    ui._make_modal(win, app.root)

    saves, clears = [], []
    for title, sec, kinds, hint in (
            ("media.image", "image", _IMAGE_KINDS, _t("media.hint.image")),
            ("media.video", "video", _VIDEO_KINDS, _t("media.hint.video"))):
        s, c = _section(win, title, sec, kinds, hint)
        saves.append(s)
        clears.append(c)
    js, jc = _jev_section(win)
    saves.append(js)
    clears.append(jc)
    bs, bc = _browser_section(win)
    saves.append(bs)
    clears.append(bc)
    ds, dc = _drama_section(win)
    saves.append(ds)
    clears.append(dc)

    status = tk.Label(win, text="", font=(FONT_UI, 9), fg="#16a34a",
                      bg=theme.PANEL)
    status.pack(anchor="w", padx=16, pady=(2, 0))

    def _save_all():
        try:
            for s in saves:
                s()
        except Exception as e:         # noqa: BLE001  非法输入就地提示
            status.config(text=f"❌ {e}", fg="#dc2626")
            return
        status.config(text=_t("media.saved"), fg="#16a34a")

    def _clear_all():
        for c in clears:
            c()
        status.config(text=_t("media.cleared"), fg="#64748b")

    btns = tk.Frame(win, bg=theme.PANEL)
    btns.pack(anchor="w", padx=16, pady=(8, 4))
    ui._flat_button(btns, _t("media.save"), _save_all).pack(side="left")
    ui._flat_button(btns, _t("media.clear"), _clear_all).pack(
        side="left", padx=(8, 0))

    tk.Label(win, text=_t("media.note"), font=(FONT_UI, 9), fg="#64748b",
             wraplength=580, justify="left", bg=theme.PANEL
             ).pack(anchor="w", padx=16, pady=(4, 10))
