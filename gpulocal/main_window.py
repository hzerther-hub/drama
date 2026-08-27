#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gpulocal 主界面（Main Window）
==============================
gpulocal 的入口窗口：一屏总览所有本地模型服务（运行状态 / 端口 / 健康检查）、
GPU 与系统资源摘要，并提供快捷 启动 / 停止 / 重启。

「模型管理面板」（local_model_panel.ModelPanel：GPU/系统/硬件详情、下载、
加载日志等完整功能）从这里以**模态子窗**打开，不再是独立主窗口。

用法：
    python3 main_window.py          # 直接启动主界面
    python3 local_model_panel.py    # 兼容入口：同样进入主界面
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

# 既支持作为 gpulocal 包导入（qwen-coder 内嵌），也支持在 gpulocal/ 目录内直接运行
try:
    from gpulocal import local_model_panel as lmp
except ImportError:                  # noqa: BLE001
    import local_model_panel as lmp

BG = "#f4f4f4"
REFRESH_MS = lmp.REFRESH_MS

# 主界面自己的文案；共享条目直接回落到 lmp.t()
_S = {
    "app.title":     {"en": "gpulocal · Local Model Services", "zh": "gpulocal · 本地模型服务"},
    "sec.models":    {"en": "Model Services", "zh": "模型服务"},
    "sec.resources": {"en": "Resources", "zh": "资源概况"},
    "st.running":    {"en": "Running · healthy", "zh": "运行中 · 健康"},
    "st.loading":    {"en": "Starting / loading…", "zh": "启动中 / 加载中…"},
    "st.stopped":    {"en": "Stopped", "zh": "未运行"},
    "st.failed":     {"en": "Failed", "zh": "失败"},
    "btn.panel":     {"en": "Model Manager Panel", "zh": "模型管理面板"},
    "btn.quit":      {"en": "Quit", "zh": "退出"},
    "act.starting":  {"en": "Starting {name}…", "zh": "正在启动 {name}…"},
    "act.stopping":  {"en": "Stopping {name}…", "zh": "正在停止 {name}…"},
    "act.done":      {"en": "Done: {what}", "zh": "已完成：{what}"},
    "act.fail":      {"en": "Failed: {what} (rc={rc})", "zh": "失败：{what}（退出码 {rc}）"},
    "gpu.none":      {"en": "GPU status unavailable", "zh": "GPU 状态不可用"},
}


def _t(key: str, **kw) -> str:
    e = _S.get(key)
    if e:
        s = e.get(lmp._lang) or e.get("en") or key
        return s.format(**kw) if kw else s
    return lmp.t(key, **kw)


_DOT = {"green": "#16a34a", "yellow": "#d97706", "gray": "#9ca3af", "red": "#dc2626"}


