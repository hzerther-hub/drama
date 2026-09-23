# -*- coding: utf-8 -*-
"""浏览器智能体引擎：驱动本机 jev-ultrafast（TypeSafe Jev）按目标操作网站。

与 browser.py 的分工：browser.py 是「模型逐条调用浏览器工具」；
jev 模式是把一句目标交给 jev-ultrafast 的 Jev 策略自动连续操作
（登录/搜索/填表等），适合一步到位的站点任务。

前置条件（客户机器一次性准备）：
  1. 安装 jev-ultrafast（git clone 后 `uv sync`），
     目录写入 /media 面板的 jev.install_dir（默认 C:\\source\\jev-ultrafast）
  2. /media 面板填入自己的 TypeSafe API Key（存 models.json，按用户隔离）

运行时：自动拉起一个带 CDP 调试端口的独立 Edge（临时 profile，不动用户
浏览器），把 BU_CDP_WS / TYPESAFE_API_KEY 注入子进程后执行
examples/run.py，返回逐动作日志。仅允许 CDP 连本机回环端口。
失败抛 JevError；工具层转中文错误字符串。
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.request


class JevError(Exception):
    pass


DEFAULT_INSTALL_DIR = r"C:\source\jev-ultrafast"


def find_install(explicit: str = "") -> str:
    """定位 jev-ultrafast 安装目录：显式配置 > 环境变量 > 默认位置。"""
    cands = [explicit, os.environ.get("LAS_JEV_DIR", ""), DEFAULT_INSTALL_DIR]
    for c in cands:
        c = (c or "").strip()
        if not c:
            continue
        c = os.path.normpath(c)
        if os.path.isfile(os.path.join(c, "examples", "run.py")):
            return c
    return ""


def installed(explicit: str = "") -> bool:
    return bool(find_install(explicit))


def _free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _find_edge() -> str:
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            p = os.path.join(base, "Microsoft", "Edge",
                             "Application", "msedge.exe")
            if os.path.isfile(p):
                return p
    return shutil_which("msedge")


def shutil_which(name: str) -> str:
    import shutil
    return shutil.which(name) or ""


def ensure_cdp_ws(timeout_s: float = 20.0) -> tuple:
    """拉起带 CDP 调试端口的独立 Edge，返回 (ws_url, proc, profile_dir)。

    只连 127.0.0.1 上自己拉起的端口；已拉起过则复用（模块级缓存）。
    """
    st = getattr(ensure_cdp_ws, "_st", None)
    if st:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{st['port']}/json/version",
                    timeout=3) as r:
                if r.status == 200:
                    return st["ws"], st["proc"], st["profile"]
        except Exception:              # noqa: BLE001  失联则重启
            pass
    exe = _find_edge()
    if not exe:
        raise JevError("未找到 Edge 浏览器（jev 模式需要一个 Chromium 系浏览器）")
    port = _free_port()
    profile = tempfile.mkdtemp(prefix="las-jev-edge-")
    proc = subprocess.Popen(
        [exe, "--remote-debugging-port=%d" % port,
         "--user-data-dir=" + profile, "--headless=new",
         "--no-first-run", "--no-default-browser-check",
         "--disable-gpu", "--window-size=1280,1600", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time
    end = time.monotonic() + timeout_s
    ws = ""
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
                ws = str(json.loads(r.read().decode("utf-8"))
                         .get("webSocketDebuggerUrl", ""))
            if ws:
                break
        except Exception:              # noqa: BLE001  未就绪继续轮询
            time.sleep(0.4)
    if not ws:
        proc.kill()
        raise JevError("jev 浏览器调试端口未就绪（20 秒超时）")
    st = {"proc": proc, "port": port, "profile": profile, "ws": ws}
    ensure_cdp_ws._st = st             # noqa: SLF001  模块内缓存
    return ws, proc, profile


def run_goal(url: str, goal: str, api_key: str, install_dir: str = "",
             model: str = "jev-latest", timeout_s: float = 240.0) -> str:
    """执行一句目标，返回 jev-ultrafast 的逐动作日志。同步阻塞调用。"""
    url = (url or "").strip()
    goal = (goal or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        raise JevError(f"URL 必须以 http(s):// 开头：{url!r}")
    if not goal:
        raise JevError("缺少目标描述")
    src = find_install(install_dir)
    if not src:
        raise JevError(
            "未找到 jev-ultrafast 安装目录。请 git clone 后 `uv sync`，"
            "并在 /media 面板填写 install_dir（默认 " + DEFAULT_INSTALL_DIR + "）")
    ws, _proc, _profile = ensure_cdp_ws()
    env = dict(os.environ)
    env.update({"TYPESAFE_API_KEY": api_key,
                "TYPESAFE_MODEL": model or "jev-latest",
                "BU_CDP_WS": ws})
    cmd = ["uv", "run", "python", "examples/run.py",
           "--url", url, "--goal", goal]
    for attempt in range(3):
        try:
            proc = subprocess.run(cmd, cwd=src, env=env, timeout=timeout_s,
                                  capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            raise JevError(f"jev 执行超时（>{int(timeout_s)}s），目标可能过大，"
                           "请拆小后再试") from None
        out = (proc.stdout or "") + (proc.stderr or "")
        # StalePage：目标站在导航中抓快照的瞬时竞态，重跑一次即过
        if proc.returncode != 0 and "StalePage" in out and attempt < 2:
            time.sleep(2)
            continue
        break
    tail = "\n".join(out.splitlines()[-12:])
    if proc.returncode != 0:
        raise JevError("jev 执行失败：" + (tail or f"exit {proc.returncode}"))
    return tail or "jev 执行完成（无输出）"


def close() -> str:
    """关闭 jev 专用的后台 Edge。"""
    st = getattr(ensure_cdp_ws, "_st", None)
    if not st:
        return "jev 浏览器未在运行"
    try:
        st["proc"].kill()
    except OSError:
        pass
    import shutil
    shutil.rmtree(st.get("profile", ""), ignore_errors=True)
    ensure_cdp_ws._st = None           # noqa: SLF001
    return "jev 浏览器已关闭"
