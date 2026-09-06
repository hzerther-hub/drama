# -*- coding: utf-8 -*-
"""异常统一上报：Tk 回调 / 工作线程异常 → 日志文件 + 界面提示。

GUI 模式下异常默认只进 stderr，窗口里完全不可见——本模块把两类异常
（Tk 回调经 report_callback_exception，工作线程经 threading.excepthook）
追加写入 CONFIG_DIR/logs/ui_errors.log，并通过 notify 回调（状态栏）提示。
console 模式仍同步打印 stderr，行为不回退。
"""

from __future__ import annotations

import datetime
import os
import sys
import threading
import traceback

_MAX_LOG_BYTES = 1_000_000     # 单文件上限，超过轮转为 .old


class ErrorReporter:
    """集中记录异常；install_* 把自己挂到 Tk / threading 的异常出口。"""

    def __init__(self, log_dir: str, notify=None):
        self.path = os.path.join(log_dir, "ui_errors.log")
        self.notify = notify or (lambda _msg: None)
        self.count = 0
        self._lock = threading.Lock()
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:                     # noqa: BLE001  目录不可用则只计数不落盘
            self.path = ""

    def report(self, where: str, etype, value, tb) -> int:
        """记录一次异常，返回累计序号；任何失败都不再向外抛。"""
        block = "".join(traceback.format_exception(etype, value, tb))
        with self._lock:
            self.count += 1
            n = self.count
            if self.path:
                try:
                    self._rotate_if_big()
                    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(self.path, "a", encoding="utf-8") as f:
                        f.write(f"\n=== [{stamp}] #{n} ({where}) "
                                f"{etype.__name__}: {value}\n{block}")
                except Exception:             # noqa: BLE001  日志失败不放大异常
                    pass
        traceback.print_exception(etype, value, tb, file=sys.stderr)
        try:
            self.notify(f"⚠️ 界面异常 #{n}（详见 ui_errors.log）")
        except Exception:                     # noqa: BLE001
            pass
        return n

    def _rotate_if_big(self):
        try:
            if os.path.getsize(self.path) > _MAX_LOG_BYTES:
                os.replace(self.path, self.path + ".old")
        except OSError:
            pass

    def install_tk(self, root):
        """接管 Tk 回调异常（按钮/绑定/after 等主循环回调）。"""
        def _handler(exc, val, tb):
            self.report("tk-callback", exc, val, tb)
        root.report_callback_exception = _handler

    def install_threading(self):
        """接管工作线程异常（daemon 线程默认只打印 stderr）。"""
        def _hook(args):
            self.report("thread", args.exc_type, args.exc_value,
                        args.exc_traceback)
        threading.excepthook = _hook
