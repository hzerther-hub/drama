# -*- coding: utf-8 -*-
"""漫画分格工作台：huobao comic_board 式（分格列表 + 镜像形象 + 单格出图）。

入口：/novel drama comicboard N → show(app, ch)。
数据来自 dramavideo 漫画支线产物约定：漫画分格/第N章.json + N-XX.png，
资产漫画镜像写 cast.json 的 comic_path（剧模式主图不动）。
所有生成在 daemon 线程执行，完成后刷新状态。

路径安全：一律 pathlib 构造 + is_file 判断，不拼不可信字符串。
"""

from __future__ import annotations

import json
import pathlib
import threading

import tkinter as tk
from tkinter import ttk

import dramavideo
from i18n import t as _t
import theme


def build_rows(panels: list, comic_dir: str, ch: int) -> list:
    """纯函数：分格 JSON → 格行（含出图在盘状态）。测试直接覆盖。"""
    base = pathlib.Path(comic_dir)
    rows = []
    for i, p in enumerate(panels, 1):
        img_ok = (base / f"{ch}-{i:02d}.png").is_file()
        rows.append({"i": i,
                     "title": str(p.get("title", "") or "")[:24],
                     "img_ok": img_ok,
                     "status": "✓完成" if img_ok else "待出图"})
    return rows


def panels_path(state: dict, ch: int) -> pathlib.Path:
    return (pathlib.Path(dramavideo._book_dir(state))
            / dramavideo._COMIC_DIR / f"第{ch}章.json")


def load_panels(state: dict, ch: int) -> list:
    try:
        data = json.loads(panels_path(state, ch).read_text(encoding="utf-8"))
    except Exception:                  # noqa: BLE001  无分格/编码坏
        return []
    return data if isinstance(data, list) else []


