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
import imggen
import videogen
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


def _comic_panels(md_text: str, ch: int) -> list:
    """从漫画分镜 md 抽取第 ch 章的出图提示词列表（纯函数，便于测试）。

    定位 `## 第{ch}章` 标题到下一个 `## ` 之间，收集表格行（行首 `|`），
    跳过表头/分隔行（分隔行含 ---，表头首格「格号」不是数字），每行取最后
    一个非空单元格去 markdown 粗体后作为出图提示词；上限 24 格防失控。
    """
    parts = re.split(rf"(?m)^##\s*第{ch}章", md_text, maxsplit=1)
    if len(parts) < 2:
        return []
    body = parts[1]
    nxt = re.search(r"(?m)^##\s", body)
    if nxt:
        body = body[:nxt.start()]
    panels = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.split("|") if c.strip()]
        if not cells or not cells[0].isdigit():
            continue                    # 表头行（首格是「格号」不是数字）
        if any("---" in c for c in cells):
            continue                    # 分隔行
        prompt = cells[-1].replace("**", "").strip()
        if prompt:
            panels.append(prompt)
        if len(panels) >= 24:
            break
    return panels


def _stitch_comic(out_dir, ch, n):
    """把 漫画/第{ch}-格01..n.png 竖向拼成 第{ch}-长图.png，返回路径。

    等宽缩放到首格宽度再贴；PIL 是可选依赖（模块头 try-import，缺失时
    Image 为 None），无 PIL 直接跳过拼接返回 ""，不影响已出的格图。
    """
    if Image is None:
        return ""
    imgs = []
    for i in range(1, n + 1):
        fp = os.path.join(out_dir, f"第{ch}-格{i:02d}.png")
        if os.path.exists(fp):
            imgs.append(Image.open(fp))
    if not imgs:
        return ""
    w = imgs[0].width
    scaled = []
    for im in imgs:
        if im.width != w:
            im = im.resize((w, max(1, int(im.height * w / im.width))))
        scaled.append(im.convert("RGB"))
    canvas = Image.new("RGB", (w, sum(im.height for im in scaled)), "white")
    y = 0
    for im in scaled:
        canvas.paste(im, (0, y))
        y += im.height
    out = os.path.join(out_dir, f"第{ch}-长图.png")
    canvas.save(out)
    return out


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
    import config
    import novel_chain
    chapters = [c for c in state.get("chapters", []) if c.get("text")]
    if not chapters:
        # 当前书没正文 ≠ 没书可做：重启后自动选中的常是 paused 大纲书，
        # 而写完的全本就在书稿根里——改投章节最多的那本
        p2, _n = app._pick_book_with_chapters()
        if p2 is not None:
            app._novel_pipe = p2
            p, state = p2, p2.state
            chapters = [c for c in state.get("chapters", []) if c.get("text")]
    if not chapters:
        app._set_status(_t("novel.no_chapters"))
        app._append("💡 " + _t("ds.no_chapters_hint") + "\n", "meta")
        return
    # v2.1：兜底补 drama_style / comic_style 字段，确保后续 inject_style 不空
    import dramavideo
    dramavideo.ensure_style_fields(state)
    book = novel_chain._book_dir(state)

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
            active = (k == n)
            b.config(bg=theme.ACCENT if active else theme.PANEL,
                     fg="white" if active else theme.TEXT)
            # _flat_button 自带的悬停钩子会把 bg 刷回浅色，激活页签
            # 白字配浅底就隐形了——这里按激活态重新接管悬停配色
            b.bind("<Enter>", lambda _e, b=b, a=active: b.config(
                bg=theme.ACCENT if a else theme.ACCENT_FAINT))
            b.bind("<Leave>", lambda _e, b=b, a=active: b.config(
                bg=theme.ACCENT if a else theme.BG))

    bar = tk.Frame(top, bg=theme.BG)
    bar.pack(side="left", padx=16)
    for n, label in ((1, "1. 剧本大纲"), (2, "2. 资产库"), (3, "3. 分集视频")):
        b = ui._flat_button(bar, text=label, width=11, font=(FONT_UI, 10),
                            command=lambda n=n: _go_step(n))
        b.pack(side="left", padx=3)
        step_btns[n] = b

    # ---- v2.5：工作流模式选择（drama / comic / both）----
    # mode = "drama"  → 工作台隐藏漫画行，专注分集视频
    # mode = "comic"  → 工作台只显示漫画行（其它 step 仍可访问，但意义不大）
    # mode = "both"    → 现状（默认）
    wf_mode_var = tk.StringVar(value=state.get("drama_workflow_mode") or "both")

    def _save_mode():
        state["drama_workflow_mode"] = wf_mode_var.get()
        p.save()
        _refresh_comic_visibility()
    ui._flat_button(bar, text="⚙", width=2, font=(FONT_UI, 9),
                    command=lambda: _cycle_mode()).pack(side="left", padx=(8, 0))

    def _cycle_mode():
        # drama → comic → both → drama（按最常用顺序循环）
        order = ("drama", "comic", "both")
        cur = wf_mode_var.get()
        nxt = order[(order.index(cur) + 1) % 3] if cur in order else "both"
        wf_mode_var.set(nxt)
        _save_mode()

    def _refresh_comic_visibility():
        # comic 行：根据 wf_mode 决定 show/hide（mode != "drama" 才显示）
        m = wf_mode_var.get()
        if m == "drama":
            comic_row.pack_forget()
        else:
            comic_row.pack(fill="x", padx=14, pady=(2, 0))

    ch_var = tk.StringVar()
    ch_box = ttk.Combobox(top, textvariable=ch_var, width=10, state="readonly",
                          font=(FONT_UI, 10),
                          values=[f"第{c['idx']}章 {c['title'][:8]}" for c in chapters])
    ch_box.current(0)
    ch_box.pack(side="right")
    ch_box.bind("<<ComboboxSelected>>", lambda e: _on_chapter())
    ui._flat_button(top, text=_t("ds.ep_list_btn"), width=7,
                    font=(FONT_UI, 9),
                    command=lambda: _episode_overview()).pack(
                        side="right", padx=(0, 6))

    # ---- 顶栏：视频模型 + 分辨率档位（provider 切换 → resolution 联动） ----
    video_providers = videogen.available_providers()
    provider_labels = ([f"自动（{_t('ds.video_model_auto') or 'auto'}）"]
                          + [f"{vp['name']}（{vp['model']}）"
                             + ("" if vp['has_key'] else " · 未填 Key")
                             for vp in video_providers])
    video_provider_var = tk.StringVar(
        value=state.get("drama_video_provider_label") or provider_labels[0])
    video_resolution_var = tk.StringVar(
        value=state.get("drama_video_resolution") or "")

    def _provider_index():
        """当前 provider 选中索引（0=自动；≥1=providers[i-1]）。"""
        s = video_provider_var.get()
        if s in provider_labels:
            return provider_labels.index(s)
        return 0

    def _current_provider_id() -> str:
        idx = _provider_index()
        return "" if idx == 0 else video_providers[idx - 1]["provider_id"]

    def _current_resolution_tiers() -> tuple:
        idx = _provider_index()
        if idx == 0:
            return videogen.provider_resolution_tiers("agnes")
        kind = video_providers[idx - 1].get("kind", "agnes")
        return videogen.provider_resolution_tiers(kind)

    def _on_provider_change(*_a):
        tiers = _current_resolution_tiers()
        res_box["values"] = tiers
        if video_resolution_var.get() not in tiers:
            video_resolution_var.set(tiers[0] if tiers else "")
        state["drama_video_provider"] = _current_provider_id()
        state["drama_video_provider_label"] = video_provider_var.get()
        state["drama_video_resolution"] = video_resolution_var.get().strip()
        try:
            p.save()
        except Exception:                  # noqa: BLE001
            pass

    def _on_resolution_change(*_a):
        state["drama_video_resolution"] = video_resolution_var.get().strip()
        try:
            p.save()
        except Exception:                  # noqa: BLE001
            pass

    tk.Label(top, text=_t("ds.video_model"), font=(FONT_UI, 9),
             bg=theme.BG, fg=theme.MUTED).pack(side="right", padx=(8, 0))
    res_box = ttk.Combobox(top, textvariable=video_resolution_var, width=8,
                           state="readonly", font=(FONT_UI, 9),
                           values=_current_resolution_tiers())
    res_box.pack(side="right", padx=(4, 0))
    res_box.bind("<<ComboboxSelected>>", lambda e: _on_resolution_change())
    if video_resolution_var.get() not in _current_resolution_tiers():
        video_resolution_var.set(_current_resolution_tiers()[0])
    prov_box = ttk.Combobox(top, textvariable=video_provider_var, width=22,
                            state="readonly", font=(FONT_UI, 9),
                            values=provider_labels)
    prov_box.pack(side="right", padx=(4, 0))
    prov_box.bind("<<ComboboxSelected>>", lambda e: _on_provider_change())

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

    # ---- 每章字数目标：写进 state["ch_words"]，pipeline 生成正文时消费 ----
    try:
        _w0 = int(state.get("ch_words") or 3000)
    except (TypeError, ValueError):    # noqa: BLE001 旧检查点脏值兜底
        _w0 = 3000
    words_var = tk.StringVar(value=str(_w0))

    def _save_words():
        # 字数是「目标」不做硬拦截：手输非法值夹回档位区间，保存绝不崩 UI
        try:
            n = max(500, min(20000, int(float(words_var.get()))))
        except (TypeError, ValueError):
            n = 3000
            words_var.set(str(n))
        state["ch_words"] = n
        try:
            p.save()
        except Exception:              # noqa: BLE001
            pass
        status(_t("novel.set_words", n=n))

    tk.Label(style_row, text=_t("ds.words_label"), font=(FONT_UI, 10),
             bg=theme.BG, fg=theme.MUTED).pack(side="right", padx=(8, 0))
    ttk.Spinbox(style_row, from_=500, to=20000, increment=100, width=7,
                font=(FONT_UI, 10), textvariable=words_var
                ).pack(side="right", padx=4)
    # side="right" 先 pack 的靠最右：按钮 → 框 → 文字，视觉顺序「每章字数 [框] 保存」
    ui._flat_button(style_row, text=_t("btn.save"), width=8,
                    font=(FONT_UI, 9), command=_save_words).pack(side="right")

    # ---- 漫画入口：生成本章分镜表 → 逐格出图 → 拼长图（进度复用底部状态栏） ----
    comic_row = tk.Frame(win, bg=theme.BG)
    comic_row.pack(fill="x", padx=14, pady=(2, 0))
    comic_btns = []
    # v2.5：跟 wf_mode 联动，初次进入时按 state 决定是否展示
    _refresh_comic_visibility()

    def _comic_btns_enabled(on):
        for b in comic_btns:
            try:
                b.config(state="normal" if on else "disabled")
            except tk.TclError:        # noqa: BLE001 窗口已关时静默
                pass

    def _gen_comic_board():
        """当前章 → comic_adapt 生成 漫画分镜.md（LLM 调用必须放后台线程）。"""
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        ch = st["ch"]

        def work():
            try:
                novel_chain.comic_adapt(state, ch, ch)
            except Exception as e:     # noqa: BLE001 StageStopError 等统一 ❌ 提示
                win.after(0, lambda err=e: status(
                    f"❌ {type(err).__name__}: {err}"))
            else:
                win.after(0, lambda: status(_t("ds.ready")))
        status(_t("ds.generating", n=_t("ds.comic_board")), busy=True)
        threading.Thread(target=work, daemon=True).start()

    def _comic_draw():
        """分镜表逐格出图（后台线程），完成后 PIL 竖拼长图；停止在格间生效。"""
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        if not imggen.available():     # 未配置图像后端：仅提示，不抛
            status(_t("ds.comic_img_unavailable"))
            return
        ch = st["ch"]
        md = os.path.join(book, "漫画分镜.md")
        panels = []
        if os.path.exists(md):
            with open(md, encoding="utf-8") as f:
                panels = _comic_panels(f.read(), ch)
        if not panels:
            status(_t("ds.comic_none"))
            return
        out_dir = os.path.join(book, "漫画")
        os.makedirs(out_dir, exist_ok=True)
        # 停止走与短剧共用的 app._drama_stop_event；没有就建一个，
        # 开跑前先 clear，防上一次中止遗留的置位让本次一格不出就退
        stop = getattr(app, "_drama_stop_event", None)
        if stop is None:
            stop = app._drama_stop_event = threading.Event()
        stop.clear()
        n = len(panels)

        def work():
            ok = fail = 0
            for i, prompt in enumerate(panels, 1):
                if stop.is_set():      # 「停止」只在格间生效，当前格跑完即收手
                    break
                try:
                    imggen.generate_ex(
                        prompt,
                        os.path.join(out_dir, f"第{ch}-格{i:02d}.png"),
                        size="1K", ratio="3:4")
                    ok += 1
                except Exception:      # noqa: BLE001 单格失败不阻断批次
                    fail += 1
                # 线程不碰控件：进度一律 win.after 回主线程刷
                win.after(0, lambda i=i: status(
                    _t("ds.comic_progress", i=i, n=n), busy=True))
            # 拼长图也是纯 PIL 计算，留在线程里做，别卡主线程
            stitched = ""
            if not stop.is_set() and ok:
                stitched = _stitch_comic(out_dir, ch, ok)

            def done():
                _comic_btns_enabled(True)
                if stop.is_set() and ok + fail < n:
                    status(("⏹ " + _t("ds.comic_done", n=ok)) if ok
                           else _t("ds.ready"))
                    return
                if ok == 0:
                    status(f"❌ {_t('ds.comic_img_unavailable')}")
                    return
                msg = "✅ " + _t("ds.comic_done", n=ok)
                if fail:
                    msg += f"（{fail} 失败）"
                if stitched:
                    msg += " · " + os.path.basename(stitched)
                status(msg)
            win.after(0, done)
        status(_t("ds.generating", n=_t("ds.comic_draw")), busy=True)
        _comic_btns_enabled(False)
        threading.Thread(target=work, daemon=True).start()

    def _open_comic_dir():
        d = os.path.join(book, "漫画")
        os.makedirs(d, exist_ok=True)
        try:
            os.startfile(d)            # Windows
        except AttributeError:         # noqa: BLE001 非 Windows 无 startfile
            import subprocess
            import sys
            try:
                subprocess.Popen(
                    ["open" if sys.platform == "darwin" else "xdg-open", d])
            except Exception as e:     # noqa: BLE001 打不开只提示不崩
                status(f"❌ {type(e).__name__}: {e}")

    b_board = ui._flat_button(comic_row, text="📖 " + _t("ds.comic_board"),
                              width=16, font=(FONT_UI, 9),
                              command=_gen_comic_board)
    b_board.pack(side="left")
    b_draw = ui._flat_button(comic_row, text="🖼 " + _t("ds.comic_draw"),
                             width=12, font=(FONT_UI, 9),
                             command=_comic_draw)
    b_draw.pack(side="left", padx=6)
    b_open = ui._flat_button(comic_row, text="📂 " + _t("ds.comic_open"),
                             width=12, font=(FONT_UI, 9),
                             command=_open_comic_dir)
    b_open.pack(side="left")
    comic_btns.extend((b_board, b_draw, b_open))

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

    # 内容审核拒绝时的「切模型重试」按钮（默认隐藏；moderation 事件触发显示）
    def _on_moderation_retry():
        """把 provider 切到列表里的下一个非当前选项，重新生成当前镜头。"""
        last = st.get("_moderation_last") or {}
        cur_pid = last.get("provider_id") or ""
        # 找到下一个不同的 provider
        nxt = ""
        for vp in video_providers:
            if vp["provider_id"] and vp["provider_id"] != cur_pid and vp["has_key"]:
                nxt = vp["provider_id"]
                break
        if not nxt:
            status(_t("ds.no_alt_provider"), busy=False)
            return
        state["drama_video_provider"] = nxt
        state["drama_video_provider_label"] = next(
            (l for l, v in zip(provider_labels[1:], video_providers)
             if v["provider_id"] == nxt), provider_labels[0])
        # resolution 联动
        tiers = _current_resolution_tiers()
        res_box["values"] = tiers
        if video_resolution_var.get() not in tiers:
            video_resolution_var.set(tiers[0] if tiers else "")
        state["drama_video_resolution"] = video_resolution_var.get().strip()
        video_provider_var.set(state["drama_video_provider_label"])
        try:
            p.save()
        except Exception:                  # noqa: BLE001
            pass
        st["_moderation_last"] = None
        mod_btn.pack_forget()
        # 重跑当前镜头
        _gen("clip")

    mod_btn = ui._icon_text_button(stat_foot, "shield",
                                   _t("ds.moderation_retry"),
                                   command=_on_moderation_retry,
                                   font=(FONT_UI, 9))
    # 不 pack，由 moderation 事件触发显示

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

    # ---- AI 改写（火宝剧本阶段）：粘贴/载入原文 → 换模型、调语气 → 存为拍摄剧本。
    # 拍摄剧本落盘 短剧剧本/第N章-剧本.md 后，分镜/资产链路自动以它为输入
    # （dramavideo._chapter_source_text，文件存在即覆盖原文，删除即回退）。
    right1 = tk.Frame(f1, bg=theme.PANEL, width=380,
                      highlightthickness=1, highlightbackground=theme.BORDER)
    right1.pack(side="left", fill="y", padx=(8, 0))
    right1.pack_propagate(False)
    tk.Label(right1, text=_t("ds.rewrite"), font=(FONT_UI, 11, "bold"),
             bg=theme.PANEL, fg=theme.ACCENT).pack(anchor="w", padx=8,
                                                   pady=(8, 2))
    tk.Label(right1, text=_t("ds.rewrite_src"), font=(FONT_UI, 8),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=8)
    src1 = tk.Text(right1, height=6, font=(FONT_UI, 9), wrap="word",
                   relief="flat", bg=theme.BG, fg=theme.TEXT, padx=6, pady=4)
    src1.pack(fill="x", padx=8, pady=(0, 4))
    hint1 = tk.Label(right1, text="", font=(FONT_UI, 8), bg=theme.PANEL)
    hint1.pack(anchor="w", padx=8)

    row1a = tk.Frame(right1, bg=theme.PANEL)
    row1a.pack(fill="x", padx=8, pady=2)
    ui._flat_button(row1a, text=_t("ds.rewrite_load"), width=12,
                    font=(FONT_UI, 9),
                    command=lambda: _load_chapter_src()).pack(side="left")
    tk.Label(row1a, text=_t("ds.rewrite_tone"), font=(FONT_UI, 8),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left", padx=(6, 0))
    tone1_e = tk.Entry(row1a, width=16, font=(FONT_UI, 9), relief="flat",
                       bg=theme.BG, fg=theme.TEXT)
    tone1_e.pack(side="left", padx=4)
    row1b = tk.Frame(right1, bg=theme.PANEL)
    row1b.pack(fill="x", padx=8, pady=2)
    tk.Label(row1b, text=_t("ds.rewrite_model"), font=(FONT_UI, 8),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left")
    _models = [m for m in (config.load_models()[0] or []) if m.key]
    _model_labels = [f"{m.display_name}（{m.key}）" for m in _models]

    def _model_by_label(lab):
        for m in _models:
            if f"{m.display_name}（{m.key}）" == lab:
                return m
        return None
    _cur = config.find_model(state.get("model_key"))
    model1_var = tk.StringVar(
        value=(f"{_cur.display_name}（{_cur.key}）" if _cur else
               (_model_labels[0] if _model_labels else "")))
    model1_box = ttk.Combobox(row1b, textvariable=model1_var, width=26,
                              state="readonly", font=(FONT_UI, 8),
                              values=_model_labels)
    model1_box.pack(side="left", padx=4)
    ui._flat_button(row1b, text=_t("ds.rewrite_go"), width=12,
                    font=(FONT_UI, 9),
                    command=lambda: _do_rewrite()).pack(side="left", padx=4)
    tk.Label(right1, text=_t("ds.rewrite_result"), font=(FONT_UI, 8),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=8,
                                                  pady=(4, 0))
    res1 = tk.Text(right1, height=10, font=(FONT_UI, 9), wrap="word",
                   relief="flat", bg="white", fg=theme.TEXT, padx=6, pady=4)
    res1.pack(fill="both", expand=True, padx=8, pady=(0, 4))
    row1c = tk.Frame(right1, bg=theme.PANEL)
    row1c.pack(fill="x", padx=8, pady=(0, 8))
    ui._flat_button(row1c, text=_t("ds.rewrite_save"), width=14,
                    font=(FONT_UI, 9),
                    command=lambda: _save_screenplay()).pack(side="left")
    ui._flat_button(row1c, text=_t("ds.rewrite_drop"), width=14,
                    font=(FONT_UI, 9),
                    command=lambda: _drop_screenplay()).pack(side="left",
                                                             padx=6)

    def _src_hint():
        using = os.path.exists(dramavideo._screenplay_path(state, st["ch"]))
        hint1.config(text=_t("ds.src_screenplay" if using
                             else "ds.src_novel"),
                     fg=theme.SUCCESS if using else theme.MUTED)

    def _load_chapter_src():
        c = next(c for c in chapters if c["idx"] == st["ch"])
        src1.delete("1.0", "end")
        src1.insert("1.0", c.get("text") or "")
        status(_t("ds.rewrite_load") + f" · 第{c['idx']}章")

    def _do_rewrite():
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        src = src1.get("1.0", "end-1c").strip()
        if not src:
            status(_t("ds.rewrite_need_src"))
            return
        tone = tone1_e.get().strip()
        model = _model_by_label(model1_var.get()) or \
            config.find_model(state.get("model_key"))
        c = next(c for c in chapters if c["idx"] == st["ch"])
        status(_t("ds.generating", n=_t("ds.rewrite")), busy=True)

        def work():
            sys_p = ("你是短剧剧本改写师。把原始内容改写成竖屏短剧拍摄剧本："
                     "按场景拆分，每场标题「## S编号 | 内景/外景 · 地点 | "
                     "时间段」（编号全章连续，时间段具体到清晨/正午/黄昏/"
                     "深夜）；动作写自然段；台词格式「角色名：（状态/表情）"
                     "台词」；不写镜头语言（景别/运镜留给分镜步）；每场 "
                     "30-60 秒体量；只输出剧本本身。"
                     + (f"\n语气要求：{tone}。" if tone else ""))
            user_p = f"第 {c['idx']} 章《{c['title']}》原始内容：\n{src}"
            try:
                text = novel_chain._ask_model(model, sys_p, user_p)  # noqa: SLF001
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda err=e: status(
                    f"❌ {type(err).__name__}: {err}"))
                return

            def done():
                res1.delete("1.0", "end")
                res1.insert("1.0", text)
                status(_t("ds.rewrite_done"))
            win.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def _save_screenplay():
        text = res1.get("1.0", "end-1c").strip()
        if not text:
            status(_t("ds.rewrite_need_src"))
            return
        path = dramavideo._screenplay_path(state, st["ch"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        # 剧本换了 → 旧分镜/参考图是旧文本的产物，清缓存让下次批量按新剧本重拆
        sf = _shots_file(st["ch"])
        if os.path.exists(sf):
            os.remove(sf)
        _src_hint()
        status(_t("ds.rewrite_save_done"))

    def _drop_screenplay():
        path = dramavideo._screenplay_path(state, st["ch"])
        if os.path.exists(path):
            os.remove(path)
        _src_hint()
        status(_t("ds.rewrite_drop_done"))

    _src_hint()

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
                if sec == "角色":
                    # 每个角色一行：形象列 | 信息与按钮列 | 三视图列
                    for j, (name, info) in enumerate(items):
                        rowf = tk.Frame(inner2, bg=theme.PANEL,
                                        highlightthickness=1,
                                        highlightbackground=theme.BORDER)
                        rowf.grid(row=row + j, column=0, columnspan=4,
                                  sticky="ew", padx=6, pady=6)
                        _build_cast_card(rowf, name, info, store_path,
                                         horizontal=True)
                    row += len(items)
                else:
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

    def _build_cast_card(card, name, info, store_path, horizontal=False):
        dramavideo._resolve_asset_image(
            state, name, info, base=os.path.dirname(store_path))
        # 默认套（default_look，单击阶段图切换）：大图随默认套显示；
        # 关键帧在镜头无 era / era 未命中时也优先用这套
        dft = str(info.get("default_look") or "")
        dpath = (((info.get("looks") or {}).get(dft) or {})
                 .get("path") or "")
        disp = dpath if dpath and os.path.exists(dpath) else (info.get("path") or "")
        imgcol = midcol = tvcol = card
        if horizontal:
            imgcol = tk.Frame(card, bg=theme.PANEL)
            imgcol.pack(side="left", padx=(10, 4), pady=8, anchor="n")
            midcol = tk.Frame(card, bg=theme.PANEL)
            midcol.pack(side="left", fill="y", padx=(2, 6), pady=6)
            tvcol = tk.Frame(card, bg=theme.PANEL)
            tvcol.pack(side="right", padx=(4, 10), pady=8, anchor="n")
        ph = _thumb(disp, (150, 200))
        if ph:
            lbl = tk.Label(imgcol, image=ph, bg=theme.PANEL)
            lbl.pack(padx=8, pady=(8, 2))
            st["img_refs"].append(ph)
        tk.Label(midcol, text=f"{name}", font=(FONT_UI, 11, "bold"),
                 bg=theme.PANEL, fg=theme.TEXT).pack()
        # 多阶段形象（现代/古装…）：小缩略图行，单击＝设为默认套（再点取消），
        # 双击＝重生成该阶段（主图锁脸）。单击/双击用 240ms 延迟区分。
        looks = info.get("looks") or {}
        if len(looks) > 1:
            cur_dft = dft
            pend = {"aid": None}

            def _set_default(era):
                c = _load_json(store_path, {})
                it = c.get(name)
                if not isinstance(it, dict):
                    return
                if it.get("default_look") == era:
                    it.pop("default_look", None)   # 再点当前默认＝取消
                else:
                    it["default_look"] = era
                _dump_json(store_path, c)
                _refresh_cast()

            def _era_click(era):
                def go():
                    pend["aid"] = None
                    _set_default(era)
                pend["aid"] = win.after(240, go)

            def _era_dbl(era):
                if pend["aid"] is not None:
                    try:
                        win.after_cancel(pend["aid"])
                    except tk.TclError:          # noqa: SIM105
                        pass
                    pend["aid"] = None
                _regen_look(era)

            lrow = tk.Frame(imgcol, bg=theme.PANEL)
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
                is_dft = era == cur_dft
                era_lbl = tk.Label(cell, text=era + (" ·默认" if is_dft else ""),
                                   font=(FONT_UI, 8), bg=theme.PANEL,
                                   fg=theme.ACCENT if is_dft else theme.MUTED)
                era_lbl.pack()
                for w in (cell, img_lbl, era_lbl):
                    if w is not None:
                        w.bind("<Button-1>",
                               lambda e, era=era: _era_click(era))
                        w.bind("<Double-Button-1>",
                               lambda e, era=era: _era_dbl(era))
            tk.Label(imgcol, text="单击设默认套 · 双击重生成",
                     font=(FONT_UI, 7), bg=theme.PANEL,
                     fg=theme.MUTED).pack()
        ent = tk.Entry(midcol, width=(52 if horizontal else 22),
                       font=(FONT_UI, 9), relief="flat",
                       bg=theme.BG, fg=theme.TEXT)
        ent.insert(0, info.get("appearance", ""))
        ent.pack(padx=8, pady=2, anchor="w" if horizontal else "n")
        tk.Label(midcol, text=_t("ds.prompt"), font=(FONT_UI, 8),
                 bg=theme.PANEL, fg=theme.MUTED).pack(
            anchor="w" if horizontal else "n")
        pmt = tk.Entry(midcol, width=(52 if horizontal else 22),
                       font=(FONT_UI, 9), relief="flat",
                       bg=theme.ACCENT_FAINT, fg=theme.TEXT)
        pmt.pack(padx=8, pady=(0, 2), anchor="w" if horizontal else "n")

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
                    try:
                        # 形象图一变，旧三视图即过期：自动续做（约定免手点）
                        dramavideo.three_view(state, name, dict(item),
                                              force=True)
                    except Exception:        # noqa: BLE001  失败可手点按钮补
                        pass
                    win.after(0, lambda: (_refresh_cast(),
                                          status(_t("ds.ready"))))
            threading.Thread(target=work, daemon=True).start()

        def _regen_look(era):
            """双击阶段缩略图：重生成该阶段形象（主图锁脸，只换服装发型）。

            提示词框非空时作为该阶段的主体提示词（取代外貌描述），
            生成前手改构图/版式从这里进。
            """
            item = _save_look_to_json(ent)      # 先存描述框改动，取回资产记录
            custom = pmt.get().strip()          # 与主图共用自定义提示词框
            if st["busy"]:
                status(_t("ds.busy"), busy=True)
                return
            status(_t("ds.generating", n=f"{name}·{era}"), busy=True)

            def work():
                ev = lambda e: win.after(0, lambda: _gen_event(e))   # noqa: E731
                try:
                    lk = dramavideo.gen_look(state, name, dict(item), era,
                                             custom_prompt=custom, on_event=ev)
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
                    try:
                        # 阶段图一变，该阶段旧三视图即过期：自动续做
                        dramavideo.three_view(state, name, dict(it), era=era,
                                              ref_path=old.get("path"),
                                              force=True)
                    except Exception:        # noqa: BLE001  失败不阻断
                        pass
                    win.after(0, lambda: (_refresh_cast(),
                                          status(_t("ds.ready"))))
            threading.Thread(target=work, daemon=True).start()

        row1 = tk.Frame(midcol, bg=theme.PANEL)
        row1.pack(pady=(0, 2), anchor="w")
        ui._flat_button(row1, text=_t("ds.save_look"), width=9,
                        font=(FONT_UI, 9), command=_save_app
                        ).pack(side="left", padx=2)
        ui._flat_button(row1, text=_t("ds.upload"), width=9,
                        font=(FONT_UI, 9), command=_upload
                        ).pack(side="left", padx=2)
        row2 = tk.Frame(midcol, bg=theme.PANEL)
        row2.pack(pady=(0, 8), anchor="w")
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
                        _refresh_cast()          # 三视图立即显示在角色行内
                    win.after(0, done)
            threading.Thread(target=work, daemon=True).start()

        ui._flat_button(row2, text=_t("ds.three_view"), width=9,
                        font=(FONT_UI, 9),
                        command=lambda: _three_view()
                        ).pack(side="left", padx=2)

        if horizontal:
            # 三视图列：主形象 + 各阶段各一张（描述生成/阶段图重生成后自动续做）
            _gb = dramavideo._global_base(state)
            _sn = dramavideo._safe_name(name)
            shown = 0
            for tv_era in [""] + list((info.get("looks") or {}).keys()):
                suffix = f"-{dramavideo._safe_name(tv_era)}" if tv_era else ""
                tvp = os.path.join(
                    _gb, f"{_sn}{suffix}-三视图.png")
                if not os.path.isfile(tvp):
                    continue
                tvph = _thumb(tvp, (176, 99))
                if not tvph:
                    continue
                st["img_refs"].append(tvph)
                tk.Label(tvcol, text=f"三视图·{tv_era or '主形象'}"
                         "（点击放大）",
                         font=(FONT_UI, 7), bg=theme.PANEL,
                         fg=theme.MUTED).pack()
                tvl = tk.Label(tvcol, image=tvph, bg=theme.PANEL,
                               cursor="hand2")
                tvl.pack(pady=(0, 4))
                tvl.bind("<Button-1>", lambda e, p=tvp: os.startfile(p))
                shown += 1
            if not shown:
                tk.Label(tvcol, text="暂无三视图（生成形象图后自动续做，"
                         "或点「三视图」）",
                         font=(FONT_UI, 8), bg=theme.PANEL,
                         fg=theme.MUTED, justify="center").pack(pady=(36, 0))

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

    def _add_asset():
        """手动新增资产（入通用库）：名称 + 类型 + 外貌锚，出图走卡片按钮。"""
        top = tk.Toplevel(win, bg=theme.PANEL)
        top.title(_t("ds.add_asset_title"))
        top.transient(win)
        top.grab_set()
        top.resizable(False, False)
        frm = tk.Frame(top, bg=theme.PANEL, padx=14, pady=10)
        frm.pack()
        tk.Label(frm, text=_t("ds.add_name"), font=(FONT_UI, 10),
                 bg=theme.PANEL, fg=theme.MUTED).grid(row=0, column=0, sticky="w")
        name_e = tk.Entry(frm, width=24, font=(FONT_UI, 10), relief="flat",
                          bg=theme.BG, fg=theme.TEXT)
        name_e.grid(row=0, column=1, padx=6, pady=3)
        tk.Label(frm, text=_t("ds.add_type"), font=(FONT_UI, 10),
                 bg=theme.PANEL, fg=theme.MUTED).grid(row=1, column=0, sticky="w")
        type_box = ttk.Combobox(frm, values=list(dramavideo._ASSET_SECTIONS),
                                state="readonly", width=10,
                                font=(FONT_UI, 10))
        type_box.set(dramavideo._ASSET_SECTIONS[0])
        type_box.grid(row=1, column=1, sticky="w", padx=6, pady=3)
        tk.Label(frm, text=_t("ds.add_appearance"), font=(FONT_UI, 10),
                 bg=theme.PANEL, fg=theme.MUTED).grid(row=2, column=0, sticky="w")
        app_e = tk.Entry(frm, width=24, font=(FONT_UI, 10), relief="flat",
                         bg=theme.BG, fg=theme.TEXT)
        app_e.grid(row=2, column=1, padx=6, pady=3)

        def _ok():
            n = name_e.get().strip()
            if not n:
                status(_t("ds.add_need_name"))
                return
            c = _cast()
            if n in c:
                status(_t("ds.add_exists", n=n))
                return
            c[n] = {"type": type_box.get() or "角色",
                    "appearance": app_e.get().strip()}
            _dump_json(cast_path, c)
            top.destroy()
            _refresh_cast()
            status(_t("ds.add_done", n=n))
        ui._flat_button(frm, text=_t("ds.add_ok"), width=10, font=(FONT_UI, 10),
                        command=_ok).grid(row=3, column=1, sticky="e",
                                          pady=(8, 0))
        name_e.focus_set()

    def _batch_class(sec):
        """按类批量出图：通用库 + 本章库中该类缺 path 的资产逐个点亮。"""
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        stores = [cast_path, dramavideo._chapter_assets_path(state, st["ch"])]
        todo = []
        for sp in stores:
            for n, info in _load_json(sp, {}).items():
                if n.startswith("_") or not isinstance(info, dict):
                    continue
                if (info.get("type") or "角色") != sec:
                    continue
                if not (info.get("path") or ""):
                    todo.append((sp, n, info))
        if not todo:
            status(_t("ds.batch_class_none", sec=sec))
            return

        def work():
            ok = fail = 0
            for sp, n, info in todo:
                try:
                    new_info = dramavideo.gen_asset(
                        state, n, dict(info), fallback_dir=os.path.dirname(sp))
                except Exception:        # noqa: BLE001 单张失败不阻断批次
                    fail += 1
                    continue
                c = _load_json(sp, {})
                it = c.get(n) or dict(info)
                it["path"] = new_info.get("path")
                it["url"] = new_info.get("url")
                c[n] = it
                _dump_json(sp, c)
                ok += 1
            win.after(0, lambda: (_refresh_cast(),
                                  status(_t("ds.batch_class_done", sec=sec,
                                            ok=ok, fail=fail))))
        status(_t("ds.generating", n=_t("ds.batch_class", sec=sec)),
               busy=True)
        threading.Thread(target=work, daemon=True).start()

    ui._flat_button(foot2, text=_t("ds.add_asset"), width=12,
                    font=(FONT_UI, 10),
                    command=_add_asset).pack(side="left", padx=(6, 2))
    for _sec in dramavideo._ASSET_SECTIONS:
        ui._flat_button(foot2, text=_t("ds.batch_class", sec=_sec), width=8,
                        font=(FONT_UI, 9),
                        command=lambda s=_sec: _batch_class(s)
                        ).pack(side="left", padx=2)
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
    # ---- 勾选拼接（参考火宝「拼接导出」选择模式）：开多选 → 勾选镜头 → 合成选中 ----
    pick_var = tk.BooleanVar(value=False)

    def _toggle_pick():
        on = not pick_var.get()
        pick_var.set(on)
        shots_lb.config(selectmode="multiple" if on else "browse")
        pick_btn.config(fg=theme.ACCENT if on else theme.MUTED)
        if not on:
            # 退出选择模式：收敛回当前编辑镜头，避免多选残留干扰导航
            shots_lb.selection_clear(0, "end")
            shots_lb.selection_set(st["shot"])
            shots_lb.see(st["shot"])
        status(_t("ds.pick_on" if on else "ds.pick_off"))
    pick_btn = ui._flat_button(left3, text=_t("ds.pick_mode"), width=16,
                               font=(FONT_UI, 9), command=_toggle_pick)
    pick_btn.pack(anchor="w", padx=8, pady=(0, 2))
    ui._flat_button(left3, text=_t("ds.concat_sel"), width=16,
                    font=(FONT_UI, 9),
                    command=lambda: _gen("concat_sel")).pack(anchor="w",
                                                             padx=8, pady=(0, 6))

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
    # 语速估算提示：旁白+台词完读所需秒数——低于它人物会说到一半被切镜
    spk_lbl = tk.Label(row3c, text="", font=(FONT_UI, 9), bg=theme.PANEL,
                       fg=theme.ACCENT)
    spk_lbl.pack(side="left", padx=(8, 0))
    row3d = tk.Frame(center3, bg=theme.PANEL)
    row3d.pack(fill="x", padx=10, pady=2)
    tk.Label(row3d, text=_t("ds.props"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(side="left")
    props_e = tk.Entry(row3d, width=26, font=(FONT_UI, 10), relief="flat",
                       bg=theme.BG, fg=theme.TEXT)
    props_e.pack(side="left", padx=4)
    tk.Label(center3, text=_t("ds.desc"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=10)
    desc_t = tk.Text(center3, height=8, font=(FONT_UI, 10), wrap="word",
                     relief="flat", bg="white", fg=theme.TEXT, padx=8, pady=6)
    desc_t.pack(fill="both", expand=True, padx=10)
    # 氛围：一句完整的环境+情绪描述（光线/色调/天气+基调），随镜头走
    tk.Label(center3, text=_t("ds.mood"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=10)
    mood_t = tk.Text(center3, height=2, font=(FONT_UI, 10), wrap="word",
                     relief="flat", bg=theme.ACCENT_FAINT, fg=theme.TEXT,
                     padx=8, pady=4)
    mood_t.pack(fill="x", padx=10, pady=(2, 4))

    # ---- @角色名 自动补全（描述编辑框输入 @ 弹候选菜单，选中插入 @name） ----
    _role_popup = {"top": None, "lb": None, "items": [],
                   "prefix": "", "insert_index": None}

    def _role_names() -> list:
        """当前 cast 里所有角色名（全书 + 本章专属），按长度排序短前缀优先。"""
        names = []
        for k in _cast():
            if not k.startswith("_") and isinstance(_cast()[k], dict):
                names.append(k)
        return sorted(set(names), key=lambda s: (len(s), s))

    def _close_role_popup():
        top = _role_popup["top"]
        if top is not None:
            try:
                top.destroy()
            except tk.TclError:
                pass
        _role_popup["top"] = None
        _role_popup["lb"] = None
        _role_popup["items"] = []
        _role_popup["prefix"] = ""
        _role_popup["insert_index"] = None

    def _show_role_popup(prefix: str):
        """在光标位置显示 popup，列出以 prefix 开头的角色名。"""
        names = _role_names()
        if prefix:
            cands = [n for n in names if n.startswith(prefix)]
        else:
            cands = names[:10]                 # 无前缀时取前 10 个
        if not cands:
            _close_role_popup()
            return
        # 关旧 popup（如有）
        if _role_popup["top"] is not None:
            _close_role_popup()
        top = tk.Toplevel(win, bg=theme.PANEL)
        top.wm_overrideredirect(True)
        # 定位到 desc_t 光标处（屏幕坐标）
        try:
            x, y, _, _ = desc_t.bbox("insert") or (0, 0, 0, 0)
            ax = desc_t.winfo_rootx() + x
            ay = desc_t.winfo_rooty() + y + 20
        except Exception:                  # noqa: BLE001
            ax, ay = win.winfo_rootx() + 50, win.winfo_rooty() + 100
        top.geometry(f"+{ax}+{ay}")
        lb = tk.Listbox(top, font=(FONT_UI, 10), bg=theme.PANEL,
                        fg=theme.TEXT, relief="flat", highlightthickness=1,
                        highlightbackground=theme.BORDER,
                        selectbackground=theme.ACCENT,
                        selectforeground="#ffffff",
                        width=18, height=min(8, len(cands)))
        lb.pack()
        for n in cands:
            lb.insert("end", n)
        lb.selection_clear(0)
        lb.selection_set(0)
        lb.activate(0)
        lb.focus_set()
        _role_popup["top"] = top
        _role_popup["lb"] = lb
        _role_popup["items"] = cands
        _role_popup["prefix"] = prefix

        def _pick(_e=None):
            sel = lb.curselection()
            if sel:
                name = cands[sel[0]]
                idx = _role_popup["insert_index"]
                _insert_at_cursor(f"@{name}", idx)
            _close_role_popup()
            return "break"

        def _on_arrow(e):
            cur = lb.curselection()
            n = len(cands)
            if not cur:
                return
            i = cur[0]
            if e.keysym == "Down" and i < n - 1:
                lb.selection_clear(i)
                lb.selection_set(i + 1)
                lb.activate(i + 1)
                lb.see(i + 1)
            elif e.keysym == "Up" and i > 0:
                lb.selection_clear(i)
                lb.selection_set(i - 1)
                lb.activate(i - 1)
                lb.see(i - 1)
            return "break"

        lb.bind("<Return>", _pick)
        lb.bind("<Double-Button-1>", _pick)
        lb.bind("<Escape>", lambda e: (_close_role_popup(), "break"))
        lb.bind("<Down>", _on_arrow)
        lb.bind("<Up>", _on_arrow)
        # 点 popup 外关闭
        top.bind("<FocusOut>", lambda e: win.after(50, _close_role_popup))

    def _insert_at_cursor(text: str, default_index: str = None):
        """在 desc_t 光标处插入 text，并保持光标在文本后。"""
        try:
            if default_index:
                desc_t.mark_set("insert", default_index)
            desc_t.insert("insert", text)
        except tk.TclError:
            desc_t.insert("end", text)

    def _filter_role_popup():
        """输入更多字符时按当前 @ 前缀过滤已显示的 popup。"""
        if _role_popup["top"] is None:
            return
        # 读取 desc_t 当前 insert 位置往前最近的 @ 到 insert 之间的内容作为新前缀
        idx = desc_t.index("insert")
        line, ch = idx.split(".")
        ch = int(ch)
        line_text = desc_t.get(f"{line}.0", idx)
        at_pos = line_text.rfind("@")
        if at_pos < 0:
            _close_role_popup()
            return
        prefix = line_text[at_pos + 1:]
        # 去掉中间含空白/中文逗号的——视为已结束输入
        if any(c in prefix for c in " \t，。；、"):
            _close_role_popup()
            return
        # prefix 里有角色名完整字符串 → 自动收尾（说明选中后继续打字）
        names = _role_names()
        for n in names:
            if prefix.startswith(n) and len(prefix) > len(n):
                _close_role_popup()
                return
        _show_role_popup(prefix)

    def _on_desc_key(e):
        """监听 desc_t 按键——`@` 触发候选菜单；其它键过滤已展开 popup。"""
        if e.char == "@" and _role_names():
            # 记录光标插入位置（@ 即将插入的地方），popup 选中后写入此处
            _role_popup["insert_index"] = desc_t.index("insert")
            win.after(0, lambda: _show_role_popup(""))
        elif _role_popup["top"] is not None:
            win.after(0, _filter_role_popup)

    desc_t.bind("<Key>", _on_desc_key)
    # 失焦 / 点击 popup 外部时关 popup
    desc_t.bind("<FocusOut>", lambda e: win.after(80, _close_role_popup))
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
    # ---- 视频提示词（火宝 3 秒分段）：查看 / 手改 / 单镜重新生成 ----
    vp_row = tk.Frame(center3, bg=theme.PANEL)
    vp_row.pack(fill="x", padx=10, pady=(0, 0))
    tk.Label(vp_row, text=_t("ds.video_prompt"), font=(FONT_UI, 10),
             bg=theme.PANEL, fg=theme.ACCENT).pack(side="left")
    ui._flat_button(vp_row, text=_t("ds.regen_vp"), width=12,
                    font=(FONT_UI, 9),
                    command=lambda: _regen_vp()).pack(side="right")
    vp_t = tk.Text(center3, height=4, font=(FONT_UI, 9), wrap="word",
                   relief="flat", bg=theme.ACCENT_FAINT, fg=theme.TEXT,
                   padx=8, pady=4)
    vp_t.pack(fill="x", padx=10, pady=(2, 4))
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

    # ---- 批量生成视频 + 重试失败（参考火宝 v3.1 选择模式 + 预生成确认） ----
    def _batch_all():
        """批量生成本章全部镜头视频（已有文件跳过）；弹确认窗。"""
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        shots = _shots()
        if not shots:
            status(_t("ds.need_shots", n=st["ch"]))
            return
        ch, n = st["ch"], len(shots)
        existing = sum(
            1 for i in range(1, n + 1)
            if os.path.exists(os.path.join(book, dramavideo._CLIP_DIR,
                                          f"{ch}-{i:02d}.mp4")))
        todo = n - existing
        total_sec = sum(max(int(s.get("duration") or 5), 5) for s in shots)
        cur_label = (video_provider_var.get() or "(自动)")
        cur_res = (video_resolution_var.get() or "(自动)")
        msg = _t("ds.batch_confirm",
                 ch=ch, todo=todo, total=total_sec,
                 n=n, cur=cur_label, res=cur_res)
        from tkinter import messagebox
        if not messagebox.askyesno(_t("ds.batch_title"), msg, parent=win):
            return

        def work():
            ev = lambda e: win.after(0, lambda: _gen_event(e))   # noqa: E731
            try:
                res = dramavideo.run_clips_batch(state, ch, on_event=ev)
                win.after(0, lambda: status(
                    _t("ds.batch_done",
                       ok=len(res.get("ok") or []),
                       skip=len(res.get("skipped_existing") or []),
                       fail=len(res.get("fail") or []))))
            except dramavideo.DramaModerationError:
                pass
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda err=e: status(
                    f"❌ {type(err).__name__}: {err}"))

        status(_t("ds.generating", n=_t("ds.batch_all_btn", n=ch)), busy=True)
        threading.Thread(target=work, daemon=True).start()

    def _batch_retry():
        """重试本章失败任务（同 batch_all，但显式提示这是补完流程）。"""
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        ch = st["ch"]
        from tkinter import messagebox
        if not messagebox.askyesno(_t("ds.batch_retry_title"),
                                   _t("ds.batch_retry_msg", n=ch),
                                   parent=win):
            return

        def work():
            ev = lambda e: win.after(0, lambda: _gen_event(e))   # noqa: E731
            try:
                res = dramavideo.run_clips_batch(state, ch, on_event=ev)
                win.after(0, lambda: status(
                    _t("ds.batch_done",
                       ok=len(res.get("ok") or []),
                       skip=len(res.get("skipped_existing") or []),
                       fail=len(res.get("fail") or []))))
            except dramavideo.DramaModerationError:
                pass
            except Exception as e:       # noqa: BLE001
                win.after(0, lambda err=e: status(
                    f"❌ {type(err).__name__}: {err}"))

        status(_t("ds.generating", n=_t("ds.batch_retry_btn", n=ch)), busy=True)
        threading.Thread(target=work, daemon=True).start()

    ui._icon_text_button(right3, "package", _t("ds.batch_all_btn"),
                       command=_batch_all, font=(FONT_UI, 10)).pack(pady=3)
    ui._icon_text_button(right3, "refresh", _t("ds.batch_retry_btn"),
                       command=_batch_retry, font=(FONT_UI, 10)).pack(pady=3)
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

    # ---- 收尾（火宝「拼接导出」）：标记完成 + 成片列表/播放 ----
    done_var = tk.BooleanVar(
        value=st["ch"] in (state.get("drama_done_chapters") or []))

    def _toggle_done():
        lst = state.setdefault("drama_done_chapters", [])
        if done_var.get() and st["ch"] not in lst:
            lst.append(st["ch"])
        elif not done_var.get() and st["ch"] in lst:
            lst.remove(st["ch"])
        try:
            p.save()
        except Exception:              # noqa: BLE001
            pass
        status(_t("ds.mark_done_on", n=st["ch"]) if done_var.get()
               else _t("ds.mark_done_off", n=st["ch"]))

    tk.Checkbutton(right3, text=_t("ds.mark_done"), variable=done_var,
                   command=_toggle_done, font=(FONT_UI, 9),
                   bg=theme.PANEL, fg=theme.MUTED,
                   activebackground=theme.PANEL).pack(anchor="w", padx=10,
                                                      pady=(6, 0))
    merge_var = tk.StringVar()
    merge_box = ttk.Combobox(right3, textvariable=merge_var, state="readonly",
                             font=(FONT_UI, 9))
    merge_box.pack(fill="x", padx=10, pady=(6, 0))

    def _refresh_merges():
        """成片列表：本章已合成的 mp4（整集 + 选段），拼完即刷新。"""
        out_dir = os.path.join(book, dramavideo._OUT_DIR)
        files = []
        if os.path.isdir(out_dir):
            files = sorted(
                (f for f in os.listdir(out_dir)
                 if f.startswith(f"第{st['ch']}章")
                 and f.endswith(".mp4")), reverse=True)
        merge_box["values"] = files
        merge_var.set(files[0] if files else _t("ds.no_merges"))

    def _play_merge():
        f = merge_var.get()
        if not f or f == _t("ds.no_merges"):
            status(_t("ds.no_out"))
            return
        os.startfile(os.path.join(book, dramavideo._OUT_DIR, f))

    ui._flat_button(right3, text=_t("ds.play_merge"), width=18,
                    font=(FONT_UI, 10),
                    command=lambda: _play_merge()).pack(pady=3)

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
        _refresh_merges()

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
        mood_t.delete("1.0", "end")
        mood_t.insert("1.0", s.get("mood", ""))
        need = dramavideo._speech_seconds(s)
        dur = int(float(s.get("duration") or 0))
        lack = dur < need
        spk_lbl.config(text=_t("ds.speech_hint", n=need) + (" ⚠" if lack else ""),
                       fg=theme.DANGER if lack else theme.ACCENT)
        chars_e.delete(0, "end")
        chars_e.insert(0, "、".join(s.get("characters", [])))
        props_e.delete(0, "end")
        props_e.insert(0, "、".join(s.get("props", [])))
        sec_sp.set(int(s.get("duration", 5)))
        desc_t.delete("1.0", "end"); desc_t.insert("1.0", s.get("description", ""))
        narr_e.delete(0, "end"); narr_e.insert(0, s.get("narration", ""))
        dlge.delete(0, "end"); dlge.insert(0, s.get("dialogue", ""))
        vp_t.delete("1.0", "end"); vp_t.insert("1.0", s.get("video_prompt", ""))
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
        s["mood"] = mood_t.get("1.0", "end-1c").strip()[:60]
        s["characters"] = [c.strip() for c in chars_e.get().split("、") if c.strip()][:4]
        s["props"] = [c.strip() for c in props_e.get().split("、") if c.strip()][:3]
        try:
            s["duration"] = max(4, min(15, int(float(sec_sp.get()))))
        except (TypeError, ValueError):
            pass
        s["description"] = desc_t.get("1.0", "end-1c").strip()
        s["narration"] = narr_e.get().strip()[:80]
        s["dialogue"] = dlge.get().strip()
        s["video_prompt"] = vp_t.get("1.0", "end-1c").strip()
        _dump_json(_shots_file(st["ch"]), data)
        _refresh_shots(st["shot"])
        status(_t("ds.saved", n=s["title"] or f"镜头{st['shot']+1}"))

    def _regen_vp():
        """单镜重新生成 video_prompt（火宝 3 秒分段规范），结果落盘并回填文本框。"""
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        _save_shot()                       # 表单改动先落盘，重生成基于最新分镜
        status(_t("ds.generating", n=_t("ds.regen_vp")), busy=True)

        def work():
            vp = dramavideo.regen_video_prompt(state, st["ch"], st["shot"] + 1)

            def done():
                if vp:
                    vp_t.delete("1.0", "end")
                    vp_t.insert("1.0", vp)
                    status(_t("ds.regen_vp_done", n=st["shot"] + 1))
                else:
                    status(_t("ds.regen_vp_fail"))
            win.after(0, done)
        threading.Thread(target=work, daemon=True).start()

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
            _src_hint()
            done_var.set(st["ch"] in (state.get("drama_done_chapters") or []))

    def _episode_overview():
        """剧集列表：每集制作状态总览（全部从磁盘产物派生），双击进入该集。"""
        top = tk.Toplevel(win, bg=theme.PANEL)
        top.title(_t("ds.ep_list", t=state.get("title", "")))
        top.transient(win)
        lb = tk.Listbox(top, width=72, height=20, font=(FONT_MONO, 10),
                        bg=theme.PANEL, fg=theme.TEXT, relief="flat",
                        highlightthickness=1,
                        highlightbackground=theme.BORDER,
                        selectbackground=theme.ACCENT,
                        selectforeground="#ffffff")
        lb.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        tk.Label(top, text=_t("ds.ep_jump"), font=(FONT_UI, 8),
                 bg=theme.PANEL, fg=theme.MUTED).pack(pady=(0, 8))
        out_dir = os.path.join(book, dramavideo._OUT_DIR)
        for c in chapters:
            ch = c["idx"]
            using_sp = os.path.exists(dramavideo._screenplay_path(state, ch))
            shots = _load_json(os.path.join(book, dramavideo._SHOT_DIR,
                                            f"第{ch}章.json"), [])
            n = len(shots)
            vids = sum(
                1 for i in range(1, n + 1)
                if os.path.exists(os.path.join(book, dramavideo._CLIP_DIR,
                                               f"{ch}-{i:02d}.mp4")))
            merged = os.path.isdir(out_dir) and any(
                f.startswith(f"第{ch}章") and f.endswith(".mp4")
                for f in os.listdir(out_dir))
            done = ch in (state.get("drama_done_chapters") or [])
            lb.insert("end", _t(
                "ds.ep_row",
                n=ch, t=str(c.get("title", ""))[:12],
                src=_t("ds.ep_src_screenplay" if using_sp
                       else "ds.ep_src_novel"),
                s=n, v=vids,
                out=_t("ds.ep_out_yes" if merged else "ds.ep_out_no"),
                done=_t("ds.ep_done" if done else "ds.ep_pending")))

        def _jump(_e=None):
            sel = lb.curselection()
            if not sel:
                return
            ch = chapters[sel[0]]["idx"]
            top.destroy()
            for i, c in enumerate(chapters):
                if c["idx"] == ch:
                    ch_box.current(i)
                    break
            _on_chapter()
        lb.bind("<Double-Button-1>", _jump)

    _GEN_KIND = {"frame": "关键帧", "clip": "镜头视频", "dub": "配音",
                 "cast": "形象", "shots": "分镜",
                 "redo": "重做", "concat_skip": "拼接跳过",
                 "moderation": "审核拒绝", "debt": "失败"}

    def _gen_event(e):
        """生成子步骤（关键帧/镜头视频/配音）→ 状态栏分步提示。"""
        if e.get("type") == "drama_media":
            if e.get("kind") == "moderation":
                st["_moderation_last"] = {
                    "label": e.get("label"),
                    "hint": e.get("hint"),
                    "original": e.get("original"),
                    "provider_id": e.get("provider_id"),
                    "model": e.get("model"),
                }
                status(_t("ds.moderation_msg",
                          n=(e.get("label") or ""),
                          h=(e.get("hint") or "")[:120]))
                mod_btn.pack(side="right", padx=(6, 0))
                return
            if e.get("kind") == "concat_skip":
                names = e.get("names") or []
                status(_t("ds.concat_skip",
                          n=len(names),
                          names="、".join(names)[:120]))
                return
            if e.get("label"):
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
        elif kind == "concat":
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
        else:
            # concat_sel：只拼勾选镜头，缺失跳过（部分拼接，huobao 语义）
            idxs = st.get("_pick_sel") or []
            if not idxs:
                raise RuntimeError(_t("ds.no_pick"))
            clips, missing = [], []
            for k in idxs:
                _, cp = _shot_paths(ch, k + 1)
                if os.path.exists(cp):
                    clips.append(cp)
                else:
                    missing.append(k + 1)
            if not clips:
                raise RuntimeError(_t("ds.no_clips"))
            c = next(c for c in chapters if c["idx"] == ch)
            out = os.path.join(
                book, dramavideo._OUT_DIR,
                f"第{ch}章-{dramavideo._safe_name(c['title'])}-选段.mp4")
            dramavideo.concat(clips, out)
            win.after(0, lambda: (os.startfile(out),
                                  status(_t("ds.concat_sel_done",
                                            n=len(clips),
                                            skip=len(missing)))))

    def _gen(kind):
        if st["busy"]:
            status(_t("ds.busy"), busy=True)
            return
        if kind in ("frame", "clip", "take"):
            # 表单编辑先落盘：改完直接点生成即生效，不必先点「保存分镜」
            _save_shot()
        if kind == "concat_sel":
            # 勾选态只能在主线程读（worker 不碰 widget），先快照进 st
            st["_pick_sel"] = sorted(int(x) for x in shots_lb.curselection())
        names = {"frame": _t("ds.gen_frame"), "clip": _t("ds.gen_clip"),
                 "take": _t("ds.take"), "concat": _t("ds.concat"),
                 "concat_sel": _t("ds.concat_sel")}
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
