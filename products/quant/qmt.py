# -*- coding: utf-8 -*-
"""QMT / miniQMT 终端探活（复用 gpulocal 的本地服务探测思路）。

probe() 返回：
  {
    "terminal_running": bool,   # 检测到 QMT/miniQMT 进程
    "processes": [进程名...],    # 命中的进程
    "xtquant": bool,            # xtquant SDK 可 import（只引用不内嵌，合规红线）
    "detail": str,              # 人类可读摘要
  }

进程识别：psutil 优先；未装则 Windows 走 tasklist、POSIX 走 ps。
进程名单保守：命中 "qmt" / "xtmini" / "xtitclient"（大小写不敏感）。
"""

from __future__ import annotations

import shutil
import subprocess
import sys

_PROCESS_HINTS = ("qmt", "xtmini", "xtitclient")


def _names_via_psutil() -> list[str] | None:
    """psutil 可用时返回进程名列表；不可用返回 None。"""
    try:
        import psutil                        # noqa: PLC0415 懒加载
    except ImportError:
        return None
    try:
        return [p.name() for p in psutil.process_iter(["name"])]
    except Exception:                         # noqa: BLE001 权限/平台问题降级
        return None


def _names_via_command() -> list[str]:
    """无 psutil 的兜底：tasklist（Windows）/ ps（POSIX）。"""
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
            return [ln.split('","')[0].strip('"') for ln in out.splitlines()
                    if ln.strip()]
        out = subprocess.run(["ps", "-eo", "comm"],
                             capture_output=True, text=True, timeout=10).stdout
        return [ln.strip() for ln in out.splitlines()[1:] if ln.strip()]
    except Exception:                         # noqa: BLE001
        return []


def list_process_names() -> list[str]:
    names = _names_via_psutil()
    return names if names is not None else _names_via_command()


def xtquant_available() -> bool:
    """xtquant SDK 是否可 import（QMT 官方 Python 接口，随终端安装）。"""
    try:
        import xtquant                       # noqa: PLC0415,F401
        return True
    except ImportError:
        return False


def probe(process_names: list[str] | None = None) -> dict:
    """探活主入口。process_names 可注入（测试用），None 时实机探测。"""
    names = list_process_names() if process_names is None else process_names
    hits = sorted({n for n in names
                   if any(h in n.lower() for h in _PROCESS_HINTS)})
    sdk = xtquant_available()
    running = bool(hits)
    if running and sdk:
        detail = f"终端运行中（{', '.join(hits)}），xtquant 可用"
    elif running:
        detail = f"终端运行中（{', '.join(hits)}），xtquant 未安装"
    elif sdk:
        detail = "终端未运行，xtquant 可用（启动 miniQMT 终端后即可连接）"
    else:
        hint = "pip install xtquant" if shutil.which("pip") else "安装 xtquant"
        detail = f"未检测到 QMT/miniQMT 终端；SDK 也未安装（{hint}）"
    return {"terminal_running": running, "processes": hits,
            "xtquant": sdk, "detail": detail}
