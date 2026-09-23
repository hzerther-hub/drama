# -*- coding: utf-8 -*-
"""短剧制作台：huobao 式分阶段工作台（镜头列表 + 单镜生成/重试/时长回写）。

入口：/novel drama board N（或 🎨 菜单）→ show(app, ch)。
数据来自 dramavideo 的产物约定：短剧分镜/第N章.json、短剧关键帧/N-01.png、
短剧片段/N-01.mp4。所有生成在 daemon 线程执行，完成后刷新状态。

路径安全：一律 pathlib 构造 + is_file 判断，不拼不可信字符串。
"""

from __future__ import annotations

import json
import os
import pathlib
import threading

import tkinter as tk
from tkinter import filedialog, ttk

import dramavideo
from i18n import t as _t
import theme


def build_rows(shots: list, frame_dir: str, clip_dir: str, ch: int) -> list:
    """纯函数：分镜 JSON → 镜头行（含关键帧/片段在盘状态）。测试直接覆盖。"""
    frame_base = pathlib.Path(frame_dir)
    clip_base = pathlib.Path(clip_dir)
    rows = []
    for i, s in enumerate(shots, 1):
        frame_ok = (frame_base / f"{ch}-{i:02d}.png").is_file()
        clip_ok = (clip_base / f"{ch}-{i:02d}.mp4").is_file()
        status = "✓完成" if clip_ok else ("关键帧✓" if frame_ok else "待生成")
        rows.append({"i": i, "title": str(s.get("title", "") or "")[:24],
                     "dur": int(s.get("duration", 0) or 0),
                     "frame_ok": frame_ok, "clip_ok": clip_ok,
                     "status": status})
    return rows


def shots_path(state: dict, ch: int) -> pathlib.Path:
    base = pathlib.Path(dramavideo._book_dir(state)) / dramavideo._SHOT_DIR
    return base / f"第{ch}章.json"


def load_shots(state: dict, ch: int) -> list:
    try:
        data = json.loads(shots_path(state, ch).read_text(encoding="utf-8"))
    except Exception:                  # noqa: BLE001  无分镜/编码坏
        return []
    return data if isinstance(data, list) else []


def save_shots(state: dict, ch: int, shots: list) -> None:
    shots_path(state, ch).parent.mkdir(parents=True, exist_ok=True)
    shots_path(state, ch).write_text(
        json.dumps(shots, ensure_ascii=False, indent=2), encoding="utf-8")


