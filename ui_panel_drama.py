# -*- coding: utf-8 -*-
"""短剧工作台：Pavo 式三步工作流（剧本大纲 → 资产库 → 分集视频）。

入口 show(app)。数据全部来自流水线 state 与 dramavideo 的磁盘产物
（短剧资产/短剧分镜/短剧关键帧/短剧片段/短剧成片），生成走 dramavideo
同一链路（文件存在即缓存）。三步均可编辑调整：
  1. 剧本大纲：大纲/世界观/故事合约/角色/每章剧本 直接改 → 写回 state+md
  2. 资产库：改外貌锚、重生成单个角色形象
  3. 分集视频：改分镜（场景/角色/时长/画面描述/台词）→ 单镜重生成 → 合成
后台线程跑生成，完事 win.after 回主线程刷新（面板规范）。
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import tkinter as tk
from tkinter import ttk

import dramavideo
from i18n import t as _t
import theme

try:
    from PIL import Image, ImageTk      # 缩略图；缺失时预览区降级为文字
except Exception:                       # noqa: BLE001
    Image = ImageTk = None


# ---------------- 小工具 ----------------

def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:                  # noqa: BLE001
        return default


def _dump_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _thumb(path, size):
    if Image is None or not os.path.exists(path):
        return None
    try:
        img = Image.open(path)
        img.thumbnail(size)
        return ImageTk.PhotoImage(img)
    except Exception:                  # noqa: BLE001
        return None


def show(app):
    import ui
    FONT_UI, FONT_MONO = ui.FONT_UI, ui.FONT_MONO

    p = getattr(app, "_novel_pipe", None)
    if p is None:
        p, _err = app._novel_pick("")
    if p is None:
        app._set_status(_t("novel.none"))
        return
    state = p.state
    import novel_chain
    book = novel_chain._book_dir(state)
    chapters = [c for c in state.get("chapters", []) if c.get("text")]
    if not chapters:
        app._set_status(_t("novel.no_chapters"))
        return

    win = tk.Toplevel(app.root)
    win.configure(bg=theme.BG)
    win.title(_t("ds.title", t=state.get("title") or state.get("pid", "")))
    win.geometry("1200x740")
    ui._make_modal(win, app.root)

    st = {"ch": chapters[0]["idx"], "shot": 0, "busy": False, "step": 3,
          "img_refs": [], "_t0": None, "_tick_id": None, "_gen_base": "",
          "_spin_i": 0}

    def _tick():
        """生成中刷新状态：「⠛ 生成中：… · Ns」盲文转圈 + 计时。"""
        tid = st.get("_tick_id")
        if tid:
            try:
                win.after_cancel(tid)
            except Exception:          # noqa: BLE001
                pass
            st["_tick_id"] = None
        if not st["busy"] or not win.winfo_exists():
            return
        el = int(time.time() - st["_t0"]) if st["_t0"] else 0
        f = theme.SPINNER[st["_spin_i"] % len(theme.SPINNER)]
        st["_spin_i"] += 1
        stat_lbl.config(text=f"{f} {st['_gen_base']} · {el}s")
        st["_tick_id"] = win.after(200, _tick)

    def status(msg, busy=False):
        st["busy"] = busy
        st["_gen_base"] = msg if busy else ""
        st["_t0"] = time.time() if busy else None
        stat_lbl.config(text=msg, fg=theme.DANGER if msg.startswith("❌")
                        else theme.MUTED)
        try:
            app._set_status(msg if busy else _t("top.ready"))
            if busy:
                app.badge_busy(_t("novel.badge_generating"))
            else:
                app.badge_done()
        except Exception:              # noqa: BLE001
            pass
        _tick()

    def _shot_paths(ch, i):
        return (os.path.join(book, dramavideo._FRAME_DIR, f"{ch}-{i:02d}.png"),
                os.path.join(book, dramavideo._CLIP_DIR, f"{ch}-{i:02d}.mp4"))

    # ---------------- 顶栏 ----------------
    top = tk.Frame(win, bg=theme.BG)
    top.pack(fill="x", padx=14, pady=(10, 4))
    tk.Label(top, text="🎬 " + (state.get("title") or ""),
             font=(FONT_UI, 13, "bold"), bg=theme.BG,
             fg=theme.TEXT).pack(side="left")
    step_btns = {}

    def _go_step(n):
        st["step"] = n
        for k, f in steps.items():
            f.pack_forget()
        steps[n].pack(fill="both", expand=True, padx=14, pady=6)
        for k, b in step_btns.items():
            b.config(bg=theme.ACCENT if k == n else theme.PANEL,
                     fg="white" if k == n else theme.TEXT)

    bar = tk.Frame(top, bg=theme.BG)
    bar.pack(side="left", padx=16)
    for n, label in ((1, "1. 剧本大纲"), (2, "2. 资产库"), (3, "3. 分集视频")):
        b = ui._flat_button(bar, text=label, width=11, font=(FONT_UI, 10),
                            command=lambda n=n: _go_step(n))
        b.pack(side="left", padx=3)
        step_btns[n] = b

    ch_var = tk.StringVar()
    ch_box = ttk.Combobox(top, textvariable=ch_var, width=10, state="readonly",
                          font=(FONT_UI, 10),
                          values=[f"第{c['idx']}章 {c['title'][:8]}" for c in chapters])
    ch_box.current(0)
    ch_box.pack(side="right")
    ch_box.bind("<<ComboboxSelected>>", lambda e: _on_chapter())

    # ---- 风格设置：预设 + 自由输入，保存进书状态（影响后续所有生成） ----
    style_row = tk.Frame(win, bg=theme.BG)
    style_row.pack(fill="x", padx=14, pady=(2, 0))
    tk.Label(style_row, text=_t("ds.style"), font=(FONT_UI, 10),
             bg=theme.BG, fg=theme.MUTED).pack(side="left")
    style_var = tk.StringVar(value=state.get("drama_style")
                             or dramavideo.DEFAULT_STYLE)
    style_box = ttk.Combobox(style_row, textvariable=style_var, width=34,
                             font=(FONT_UI, 10),
                             values=list(dramavideo.STYLE_PRESETS))
    style_box.pack(side="left", padx=6)

    def _save_style():
        v = style_var.get().strip() or dramavideo.DEFAULT_STYLE
        state["drama_style"] = v
        try:
            p.save()
        except Exception:              # noqa: BLE001
            pass
        status(_t("ds.style_saved", n=v[:30]))

    ui._flat_button(style_row, text=_t("ds.style_save"), width=10,
                    font=(FONT_UI, 9), command=_save_style).pack(side="left")
    ui._flat_button(style_row, text="🎨", width=2,
                    font=(FONT_UI, 9),
                    command=lambda: __import__("ui_panel_style").show(app)
                    ).pack(side="left", padx=2)
    tk.Label(style_row, text=_t("ds.style_hint"), font=(FONT_UI, 8),
             bg=theme.BG, fg=theme.MUTED).pack(side="left", padx=8)

    stat_foot = tk.Frame(win, bg=theme.BG)
    stat_foot.pack(fill="x", padx=14)
    stat_lbl = tk.Label(stat_foot, text=_t("ds.ready"), font=(FONT_UI, 9),
                        bg=theme.BG, fg=theme.MUTED, anchor="w")
    stat_lbl.pack(side="left", fill="x", expand=True)

    def _stop_gen():
        ev = getattr(app, "_drama_stop_event", None)
        if ev is not None:
            ev.set()
            status(_t("ds.stop_req"), busy=st["busy"])
        else:
            status(_t("novel.drama_stop_idle"))

    ui._flat_button(stat_foot, text=_t("ds.stop"), width=12,
                    font=(FONT_UI, 9), command=_stop_gen
                    ).pack(side="right", padx=(8, 0))

    steps = {}

    # ================ 步骤1：剧本大纲（可编辑） ================
    f1 = tk.Frame(win, bg=theme.BG)
    steps[1] = f1
    docs = []

    def _collect_docs():
        docs.clear()
        docs.append(("总纲（大纲）", "outline",
                     os.path.join(book, novel_chain._DIR_OUTLINE,
                                  novel_chain._OUTLINE_FILE)))
        docs.append(("世界观", "world",
                     os.path.join(book, novel_chain._DIR_SETTING, "世界观.md")))
        docs.append(("故事合约", "contract",
                     os.path.join(book, novel_chain._DIR_SETTING, "故事合约.md")))
        docs.append(("角色设定", "characters",
                     os.path.join(book, novel_chain._DIR_SETTING, "角色.md")))
        for c in chapters:
            docs.append((f"第{c['idx']}章剧本 {c['title'][:10]}", None,
                         c.get("file") or ""))

    _collect_docs()
    nav1 = tk.Listbox(f1, width=22, font=(FONT_UI, 10), bg=theme.PANEL,
                      fg=theme.TEXT, relief="flat", highlightthickness=1,
                      highlightbackground=theme.BORDER,
                      selectbackground=theme.ACCENT,
                      selectforeground="#ffffff", exportselection=False)
    nav1.pack(side="left", fill="y", padx=(0, 8))
    for name, _, _ in docs:
        nav1.insert("end", name)
    nav1.selection_set(0)

    mid1 = tk.Frame(f1, bg=theme.PANEL)
    mid1.pack(side="left", fill="both", expand=True)
    ed1 = tk.Text(mid1, font=(FONT_UI, 11), wrap="word", relief="flat",
                  bg="white", fg=theme.TEXT, padx=10, pady=8, undo=True)
    ysb1 = ttk.Scrollbar(mid1, command=ed1.yview)
    ed1.config(yscrollcommand=ysb1.set)
    ysb1.pack(side="right", fill="y")
    ed1.pack(fill="both", expand=True, padx=8, pady=8)
    btn1 = ui._flat_button(mid1, text=_t("ds.save_doc"), width=12,
                           font=(FONT_UI, 10), command=lambda: _save_doc())
    btn1.pack(anchor="e", padx=8, pady=(0, 8))

    def _show_doc():
        i = nav1.curselection()
        if not i:
            return
        _, key, path = docs[i[0]]
        if key:                          # 设定：优先 state（权威），文件兜底
            text = state.get(key) or ""
            if not text and os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
        else:
            text = ""
            c = next(c for c in chapters if c["idx"] == st["ch"])
            if i[0] >= 4:
                c = chapters[i[0] - 4]
                text = c.get("text") or ""
            if not text and os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
        ed1.delete("1.0", "end")
        ed1.insert("1.0", text)

    def _save_doc():
        i = nav1.curselection()
        if not i:
            return
        name, key, path = docs[i[0]]
        text = ed1.get("1.0", "end-1c").strip()
        try:
            if key:                      # 设定 → state + md 文件
                state[key] = text
            else:
                chapters[i[0] - 4]["text"] = text
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            p.save()
            status(_t("ds.saved", n=name))
        except Exception as e:           # noqa: BLE001
            status(f"❌ {type(e).__name__}: {e}")

    nav1.bind("<<ListboxSelect>>", lambda e: _show_doc())
    _show_doc()

    # ================ 步骤2：资产库 ================
    f2 = tk.Frame(win, bg=theme.BG)
    steps[2] = f2
    cast_path = dramavideo._global_cast_path(state)

    def _cast():
        return _load_json(cast_path, {})

    wrap2 = tk.Frame(f2, bg=theme.PANEL)
    wrap2.pack(fill="both", expand=True)
    cv2 = tk.Canvas(wrap2, bg=theme.PANEL, highlightthickness=0)
    sb2 = ttk.Scrollbar(wrap2, orient="vertical", command=cv2.yview)
    cv2.configure(yscrollcommand=sb2.set)
    sb2.pack(side="right", fill="y")
    cv2.pack(side="left", fill="both", expand=True)
    inner2 = tk.Frame(cv2, bg=theme.PANEL)
    inner2.bind("<Configure>",
                lambda e: cv2.configure(scrollregion=cv2.bbox("all")))
    _win_id = cv2.create_window((0, 0), window=inner2, anchor="nw")
    # 画布宽度跟随面板（卡片列随窗口拉伸），滚轮可滚动
    cv2.bind("<Configure>",
             lambda e: cv2.itemconfigure(_win_id, width=e.width))

    def _on_wheel(e):
        cv2.yview_scroll(-1 * (e.delta // 120), "units")

    win.bind_all("<MouseWheel>", _on_wheel)
    win.protocol("WM_DELETE_WINDOW", lambda: (win.unbind_all("<MouseWheel>"),
                                              win.destroy()))
    foot2 = tk.Frame(f2, bg=theme.BG)
    foot2.pack(fill="x", pady=4)

    def _maybe_migrate_old_cast(path):
        """一次性迁移：旧版 短剧资产/cast.json（含旧 png 路径）→ 短剧资产/全书/."""
        if not cast_path.endswith(os.sep + "全书" + os.sep + "cast.json"):
            return                          # 仅在新路径下第一次跑触发
        old_root = os.path.dirname(os.path.dirname(path))  # 短剧资产/
        old = os.path.join(old_root, "cast.json")
        if os.path.exists(old) and not os.path.exists(path):
            import shutil as _sh
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _sh.copy(old, path)
        if os.path.exists(old_root) and not os.path.exists(
                os.path.dirname(path)):
            pass                          # 已无顶层残留 png（项目化旧布局会被 reset 清理）

    _maybe_migrate_old_cast(cast_path)

    def _refresh_cast():
        for w in inner2.winfo_children():
            w.destroy()
        cast = _cast()
        local = _cast_local(st["ch"])
        row = 0

        def _grid_group(store, title_prefix, store_path):
            nonlocal row
            for sec in ("角色", "场景", "道具"):
                items = [(n, i) for n, i in store.items()
                         if not n.startswith("_") and isinstance(i, dict)
                         and (i.get("type") or "角色") == sec]
                if not items:
                    continue
                tk.Label(inner2,
                         text=f"── {title_prefix}{sec}（{len(items)}）──",
                         font=(FONT_UI, 11, "bold"),
                         bg=theme.PANEL,
                         fg=theme.ACCENT
                         ).grid(row=row, column=0, columnspan=4, sticky="w",
                                padx=4, pady=(10, 2))
                row += 1
                for j, (name, info) in enumerate(items):
                    card = tk.Frame(inner2, bg=theme.PANEL,
                                    highlightthickness=1,
                                    highlightbackground=theme.BORDER)
                    card.grid(row=row + j // 4, column=j % 4, sticky="nw",
                              padx=6, pady=6)
                    _build_cast_card(card, name, info, store_path)
                row += (len(items) + 3) // 4

        _grid_group(cast, "通用库·", cast_path)     # 全书长期资产（所有章共用）
        _grid_group(local, f"第{st['ch']}章·",      # 本章暂时资产，随章切换
                    dramavideo._chapter_assets_path(state, st["ch"]))

    def _cast_local(ch):
        return _load_json(
            dramavideo._chapter_assets_path(state, ch), {})

    def _build_cast_card(card, name, info, store_path):
        dramavideo._resolve_asset_image(
            state, name, info, base=os.path.dirname(store_path))
        ph = _thumb(info.get("path") or "", (150, 200))
        if ph:
            lbl = tk.Label(card, image=ph, bg=theme.PANEL)
            lbl.pack(padx=8, pady=(8, 2))
            st["img_refs"].append(ph)
        tk.Label(card, text=f"{name}", font=(FONT_UI, 11, "bold"),
                 bg=theme.PANEL, fg=theme.TEXT).pack()
        # 多阶段形象（现代/古装…）：小缩略图行，双击重生成该阶段（主图锁脸）
        looks = info.get("looks") or {}
        if len(looks) > 1:
            lrow = tk.Frame(card, bg=theme.PANEL)
            lrow.pack(pady=1)
            for era, lk in looks.items():
                cell = tk.Frame(lrow, bg=theme.PANEL)
                cell.pack(side="left", padx=3)
                lph = _thumb(lk.get("path") or "", (56, 74))
                img_lbl = (tk.Label(cell, image=lph, bg=theme.PANEL)
                           if lph else None)
                if img_lbl is not None:
                    img_lbl.pack()
                    st["img_refs"].append(lph)
                era_lbl = tk.Label(cell, text=era, font=(FONT_UI, 8),
                                   bg=theme.PANEL, fg=theme.MUTED)
                era_lbl.pack()
                for w in (cell, img_lbl, era_lbl):
                    if w is not None:
                        w.bind("<Double-Button-1>",
                               lambda e, era=era: _regen_look(era))
            tk.Label(lrow, text="双击阶段图＝重生成（主图锁脸）",
                     font=(FONT_UI, 7), bg=theme.PANEL,
                     fg=theme.MUTED).pack()
        ent = tk.Entry(card, width=22, font=(FONT_UI, 9), relief="flat",
                       bg=theme.BG, fg=theme.TEXT)
        ent.insert(0, info.get("appearance", ""))
        ent.pack(padx=8, pady=2)
        tk.Label(card, text=_t("ds.prompt"), font=(FONT_UI, 8),
                 bg=theme.PANEL, fg=theme.MUTED).pack()
        pmt = tk.Entry(card, width=22, font=(FONT_UI, 9), relief="flat",
                       bg=theme.ACCENT_FAINT, fg=theme.TEXT)
        pmt.pack(padx=8, pady=(0, 2))

        def _store():
            return _load_json(store_path, {})

        def _save_look_to_json(e_widget):
            c = _store()
            item = c.setdefault(name, {"type": info.get("type", "角色")})
            item.update({k: v for k, v in info.items()
                         if k in ("path", "url", "type")})
            item["appearance"] = e_widget.get().strip()
            _dump_json(store_path, c)
            return item

        def _save_app(n=name, e=ent):
            _save_look_to_json(e)
            status(_t("ds.saved", n=n))

        def _upload(n=name):
            from tkinter import filedialog
            src = filedialog.askopenfilename(
                title=_t("ds.pick_image"),
                filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.bmp"),
                           ("所有文件", "*.*")])
            if not src:
                return
            c = _store()
            item = c.setdefault(n, {"type": info.get("type", "角色")})
            item.update(info)
            try:
                dramavideo.replace_asset_image(
                    state, n, item, src,
                    fallback_dir=os.path.dirname(store_path))
            except Exception as e:       # noqa: BLE001
                status(f"❌ {type(e).__name__}: {e}")
                return
            _dump_json(store_path, c)
            _refresh_cast()
            status(_t("ds.uploaded", n=n))

        def _regen_by(mode):          # mode: t2i=描述生成 / i2i=图生图
            item = _save_look_to_json(ent)      # 先把描述框的改动存进去
            custom = pmt.get().strip()          # 用户自填提示词（可为空）
            if st["busy"]:
                status(_t("ds.busy"), busy=True)
                return
            label = _t("ds.gen_i2i" if mode == "i2i" else "ds.gen_t2i")
            status(_t("ds.generating", n=f"{name} {label}"), busy=True)

            def work():
                try:
                    new_info = dramavideo.gen_asset(
                        state, name, dict(item),
                        image_ref=(mode == "i2i"), custom_prompt=custom,
                        fallback_dir=os.path.dirname(store_path))
                except Exception as e:           # noqa: BLE001
                    win.after(0, lambda err=e: status(f"❌ {type(err).__name__}: {err}"))
                else:
                    # 接住返回值：path/url 必须落回 store——无 path 的资产
                    # 首次生成全靠这里记路，否则图在磁盘、卡片永远不出图
                    item["path"] = new_info.get("path")
                    item["url"] = new_info.get("url")
                    c = _store()
                    c[name] = item
                    _dump_json(store_path, c)
                    win.after(0, lambda: (_refresh_cast(),
                                          status(_t("ds.ready"))))
            threading.Thread(target=work, daemon=True).start()

        def _regen_look(era):
            """双击阶段缩略图：重生成该阶段形象（主图锁脸，只换服装发型）。"""
            _save_look_to_json(ent)             # 先存描述框改动
            if st["busy"]:
                status(_t("ds.busy"), busy=True)
                return
            status(_t("ds.generating", n=f"{name}·{era}"), busy=True)

            def work():
                try:
                    lk = dramavideo.gen_look(state, name, dict(item), era)
                except Exception as e:           # noqa: BLE001
                    win.after(0, lambda err=e: status(f"❌ {type(err).__name__}: {err}"))
                else:
                    c = _store()
                    it = c.setdefault(name, {"type": info.get("type", "角色")})
                    looks = it.setdefault("looks", {})
                    old = looks.get(era) or {}
                    old["path"] = lk.get("path")
                    old["url"] = lk.get("url")
                    looks[era] = old
                    it["looks"] = looks
                    _dump_json(store_path, c)
                    win.after(0, lambda: (_refresh_cast(),
                                          status(_t("ds.ready"))))
            threading.Thread(target=work, daemon=True).start()

        row1 = tk.Frame(card, bg=theme.PANEL)
        row1.pack(pady=(0, 2))
        ui._flat_button(row1, text=_t("ds.save_look"), width=9,
                        font=(FONT_UI, 9), command=_save_app
                        ).pack(side="left", padx=2)
        ui._flat_button(row1, text=_t("ds.upload"), width=9,
                        font=(FONT_UI, 9), command=_upload
                        ).pack(side="left", padx=2)
        row2 = tk.Frame(card, bg=theme.PANEL)
        row2.pack(pady=(0, 8))
        ui._flat_button(row2, text=_t("ds.gen_t2i"), width=9,
                        font=(FONT_UI, 9), command=lambda: _regen_by("t2i")
                        ).pack(side="left", padx=2)
        ui._flat_button(row2, text=_t("ds.gen_i2i"), width=9,
                        font=(FONT_UI, 9), command=lambda: _regen_by("i2i")
                        ).pack(side="left", padx=2)

        def _three_view():
            """三视图设定图（面特+正/侧/背，锁脸）：关键帧的高一致参考源。"""
            item2 = _save_look_to_json(ent)     # 先把描述框的改动存进去
            if st["busy"]:
                status(_t("ds.busy"), busy=True)
                return
            if not (item2.get("path") or ""):
                status(_t("ds.need_face", n=name))
                return
            status(_t("ds.generating", n=f"{name} 三视图"), busy=True)

            def work():
                try:
                    tp = dramavideo.three_view(state, name, dict(item2))
                except Exception as e:       # noqa: BLE001
                    win.after(0, lambda err=e: status(
                        f"❌ {type(err).__name__}: {err}"))
                else:
                    def done():
                        status(_t("ds.ready"))
                        if os.path.exists(tp):
                            os.startfile(tp)
                    win.after(0, done)
            threading.Thread(target=work, daemon=True).start()

        ui._flat_button(row2, text=_t("ds.three_view"), width=9,
                        font=(FONT_UI, 9),
                        command=lambda: _three_view()
                        ).pack(side="left", padx=2)

    ui._flat_button(foot2, text=_t("ds.fill_cast"), width=14,
                    font=(FONT_UI, 10),
                    command=lambda: _run_thread(
                        lambda: (dramavideo.build_cast(state),
                                 win.after(0, lambda: (_refresh_cast(),
                                                       status(_t("ds.ready"))))))
                    ).pack(side="left")

    def _extract_chapter_assets():
        ch = st["ch"]
        shots = _shots()
        if not shots:
            status(_t("ds.need_shots", n=ch))
            return

        def work():
            try:
                dramavideo.chapter_assets(
                    state, {"idx": ch, "title": "", "text": ""},
                    shots, _cast())
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda err=e: status(f"❌ {type(err).__name__}: {err}"))
            else:
                win.after(0, lambda: (_refresh_cast(),
                                      status(_t("ds.ready"))))
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        status(_t("ds.generating", n=_t("ds.ch_assets", n=ch)), busy=True)
        threading.Thread(target=work, daemon=True).start()

    ch_assets_btn = ui._flat_button(
        foot2, text=_t("ds.ch_assets_btn", n=st["ch"]),
        width=16, font=(FONT_UI, 10),
        command=_extract_chapter_assets)
    ch_assets_btn.pack(side="left", padx=6)
    _refresh_cast()

    # ================ 步骤3：分集视频 ================
    f3 = tk.Frame(win, bg=theme.BG)
    steps[3] = f3

    left3 = tk.Frame(f3, bg=theme.PANEL, width=210,
                     highlightthickness=1, highlightbackground=theme.BORDER)
    left3.pack(side="left", fill="y", padx=(0, 8))
    left3.pack_propagate(False)
    tk.Label(left3, text=_t("ds.shots"), font=(FONT_UI, 10, "bold"),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=8, pady=6)
    shots_lb = tk.Listbox(left3, font=(FONT_UI, 10), bg=theme.PANEL,
                          fg=theme.TEXT, relief="flat", highlightthickness=0,
                          selectbackground=theme.ACCENT,
                          selectforeground="#ffffff", exportselection=False)
    shots_lb.pack(fill="both", expand=True, padx=4, pady=(0, 6))
    shots_lb.bind("<<ListboxSelect>>", lambda e: _show_shot())

    center3 = tk.Frame(f3, bg=theme.PANEL)
    center3.pack(side="left", fill="both", expand=True, padx=(0, 8))
    row3 = tk.Frame(center3, bg=theme.PANEL)
    row3.pack(fill="x", padx=10, pady=(10, 2))
    tk.Label(row3, text=_t("ds.shot_title"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left")
    title_e = tk.Entry(row3, width=24, font=(FONT_UI, 10), relief="flat",
                       bg=theme.BG, fg=theme.TEXT)
    title_e.pack(side="left", padx=4)
    tk.Label(row3, text=_t("ds.scene"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left", padx=(8, 0))
    scene_e = tk.Entry(row3, width=14, font=(FONT_UI, 10), relief="flat",
                       bg=theme.BG, fg=theme.TEXT)
    scene_e.pack(side="left", padx=4)
    row3b = tk.Frame(center3, bg=theme.PANEL)
    row3b.pack(fill="x", padx=10, pady=2)
    tk.Label(row3b, text=_t("ds.chars"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left")
    chars_e = tk.Entry(row3b, width=26, font=(FONT_UI, 10), relief="flat",
                       bg=theme.BG, fg=theme.TEXT)
    chars_e.pack(side="left", padx=4)
    tk.Label(row3b, text=_t("ds.seconds"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left", padx=(8, 0))
    sec_sp = ttk.Spinbox(row3b, from_=4, to=15, width=4, font=(FONT_UI, 10))
    sec_sp.pack(side="left", padx=4)
    row3c = tk.Frame(center3, bg=theme.PANEL)
    row3c.pack(fill="x", padx=10, pady=2)
    tk.Label(row3c, text=_t("ds.era"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left")
    era_e = tk.Entry(row3c, width=10, font=(FONT_UI, 10), relief="flat",
                     bg=theme.BG, fg=theme.TEXT)
    era_e.pack(side="left", padx=4)
    tk.Label(row3c, text=_t("ds.camera"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left", padx=(8, 0))
    cam_e = tk.Entry(row3c, width=12, font=(FONT_UI, 10), relief="flat",
                     bg=theme.BG, fg=theme.TEXT)
    cam_e.pack(side="left", padx=4)
    tk.Label(row3c, text=_t("ds.mood"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left", padx=(8, 0))
    mood_e = tk.Entry(row3c, width=10, font=(FONT_UI, 10), relief="flat",
                      bg=theme.BG, fg=theme.TEXT)
    mood_e.pack(side="left", padx=4)
    # 语速估算提示：旁白+台词完读所需秒数——低于它人物会说到一半被切镜
    spk_lbl = tk.Label(row3c, text="", font=(FONT_UI, 9), bg=theme.PANEL,
                       fg=theme.ACCENT)
    spk_lbl.pack(side="left", padx=(8, 0))
    tk.Label(center3, text=_t("ds.desc"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=10)
    desc_t = tk.Text(center3, height=8, font=(FONT_UI, 10), wrap="word",
                     relief="flat", bg="white", fg=theme.TEXT, padx=8, pady=6)
    desc_t.pack(fill="both", expand=True, padx=10)
    tk.Label(center3, text=_t("ds.narration"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=10)
    narr_e = tk.Entry(center3, font=(FONT_UI, 10), relief="flat",
                      bg=theme.ACCENT_FAINT, fg=theme.TEXT)
    narr_e.pack(fill="x", padx=10, pady=(2, 4))
    tk.Label(center3, text=_t("ds.dialogue"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=10)
    dlge = tk.Entry(center3, font=(FONT_UI, 10), relief="flat",
                    bg=theme.BG, fg=theme.TEXT)
    dlge.pack(fill="x", padx=10, pady=(2, 6))
    btn3 = tk.Frame(center3, bg=theme.PANEL)
    btn3.pack(fill="x", padx=10, pady=(0, 10))
    ui._flat_button(btn3, text=_t("ds.save_shot"), width=12, font=(FONT_UI, 10),
                    command=lambda: _save_shot()).pack(side="left")
    ui._flat_button(btn3, text=_t("ds.drop_media"), width=12, font=(FONT_UI, 10),
                    command=lambda: _drop_media()).pack(side="left", padx=6)

    right3 = tk.Frame(f3, bg=theme.PANEL, width=330,
                      highlightthickness=1, highlightbackground=theme.BORDER)
    right3.pack(side="left", fill="y")
    right3.pack_propagate(False)
    prev = tk.Label(right3, text=_t("ds.no_frame"), font=(FONT_UI, 10),
                    bg=theme.PANEL, fg=theme.MUTED, width=30, height=14,
                    wraplength=300)
    prev.pack(padx=10, pady=10)
    ui._flat_button(right3, text=_t("ds.gen_frame"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: _gen("frame")).pack(pady=3)
    ui._flat_button(right3, text=_t("ds.gen_clip"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: _gen("clip")).pack(pady=3)
    ui._flat_button(right3, text=_t("ds.take"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: _gen("take")).pack(pady=3)
    ui._flat_button(right3, text=_t("ds.concat"), width=18, font=(FONT_UI, 10),
                    command=lambda: _gen("concat")).pack(pady=3)
    ui._flat_button(right3, text=_t("ds.open_out"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: os.startfile(os.path.join(
                        book, dramavideo._OUT_DIR))
                    if os.path.isdir(os.path.join(book, dramavideo._OUT_DIR))
                    else status(_t("ds.no_out"))).pack(pady=3)
    # 片段都在 短剧片段/ 保留（每镜主成片 + 各条 take），换卡/重抽互不影响
    ui._flat_button(right3, text=_t("ds.open_clips"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: os.startfile(os.path.join(
                        book, dramavideo._CLIP_DIR))
                    if os.path.isdir(os.path.join(book, dramavideo._CLIP_DIR))
                    else status(_t("ds.no_clips_dir"))).pack(pady=3)
    ui._flat_button(right3, text=_t("ds.play_clip"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: _play_current()).pack(pady=3)
    # ---- 抽卡选择器：take 列表 + 首帧缩略图预览 + 采用为当前成片 ----
    take_var = tk.StringVar()
    take_box = ttk.Combobox(right3, textvariable=take_var, state="readonly",
                            font=(FONT_UI, 9))
    take_box.pack(fill="x", padx=10, pady=(6, 0))
    take_box.bind("<<ComboboxSelected>>", lambda e: _preview_take())
    ui._flat_button(right3, text=_t("ds.adopt"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: _adopt_take()).pack(pady=3)
    tts_var = tk.BooleanVar(value=bool(state.get("drama_tts")))

    def _toggle_tts():
        state["drama_tts"] = bool(tts_var.get())
        try:
            p.save()
        except Exception:              # noqa: BLE001
            pass
        key = "ds.tts_on" if tts_var.get() else "ds.tts_off"
        status(_t(key))

    tk.Checkbutton(right3, text=_t("ds.tts"), variable=tts_var,
                   command=_toggle_tts, font=(FONT_UI, 9),
                   bg=theme.PANEL, fg=theme.MUTED,
                   activebackground=theme.PANEL).pack(anchor="w", padx=10)

    # ---- 抽卡动作：列表 / 预览 / 采用（widget 在上方已建） ----
    def _canonical_clip():
        return os.path.join(book, dramavideo._CLIP_DIR,
                            f"{st['ch']}-{st['shot']+1:02d}.mp4")

    def _refresh_takes(sel=None):
        """重建 take 下拉：当前成片 + take1..N；sel 指定选中项（生成新卡后用）。"""
        takes = dramavideo.list_takes(state, st["ch"], st["shot"] + 1)
        cur = _canonical_clip()
        st["takes"] = [(_t("ds.take_main"), cur)] + [
            (f"take{n}", p) for n, p in takes]
        take_box["values"] = [lb for lb, _ in st["takes"]]
        want = sel or st.get("take_sel") or cur
        for lb, p in st["takes"]:
            if p == want:
                take_var.set(lb)
                break
        else:
            take_var.set(st["takes"][0][0])
        _preview_take()

    def _selected_take_path():
        lb = take_var.get()
        for l, p in st.get("takes", []):
            if l == lb:
                return p
        return st["takes"][0][1] if st.get("takes") else ""

    def _preview_take():
        """预览选中项：主成片显示关键帧；take 用 ffmpeg 首帧缩略图。"""
        p = st["take_sel"] = _selected_take_path()
        cur = _canonical_clip()
        if p and p != cur and os.path.exists(p):
            thumbs = os.path.join(book, dramavideo._CLIP_DIR, ".thumbs")
            os.makedirs(thumbs, exist_ok=True)
            tp = os.path.join(thumbs, os.path.basename(p) + ".png")
            if not os.path.exists(tp):
                tp = dramavideo.take_thumb(p, tp)
            ph = _thumb(tp, (300, 300)) if tp else None
            if ph is not None:
                prev.config(image=ph, text="", width=0, height=0)
                st["img_refs"].append(ph)
                return
            # 无 ffmpeg 抽不了首帧：明说，而不是装作没变化
            prev.config(image="", width=30, height=6,
                        text=f"{take_var.get()}\n· {_t('ds.take_no_preview')}")
            return
        _show_shot_frame()

    def _adopt_take():
        p = st.get("take_sel") or ""
        cur = _canonical_clip()
        if not p or p == cur:
            status(_t("ds.adopt_none"))
            return
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        dramavideo.select_clip_take(state, st["ch"], st["shot"] + 1, p)
        status(_t("ds.adopt_done"))

    def _show_shot_frame():
        """预览区显示当前成片对应的关键帧（主成片态）。"""
        frame, _ = _shot_paths(st["ch"], st["shot"] + 1)
        ph = _thumb(frame, (300, 300))
        if ph:
            prev.config(image=ph, text="", width=0, height=0)
            st["img_refs"].append(ph)
        else:
            prev.config(image="", text=_t("ds.no_frame"),
                        width=30, height=14)

    def _play_current():
        """播放下拉当前选中的卡（take2 等）；未选 take 则播主成片。"""
        for p in (_selected_take_path(), _canonical_clip()):
            if p and os.path.exists(p):
                os.startfile(p)
                return
        status(_t("ds.no_clip"))

    # ---- 步骤3 数据与动作 ----
    def _shots_file(ch):
        return os.path.join(book, dramavideo._SHOT_DIR, f"第{ch}章.json")

    def _shots():
        s = _load_json(_shots_file(st["ch"]), [])
        return s if isinstance(s, list) else []

    def _refresh_shots(sel=None):
        shots_lb.delete(0, "end")
        for i, s in enumerate(_shots(), 1):
            _, clip = _shot_paths(st["ch"], i)
            frame, _ = _shot_paths(st["ch"], i)
            mark = "▶" if os.path.exists(clip) else (
                "◈" if os.path.exists(frame) else "○")
            shots_lb.insert("end", f"{mark} {i} {s.get('title', '')[:14]}")
        if sel is not None and shots_lb.size():
            shots_lb.selection_clear(0, "end")
            shots_lb.selection_set(min(sel, shots_lb.size() - 1))
            shots_lb.see(min(sel, shots_lb.size() - 1))
        _show_shot()

    def _show_shot():
        sel = shots_lb.curselection()
        if not sel:
            return
        st["shot"] = sel[0]
        s = _shots()[sel[0]]
        title_e.delete(0, "end"); title_e.insert(0, s.get("title", ""))
        scene_e.delete(0, "end"); scene_e.insert(0, s.get("scene", ""))
        era_e.delete(0, "end"); era_e.insert(0, s.get("era", ""))
        cam_e.delete(0, "end"); cam_e.insert(0, s.get("camera", ""))
        mood_e.delete(0, "end"); mood_e.insert(0, s.get("mood", ""))
        need = dramavideo._speech_seconds(s)
        dur = int(float(s.get("duration") or 0))
        lack = dur < need
        spk_lbl.config(text=_t("ds.speech_hint", n=need) + (" ⚠" if lack else ""),
                       fg=theme.DANGER if lack else theme.ACCENT)
        chars_e.delete(0, "end")
        chars_e.insert(0, "、".join(s.get("characters", [])))
        sec_sp.set(int(s.get("duration", 5)))
        desc_t.delete("1.0", "end"); desc_t.insert("1.0", s.get("description", ""))
        narr_e.delete(0, "end"); narr_e.insert(0, s.get("narration", ""))
        dlge.delete(0, "end"); dlge.insert(0, s.get("dialogue", ""))
        st["take_sel"] = ""                # 换镜头：take 选择复位
        _refresh_takes()

    def _save_shot():
        data = _shots()
        if not data or st["shot"] >= len(data):
            return
        s = data[st["shot"]]
        s["title"] = title_e.get().strip()[:30]
        s["scene"] = scene_e.get().strip()[:30]
        s["era"] = era_e.get().strip()[:12]
        s["camera"] = cam_e.get().strip()[:20]
        s["mood"] = mood_e.get().strip()[:12]
        s["characters"] = [c.strip() for c in chars_e.get().split("、") if c.strip()][:4]
        try:
            s["duration"] = max(4, min(15, int(float(sec_sp.get()))))
        except (TypeError, ValueError):
            pass
        s["description"] = desc_t.get("1.0", "end-1c").strip()
        s["narration"] = narr_e.get().strip()[:80]
        s["dialogue"] = dlge.get().strip()
        _dump_json(_shots_file(st["ch"]), data)
        _refresh_shots(st["shot"])
        status(_t("ds.saved", n=s["title"] or f"镜头{st['shot']+1}"))

    def _drop_media():
        i = st["shot"] + 1
        frame, clip = _shot_paths(st["ch"], i)
        for f in (frame, clip):
            if os.path.exists(f):
                os.remove(f)            # 删除产物 → 下次生成视为缺失重建
        _refresh_shots(st["shot"])
        status(_t("ds.dropped", n=i))

    def _on_chapter():
        idx = ch_box.current()
        if 0 <= idx < len(chapters):
            st["ch"] = chapters[idx]["idx"]
            _refresh_shots(0)
            # 资产库跟着章节走：本章专属分组 + 提取按钮文字同步切换
            if ch_assets_btn.winfo_exists():
                ch_assets_btn.config(text=_t("ds.ch_assets_btn", n=st["ch"]))
            _refresh_cast()

    _GEN_KIND = {"frame": "关键帧", "clip": "镜头视频", "dub": "配音",
                 "cast": "形象", "shots": "分镜"}

    def _gen_event(e):
        """生成子步骤（关键帧/镜头视频/配音）→ 状态栏分步提示。"""
        if e.get("type") == "drama_media" and e.get("label"):
            k = _GEN_KIND.get(e.get("kind"), "")
            extra = f"{e['label']}{('·' + k) if k else ''}"
            if e.get("sec"):
                extra += f"（出片 {int(float(e['sec']))}s）"
            st["_gen_base"] = _t("ds.generating", n=extra)

    def _gen_work(kind):
        ch, i = st["ch"], st["shot"] + 1
        if kind in ("frame", "clip", "take") and not _shots():
            return
        cast = _cast()
        shot = _shots()[st["shot"]]
        ev = lambda e: win.after(0, lambda: _gen_event(e))   # noqa: E731
        if kind == "frame":
            # 点按即（重）生成：force=True 无视「文件存在即跳过」缓存
            dramavideo.keyframe(state, cast, shot, ch, i,
                                on_event=ev, force=True)
        elif kind == "clip":
            frame, _ = _shot_paths(ch, i)
            if not os.path.exists(frame):
                dramavideo.keyframe(state, cast, shot, ch, i, on_event=ev)
            urls = _load_json(os.path.join(book, dramavideo._SHOT_DIR,
                                           "urls.json"), {})
            dramavideo.clip(state, shot, urls.get(f"{ch}-{i:02d}", ""),
                            ch, i, on_event=ev, force=True)
        elif kind == "take":
            # 抽卡：同关键帧再生成一条候选，旧卡与新卡都保留
            frame, _ = _shot_paths(ch, i)
            if not os.path.exists(frame):
                dramavideo.keyframe(state, cast, shot, ch, i, on_event=ev)
            urls = _load_json(os.path.join(book, dramavideo._SHOT_DIR,
                                           "urls.json"), {})
            tpath = dramavideo.gen_clip_take(
                state, shot, urls.get(f"{ch}-{i:02d}", ""), ch, i,
                on_event=ev)
            m = re.search(r"take(\d+)\.mp4$", tpath.replace("\\", "/"))
            st["_last_take_n"] = m.group(1) if m else ""
            win.after(0, lambda tp=tpath: _refresh_takes(tp))
        else:
            n = len(_shots())
            clips = []
            for k in range(1, n + 1):
                _, cp = _shot_paths(ch, k)
                if os.path.exists(cp):
                    clips.append(cp)
            if not clips:
                raise RuntimeError(_t("ds.no_clips"))
            c = next(c for c in chapters if c["idx"] == ch)
            out = os.path.join(book, dramavideo._OUT_DIR,
                               f"第{ch}章-{dramavideo._safe_name(c['title'])}.mp4")
            dramavideo.concat(clips, out)
            win.after(0, lambda: os.startfile(out))

    def _gen(kind):
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        if kind in ("frame", "clip", "take"):
            # 表单编辑先落盘：改完直接点生成即生效，不必先点「保存分镜」
            _save_shot()
        names = {"frame": _t("ds.gen_frame"), "clip": _t("ds.gen_clip"),
                 "take": _t("ds.take"), "concat": _t("ds.concat")}
        status(_t("ds.generating", n=names[kind]), busy=True)

        def work():
            try:
                _gen_work(kind)
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda err=e: status(f"❌ {type(err).__name__}: {err}"))
            else:
                def done():
                    _refresh_shots(st["shot"])
                    if kind == "take":
                        n = st.get("_last_take_n") or ""
                        status(_t("ds.take_done", n=n) if n
                               else _t("ds.ready"))
                    else:
                        status(_t("ds.ready"))
                win.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def _run_thread(fn):
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        status(_t("ds.generating", n=""), busy=True)

        def work():
            try:
                fn()
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda err=e: status(f"❌ {type(err).__name__}: {err}"))
            else:
                win.after(0, lambda: status(_t("ds.ready")))
        threading.Thread(target=work, daemon=True).start()

    _refresh_shots(0)
    _go_step(3)
