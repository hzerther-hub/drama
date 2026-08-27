#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地编程助手 · 本地模型管理面板  ——  独立 tkinter 程序
=====================================================
串行管理本地模型（Linux+systemd 用用户服务；Windows/macOS/无 systemd 用后台进程守护）：
  · Qwen3-Coder-30B-A3B (Q4_K_M)  —— 端口 8080，编程主模型（CPU+GPU 混合）
  · Qwen3.8-27B (DFlash2 加速)   —— 端口 8097，投机解码 draft-dflash
  · Qwen3-VL-32B (Q6_K)           —— 端口 8098，视觉多模态（mmproj）
  · Ornith-1.5-35B-A3B (Q6_K)     —— 端口 8099，编程助手（双卡，尽量大）
实时显示双卡 GPU / 系统 / 硬件状态，提供 启动 / 停止 / 重启 / 刷新 / 下载 与加载日志。

运行环境（你的 GPU 工作站，Ubuntu 24.04 + 桌面）：
    sudo apt install -y python3-tk      # tkinter
    pip install psutil                  # 系统状态（CPU/内存/磁盘/温度）
    nvidia-smi 可用                     # GPU 状态（需 NVIDIA 驱动正常）
    systemctl --user 可用               # systemd 用户服务（qwen38-27b-q8.service）

用法：
    python3 local_model_panel.py

说明：
    * 模型清单：Qwen3.8-27B (DFlash2 加速)、Qwen3-VL-32B (Q6_K)、Ornith-1.5-35B-A3B (Q6_K)。
      GLM-4.6V-Flash / Qwen2.5-Coder-32B 不在此列。
    * 所有数值（GPU 数量/显存、内存、磁盘、CPU 频率/温度/负载）均实时探测，
      不写死机器参数，因此在不同物理机上也能正确显示。