def show(app, ch: int = 0):
    """打开短剧制作台（chapter=0 时自动选第一章）。"""
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
    win.title(_t("vb.title"))
    win.geometry("960x640")
    ui._make_modal(win, app.root)

    top = tk.Frame(win, bg=theme.PANEL)
    top.pack(fill="x", padx=12, pady=(10, 4))
    tk.Label(top, text=_t("vb.chapter"), font=(FONT_UI, 10),
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

    cols = ("i", "title", "dur", "frame", "clip", "status")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=14)
    for cid, txt, w in (("i", _t("vb.shot"), 50),
                        ("title", _t("vb.desc"), 380),
                        ("dur", _t("vb.dur"), 60),
                        ("frame", _t("vb.frame"), 70),
                        ("clip", _t("vb.clip"), 60),
                        ("status", _t("vb.status"), 80)):
        tree.heading(cid, text=txt)
        tree.column(cid, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=12, pady=(6, 2))

    def current_ch() -> int:
        try:
            return int(ch_var.get())
        except (TypeError, ValueError):
            return chapters[0]["idx"]

    def _reload_rows():
        rows = build_rows(load_shots(state, current_ch()),
                          str(pathlib.Path(dramavideo._book_dir(state))
                              / dramavideo._FRAME_DIR),
                          str(pathlib.Path(dramavideo._book_dir(state))
                              / dramavideo._CLIP_DIR),
                          current_ch())
        tree.delete(*tree.get_children())
        if not rows:
            tree.insert("", "end", iid="hint", values=(
                "", _t("vb.hint_shots").format(ch=current_ch()), "", "", "",
                ""))
            return rows
        for r in rows:
            tree.insert("", "end", iid=str(r["i"]),
                        values=(f"第{r['i']:02d}镜", r["title"],
                                f"{r['dur']}s" if r["dur"] else "—",
                                "✓" if r["frame_ok"] else "—",
                                "✓" if r["clip_ok"] else "—", r["status"]))
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
                    _reload_rows(), status_lbl.config(
                        text=f"✓ {label} 完成", fg="#16a34a")))

        threading.Thread(target=run, daemon=True).start()

    def load_cast():
        cast_path = pathlib.Path(dramavideo._book_dir(state)) / "短剧资产" / "cast.json"
        try:
            return json.loads(cast_path.read_text(encoding="utf-8")), str(cast_path)
        except Exception:              # noqa: BLE001  无 cast
            return {}, str(cast_path)

    def save_cast(cast, cast_path):
        pathlib.Path(cast_path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(cast_path).write_text(
            json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")

    def do_frame(force):
        ch = current_ch()
        i = selected_i()
        if not i:
            status_lbl.config(text=_t("vb.pick_shot"), fg="#d97706")
            return
        shots = load_shots(state, ch)
        if not 0 < i <= len(shots):
            status_lbl.config(text=_t("vb.pick_shot"), fg="#d97706")
            return
        shot = shots[i - 1]
        cast, cast_path = load_cast()
        cast_ch = dramavideo.effective_cast(cast, {})
        _spawn(_t("vb.frame"), lambda: (
            dramavideo.keyframe(state, cast_ch, shot, ch, i, force=force),
            save_cast(cast, cast_path)))

    def do_clip(force):
        ch = current_ch()
        i = selected_i()
        if not i:
            status_lbl.config(text=_t("vb.pick_shot"), fg="#d97706")
            return
        shots = load_shots(state, ch)
        if not 0 < i <= len(shots):
            status_lbl.config(text=_t("vb.pick_shot"), fg="#d97706")
            return
        shot = shots[i - 1]
        frame = str(pathlib.Path(dramavideo._book_dir(state))
                    / dramavideo._FRAME_DIR / f"{ch}-{i:02d}.png")
        url = ""
        try:
            urls = json.loads((pathlib.Path(dramavideo._book_dir(state))
                               / dramavideo._SHOT_DIR / "urls.json")
                              .read_text(encoding="utf-8"))
            url = urls.get(f"{ch}-{i:02d}", "")
        except Exception:              # noqa: BLE001
            pass
        cast, cast_path = load_cast()
        cast_ch = dramavideo.effective_cast(cast, {})
        _spawn(_t("vb.clip"), lambda: (
            dramavideo.clip(state, shot, url or frame, ch, i, force=force),
            save_cast(cast, cast_path)))

    # ---- 资产（角色）区 ----
    tk.Label(win, text=_t("vb.assets"), font=(FONT_UI, 11, "bold"),
             bg=theme.PANEL).pack(anchor="w", padx=12, pady=(8, 2))
    asset_list = ttk.Treeview(win, columns=("n", "s"), show="headings",
                              height=4)
    asset_list.heading("n", text=_t("vb.name"))
    asset_list.heading("s", text=_t("vb.ast_status"))
    asset_list.column("n", width=240)
    asset_list.column("s", width=300)
    asset_list.pack(fill="x", padx=12)

    def _reload_assets():
        cast, _ = load_cast()
        asset_list.delete(*asset_list.get_children())
        for name, info in cast.items():
            ok = bool(info.get("path")) and pathlib.Path(
                str(info["path"])).is_file()
            asset_list.insert("", "end", values=(
                name, "✓ " + _t("vb.done") if ok else _t("vb.pending")))
        if not cast:
            asset_list.insert("", "end", values=(
                "（还没有角色资产——先执行 /novel drama assets 生成）", ""))

    # ---- 时长回写 ----
    dur_row = tk.Frame(win, bg=theme.PANEL)
    dur_row.pack(fill="x", padx=12, pady=(6, 0))
    tk.Label(dur_row, text=_t("vb.dur_edit"), font=(FONT_UI, 10),
             bg=theme.PANEL).pack(side="left")
    dur_var = tk.StringVar(value="9")
    ttk.Spinbox(dur_row, from_=4, to=15, textvariable=dur_var, width=5,
                font=(FONT_MONO, 10)).pack(side="left", padx=(6, 10))

    def save_dur():
        ch = current_ch()
        i = selected_i()
        if not i:
            status_lbl.config(text=_t("vb.pick_shot"), fg="#d97706")
            return
        shots = load_shots(state, ch)
        if 0 < i <= len(shots):
            shots[i - 1]["duration"] = max(4, min(15, int(dur_var.get())))
            save_shots(state, ch, shots)
            status_lbl.config(text=_t("vb.dur_saved"), fg="#16a34a")
            _reload_rows()

    ui._flat_button(dur_row, _t("vb.dur_save"), save_dur).pack(side="left")

    # ---- 底部按钮 ----
    btns = tk.Frame(win, bg=theme.PANEL)
    btns.pack(fill="x", padx=12, pady=(6, 10))
    ui._flat_button(btns, _t("vb.gen_frame"),
                    lambda: do_frame(False)).pack(side="left")
    ui._flat_button(btns, _t("vb.gen_clip"),
                    lambda: do_clip(False)).pack(side="left", padx=(8, 0))
    ui._flat_button(btns, _t("vb.regenerate"),
                    lambda: do_frame(True)).pack(side="left", padx=(8, 0))
    ui._flat_button(btns, _t("vb.upload"),
                    lambda: _upload_asset(win)).pack(side="left", padx=(8, 0))
    ui._flat_button(btns, _t("vb.refresh"),
                    lambda: (_reload_rows(), _reload_assets())).pack(
        side="left", padx=(8, 0))

    def _upload_asset():
        i = selected_i()
        cast, _ = load_cast()
        names = list(cast.keys())
        if not 0 < i <= len(names):
            status_lbl.config(text=_t("vb.pick_asset"), fg="#d97706")
            return
        name = names[i - 1]
        src = filedialog.askopenfilename(
            parent=win, title=_t("vb.upload"),
            filetypes=[("PNG/JPG", "*.png *.jpg *.jpeg *.webp")])
        if not src:
            return
        _spawn(_t("vb.upload"), lambda: _do_upload(name, src))

    def _do_upload(name, src):
        cast, cast_path = load_cast()
        info = cast.get(name) or {}
        cast[name] = dramavideo.replace_asset_image(state, name, info, src)
        save_cast(cast, cast_path)

    box.bind("<<ComboboxSelected>>", lambda e: _reload_all())
    _reload_all()
