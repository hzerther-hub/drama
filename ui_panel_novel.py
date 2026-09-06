# -*- coding: utf-8 -*-
"""开书工作台（纯 Tkinter）：自动导演开书 / 运行监控 / 拆书·短剧衍生。

三个标签页：
- 开书：一句灵感 + 章数 + 逐阶段确认 + 写法参考 → 自动导演主链
- 运行：阶段状态、质量债、日志、暂停/继续/停止、打开书稿（进编辑器）
- 衍生：拆书（外部文本→报告+写法特征）、短剧改编（章节→剧本+分镜）
纯 tk/ttk 实现，无 Web 依赖；流水线在 daemon 线程跑，事件回主线程渲染。
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, ttk

from i18n import t as _t

import novel_chain
import pipeline
import vecstore
import imggen


def show(app):
    """打开（或聚焦）开书工作台。"""
    existing = getattr(app, "_novel_win", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        return existing
    win = NovelWorkbench(app)
    app._novel_win = win
    return win


class NovelWorkbench(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("📖 " + _t("novel.title"))
        self.geometry("760x600+80+60")
        self.pipe: pipeline.Pipeline | None = None
        self._busy = False

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.tab_new = tk.Frame(nb, bg=theme_bg())
        self.tab_run = tk.Frame(nb, bg=theme_bg())
        self.tab_tools = tk.Frame(nb, bg=theme_bg())
        nb.add(self.tab_new, text=_t("novel.tab.new"))
        nb.add(self.tab_run, text=_t("novel.tab.run"))
        nb.add(self.tab_tools, text=_t("novel.tab.tools"))
        self._build_new_tab()
        self._build_run_tab()
        self._build_tools_tab()
        self.refresh_pipelines()

    # ---------------- Tab 1：开书 ----------------

    def _build_new_tab(self):
        f = self.tab_new
        tk.Label(f, text=_t("novel.idea"), bg=theme_bg(), anchor="w").pack(
            fill="x", padx=12, pady=(10, 2))
        self.txt_idea = tk.Text(f, height=3, font=("Consolas", 11), wrap="word")
        self.txt_idea.pack(fill="x", padx=12)

        row = tk.Frame(f, bg=theme_bg())
        row.pack(fill="x", padx=12, pady=6)
        tk.Label(row, text=_t("novel.chapters"), bg=theme_bg()).pack(side="left")
        self.spin_ch = tk.Spinbox(row, from_=1, to=12, width=4)
        self.spin_ch.delete(0, "end")
        self.spin_ch.insert(0, "3")
        self.spin_ch.pack(side="left", padx=(4, 16))
        self.var_step = tk.BooleanVar(value=False)
        tk.Checkbutton(row, text=_t("novel.stepwise"), variable=self.var_step,
                       bg=theme_bg()).pack(side="left")

        tk.Label(f, text=_t("novel.style"), bg=theme_bg(), anchor="w").pack(
            fill="x", padx=12, pady=(2, 2))
        self.txt_style = tk.Text(f, height=3, font=("Consolas", 10), wrap="word")
        self.txt_style.pack(fill="x", padx=12)

        rag = ("RAG: Qdrant" if vecstore.rag_enabled() else "RAG: " + _t("novel.rag_local"))
        img = ("Img: " + imggen.model() if imggen.available()
               else "Img: " + _t("novel.img_off"))
        tk.Label(f, text=f"{rag}    {img}", bg=theme_bg(), fg="#64748b",
                 anchor="w").pack(fill="x", padx=12, pady=(6, 2))

        tk.Button(f, text="🎬 " + _t("novel.start"), font=("TkDefault Font", 11, "bold"),
                  command=self.start, bg="#2563eb", fg="white", relief="flat",
                  padx=14, pady=4).pack(pady=10)

    def start(self):
        idea = self.txt_idea.get("1.0", "end").strip()
        if not idea:
            self.log(_t("novel.need_idea"))
            return
        model_key = self.app.current_model.key if self.app.current_model else ""
        if not model_key:
            self.log(_t("novel.need_model"))
            return
        try:
            total = int(self.spin_ch.get())
        except ValueError:
            total = 3
        style = self.txt_style.get("1.0", "end").strip()
        p = novel_chain.new_pipeline(idea, total, model_key, style)
        self._run_pipe(p, until="volume" if self.var_step.get() else None)

    # ---------------- Tab 2：运行 ----------------

    def _build_run_tab(self):
        f = self.tab_run
        top = tk.Frame(f, bg=theme_bg())
        top.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(top, text=_t("novel.pick_pipeline"), bg=theme_bg()).pack(side="left")
        self.cmb_pipes = ttk.Combobox(top, state="readonly", width=42)
        self.cmb_pipes.pack(side="left", padx=6)
        for text, cmd in ((_t("novel.refresh"), self.refresh_pipelines),
                          (_t("novel.continue"), self.resume),
                          (_t("novel.stop"), self.stop),
                          (_t("novel.open_book"), self.open_book)):
            tk.Button(top, text=text, command=cmd, relief="flat",
                      bg="#e2e8f0").pack(side="left", padx=3)

        tk.Label(f, text=_t("novel.stage_status"), bg=theme_bg(),
                 anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        self.lb_stages = tk.Listbox(f, height=8, font=("Consolas", 10))
        self.lb_stages.pack(fill="x", padx=12)

        tk.Label(f, text=_t("novel.debts"), bg=theme_bg(), anchor="w").pack(
            fill="x", padx=12, pady=(8, 2))
        self.txt_debts = tk.Text(f, height=5, font=("Consolas", 9), wrap="word",
                                 bg="#fff7ed")
        self.txt_debts.pack(fill="x", padx=12)

        tk.Label(f, text="Log", bg=theme_bg(), anchor="w").pack(
            fill="x", padx=12, pady=(8, 2))
        self.txt_log = tk.Text(f, height=8, font=("Consolas", 9), wrap="word",
                               bg="#0f172a", fg="#e2e8f0")
        self.txt_log.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    def refresh_pipelines(self):
        rows = pipeline.list_pipelines()
        self._pipe_rows = rows
        vals = [f"{r['pid']}  [{r['pipeline_status']}]  {r['title']}"
                for r in rows]
        self.cmb_pipes["values"] = vals
        if vals:
            self.cmb_pipes.current(0)
        self._render_pipe(self._current_pipe())

    def _current_pipe(self):
        i = self.cmb_pipes.current()
        if 0 <= i < len(getattr(self, "_pipe_rows", [])):
            row = self._pipe_rows[i]
            return pipeline.load(row["pid"], novel_chain.STAGES)
        return self.pipe

    def _render_pipe(self, p):
        self.lb_stages.delete(0, "end")
        self.txt_debts.delete("1.0", "end")
        if not p:
            return
        for s in p.stages:
            st = p.status.get(s.name, "pending")
            label = novel_chain.STAGE_LABELS.get(s.name, s.name)
            self.lb_stages.insert("end", f"[{st:>7}]  {label} ({s.name})")
        for d in p.debts + p.state.get("debts", []):
            line = f"第{d['chapter']}章  {d['detail']}" if d.get("chapter") \
                else f"{d.get('stage','')}  {d.get('detail','')}"
            self.txt_debts.insert("end", line + "\n")

    def resume(self):
        p = self._current_pipe()
        if not p:
            self.log(_t("novel.none"))
            return
        self._run_pipe(p)

    def stop(self):
        if self.pipe:
            self.pipe.request_stop()
            self.log(_t("novel.stopped"))

    def open_book(self):
        p = self._current_pipe() or self.pipe
        path = (p.state.get("file") if p else None) or ""
        if path and __import__("os").path.exists(path):
            self.app._open_file_editor(path)
        else:
            self.log(_t("novel.no_book"))

    # ---------------- Tab 3：衍生（拆书 / 短剧） ----------------

    def _build_tools_tab(self):
        f = self.tab_tools
        tk.Label(f, text=_t("novel.deconstruct"), bg=theme_bg(),
                 anchor="w").pack(fill="x", padx=12, pady=(12, 2))
        tk.Button(f, text="📂 " + _t("novel.pick_file"), command=self.deconstruct,
                  relief="flat", bg="#e2e8f0").pack(padx=12, anchor="w")

        tk.Label(f, text=_t("novel.drama"), bg=theme_bg(),
                 anchor="w").pack(fill="x", padx=12, pady=(18, 2))
        row = tk.Frame(f, bg=theme_bg())
        row.pack(padx=12, anchor="w")
        tk.Label(row, text=_t("novel.drama_range"), bg=theme_bg()).pack(side="left")
        self.spin_from = tk.Spinbox(row, from_=1, to=99, width=4)
        self.spin_to = tk.Spinbox(row, from_=1, to=99, width=4)
        self.spin_from.delete(0, "end")
        self.spin_from.insert(0, "1")
        self.spin_to.delete(0, "end")
        self.spin_to.insert(0, "1")
        self.spin_from.pack(side="left", padx=4)
        tk.Label(row, text="-", bg=theme_bg()).pack(side="left")
        self.spin_to.pack(side="left", padx=4)
        tk.Button(row, text="🎬 " + _t("novel.drama_go"), command=self.drama,
                  relief="flat", bg="#2563eb", fg="white").pack(side="left", padx=8)

    def deconstruct(self):
        path = filedialog.askopenfilename(
            title=_t("novel.pick_file"),
            filetypes=[("Text", "*.txt *.md"), ("All", "*.*")])
        if not path:
            return
        model_key = self.app.current_model.key if self.app.current_model else ""
        if not model_key:
            self.log(_t("novel.need_model"))
            return

        def work():
            try:
                out = novel_chain.deconstruct(path, model_key)
                self.win_log(_t("novel.deconstruct_done", file=out))
            except Exception as e:  # noqa: BLE001
                self.win_log(f"❌ {e}")
        threading.Thread(target=work, daemon=True).start()

    def drama(self):
        p = self._current_pipe() or self.pipe
        if not p or not p.state.get("chapters"):
            self.log(_t("novel.no_chapters"))
            return
        try:
            a = int(self.spin_from.get())
            b = int(self.spin_to.get())
        except ValueError:
            return

        def work():
            try:
                out = novel_chain.drama_adapt(
                    p.state, a, b,
                    on_event=lambda e: self.win_log(
                        _t("novel.drama_ch", n=e.get("idx"))))
                self.win_log(_t("novel.drama_done", file=out))
            except Exception as e:  # noqa: BLE001
                self.win_log(f"❌ {e}")
        threading.Thread(target=work, daemon=True).start()

    # ---------------- 流水线执行 ----------------

    def _run_pipe(self, p, until=None):
        if self._busy:
            self.log(_t("novel.busy"))
            return
        self.pipe = p
        self._busy = True

        def on_event(e):
            self.after(0, lambda: self._on_event(e))

        def work():
            try:
                p.run(on_event=on_event, until=until)
            finally:
                self.after(0, lambda: setattr(self, "_busy", False))
                self.after(0, lambda: self._render_pipe(self.pipe))
                self.after(0, lambda: self._render_pipe_done(self.pipe))
        threading.Thread(target=work, daemon=True).start()

    def _render_pipe_done(self, p):
        self._render_pipe(p)
        if p.pipeline_status == "done" and p.state.get("file"):
            try:
                self.app._open_file_editor(p.state["file"])
            except Exception:          # noqa: BLE001
                pass

    def _on_event(self, e):
        t = e.get("type")
        if t == "stage_start":
            self.log("▶ " + _t("novel.stage",
                               label=novel_chain.STAGE_LABELS.get(
                                   e.get("name"), e.get("name"))))
        elif t == "chapter_done":
            self.log(_t("novel.chapter", n=e.get("idx"),
                        t=e.get("title"), w=e.get("words")))
        elif t == "stage_debt":
            self.log("⚠ " + _t("novel.debt", e=e.get("detail")))
            self._render_pipe(self.pipe)
        elif t == "pipeline_done":
            self.log("✅ " + _t("novel.done_msg", file=self.pipe.state.get("file", "")))
        elif t == "pipeline_paused":
            self.log("⏸ " + _t("novel.paused_msg"))
        elif t == "pipeline_failed":
            self.log("❌ " + _t("novel.failed_msg", e=self.pipe.error))
        self._render_pipe(self.pipe)

    # ---------------- 日志 ----------------

    def log(self, msg):
        self.txt_log.insert("end", str(msg) + "\n")
        self.txt_log.see("end")

    def win_log(self, msg):
        """线程安全日志（工作线程调用）。"""
        self.after(0, lambda: self.log(msg))


def theme_bg():
    try:
        import theme
        return theme.PANEL
    except Exception:                  # noqa: BLE001
        return "#f8fafc"