"""

from __future__ import annotations

import os
import re
import shutil
import time
import math
import threading
import subprocess
import sys as _sys
import urllib.request

# 平台检测：Linux+systemd 用用户服务；Windows/macOS/无 systemd 用后台进程守护
IS_WINDOWS = _sys.platform == "win32"
IS_MACOS = _sys.platform == "darwin"
IS_LINUX = not (IS_WINDOWS or IS_MACOS)

# Windows 下从 pythonw（无控制台）启动子进程时，必须带 CREATE_NO_WINDOW，
# 否则每个轮询命令（powershell/nvidia-smi/taskkill…）都会闪一个 cmd 黑窗
_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0   # CREATE_NO_WINDOW

try:
    import tkinter as tk
    from tkinter import ttk
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

try:
    import psutil
except Exception:
    psutil = None


# ─────────────────────────────────────────────────────────────────────────────
# 模型配置（按你的工作站；这里是默认值，可自行修改）
# ─────────────────────────────────────────────────────────────────────────────
MODELS = {
    # ── 编程主模型：Qwen3-Coder-30B-A3B (Q4_K_M，CPU+GPU 混合推理) ──────────
    "Qwen3-Coder-30B-A3B (Q4_K_M)": {
        "service":     "qwen3-coder-30b.service",
        "port":        8080,
        "endpoint":    "http://127.0.0.1:8080/v1",
        "health_url":  "http://127.0.0.1:8080/v1/models",
        "spec_type":   "",                                        # 无投机 drafter
        "models_dir":  os.path.expanduser("~/models/Qwen3-Coder-30B-A3B-GGUF"),
        "models_dir_alt": [r"D:\llama\models"],                   # 本机 Windows 安装位置（回退）
        "llama_server": r"D:\llama\bin\llama-server.exe",         # 本机 llama.cpp；不存在则找 PATH
        "main_model":  "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf",
        "mmproj":      "",                                        # 纯文本模型，无视觉投影
        "drafter":     "",
        "launch_args": [                                          # 单卡 6GB + 128GB 内存混合：注意力+6层专家进 GPU
            "--n-gpu-layers", "99", "--n-cpu-moe", "42",
            "--ctx-size", "16384", "--parallel", "1",
            "--flash-attn", "auto",
            "--threads", "6", "--threads-batch", "12",
            "--load-mode", "none",
            "--alias", "qwen3-coder-30b",
        ],
        "ms_repo": "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",   # ModelScope 仓库（下载用）
        "ms_files": ["Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"],
        "load_timeout_s": 300,
        "load_poll_s":    5,
        "health_timeout": 3,
    },
    # ── 编程主模型：Qwen3-Coder-30B-A3B (Q6_K) ──────────────────────────────
    "Qwen3-Coder-30B-A3B (Q6_K)": {
        "service":     "qwen3-coder-30b-q6k.service",
        "port":        8081,
        "endpoint":    "http://127.0.0.1:8081/v1",
        "health_url":  "http://127.0.0.1:8081/v1/models",
        "spec_type":   "",                                        # 无投机 drafter
        "models_dir":  os.path.expanduser("~/models/Qwen3-Coder-30B-A3B-GGUF"),
        "models_dir_alt": [r"D:\llama\models"],                   # 本机 Windows 安装位置（回退）
        "llama_server": r"D:\llama\bin\llama-server.exe",         # 本机 llama.cpp；不存在则找 PATH
        "main_model":  "Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf",
        "mmproj":      "",                                        # 纯文本模型，无视觉投影
        "drafter":     "",
        "launch_args": [                                          # 单卡 6GB + 128GB 内存混合：注意力+6层专家进 GPU
            "--n-gpu-layers", "99", "--n-cpu-moe", "42",
            "--ctx-size", "16384", "--parallel", "1",
            "--flash-attn", "auto",
            "--threads", "6", "--threads-batch", "12",
            "--load-mode", "none",
            "--alias", "qwen3-coder-30b-q6k",
        ],
        "ms_repo": "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",   # ModelScope 仓库（下载用）
        "ms_files": ["Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf"],
        "load_timeout_s": 300,
        "load_poll_s":    5,
        "health_timeout": 3,
    },
    # ── 编程主模型：Qwen3-Coder-30B-A3B (Q8_0) ──────────────────────────────
    "Qwen3-Coder-30B-A3B (Q8_0)": {
        "service":     "qwen3-coder-30b-q8_0.service",
        "port":        8082,
        "endpoint":    "http://127.0.0.1:8082/v1",
        "health_url":  "http://127.0.0.1:8082/v1/models",
        "spec_type":   "",                                        # 无投机 drafter
        "models_dir":  os.path.expanduser("~/models/Qwen3-Coder-30B-A3B-GGUF"),
        "models_dir_alt": [r"D:\llama\models"],                   # 本机 Windows 安装位置（回退）
        "llama_server": r"D:\llama\bin\llama-server.exe",         # 本机 llama.cpp；不存在则找 PATH
        "main_model":  "Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf",
        "mmproj":      "",                                        # 纯文本模型，无视觉投影
        "drafter":     "",
        "launch_args": [                                          # 单卡 6GB + 128GB 内存混合：注意力+6层专家进 GPU
            "--n-gpu-layers", "99", "--n-cpu-moe", "42",
            "--ctx-size", "16384", "--parallel", "1",
            "--flash-attn", "auto",
            "--threads", "6", "--threads-batch", "12",
            "--load-mode", "none",
            "--alias", "qwen3-coder-30b-q8_0",
        ],
        "ms_repo": "unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF",   # ModelScope 仓库（下载用）
        "ms_files": ["Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf"],
        "load_timeout_s": 300,
        "load_poll_s":    5,
        "health_timeout": 3,
    },
    # ── 常驻主模型：Qwen3.8-27B (DFlash2 加速) ──────────────────────────────
    "Qwen3.8-27B (DFlash2 加速)": {
        "service":     "qwen38-27b-q8.service",
        "port":        8097,
        "endpoint":    "http://127.0.0.1:8097/v1",
        "health_url":  "http://127.0.0.1:8097/v1/models",
        "spec_type":   "draft-dflash",
        "models_dir":  os.path.expanduser("~/models/Qwen3.8-27B-GGUF"),
        "main_model":  "Qwen3.8-27B-Q8_0.gguf",
        "mmproj":      "mmproj-BF16.gguf",                        # 图片输入必需（实际文件名）
        "drafter":     "Qwen3.8-27B-DFlash2-Q4_K_M.gguf",       # 投机解码 DFlash2（需从 z-lab 转换）
        "launch_args": [                                        # 参考：qwen38 service 实际启动参数
            "--split-mode", "layer", "--n-gpu-layers", "99",
            "--flash-attn", "on",
            "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
            "--spec-type", "draft-dflash",
            "--spec-draft-ngl", "99", "--spec-draft-n-max", "5",
        ],
        "ms_repo": "unsloth/Qwen3.8-27B-GGUF",                   # ModelScope 仓库（主模型+mmproj）
        "ms_files": ["Qwen3.8-27B-Q8_0.gguf",
                     "mmproj-BF16.gguf"],
        "ms_drafter_repo": "z-lab/Qwen3.8-27B-DFlash2",         # DFlash2 drafter 源（safetensors，需转 GGUF）
        "load_timeout_s": 300,                                    # 等模型加载的最长时间（秒）
        "load_poll_s":    5,                                      # 加载日志轮询间隔（秒）
        "health_timeout": 3,                                      # 健康检查超时（秒）
    },
    # ── 视觉多模态：Qwen3-VL-32B（Q6_K，从 ModelScope 下载）────────────────
    "Qwen3-VL-32B (Q6_K)": {
        "service":     "qwen3-vl-32b.service",
        "port":        8098,
        "endpoint":    "http://127.0.0.1:8098/v1",
        "health_url":  "http://127.0.0.1:8098/v1/models",
        "spec_type":   "",                                        # 无投机 drafter
        "models_dir":  os.path.expanduser("~/models/Qwen3-VL-32B-GGUF"),
        "main_model":  "Qwen3-VL-32B-Instruct-Q6_K.gguf",
        "mmproj":      "mmproj-F16.gguf",                     # 视觉投影（图片必需，实际文件名）
        "drafter":     "",
        "launch_args": [                                          # 双卡 NVLink：按层拆分 + 全部进 GPU
            "--split-mode", "layer", "--n-gpu-layers", "99",
            "--flash-attn", "on",
            "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
        ],
        "ms_repo": "unsloth/Qwen3-VL-32B-Instruct-GGUF",          # ModelScope 镜像仓库
        "ms_files": ["Qwen3-VL-32B-Instruct-Q6_K.gguf",
                     "mmproj-F16.gguf"],
        "load_timeout_s": 300,
        "load_poll_s":    5,
        "health_timeout": 3,
    },
    # ── 编程助手：Ornith-1.5-35B-A3B（Q6_K，双卡，尽量大）────────────────────
    "Ornith-1.5-35B-A3B (Q6_K)": {
        "service":     "ornith-1.5-35b.service",
        "port":        8099,
        "endpoint":    "http://127.0.0.1:8099/v1",
        "health_url":  "http://127.0.0.1:8099/v1/models",
        "spec_type":   "",
        "models_dir":  os.path.expanduser("~/models/Ornith-1.5-35B-A3B-GGUF"),
        "main_model":  "Ornith-1.5-35B-Q6_K.gguf",
        "mmproj":      "mmproj-Ornith-1.5-35B-BF16.gguf",       # 该模型同样带视觉投影
        "drafter":     "",
        "launch_args": [                                          # 双卡 NVLink，按层拆分
            "--split-mode", "layer", "--n-gpu-layers", "99",
            "--flash-attn", "on",
            "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
        ],
        "ms_repo": "ornith-ai/Ornith-1.5-35B-A3B-GGUF",           # ModelScope 仓库
        "ms_files": ["Ornith-1.5-35B-Q6_K.gguf",
                     "mmproj-Ornith-1.5-35B-BF16.gguf"],
        "load_timeout_s": 300,
        "load_poll_s":    5,
        "health_timeout": 3,
    },
}

REFRESH_MS = 2500          # GPU/系统状态刷新周期（毫秒）
LOG_LIMIT   = 1200         # 日志区最多保留的字符数


# ─────────────────────────────────────────────────────────────────────────────
# 基础工具
# ─────────────────────────────────────────────────────────────────────────────
def _disk_root() -> str:
    """系统根路径：Windows 用系统盘，其它用 /。"""
    if IS_WINDOWS:
        return os.environ.get("SystemDrive", "C:") + os.sep
    return "/"


def _run(cmd, timeout=10):
    """运行命令（参数列表，不经 shell），返回 (rc, stdout, stderr)。"""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, errors="replace",
                           creationflags=_NO_WINDOW)
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except FileNotFoundError:
        return 127, "", "找不到命令: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "", "命令超时: %s" % " ".join(cmd)
    except Exception as e:                      # noqa: BLE001
        return 1, "", str(e)


def _powershell() -> str:
    """定位 powershell 可执行文件：PATH 找不到时回退系统目录全路径。

    某些运行环境（无控制台 pythonw、精简 PATH）里 'powershell' 不在 PATH，
    直接 _run(["powershell", ...]) 会 127 找不到命令。
    """
    p = shutil.which("powershell") or shutil.which("pwsh")
    if p:
        return p
    for cand in (r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",):
        if os.path.exists(cand):
            return cand
    return "powershell"


def fmt_bytes(n):
    if n is None:
        return "—"
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return ("%.0f %s" if unit == "B" else "%.1f %s") % (n, unit)
        n /= 1024
    return "—"


def fmt_gib(num, digits=1):
    try:
        return "%.*f GiB" % (digits, float(num) / (1024 ** 3))
    except Exception:
        return "—"


def human_pct(v):
    try:
        return "%.0f%%" % float(v)
    except Exception:
        return "—"


def find_modelscope():
    """返回 modelscope 命令路径；找不到返回 None。优先 PATH，回退 ~/.local/bin。"""
    p = shutil.which("modelscope")
    if p:
        return p
    cand = os.path.expanduser("~/.local/bin/modelscope")
    if os.path.isfile(cand) and os.access(cand, os.X_OK):
        return cand
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 服务 / 健康检查
# ─────────────────────────────────────────────────────────────────────────────
def _use_systemd() -> bool:
    """Linux 且 systemctl 可用才走 systemd；Windows/macOS/无 systemd 用进程守护。"""
    if IS_WINDOWS or IS_MACOS:
        return False
    return shutil.which("systemctl") is not None


def service_status(name):
    """返回服务状态字符串 active/inactive/failed/activating/deactivating/unknown。

    Linux+systemd 走 systemd；Windows/macOS/无 systemd 改用后台进程守护
    （由 _RUN_DIR 下的状态文件记录 pid + 端口）。
    """
    if not _use_systemd():
        return win_svc_status(name)
    rc, out, _ = _run(["systemctl", "--user", "is-active", name], timeout=6)
    state = (out or "").strip().lower()
    if state in ("active", "inactive", "failed", "activating", "deactivating"):
        return state
    return "unknown"


# ---- Windows 进程守护（无 systemd 时用） ------------------------------------
_RUN_DIR = os.path.join(os.path.expanduser("~"), ".gpulocal", "run")


def _state_path(name: str) -> str:
    return os.path.join(_RUN_DIR, name.replace(".service", "") + ".json")


def win_svc_status(name: str) -> str:
    """读取状态文件，进程存活且健康 → active，否则 inactive。"""
    try:
        with open(_state_path(name), "r", encoding="utf-8") as f:
            import json as _json
            st = _json.load(f)
        pid = int(st.get("pid", 0))
        if pid <= 0:
            return "inactive"
        # 进程存活？
        if _process_alive(pid):
            return "active"
    except Exception:                # noqa: BLE001  无状态文件/损坏 → 未运行
        pass
    return "inactive"


def _process_alive(pid: int) -> bool:
    """探测进程是否存活。注意：Windows 上 os.kill(pid, 0) 等价 TerminateProcess，
    会把进程杀掉（历史 bug），必须用 OpenProcess 探测。"""
    if pid <= 0:
        return False
    if IS_WINDOWS:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(h, ctypes.byref(code)):
                return code.value == STILL_ACTIVE
            return True
        finally:
            kernel32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _model_dir(cfg: dict) -> str:
    """定位模型目录：models_dir 优先，models_dir_alt 依次回退（跨机器部署）。"""
    cands = [cfg.get("models_dir", "")] + list(cfg.get("models_dir_alt", []))
    main = cfg.get("main_model", "")
    for d in cands:
        if d and main and os.path.isfile(os.path.join(d, main)):
            return d
    for d in cands:
        if d and os.path.isdir(d):
            return d
    return cfg.get("models_dir", "")


def win_llama_cmd(cfg: dict) -> list:
    """进程守护模式下构造 llama-server 启动命令（Windows/macOS/无 systemd）。"""
    exe = cfg.get("llama_server")
    if not (exe and os.path.isfile(exe)):
        exe = shutil.which("llama-server") or "llama-server"
    ml_dir = _model_dir(cfg)
    cmd = [exe,
           "-m", os.path.join(ml_dir, cfg["main_model"]),
           "--host", "127.0.0.1", "--port", str(cfg["port"])]
    if cfg.get("mmproj"):
        cmd += ["--mmproj", os.path.join(ml_dir, cfg["mmproj"])]
    if cfg.get("drafter"):
        cmd += ["--spec-draft-model", os.path.join(ml_dir, cfg["drafter"])]
    cmd += list(cfg.get("launch_args", []))
    return cmd


def win_svc_start(cfg: dict):
    """Windows 启动：Popen 后台进程 + 落盘 pid/端口（健康状态由 status 判定）。"""
    os.makedirs(_RUN_DIR, exist_ok=True)
    # 先停旧实例（若同端口/同名已启动）
    win_svc_stop(cfg["service"])
    cmd = win_llama_cmd(cfg)
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if IS_WINDOWS:
            # DETACHED_PROCESS：服务进程不带控制台、独立于面板存活
            kwargs["creationflags"] = 0x00000008 | _NO_WINDOW
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception as e:                         # noqa: BLE001
        return 1, str(e)
    import json as _json
    with open(_state_path(cfg["service"]), "w", encoding="utf-8") as f:
        _json.dump({"pid": proc.pid, "port": cfg["port"]}, f)
    return 0, ""


def win_svc_stop(name: str):
    """Windows 停止：按状态文件 pid 结束进程并清理状态文件。"""
    try:
        with open(_state_path(name), "r", encoding="utf-8") as f:
            import json as _json
            st = _json.load(f)
        pid = int(st.get("pid", 0))
        if pid > 0:
            _kill_tree(pid)
    except Exception:                # noqa: BLE001
        pass
    try:
        os.remove(_state_path(name))
    except OSError:
        pass


def _kill_tree(pid: int):
    """结束进程树（Windows 用 taskkill /T；其它平台 terminate）。"""
    if IS_WINDOWS:
        _run(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=15)
        return
    try:
        import signal
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        os.kill(pid, signal.SIGKILL)
    except Exception:                # noqa: BLE001
        pass


# ---- 统一服务控制入口 --------------------------------------------------------
def svc_start(cfg: dict):
    """启动模型服务。Linux+systemd=systemctl；否则（Windows/macOS）=后台进程。"""
    if not _use_systemd():
        rc, err = win_svc_start(cfg)
        return rc
    rc, _, _ = _run(["systemctl", "--user", "start", cfg["service"]], timeout=180)
    return rc


def svc_stop(cfg: dict):
    """停止模型服务，返回 rc。"""
    if not _use_systemd():
        win_svc_stop(cfg["service"])
        return 0
    rc, _, _ = _run(["systemctl", "--user", "stop", cfg["service"]], timeout=60)
    return rc


def svc_restart(cfg: dict):
    """重启模型服务，返回 rc。"""
    if not _use_systemd():
        win_svc_stop(cfg["service"])
        return svc_start(cfg)
    rc, _, _ = _run(["systemctl", "--user", "restart", cfg["service"]], timeout=180)
    return rc


def health_check(url, timeout=3):
    """返回 (ok: bool, detail: str)。"""
    try:
        # 直连（禁用代理）：127.0.0.1 会被 http_proxy 代理（no_proxy 常为 CIDR，
        # urllib 不识别）误判为 URLError，导致模型明明在跑却显示未起/失败。
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=timeout) as r:
            if r.status == 200:
                return True, "HTTP %s" % r.status
            return False, "HTTP %s" % r.status
    except Exception as e:                       # noqa: BLE001
        return False, type(e).__name__


# ─────────────────────────────────────────────────────────────────────────────
# GPU 状态（nvidia-smi）
# ─────────────────────────────────────────────────────────────────────────────
def query_gpu():
    """返回 (gpus: list[dict], topo_desc: str, err: str)。"""
    rc, out, err = _run(
        ["nvidia-smi",
         "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu,fan.speed",
         "--format=csv,noheader,nounits"],
        timeout=8,
    )
    if rc != 0 or not out.strip():
        # 只返回原始错误；语义化的「不可用」文案由显示层决定，
        # 避免显示成「GPU status unavailable · GPU status unavailable」。
        # 注意 nvidia-smi 的 NVML 错误（如 "Failed to initialize NVML"）
        # 打到 stdout 而非 stderr，stderr 为空时要回退取 stdout 首行。
        detail = err.strip() or (out.strip().splitlines() or [""])[0].strip()
        return [], "—", detail

    gpus = []
    for line in out.strip().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 7:
            continue
        gpus.append({
            "index": parts[0],
            "name": parts[1],
            "mem_used": parts[2],
            "mem_total": parts[3],
            "util": parts[4],
            "temp": parts[5],
            "fan": parts[6],
        })

    topo_desc = gpu_topology(len(gpus))
    return gpus, topo_desc, ""


def gpu_static_names():
    """nvidia-smi 不可用时的静态 GPU 型号兜底（三平台），返回型号名列表。

    Windows 走 CIM Win32_VideoController；macOS 走 system_profiler；
    Linux 走 lspci。过滤远控/虚拟显示适配器（向日葵 OrayIddDriver 等）。
    """
    names = []
    try:
        if IS_WINDOWS:
            rc, out, _ = _run([_powershell(), "-NoProfile", "-Command",
                               "Get-CimInstance Win32_VideoController | "
                               "Select-Object -ExpandProperty Name"],
                              timeout=10)
            if rc == 0:
                names = [l.strip() for l in out.splitlines() if l.strip()]
        elif IS_MACOS:
            rc, out, _ = _run(["system_profiler", "SPDisplaysDataType"], timeout=15)
            if rc == 0:
                for m in re.finditer(r"Chipset Model:\s*(.+)", out):
                    names.append(m.group(1).strip())
        else:
            rc, out, _ = _run(["lspci"], timeout=8)
            if rc == 0:
                for line in out.splitlines():
                    m = re.search(r"(?:VGA|3D) compatible controller:\s*(.+)",
                                  line, re.I)
                    if m:
                        names.append(m.group(1).strip())
    except Exception:                      # noqa: BLE001
        pass
    virt = ("oray", "idd", "microsoft basic", "rdp", "virtual", "remote")
    seen, out_names = set(), []
    for n in names:
        if any(v in n.lower() for v in virt) or n.lower() in seen:
            continue
        seen.add(n.lower())
        out_names.append(n)
    return out_names


def gpu_topology(n_gpu):
    """尝试识别 NVLink / P2P，返回描述字符串。"""
    parts = []
    parts.append(t("gpu.cards", n=n_gpu))
    rc, out, _ = _run(["nvidia-smi", "topo", "-m"], timeout=8)
    if rc == 0 and out:
        if "NVLink" in out:
            parts.append(t("gpu.nvlink"))
        if "PIX" in out or "PXB" in out:
            parts.append(t("gpu.p2p"))
    return " · ".join(parts)


def query_nvlink():
    """返回 NVLink 级联的动态状态：链路数 + 各链路实时速率（每秒刷新，反映链路变化）。"""
    rc, out, _ = _run(["nvidia-smi", "nvlink", "--status"], timeout=8)
    if rc != 0 or not out.strip():
        return ""
    links = 0
    rates = set()
    for line in out.splitlines():
        m = re.search(r"Link \d+:\s*([\d.]+)\s*GB/s", line)
        if m:
            links += 1
            rates.add(round(float(m.group(1)), 1))
    if not links:
        return ""
    if len(rates) == 1:
        rate = "%.1f" % next(iter(rates))
    else:
        rate = "~" + "/".join(sorted("%.1f" % r for r in rates))
    return t("gpu.links", n=links, rate=rate)


def _read_cmdline(pid):
    """读取某 PID 的完整命令行，失败返回空串。"""
    try:
        with open("/proc/%s/cmdline" % pid, "rb") as f:
            return f.read().decode(errors="replace").replace("\x00", " ").strip()
    except Exception:
        return ""


def _short_model_name(basename):
    """把 GGUF 文件名映射成简洁模型名（去掉 .gguf 与量化括号，尽量用配置友好名）。"""
    try:
        for label, cfg in MODELS.items():
            files = [cfg.get("main_model", "")] + list(cfg.get("ms_files", []))
            if basename in [f for f in files if f]:
                return label.split("(")[0].strip()
    except Exception:
        pass
    return basename.replace(".gguf", "").strip()


def _model_from_cmd(cmd):
    """从 llama-server 命令行提取简洁模型名（-m/--model 后面的文件）。"""
    if not cmd or "llama-server" not in cmd:
        return ""
    m = re.search(r"(?:-m|--model)\s+(\S+)", cmd)
    if m:
        return _short_model_name(os.path.basename(m.group(1)))
    return ""


def query_model_usage():
    """按 GPU 查询模型(llama-server)显存占用与模型名。

    返回 {gpu_index: {"model_mem": int(MiB), "model": str}}。
    仅统计 compute 类进程中的 llama-server；桌面/系统(G)进程不在此列。
    """
    # uuid -> index
    uuid2idx = {}
    rc, out, _ = _run(["nvidia-smi", "--query-gpu=index,uuid",
                       "--format=csv,noheader,nounits"], timeout=8)
    if rc == 0:
        for line in out.splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) >= 2:
                uuid2idx[p[1]] = p[0]

    result = {}
    rc, out, _ = _run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory",
                       "--format=csv,noheader,nounits"], timeout=8)
    if rc == 0:
        for line in out.splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) < 3:
                continue
            uuid, pid, mem = p[0], p[1], p[2]
            gidx = uuid2idx.get(uuid)
            if gidx is None:
                continue
            cmd = _read_cmdline(pid)
            if "llama-server" in cmd:
                r = result.setdefault(gidx, {"model_mem": 0, "model": ""})
                r["model_mem"] += int(float(mem or 0))
                r["model"] = _model_from_cmd(cmd) or r["model"]
    return result



# ─────────────────────────────────────────────────────────────────────────────
# 系统状态（psutil + /proc）
# ─────────────────────────────────────────────────────────────────────────────
def query_system():
    info = {"cpu_temp": None, "cpu_freq": None, "cpu_freq_max": None,
            "load": None}
    if psutil:
        try:
            info["cpu_percent"] = psutil.cpu_percent(interval=0.4)
        except Exception:
            info["cpu_percent"] = None
        try:
            fr = psutil.cpu_freq()
            info["cpu_freq"] = round(fr.current, 2) if fr else None
            info["cpu_freq_max"] = round(fr.max, 2) if fr else None
        except Exception:
            pass
        vm = psutil.virtual_memory()
        info["mem_total"] = vm.total
        info["mem_used"] = vm.used
        info["mem_percent"] = vm.percent
        try:
            sw = psutil.swap_memory()
            info["swap_total"] = sw.total
            info["swap_used"] = sw.used
        except Exception:
            info["swap_total"] = info["swap_used"] = None
        du = psutil.disk_usage(_disk_root())
        info["disk_total"] = du.total
        info["disk_used"] = du.used
        info["disk_free"] = du.free
        info["disk_percent"] = du.percent
        try:
            temps = psutil.sensors_temperatures() or {}
            for key in ("coretemp", "k10temp", "acpitz", "cpu_thermal", "thinkpad"):
                if key in temps and temps[key]:
                    info["cpu_temp"] = round(temps[key][0].current, 1)
                    break
        except Exception:
            pass
    else:
        info["cpu_percent"] = None
        mem = _mem_from_proc()
        info.update(mem)
        # shutil.disk_usage 跨平台（os.statvfs 在 Windows 上不存在，会抛 AttributeError）
        du = shutil.disk_usage(_disk_root())
        info["disk_total"] = du.total
        info["disk_used"] = du.used
        info["disk_free"] = du.free
        info["disk_percent"] = du.used / du.total * 100 if du.total else 0

    try:
        info["load"] = os.getloadavg()
    except Exception:
        info["load"] = None
    return info


def _mem_from_proc():
    """读内存（无 psutil 时备用）：Linux 走 /proc/meminfo，Windows 走 ctypes API。"""
    total = used = None
    if IS_WINDOWS:
        try:
            import ctypes

            class _MEMSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = _MEMSTATUSEX()
            st.dwLength = ctypes.sizeof(st)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                total = st.ullTotalPhys
                used = total - st.ullAvailPhys
        except Exception:
            pass
    else:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total = int(line.split()[1]) * 1024
                    elif line.startswith("MemAvailable:"):
                        avail = int(line.split()[1]) * 1024
                        if total:
                            used = total - avail
                        break
        except Exception:
            pass
    return {"mem_total": total, "mem_used": used,
            "mem_percent": (used / total * 100) if (total and used) else None}


# ─────────────────────────────────────────────────────────────────────────────
# 硬件信息（一次性探测）
# ─────────────────────────────────────────────────────────────────────────────
def detect_hardware():
    hw = {}
    # CPU 型号 / 逻辑线程（Windows 走 powershell/wmic，Linux 走 /proc）
    model = t("hw.unknown")
    threads = None
    if IS_WINDOWS:
        rc, out, _ = _run([_powershell(), "-NoProfile", "-Command",
                           "(Get-CimInstance Win32_Processor).Name"],
                          timeout=10)
        if rc == 0 and out.strip():
            model = out.strip().splitlines()[0].strip()
    else:
        try:
            with open("/proc/cpuinfo") as f:
                text = f.read()
            m = re.search(r"model name\s*:\s*(.+)", text)
            if m:
                model = m.group(1).strip()
            threads = text.count("processor")
        except Exception:
            pass
    hw["cpu_model"] = model
    hw["threads"] = threads
    # 无 psutil 时回退：逻辑核用 os.cpu_count()，物理核 Windows 走 CIM 查询，
    # 否则面板显示「0 核 0 线程」
    hw["physical_cores"] = psutil.cpu_count(logical=False) if psutil else None
    hw["logical_cpus"] = (psutil.cpu_count(logical=True) if psutil
                          else (threads or os.cpu_count()))
    if hw["physical_cores"] is None and IS_WINDOWS:
        rc, out, _ = _run([_powershell(), "-NoProfile", "-Command",
                           "(Get-CimInstance Win32_Processor) | "
                           "Measure-Object NumberOfCores -Sum | "
                           "Select-Object -ExpandProperty Sum"],
                          timeout=10)
        if rc == 0 and out.strip():
            try:
                hw["physical_cores"] = int(float(out.strip().splitlines()[0]))
            except ValueError:
                pass

    # CPU 最大频率（Windows 用 wmic；Linux 用 lscpu）
    freq_max = None
    if IS_WINDOWS:
        rc, out, _ = _run([_powershell(), "-NoProfile", "-Command",
                           "(Get-CimInstance Win32_Processor).MaxClockSpeed"],
                          timeout=10)
        if rc == 0 and out.strip():
            try:
                freq_max = round(float(out.strip().splitlines()[0].strip()), 1)
            except ValueError:
                freq_max = None
    else:
        rc, out, _ = _run(["lscpu"], timeout=8)
        if rc == 0:
            m = re.search(r"CPU max MHz:\s*([\d.]+)", out)
            if not m:
                m = re.search(r"最大 MHz：\s*([\d.]+)", out)
            if m:
                freq_max = round(float(m.group(1)), 1)
    hw["freq_max"] = freq_max

    # 内存总量（真实探测；无 psutil 时用平台备用实现）
    hw["mem_total"] = (psutil.virtual_memory().total if psutil
                       else _mem_from_proc().get("mem_total"))

    # 根磁盘型号（跳过 loop/ram/zram 等虚拟设备；Windows 跳过）
    disk_model = "—"
    if not IS_WINDOWS:
        rc, out, _ = _run(["lsblk", "-d", "-o", "NAME,MODEL,SIZE", "-n"], timeout=6)
        if rc == 0 and out.strip():
            cands = []
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) < 2:
                    continue
                name = parts[0]
                if name.startswith(("loop", "ram", "zram", "sr", "fd")):
                    continue
                cands.append((name, " ".join(parts[1:])))
            # 优先 nvme，其次 sd/vd
            for prefix in ("nvme", "sd", "vd", "hd"):
                for name, model in cands:
                    if name.startswith(prefix):
                        disk_model = "%s %s" % (name, model)
                        break
                if disk_model != "—":
                    break
            if disk_model == "—" and cands:
                disk_model = "%s %s" % cands[0]
    hw["disk_model"] = disk_model
    return hw



# ─────────────────────────────────────────────────────────────────────────────
# 中英文双语（默认英文，可切换并持久化到 ~/.gpulocal/config.json）
# ─────────────────────────────────────────────────────────────────────────────
_LANG_FILE = os.path.join(os.path.expanduser("~"), ".gpulocal", "config.json")
_STRINGS = {
    "title":          {"en": "Local Model Hub", "zh": "本地模型管理面板"},
    "status.frame":   {"en": "Status", "zh": "状态"},
    "model.frame":    {"en": "Model", "zh": "模型"},
    "model.label":    {"en": "Model:", "zh": "模型:"},
    "gpu.frame":      {"en": "GPU Status", "zh": "GPU 状态"},
    "sys.frame":      {"en": "System Status", "zh": "系统状态"},
    "hw.frame":       {"en": "Hardware Info", "zh": "硬件信息"},
    "log.frame":      {"en": "Log", "zh": "日志"},
    "subtitle.linux": {"en": "systemd user services · serial (one model at a time)",
                       "zh": "systemd 用户服务 · 串行切换（一次只跑一个模型）"},
    "subtitle.win":   {"en": "Process daemon · serial (one model at a time)",
                       "zh": "后台进程守护 · 串行切换（一次只跑一个模型）"},
    "srv.line":       {"en": "Service {svc} · Port {port} · Spec {spec}",
                       "zh": "服务 {svc} · 端口 {port} · 投机解码 {spec}"},
    "btn.start":      {"en": "Start", "zh": "启动"},
    "btn.stop":       {"en": "Stop", "zh": "停止"},
    "btn.restart":    {"en": "Restart", "zh": "重启"},
    "btn.refresh":    {"en": "Refresh", "zh": "刷新"},
    "btn.copylog":    {"en": "Copy Log", "zh": "复制日志"},
    "btn.download":   {"en": "Download Model", "zh": "下载模型"},
    "btn.lang":       {"en": "EN/中文", "zh": "EN/中文"},
    "status.checking":{"en": "● Checking", "zh": "● 检测中"},
    "hw.cpu":      {"en": "CPU: {cpu} · {cores} cores {threads} threads{max}",
                    "zh": "CPU：{cpu} · {cores} 核 {threads} 线程{max}"},
    "hw.cpu_max":  {"en": " · max {freq} GHz", "zh": " · 最大 {freq} GHz"},
    "hw.mem":      {"en": "Memory: {mem} (live probe)", "zh": "内存：{mem}（实时探测）"},
    "hw.disk":     {"en": "Disk: {disk}", "zh": "硬盘：{disk}"},
    "gpu.mem_model": {"en": "model[{name}]{m:.1f}G·desktop{d:.1f}G",
                      "zh": "模型[{name}]{m:.1f}G·桌面{d:.1f}G"},
    "gpu.fan":       {"en": "Fan {fan}%", "zh": "风扇{fan}%"},
    "gpu.unavail":      {"en": "GPU status unavailable", "zh": "GPU 状态不可用"},
    "gpu.err_unavail":  {"en": "GPU status unavailable · {err}", "zh": "GPU 状态不可用 · {err}"},
    "gpu.nvml_hint":    {"en": "NVML init failed — usually fixed by a system reboot after driver update",
                         "zh": "NVML 初始化失败——驱动更新后未重启，重启系统通常可恢复"},
    "gpu.cards":        {"en": "{n} GPU", "zh": "{n} 卡"},
    "gpu.nvlink":       {"en": "NVLink", "zh": "NVLink 级联"},
    "gpu.p2p":          {"en": "P2P", "zh": "P2P 直连"},
    "gpu.links":        {"en": "{n} links · {rate} GB/s", "zh": "{n} 链路 · {rate} GB/s"},
    "hw.unknown":       {"en": "Unknown", "zh": "未知"},
    "status.running":     {"en": "● Running", "zh": "● 运行中"},
    "status.running_fail":{"en": "● Running (health check failed)", "zh": "● 运行中（健康检查失败）"},
    "status.loading":     {"en": "● Loading", "zh": "● 加载中"},
    "status.failed":      {"en": "● Start failed", "zh": "● 启动失败"},
    "status.stopped":     {"en": "● Stopped", "zh": "● 已停止"},
    "status.health":      {"en": "Health check {x}", "zh": "健康检查 {x}"},
    "log.stop_others":    {"en": "[Op] Serial switch, stopping {name} first…", "zh": "[操作] 串行切换，先停止 {name} ..."},
    "log.starting":       {"en": "[Op] Starting {name} …", "zh": "[操作] 启动 {name} ..."},
    "log.start_fail":     {"en": "[Error] Start failed (rc={rc}) — Linux: journalctl --user; Windows: ensure llama-server on PATH", "zh": "[错误] 启动失败（rc={rc}）。Linux 请查 systemctl --user; Windows 请确认 llama-server 已安装并在 PATH。"},
    "log.started_wait":   {"en": "[Info] Service started, waiting for model to load…", "zh": "[信息] 服务已启动，等待模型加载..."},
    "log.stopping":       {"en": "[Op] Stopping {name} …", "zh": "[操作] 停止 {name} ..."},
    "log.stop_fail":      {"en": "[Error] Stop failed (check journalctl --user)", "zh": "[错误] 停止失败（请查 systemctl --user）"},
    "log.stopped":        {"en": "[Info] Stopped", "zh": "[信息] 已停止"},
    "log.restarting":     {"en": "[Op] Restarting {name} …", "zh": "[操作] 重启 {name} ..."},
    "log.restart_fail":   {"en": "[Error] Restart failed (check journalctl --user)", "zh": "[错误] 重启失败（请查 systemctl --user）"},
    "log.state_end":      {"en": "[Info] Service state became '{state}', ending wait.", "zh": "[信息] 服务状态变为 '{state}'，结束等待。"},
    "log.load_done":      {"en": "[Info] {name} loaded in {sec}s", "zh": "[信息] {name} 加载完成，耗时 {sec} 秒"},
    "log.svc_addr":       {"en": "      Service address: {url}", "zh": "      服务地址: {url}"},
    "log.load_timeout":   {"en": "[Warning] Timed out waiting for model to load ({sec}s).", "zh": "[警告] 等待模型加载超时（{sec} 秒）。"},
    "log.loading_wait":   {"en": "      Model loading, {sec}s elapsed", "zh": "      模型加载中，已等待 {sec} 秒"},
    "sys.cpu":        {"en": "CPU", "zh": "CPU"},
    "sys.mem":        {"en": "Memory", "zh": "内存"},
    "sys.disk":       {"en": "Disk", "zh": "硬盘"},
    "sys.swap":       {"en": "Swap", "zh": "交换"},
    "sys.load":       {"en": "Load", "zh": "负载"},
    "sys.temp":       {"en": "Temp", "zh": "温度"},
    "sys.freq":       {"en": "Freq", "zh": "频率"},
    "log.panel_ready":{"en": "[Info] Panel ready, models: {names}",
                       "zh": "[信息] 面板已就绪，模型清单：{names}"},
}

_lang = "en"


def _try_main_config():
    """作为 qwen-coder 内嵌子模块时，语言源对齐主应用（config.py 的 language）。

    仅在能 import 到主 config 时生效（内嵌场景）；本面板独立运行时
    sys.path 无主 config，回到 ~/.gpulocal/config.json。
    """
    try:
        import config as _main_config
        return _main_config
    except Exception:                      # noqa: BLE001
        return None


def _load_lang():
    global _lang
    mc = _try_main_config()
    if mc is not None:
        try:
            _lang = "zh" if str(mc.get_language()).lower() == "zh" else "en"
            return
        except Exception:                  # noqa: BLE001
            pass
    try:
        import json as _j
        with open(_LANG_FILE, "r", encoding="utf-8") as f:
            _lang = _j.load(f).get("language", "en")
        if _lang != "en":
            _lang = "zh"
    except Exception:                      # noqa: BLE001
        _lang = "en"


def _save_lang():
    mc = _try_main_config()
    if mc is not None:
        try:
            mc.set_language(_lang)         # 内嵌：语言写入主应用配置
            return
        except Exception:                  # noqa: BLE001
            pass
    try:
        import json as _j
        os.makedirs(os.path.dirname(_LANG_FILE), exist_ok=True)
        with open(_LANG_FILE, "w", encoding="utf-8") as f:
            _j.dump({"language": _lang}, f, ensure_ascii=False)
            f.write("\n")
    except Exception:                      # noqa: BLE001
        pass


def _read_cfg():
    """读取 ~/.gpulocal/config.json，返回 dict；缺失/损坏返回 {}。"""
    import json as _j
    try:
        with open(_LANG_FILE, "r", encoding="utf-8") as f:
            return _j.load(f)
    except Exception:                      # noqa: BLE001
        return {}


def _save_cfg(patch: dict):
    """把 patch 合并进 config.json 并写回（保留 language 等其它字段）。"""
    import json as _j
    try:
        cfg = _read_cfg()
        cfg.update(patch)
        os.makedirs(os.path.dirname(_LANG_FILE), exist_ok=True)
        with open(_LANG_FILE, "w", encoding="utf-8") as f:
            _j.dump(cfg, f, ensure_ascii=False)
            f.write("\n")
    except Exception:                      # noqa: BLE001
        pass


def _load_last_model():
    """面板打开时恢复上次选中的模型名；无记录或名字失效时返回 None。"""
    return _read_cfg().get("last_model")


def _save_last_model(name: str):
    """记录当前选中的模型名，供下次打开面板恢复。"""
    _save_cfg({"last_model": name})


def set_lang(lang):
    """供主应用联动：按指定语言设置面板语言（不写配置，刷新交给 _relabel）。"""
    global _lang
    _lang = "zh" if str(lang or "").lower() == "zh" else "en"


def t(key: str, **kw) -> str:
    e = _STRINGS.get(key)
    if not e:
        return key
    s = e.get(_lang) or e.get("en") or key
    return s.format(**kw) if kw else s


# ─────────────────────────────────────────────────────────────────────────────
# tkinter 界面
# ─────────────────────────────────────────────────────────────────────────────
if TK_AVAILABLE:
    class ModelPanel:
        """本地模型管理面板。

        master 为 None 时自建 Tk 主窗口（独立运行）；提供 master 时作为
        Toplevel 挂在已有主窗口下（嵌入主程序子窗）。
        """
        def __init__(self, master=None):
            self._embedded = master is not None
            self.win = (tk.Toplevel(master) if master is not None else tk.Tk())
            _load_lang()
            self.win.title("")
            self.win.geometry("900x880")
            self.win.minsize(760, 640)
            # 内嵌场景：无边框窗口（去掉最大/最小/关闭三个系统按钮），
            # 用自定义拖动条 + ✕ 关闭 + Esc 关闭。独立运行保留标题栏。
            if self._embedded:
                try:
                    self.win.overrideredirect(True)
                except Exception:                # noqa: BLE001  Wayland 个别环境
                    self._embedded = False

            # 只保留常驻模型：Qwen3.8-27B (DFlash2 加速)
            self.model_names = list(MODELS.keys())
            # 记住上次选中的模型；无记录或失效时默认第一个
            _saved = _load_last_model()
            _init = _saved if _saved in self.model_names else self.model_names[0]
            self._model_var = tk.StringVar(value=_init)

            self._gpu_rows = {}            # index -> dict of widgets
            self._gpu_count = 0
            self._status = "unknown"
            self._last_health = None

            self._build_ui()
            self.win.after(300, self._refresh_once)
            self.win.after(REFRESH_MS, self._refresh_loop)
            self._log(t("log.panel_ready", names="、".join(self.model_names)))

        # ─────────────────── 界面骨架 ───────────────────
        def _build_ui(self):
            BG = "#f4f4f4"
            self.win.configure(bg=BG)
            style = ttk.Style(self.win)
            try:
                style.theme_use("clam")
                # 统一背景：clam 主题默认底色与窗口 #f4f4f4 不一致，
                # 文字控件会带白底块。所有容器/标签显式对齐窗口底色。
                style.configure("TFrame", background=BG)
                style.configure("TLabel", background=BG)
                style.configure("TCheckbutton", background=BG)
                style.configure("TSeparator", background=BG)
                style.configure("TCombobox", background=BG)
                # 扁平化：细/浅边框、无立体
                style.configure("TLabelframe", relief="flat",
                                background=BG,
                                bordercolor="#d4d4d4", borderwidth=1)
                style.configure("TLabelframe.Label", background=BG,
                                foreground="#334155")
                style.configure("TButton", relief="flat", background=BG,
                                bordercolor="#d4d4d4", borderwidth=1)
                style.map("TButton", background=[("active", "#e2e2e2")])
            except Exception:
                pass

            pad = (12, 6)   # ttk padding: (horizontal, vertical)

            # 标题条（仅内嵌无边框窗口）：拖动 + ✕ 关闭
            if self._embedded:
                grip = tk.Frame(self.win, bg="#e2e2e2", height=26)
                grip.pack(fill="x", side="top")
                grip.pack_propagate(False)
                grip.bind("<ButtonPress-1>", self._drag_start)
                grip.bind("<B1-Motion>", self._drag_move)
                tk.Label(grip, text=t("title"), bg="#e2e2e2", fg="#555",
                         font=("Microsoft YaHei UI", 9)).pack(side="left", padx=8)
                xbtn = tk.Label(grip, text="✕", bg="#e2e2e2", fg="#333",
                                font=("Microsoft YaHei UI", 11, "bold"), cursor="hand2")
                xbtn.pack(side="right", padx=8)
                xbtn.bind("<Button-1>", lambda e: self.win.destroy())
                self.win.bind("<Escape>", lambda e: self.win.destroy())


            # 标题
            hdr = ttk.Frame(self.win, padding=(12, 10))
            hdr.pack(fill="x", padx=5)

            self._subtitle_lbl = ttk.Label(
                hdr, text=(t("subtitle.win") if IS_WINDOWS else t("subtitle.linux")),
                foreground="#666")
            self._subtitle_lbl.pack(anchor="w")

            # 状态区（放到最顶上，内容一行显示）
            self.status_frame = tk.Frame(self.win, bg=BG)
            self.status_frame.pack(fill="x", padx=5)
            ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=5, pady=6)
            srow = ttk.Frame(self.status_frame)
            srow.pack(fill="x")
            self._status_lbl = tk.Label(srow, text=t("status.checking"),
                                        font=("Microsoft YaHei UI", 17, "bold"),
                                        fg="#888", bg=BG)
            self._status_lbl.pack(side="left")
            self._endpoint_lbl = ttk.Label(srow, foreground="#555")
            self._endpoint_lbl.pack(side="left", padx=10)
            self._health_lbl = ttk.Label(srow, foreground="#555")
            self._health_lbl.pack(side="left", padx=10)

            # 模型选择条
            self.mbar = tk.Frame(self.win, bg=BG)
            self.mbar.pack(fill="x", padx=5)
            ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=5, pady=6)
            row = ttk.Frame(self.mbar)
            row.pack(fill="x")
            self._model_lbl = ttk.Label(row, text=t("model.label"))
            self._model_lbl.pack(side="left")
            cb = ttk.Combobox(row, textvariable=self._model_var,
                              values=self.model_names, state="readonly", width=32)
            cb.pack(side="left", padx=6)
            cb.bind("<<ComboboxSelected>>", lambda _e: self._on_model_change())

            self._svc_label = ttk.Label(row, foreground="#444")
            self._svc_label.pack(side="left", padx=10)

            # GPU 状态
            self.gpu_frame = tk.Frame(self.win, bg=BG)
            # 扩展填满垂直空间：吸收原日志区位置，避免底部留白
            self.gpu_frame.pack(fill="both", expand=True, padx=5)
            ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=5, pady=6)
            self._topo_lbl = ttk.Label(self.gpu_frame, foreground="#555")
            self._topo_lbl.pack(anchor="w")
            self._gpu_body = ttk.Frame(self.gpu_frame)
            self._gpu_body.pack(fill="x", pady=(6, 0))

            # 系统状态
            self.sys_frame = tk.Frame(self.win, bg=BG)
            self.sys_frame.pack(fill="x", padx=5)
            ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=5, pady=6)
            self._sys_rows = {}
            self._sys_row_labels = {}
            self._sys_row_keys = {"cpu": "sys.cpu", "mem": "sys.mem", "disk": "sys.disk",
                                  "swap": "sys.swap", "load": "sys.load",
                                  "temp": "sys.temp", "freq": "sys.freq"}
            grid = ttk.Frame(self.sys_frame)
            grid.pack(fill="x")
            for i, (key, label) in enumerate([
                ("cpu", t("sys.cpu")), ("mem", t("sys.mem")), ("disk", t("sys.disk")),
                ("swap", t("sys.swap")), ("load", t("sys.load")), ("temp", t("sys.temp")),
                ("freq", t("sys.freq")),
            ]):
                r, c = divmod(i, 4)
                cell = ttk.Frame(grid)
                cell.grid(row=r, column=c, sticky="w", padx=8, pady=2)
                lbl = ttk.Label(cell, text=label + ":")
                lbl.pack(side="left")
                self._sys_row_labels[key] = lbl
                val = ttk.Label(cell, text="—", width=16, anchor="w")
                val.pack(side="left")
                self._sys_rows[key] = val

            # 硬件信息
            self.hw_frame = tk.Frame(self.win, bg=BG)
            self.hw_frame.pack(fill="x", padx=5)
            ttk.Separator(self.win, orient="horizontal").pack(fill="x", padx=5, pady=6)
            self._hw_lbl = ttk.Label(self.hw_frame, text="—", foreground="#555",
                                     justify="left", wraplength=820)
            self._hw_lbl.pack(anchor="w")

            # 按钮
            btns = ttk.Frame(self.win, padding=(12, 8))
            btns.pack(fill="x", padx=5)
            tb_font = ("Microsoft YaHei UI", 10)
            self._btn = {
                "start": tk.Button(btns, text=t("btn.start"), command=self._start_model,
                                   relief="flat", cursor="hand2", padx=8, pady=4, font=tb_font,
                                   bg="#f4f4f4", activebackground="#e2e2e2", bd=0),
                "stop": tk.Button(btns, text=t("btn.stop"), command=self._stop_model,
                                  relief="flat", cursor="hand2", padx=8, pady=4, font=tb_font,
                                  bg="#f4f4f4", activebackground="#e2e2e2", bd=0),
                "restart": tk.Button(btns, text=t("btn.restart"), command=self._restart_model,
                                     relief="flat", cursor="hand2", padx=8, pady=4, font=tb_font,
                                     bg="#f4f4f4", activebackground="#e2e2e2", bd=0),
                "refresh": tk.Button(btns, text=t("btn.refresh"), command=self._refresh_once,
                                     relief="flat", cursor="hand2", padx=8, pady=4, font=tb_font,
                                     bg="#f4f4f4", activebackground="#e2e2e2", bd=0),
                "download": tk.Button(btns, text=t("btn.download"), command=self._download_model,
                                      relief="flat", cursor="hand2", padx=8, pady=4, font=tb_font,
                                      bg="#f4f4f4", activebackground="#e2e2e2", bd=0),
            }
            for b in self._btn.values():
                b.pack(side="left", padx=4)

            self._busy_lbl = ttk.Label(btns, foreground="#aa6")
            self._busy_lbl.pack(side="left", padx=8)


            self._apply_model_texts()
            self._refresh_hw()

        def _drag_start(self, e):
            self._drag_x, self._drag_y = e.x, e.y

        def _drag_move(self, e):
            try:
                x = self.win.winfo_x() + (e.x - self._drag_x)
                y = self.win.winfo_y() + (e.y - self._drag_y)
                m = getattr(self.win, "master", None)
                if m is not None:
                    # 限制在主窗口范围内，不跑到外面
                    mw, mh = m.winfo_width(), m.winfo_height()
                    mx, my = m.winfo_rootx(), m.winfo_rooty()
                    ww, wh = self.win.winfo_width(), self.win.winfo_height()
                    x = min(max(x, mx - 10), mx + mw - ww + 10)
                    y = min(max(y, my - 10), my + mh - wh + 10)
                self.win.geometry("+%d+%d" % (x, y))
            except Exception:                # noqa: BLE001
                pass

        def _toggle_lang(self):
            global _lang
            _lang = "zh" if _lang != "zh" else "en"
            _save_lang()
            self._relabel()

        def _relabel(self):
            """按当前语言刷新可见文案。"""
            self.win.title("")
            self._subtitle_lbl.config(text=(t("subtitle.win") if IS_WINDOWS else t("subtitle.linux")))
            self._model_lbl.config(text=t("model.label"))
            self._btn["start"].config(text=t("btn.start"))
            self._btn["stop"].config(text=t("btn.stop"))
            self._btn["restart"].config(text=t("btn.restart"))
            self._btn["refresh"].config(text=t("btn.refresh"))
            self._btn["download"].config(text=t("btn.download"))
            self._status_lbl.config(text=t("status.checking"))
            # 系统状态行标签
            for key, k in self._sys_row_keys.items():
                w = self._sys_row_labels.get(key)
                if w:
                    w.config(text=t(k) + ":")
            self._apply_model_texts()

        def _current_cfg(self):
            return MODELS[self._model_var.get()]

        def _apply_model_texts(self):
            cfg = self._current_cfg()
            self._svc_label.config(
                text=t("srv.line", svc=cfg["service"], port=cfg["port"],
                     spec=cfg["spec_type"]))
            self._endpoint_lbl.config(text="%s   ·   %s" % (cfg["endpoint"], cfg["health_url"]))

        def _on_model_change(self):
            self._apply_model_texts()
            self._refresh_once()
            # 仅记住选择，不做自动启动；启动交给用户点「启动」按钮
            try:
                _save_last_model(self._model_var.get())
            except Exception:                # noqa: BLE001
                pass

        # ─────────────────── 日志 ───────────────────
        def _log(self, msg):
            # 日志区已去掉：打印到控制台（调试用），不占用界面
            try:
                print("[%s] %s" % (time.strftime("%H:%M:%S"), msg))
            except Exception:                # noqa: BLE001
                pass

        def _copy_log(self):
            # 日志区已去掉，此项不再可用
            pass

        @staticmethod
        def _ishex(c):
            return c in "0123456789abcdefABCDEF"

        # ─────────────────── 刷新 ───────────────────
        def _refresh_loop(self):
            try:
                self._refresh_once()
            except Exception as e:                       # noqa: BLE001
                # 刷新异常不中断循环，避免面板"冻结"
                self._log("[警告] 刷新异常已忽略：%s" % e)
            self.win.after(REFRESH_MS, self._refresh_loop)

        def _refresh_once(self):
            self._refresh_status()
            self._refresh_gpu()
            self._refresh_system()

        def _refresh_status(self):
            cfg = self._current_cfg()
            state = service_status(cfg["service"])
            self._status = state

            if state == "active":
                ok, detail = health_check(cfg["health_url"], cfg["health_timeout"])
                color, text = "#2e9e3f", t("status.running")
                extra = ""
                if not ok:
                    color, text = "#c9a227", t("status.running_fail")
                    extra = " · " + detail
            elif state == "activating":
                color, text = "#3f7fbf", t("status.loading")
                extra = ""
            elif state == "failed":
                color, text = "#c0392b", t("status.failed")
                extra = ""
            else:
                color, text = "#b0b0b0", t("status.stopped")
                extra = ""
            self._status_lbl.config(fg=color, text=text)
            self._health_lbl.config(text=t("status.health", x=extra.strip() or "OK"))

        def _refresh_gpu(self):
            gpus, topo, err = query_gpu()
            if gpus:
                nv = query_nvlink()                 # 动态 NVLink 级联状态
                topo = topo + (" · " + nv) if nv else topo
            if gpus:
                self._topo_lbl.config(text=topo)
            else:
                # 不可用也要告诉用户机器上有什么卡（三平台静态探测），
                # NVML 类错误附修复提示
                if err:
                    msg = t("gpu.err_unavail", err=err)
                    if "NVML" in err:
                        msg += " · " + t("gpu.nvml_hint")
                else:
                    msg = t("gpu.unavail")
                names = gpu_static_names()
                if names:
                    msg = " · ".join(names) + " — " + msg
                self._topo_lbl.config(text=msg)
            if not gpus:
                # 清空旧的 GPU 行
                if self._gpu_count:
                    for w in self._gpu_body.winfo_children():
                        w.destroy()
                    self._gpu_rows = {}
                    self._gpu_count = 0
                return

            # 数量变化则重建行
            if len(gpus) != self._gpu_count:
                for w in self._gpu_body.winfo_children():
                    w.destroy()
                self._gpu_rows = {}
                for g in gpus:
                    self._build_gpu_row(g)
                self._gpu_count = len(gpus)

            usage_by_gpu = query_model_usage()          # 模型(llama-server)占用明细

            for g in gpus:
                idx = g["index"]
                row = self._gpu_rows.get(idx)
                if not row:
                    continue
                row["name"].config(text="%s  %s" % (
                    g["name"].replace("NVIDIA GeForce ", "").replace("NVIDIA ", ""), idx))
                # nvidia-smi --format=nounits 的 memory.used/total 单位是 MiB
                used_mib = float(g["mem_used"])
                total_mib = float(g["mem_total"])
                # 模型 vs 桌面/系统 拆分
                du = usage_by_gpu.get(idx, {})
                model_mib = du.get("model_mem", 0)
                model_name = du.get("model", "") or "—"
                desk_mib = max(0.0, used_mib - model_mib)
                row["mem"].config(
                    text="%.1f/%.1fG" % (used_mib / 1024.0, total_mib / 1024.0))
                row["usage"].config(
                    text=t("gpu.mem_model", name=model_name,
                           m=model_mib / 1024.0, d=desk_mib / 1024.0))
                util = g["util"]
                try:
                    row["util"].config(value=float(util))
                except Exception:
                    row["util"].config(value=0)
                row["util_lbl"].config(text="%s%%" % util)
                row["temp"].config(text="%s°C" % g["temp"])
                row["fan"].config(text=t("gpu.fan", fan=g["fan"]))

        def _build_gpu_row(self, g):
            wrap = ttk.Frame(self._gpu_body)
            wrap.pack(fill="x", pady=2)
            name = ttk.Label(wrap, text="", width=26, anchor="w")
            name.pack(side="left")
            util = ttk.Progressbar(wrap, length=70, maximum=100, mode="determinate")
            util.pack(side="left", padx=5)
            util_lbl = ttk.Label(wrap, text="0%", width=4)
            util_lbl.pack(side="left")
            temp = ttk.Label(wrap, text="—", width=5)
            temp.pack(side="left")
            fan = ttk.Label(wrap, text="—", width=10)
            fan.pack(side="left")
            mem = ttk.Label(wrap, text="—", width=14, anchor="e")
            mem.pack(side="left")
            usage = ttk.Label(wrap, text="", anchor="w")
            usage.pack(side="left")
            self._gpu_rows[g["index"]] = {
                "name": name, "util": util, "util_lbl": util_lbl,
                "temp": temp, "fan": fan, "mem": mem, "usage": usage,
            }

        def _refresh_system(self):
            s = query_system()

            def setv(key, val):
                w = self._sys_rows.get(key)
                if w:
                    w.config(text=str(val))

            setv("cpu", human_pct(s.get("cpu_percent")))
            setv("mem", "%s / %s" % (fmt_gib(s.get("mem_used")), fmt_gib(s.get("mem_total"))))
            setv("disk", "%s / %s" % (fmt_gib(s.get("disk_used")), fmt_gib(s.get("disk_total"))))
            if s.get("swap_total"):
                setv("swap", "%s / %s" % (fmt_gib(s.get("swap_used")), fmt_gib(s.get("swap_total"))))
            else:
                setv("swap", "—")
            if s.get("load"):
                setv("load", "%.2f / %.2f / %.2f" % tuple(s["load"]))
            if s.get("cpu_temp") is not None:
                setv("temp", "%.1f°C" % s["cpu_temp"])
            if s.get("cpu_freq") is not None:
                fmax = s.get("cpu_freq_max")
                cur_ghz = s["cpu_freq"] / 1000
                max_ghz = (fmax / 1000) if fmax else None
                setv("freq", "%.2f GHz%s" % (cur_ghz,
                                             ("/%.2f GHz" % max_ghz) if max_ghz else ""))
            self._health_lbl.config  # no-op (already set)

        def _refresh_hw(self):
            hw = detect_hardware()
            lines = []
            # MaxClockSpeed / lscpu 返回 MHz，转成 GHz 再显示（避免出现 2592.0 GHz）
            fmax = (hw["freq_max"] / 1000) if hw.get("freq_max") else None
            max_txt = t("hw.cpu_max", freq="%.2f" % fmax) if fmax else ""
            lines.append(t("hw.cpu", cpu=hw["cpu_model"],
                           cores=hw["physical_cores"] if hw["physical_cores"] else 0,
                           threads=hw["logical_cpus"] or hw["threads"] or 0,
                           max=max_txt))
            lines.append(t("hw.mem", mem=fmt_gib(hw.get("mem_total"))))
            lines.append(t("hw.disk", disk=hw.get("disk_model") or "—"))
            self._hw_lbl.config(text="   ".join(lines))

        # ─────────────────── 启停控制 ───────────────────
        def _set_busy(self, busy, txt=""):
            self._busy_lbl.config(text=txt if busy else "")

        def _download_model(self):
            """从 ModelScope 下载当前所选模型（后台线程，输出到日志）。"""
            cfg = self._current_cfg()
            name = self._model_var.get()
            repo = cfg.get("ms_repo") or ""
            if not repo:
                self._log("[提示] %s 未配置 ModelScope 仓库（ms_repo），无法自动下载。" % name)
                return
            if find_modelscope() is None:
                self._log("[错误] 未找到 modelscope 命令。请先：pip install modelscope")
                return
            os.makedirs(cfg["models_dir"], exist_ok=True)
            self._log("[操作] 开始从 ModelScope 下载 %s ..." % repo)
            if cfg.get("ms_files"):
                self._log("      目标文件：%s" % "、".join(cfg["ms_files"]))
            self._set_busy(True, "下载中...")
            threading.Thread(target=self._do_download, args=(cfg,), daemon=True).start()

        def _do_download(self, cfg):
            ms = find_modelscope()
            cmd = [ms, "download", cfg["ms_repo"], "--local_dir", cfg["models_dir"]]
            if cfg.get("ms_files"):
                cmd += list(cfg["ms_files"])        # 位置参数指定文件
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True,
                                     errors="replace", bufsize=1,
                                     creationflags=_NO_WINDOW)
                for line in p.stdout:
                    line = line.rstrip()
                    if line:
                        self._log("      " + line)
                p.wait()
                self._set_busy(False)
                if p.returncode == 0:
                    self._log("[信息] %s 下载完成，位于 %s" % (cfg["ms_repo"], cfg["models_dir"]))
                else:
                    self._log("[错误] 下载结束（退出码 %s）。" % p.returncode)
            except Exception as e:                       # noqa: BLE001
                self._set_busy(False)
                self._log("[错误] 下载异常：%s" % e)

        def _stop_others(self, cur_cfg):
            """串行切换：启动某模型前，无条件停掉所有其它已配置模型的 user 服务。

            对已停止的服务 systemctl stop 是安全的 no-op，故不必先判断状态——
            避免漏停“启动中/状态探测异常”的模型，导致两个模型同时抢显存。
            """
            for name, other in MODELS.items():
                if other is cur_cfg or not other.get("service"):
                    continue
                if service_status(other["service"]) == "active":
                    self._log(t("log.stop_others", name=name))
                svc_stop(other)

        def _start_model(self):
            cfg = self._current_cfg()
            name = self._model_var.get()
            _save_last_model(name)           # 记住本次启动的模型
            self._stop_others(cfg)
            self._log(t("log.starting", name=name))
            rc = svc_start(cfg)
            if rc != 0:
                self._log(t("log.start_fail", rc=rc))
                return
            self._log(t("log.started_wait"))
            threading.Thread(target=self._wait_loading, args=(cfg,), daemon=True).start()

        def _stop_model(self):
            cfg = self._current_cfg()
            name = self._model_var.get()
            self._log(t("log.stopping", name=name))
            if svc_stop(cfg) != 0:
                self._log(t("log.stop_fail"))
                return
            self._log(t("log.stopped"))

        def _restart_model(self):
            cfg = self._current_cfg()
            name = self._model_var.get()
            self._log(t("log.restarting", name=name))
            if svc_restart(cfg) != 0:
                self._log(t("log.restart_fail"))
                return
            self._log("[信息] 服务已启动，等待模型加载...")
            threading.Thread(target=self._wait_loading, args=(cfg,), daemon=True).start()

        def _wait_loading(self, cfg):
            """后台轮询健康端点，模拟截图中的加载进度日志。"""
            t0 = time.time()
            poll = cfg["load_poll_s"]
            timeout = cfg["load_timeout_s"]
            shown = 0
            while True:
                state = service_status(cfg["service"])
                if state == "inactive" or state == "failed":
                    self._log(t("log.state_end", state=state))
                    return
                ok, _ = health_check(cfg["health_url"], cfg["health_timeout"])
                if ok:
                    el = time.time() - t0
                    self._log(t("log.load_done", name=self._model_var.get(), sec=int(el)))
                    self._log(t("log.svc_addr", url=cfg["endpoint"]))
                    return
                if time.time() - t0 > timeout:
                    self._log(t("log.load_timeout", sec=timeout))
                    return
                # 每 load_poll_s 秒打一次进度
                if shown < 30:
                    self._log(t("log.loading_wait", sec=int(time.time() - t0)))
                    shown += 1
                time.sleep(poll)


# ─────────────────────────────────────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if not TK_AVAILABLE:
        print("未安装 tkinter。请先执行:  sudo apt install -y python3-tk")
        sys.exit(1)
    # 主界面为入口；模型管理面板（ModelPanel）从主界面以模态子窗打开
    try:
        from gpulocal.main_window import MainWindow
    except ImportError:                # noqa: BLE001  gpulocal/ 目录内直接运行
        from main_window import MainWindow
    app = MainWindow()
    app.root.mainloop()


if __name__ == "__main__":
    main()