class MainWindow:
    """gpulocal 主界面：模型服务总览 + 资源摘要 + 模态打开管理面板。"""

    def __init__(self):
        lmp._load_lang()
        self.root = tk.Tk()
        self.root.title(_t("app.title"))
        self.root.geometry("680x560")
        self.root.minsize(560, 420)
        self.root.configure(bg=BG)

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
            style.configure("TFrame", background=BG)
            style.configure("TLabel", background=BG)
            style.configure("TLabelframe", relief="flat", background=BG,
                            bordercolor="#d4d4d4", borderwidth=1)
            style.configure("TLabelframe.Label", background=BG, foreground="#334155")
        except Exception:              # noqa: BLE001
            pass

        self._panel = None             # 已打开的 ModelPanel（模态）
        self._rows = {}                # name -> dict(dot, status)
        self._busy = False             # 有启停动作进行中时禁用按钮

        self._build()
        self.root.after(200, self._refresh_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    # ─────────────────── 界面 ───────────────────
    def _build(self):
        hdr = ttk.Frame(self.root, padding=(14, 12))
        hdr.pack(fill="x")
        self._title_lbl = ttk.Label(hdr, text=_t("app.title"),
                                    font=("Microsoft YaHei UI", 14, "bold"))
        self._title_lbl.pack(side="left")
        self._lang_btn = tk.Button(hdr, text="EN/中文", command=self._toggle_lang,
                                   relief="flat", cursor="hand2", padx=8,
                                   bg="#e2e2e2", font=("Microsoft YaHei UI", 9))
        self._lang_btn.pack(side="right")

        # 模型服务列表
        self._models_lf = ttk.Labelframe(self.root, text=_t("sec.models"), padding=(10, 6))
        self._models_lf.pack(fill="x", padx=14, pady=(2, 6))
        tb_font = ("Microsoft YaHei UI", 9)
        for name, cfg in lmp.MODELS.items():
            row = tk.Frame(self._models_lf, bg=BG)
            row.pack(fill="x", pady=3)
            dot = tk.Label(row, text="●", fg=_DOT["gray"], bg=BG,
                           font=("Microsoft YaHei UI", 12))
            dot.pack(side="left")
            ttk.Label(row, text=name, font=("Microsoft YaHei UI", 10, "bold")
                      ).pack(side="left", padx=(4, 8))
            ttk.Label(row, text=":%s" % cfg["port"], foreground="#777"
                      ).pack(side="left")
            status = ttk.Label(row, text="—", foreground="#555")
            status.pack(side="left", padx=10)
            for text_key, cmd in (("btn.restart", lambda n=name: self._svc(n, "restart")),
                                  ("btn.stop", lambda n=name: self._svc(n, "stop")),
                                  ("btn.start", lambda n=name: self._svc(n, "start"))):
                b = tk.Button(row, text=lmp.t(text_key), command=cmd, relief="flat",
                              cursor="hand2", padx=6, pady=1, font=tb_font, bg="#e7e7e7")
                b.pack(side="right", padx=2)
            self._rows[name] = {"dot": dot, "status": status, "frame": row}

        # 资源概况
        self._res_lf = ttk.Labelframe(self.root, text=_t("sec.resources"), padding=(10, 6))
        self._res_lf.pack(fill="x", padx=14, pady=6)
        self._gpu_lbl = ttk.Label(self._res_lf, text="GPU: —", foreground="#444")
        self._gpu_lbl.pack(anchor="w")
        self._sys_lbl = ttk.Label(self._res_lf, text="CPU/Mem: —", foreground="#444")
        self._sys_lbl.pack(anchor="w", pady=(2, 0))

        # 底部动作行
        foot = ttk.Frame(self.root, padding=(14, 10))
        foot.pack(fill="x", side="bottom")
        self._action_lbl = ttk.Label(foot, text="", foreground="#666")
        self._action_lbl.pack(side="left")
        self._quit_btn = tk.Button(foot, text=_t("btn.quit"), command=self.root.destroy,
                                   relief="flat", cursor="hand2", padx=10, pady=3,
                                   bg="#e7e7e7", font=("Microsoft YaHei UI", 10))
        self._quit_btn.pack(side="right")
        self._panel_btn = tk.Button(foot, text=_t("btn.panel"), command=self._open_panel,
                                    relief="flat", cursor="hand2", padx=10, pady=3,
                                    bg="#dbeafe", font=("Microsoft YaHei UI", 10, "bold"))
        self._panel_btn.pack(side="right", padx=8)

    # ─────────────────── 模态面板 ───────────────────
    def _open_panel(self):
        """模型管理面板作为主界面的模态子窗打开（依附主窗 + 锁定主窗交互）。"""
        if self._panel is not None:
            try:
                if self._panel.win.winfo_exists():
                    self._panel.win.lift()
                    self._panel.win.focus_force()
                    return
            except Exception:          # noqa: BLE001  面板已关闭
                pass
            self._panel = None
        panel = lmp.ModelPanel(master=self.root)
        self._panel = panel
        panel.win.bind("<Destroy>", lambda _e: setattr(self, "_panel", None), add="+")
        try:
            import ui as _ui          # 惰性导入，避免与按路径加载成环
            _ui._make_modal(panel.win, self.root)  # 模态：面板关闭前主窗不响应
        except Exception:              # noqa: BLE001
            pass

    # ─────────────────── 启停 ───────────────────
    def _svc(self, name: str, action: str):
        if self._busy:
            return
        cfg = lmp.MODELS[name]
        self._busy = True
        what = {"start": _t("act.starting", name=name),
                "stop": _t("act.stopping", name=name),
                "restart": _t("act.starting", name=name)}[action]
        self._action_lbl.config(text=what)

        def work():
            if action in ("start", "restart"):
                # 串行：先停掉其它模型
                for other_name, other in lmp.MODELS.items():
                    if other is cfg or not other.get("service"):
                        continue
                    if lmp.service_status(other["service"]) == "active":
                        lmp.svc_stop(other)
            rc = {"start": lmp.svc_start, "stop": lmp.svc_stop,
                  "restart": lmp.svc_restart}[action](cfg)
            self.root.after(0, self._svc_done, what, rc)

        threading.Thread(target=work, daemon=True).start()

    def _svc_done(self, what: str, rc: int):
        self._busy = False
        self._action_lbl.config(
            text=_t("act.done", what=what) if rc == 0 else _t("act.fail", what=what, rc=rc))
        self._refresh_async()

    # ─────────────────── 刷新 ───────────────────
    def _refresh_loop(self):
        self._refresh_async()
        try:
            self.root.after(REFRESH_MS, self._refresh_loop)
        except Exception:              # noqa: BLE001  窗口已销毁
            pass

    def _refresh_async(self):
        if not self.root.winfo_exists():
            return

        def collect():
            services = {}
            for name, cfg in lmp.MODELS.items():
                st = lmp.service_status(cfg["service"])
                ok = False
                if st == "active":
                    ok, _ = lmp.health_check(cfg["health_url"], cfg["health_timeout"])
                services[name] = (st, ok)
            gpus, _topo, err = lmp.query_gpu()
            sysinfo = lmp.query_system()
            try:
                self.root.after(0, self._apply, services, gpus, err, sysinfo)
            except Exception:          # noqa: BLE001  窗口已销毁
                pass

        threading.Thread(target=collect, daemon=True).start()

    def _apply(self, services, gpus, gpu_err, sysinfo):
        if not self.root.winfo_exists():
            return
        for name, (st, healthy) in services.items():
            row = self._rows.get(name)
            if not row:
                continue
            if st == "active" and healthy:
                color, txt = _DOT["green"], _t("st.running")
            elif st == "active":
                color, txt = _DOT["yellow"], _t("st.loading")
            elif st == "failed":
                color, txt = _DOT["red"], _t("st.failed")
            else:
                color, txt = _DOT["gray"], _t("st.stopped")
            row["dot"].config(fg=color)
            row["status"].config(text=txt)

        if gpus:
            names = " · ".join("%s %s/%sG" % (
                g["name"].replace("NVIDIA GeForce ", "").replace("NVIDIA ", ""),
                round(float(g["mem_used"]) / 1024, 1),
                round(float(g["mem_total"]) / 1024, 1)) for g in gpus)
            self._gpu_lbl.config(text="GPU: " + names)
        else:
            detail = gpu_err if gpu_err else _t("gpu.none")
            if gpu_err and "NVML" in gpu_err:
                detail += " · " + lmp.t("gpu.nvml_hint")
            names = lmp.gpu_static_names()
            if names:
                detail = " · ".join(names) + " — " + detail
            self._gpu_lbl.config(text="GPU: " + detail)

        cpu = sysinfo.get("cpu_percent")
        mem_u, mem_t = sysinfo.get("mem_used"), sysinfo.get("mem_total")
        disk = sysinfo.get("disk_percent")
        parts = []
        parts.append("CPU %.0f%%" % cpu if cpu is not None else "CPU —")
        if mem_u and mem_t:
            parts.append("Mem %s/%s" % (lmp.fmt_bytes(mem_u), lmp.fmt_bytes(mem_t)))
        parts.append("Disk %.0f%%" % disk if disk is not None else "Disk —")
        self._sys_lbl.config(text=" · ".join(parts))

    # ─────────────────── 语言 ───────────────────
    def _toggle_lang(self):
        lmp._lang = "zh" if lmp._lang == "en" else "en"
        lmp._save_lang()
        self._relabel()
        if self._panel is not None:
            try:
                self._panel._relabel()
            except Exception:          # noqa: BLE001
                pass

    def _relabel(self):
        self.root.title(_t("app.title"))
        self._title_lbl.config(text=_t("app.title"))
        self._models_lf.config(text=_t("sec.models"))
        self._res_lf.config(text=_t("sec.resources"))
        self._panel_btn.config(text=_t("btn.panel"))
        self._quit_btn.config(text=_t("btn.quit"))
        self._refresh_async()


def main():
    if not lmp.TK_AVAILABLE:
        print("未安装 tkinter。请先执行:  sudo apt install -y python3-tk")
        raise SystemExit(1)
    app = MainWindow()
    app.root.mainloop()


if __name__ == "__main__":
    main()