def show(app, ch: int = 0):
    """打开漫画分格工作台（chapter=0 时自动选第一章）。"""
    import ui  # 延迟导入：字体/共享 helper
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    pipe = getattr(app, "_novel_pipe", None)
    state = getattr(pipe, "state", None) if pipe else None
    chapters = [c for c in (state or {}).get("chapters", [])
                if c.get("text")]
    if not state or not chapters:
        app._set_status(_t("novel.no_chapters"))
        return

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.PANEL)
    win.title(_t("cb.title"))
    win.geometry("920x620")
    ui._make_modal(win, app.root)

    top = tk.Frame(win, bg=theme.PANEL)
    top.pack(fill="x", padx=12, pady=(10, 4))
    tk.Label(top, text=_t("cb.chapter"), font=(FONT_UI, 10),
             bg=theme.PANEL).pack(side="left")
    ch_var = tk.StringVar(value=str(ch or chapters[0]["idx"]))
    box = ttk.Combobox(top, textvariable=ch_var, state="readonly", width=6,
                       font=(FONT_MONO, 10),
                       values=[str(c["idx"]) for c in chapters])
    box.pack(side="left", padx=(6, 10))

    status_lbl = tk.Label(win, text="", font=(FONT_UI, 9), fg="#64748b",
                          bg=theme.PANEL)
    status_lbl.pack(fill="x", padx=12)
    busy = {"on": False}

    cols = ("i", "title", "desc", "img", "status")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=11)
    for cid, txt, w in (("i", _t("cb.panel"), 50),
                        ("title", _t("vb.desc"), 160),
                        ("desc", _t("cb.content"), 480),
                        ("img", _t("cb.image"), 60),
                        ("status", _t("vb.status"), 80)):
        tree.heading(cid, text=txt)
        tree.column(cid, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=12, pady=(6, 2))

    def current_ch() -> int:
        try:
            return int(ch_var.get())
        except (TypeError, ValueError):
            return chapters[0]["idx"]

    def comic_dir() -> str:
        return str(pathlib.Path(dramavideo._book_dir(state))
                   / dramavideo._COMIC_DIR)

    def _reload_rows():
        panels = load_panels(state, current_ch())
        rows = build_rows(panels, comic_dir(), current_ch())
        tree.delete(*tree.get_children())
        if not rows:
            tree.insert("", "end", iid="hint", values=(
                "", "", _t("cb.hint_panels").format(ch=current_ch()), "", ""))
            return rows
        for i, r in enumerate(rows, 1):
            tree.insert("", "end", iid=str(r["i"]),
                        values=(f"第{r['i']:02d}格", r["title"],
                                str(panels[i - 1].get("description", ""))[:120],
                                "✓" if r["img_ok"] else "—", r["status"]))
        return rows

    ops = tk.Frame(win, bg=theme.PANEL)
    ops.pack(fill="x", padx=12)

    def selected_i():
        sel = tree.selection()
        try:
            return int(sel[0]) if sel else 0
        except (TypeError, ValueError):
            return 0

    def _spawn(label, fn):
        if busy["on"]:
            status_lbl.config(text=_t("vb.busy"), fg="#d97706")
            return
        busy["on"] = True
        status_lbl.config(text=f"⏳ {label}…", fg="#d97706")

        def run():
            try:
                fn()
            except Exception as e:     # noqa: BLE001
                msg = str(e).splitlines()[-1][:120]
                app.root.after(0, lambda: status_lbl.config(
                    text=f"❌ {msg}", fg="#dc2626"))
            finally:
                app.root.after(0, lambda: (
                    _reload_rows(), _reload_assets(), status_lbl.config(
                        text=f"✓ {label} 完成", fg="#16a34a")))

        threading.Thread(target=run, daemon=True).start()

    def load_cast():
        cast_path = (pathlib.Path(dramavideo._book_dir(state))
                     / "短剧资产" / "cast.json")
        try:
            return json.loads(cast_path.read_text(encoding="utf-8")), str(cast_path)
        except Exception:              # noqa: BLE001  无 cast
            return {}, str(cast_path)

    def save_cast(cast, cast_path):
        pathlib.Path(cast_path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(cast_path).write_text(
            json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")

    def do_panels(redo):
        ch = current_ch()
        chp = next((c for c in chapters if c["idx"] == ch), None)
        if chp is None:
            status_lbl.config(text=_t("novel.no_chapters"), fg="#d97706")
            return
        cast, cast_path = load_cast()
        _spawn(_t("cb.gen_panels"), lambda: (
            dramavideo.build_comic_panels(state, chp, cast, redo=redo),
            save_cast(cast, cast_path)))

    def do_panel_image(i, force):
        ch = current_ch()
        panels = load_panels(state, ch)
        if not 0 < i <= len(panels):
            status_lbl.config(text=_t("cb.pick_panel"), fg="#d97706")
            return
        cast, cast_path = load_cast()
        _spawn(_t("cb.gen_img"), lambda: (
            dramavideo.comic_panel_image(state, cast, panels[i - 1],
                                         ch, i, force=force),
            save_cast(cast, cast_path)))

    def do_missing():
        ch = current_ch()
        panels = load_panels(state, ch)
        cast, cast_path = load_cast()
        todo = [i for i, p in enumerate(panels, 1)
                if not (pathlib.Path(comic_dir()) / f"{ch}-{i:02d}.png").is_file()]

        def work():
            for i in todo:
                dramavideo.comic_panel_image(state, cast, panels[i - 1],
                                             ch, i, force=False)
            save_cast(cast, cast_path)

        _spawn(_t("cb.gen_missing") if todo else _t("vb.refresh"), work)

    # ---- 资产漫画镜像区 ----
    tk.Label(win, text=_t("cb.mirror_assets"), font=(FONT_UI, 11, "bold"),
             bg=theme.PANEL).pack(anchor="w", padx=12, pady=(8, 2))
    asset_list = ttk.Treeview(win, columns=("n", "s"), show="headings",
                              height=4)
    asset_list.heading("n", text=_t("vb.name"))
    asset_list.heading("s", text=_t("cb.mirror_status"))
    asset_list.column("n", width=240)
    asset_list.column("s", width=300)
    asset_list.pack(fill="x", padx=12)

    def _reload_assets():
        cast, _ = load_cast()
        asset_list.delete(*asset_list.get_children())
        for name, info in cast.items():
            if str(name).startswith("_") or not isinstance(info, dict):
                continue
            ok = bool(info.get("comic_path")) and pathlib.Path(
                str(info["comic_path"])).is_file()
            asset_list.insert("", "end", values=(
                name, "✓ " + _t("cb.mirror_done") if ok
                else _t("cb.mirror_pending")))
        if not cast:
            asset_list.insert("", "end", values=(
                "（还没有资产——先执行 /novel drama assets）", ""))

    # ---- 底部按钮 ----
    btns = tk.Frame(win, bg=theme.PANEL)
    btns.pack(fill="x", padx=12, pady=(6, 10))
    ui._flat_button(btns, _t("cb.gen_panels"),
                    lambda: do_panels(False)).pack(side="left")
    ui._flat_button(btns, _t("cb.repanel"),
                    lambda: do_panels(True)).pack(side="left", padx=(8, 0))
    ui._flat_button(btns, _t("cb.gen_img"),
                    lambda: do_panel_image(selected_i(), False)).pack(
        side="left", padx=(8, 0))
    ui._flat_button(btns, _t("cb.regenerate"),
                    lambda: do_panel_image(selected_i(), True)).pack(
        side="left", padx=(8, 0))
    ui._flat_button(btns, _t("cb.gen_missing"),
                    do_missing).pack(side="left", padx=(8, 0))
    ui._flat_button(btns, _t("vb.refresh"),
                    lambda: (_reload_rows(), _reload_assets())).pack(
        side="left", padx=(8, 0))

    box.bind("<<ComboboxSelected>>", lambda e: (
        _reload_rows(), _reload_assets()))
    _reload_rows()
    _reload_assets()
