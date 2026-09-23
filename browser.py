# -*- coding: utf-8 -*-
"""Agent 浏览器：通过 Playwright 驱动系统 Edge/Chrome（可选依赖，优雅降级）。

像 ZCode 的 browser-use：模型通过 browser_* 工具打开网页、读正文、点击、
填表、执行 JS、整页截图。依赖 playwright（pip install playwright 即可，
浏览器用系统自带 Edge，无需 playwright install 下载内核）；未安装时
available()=False，工具返回安装提示而不是报错中断（与 voice/faster-whisper
同款降级策略）。

线程模型：Playwright sync API 与创建线程绑定，而工具执行每次起独立
worker 线程——因此所有页面操作经队列派发给一条常驻浏览器线程串行执行
（_run_in_worker），状态无需加锁。

安全边界：不触碰用户浏览器配置（launch 用独立 context）；可执行页面
脚本/点击的工具在 tools.py 里归入审批层（WRITE_TOOLS）。
失败抛 BrowserError；reset() 供测试隔离。
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import os
import queue
import threading


class BrowserError(Exception):
    pass


def available() -> bool:
    """Playwright 是否已安装（浏览器内核用系统 Edge，不另下载）。"""
    return importlib.util.find_spec("playwright") is not None


def find_browser() -> str:
    """定位 Edge/Chrome 可执行文件；找不到返回空串（用 Playwright 自带内核）。"""
    cands = []
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if not base:
            continue
        cands += [
            os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
        ]
    for p in cands:
        if os.path.isfile(p):
            return p
    import shutil
    return shutil.which("msedge") or shutil.which("chrome") or \
        shutil.which("chromium") or ""


def _read_system_proxy() -> str:
    """读 Windows 系统代理（WinINET——用户浏览器走的那一个）；非 Windows 返回空。

    ProxyServer 有两种形态："127.0.0.1:7890" 或 "http=…;https=…" 分协议写法。
    """
    if os.name != "nt":
        return ""
    try:
        import winreg
        with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as k:
            enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
            server, _ = winreg.QueryValueEx(k, "ProxyServer")
        server = str(server or "").strip()
        if enable and server:
            if ";" in server or "=" in server:
                for part in server.split(";"):
                    if part.lower().startswith(("https=", "http=")):
                        server = part.split("=", 1)[1]
                        break
            return server
    except Exception:                      # noqa: BLE001  无代理/注册表不可读
        pass
    return ""


def _cfg_browser() -> dict:
    """/media 面板的浏览器行为配置（headed/proxy）；读不到按空处理。"""
    try:
        import config
        return config.get_browser()
    except Exception:              # noqa: BLE001  未装/损坏时降级
        return {}


def _headed() -> bool:
    """可见窗口开关：环境变量 > 面板配置。"""
    env = os.environ.get("LAS_BROWSER_HEADED", "").strip()
    if env:
        return env != "0"
    return _cfg_browser().get("headed", "") in ("1", "true", "on")


def _proxy_mode() -> str:
    """代理模式：auto（跟随系统）/ direct（强制直连）。环境变量优先。"""
    env = os.environ.get("LAS_BROWSER_PROXY", "").strip().lower()
    if env:
        return "direct" if env in ("off", "none", "direct") else "system"
    return _cfg_browser().get("proxy", "") or "system"


def _detect_proxy() -> dict | None:
    """浏览器出网代理，优先级：

    1. LAS_BROWSER_PROXY：off/direct=强制直连；否则视为代理地址本身
    2. 面板配置 proxy=direct：强制直连
    3. 系统代理（用户浏览器可达性 = agent 一致）；本机地址永远绕行
    """
    env = os.environ.get("LAS_BROWSER_PROXY", "").strip()
    if env.lower() in ("off", "none", "direct"):
        return None
    if env:
        p = env
    elif _cfg_browser().get("proxy", "") == "direct":
        return None
    else:
        p = _read_system_proxy()
    if not p:
        return None
    if not p.lower().startswith(("http://", "https://", "socks5://")):
        p = "http://" + p
    return {"server": p, "bypass": "localhost,127.0.0.1,<local>"}


# ---------------- 常驻浏览器线程（sync API 线程亲和） ----------------

_QUEUE: "queue.Queue | None" = None
_THREAD: threading.Thread | None = None
_SPAWN_LOCK = threading.Lock()


def _worker_loop(q: "queue.Queue"):
    pw = None
    while True:
        item = q.get()
        if item is None:
            break
        fn, fut = item
        try:
            if pw is None:
                from playwright.sync_api import sync_playwright
                pw = sync_playwright().start()
            fut.set_result(fn(pw))
        except Exception as e:                 # noqa: BLE001  原样回传调用方
            try:
                fut.set_exception(e)
            except Exception:                  # noqa: BLE001  future 已失效
                pass


def _run_in_worker(fn, timeout: float = 60.0):
    """把页面操作派发给常驻线程执行并等结果；异常原样抛回。"""
    global _QUEUE, _THREAD
    with _SPAWN_LOCK:
        if _THREAD is None or not _THREAD.is_alive():
            _QUEUE = queue.Queue()
            _THREAD = threading.Thread(target=_worker_loop, args=(_QUEUE,),
                                       daemon=True, name="las-browser")
            _THREAD.start()
    fut: concurrent.futures.Future = concurrent.futures.Future()
    _QUEUE.put((fn, fut))
    return fut.result(timeout=timeout)


# ---------------- 浏览器/页面状态（仅浏览器线程内访问） ----------------

def _profile_dir() -> str:
    """持久化浏览器用户目录：cookie 落盘，登录状态跨进程/跨重启保留。"""
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    p = os.path.join(base, "local-ai-studio", "browser-profile")
    os.makedirs(p, exist_ok=True)
    return p


_TRANSIENT_ERRORS = ("Execution context was destroyed",
                     "Document is navigating",
                     "navigation to about:blank was interrupted",
                     "Target page, context or browser has been closed")


def _page_eval(page, expression, tries: int = 4):
    """页面求值，导航瞬时的报错自动等待重试（站内跳转高频踩坑）。"""
    import time as _t
    last = None
    for i in range(tries):
        try:
            return page.evaluate(expression)
        except Exception as e:         # noqa: BLE001
            last = e
            if any(k in str(e) for k in _TRANSIENT_ERRORS) and i < tries - 1:
                _t.sleep(1.2)
                continue
            raise
    raise last


def _ensure_state(pw):
    """拿可用的 page；浏览器未启动/已断开则重启。仅在浏览器线程内调用。"""
    st = getattr(_worker_loop, "_st", None)
    if st is not None:
        try:
            if st["page"].evaluate("1") == 1:
                return st
        except Exception:                  # noqa: BLE001  断开则重建
            pass
    exe = find_browser()
    kwargs = {"headless": not _headed(),
              "args": ["--hide-scrollbars", "--window-size=1280,1600",
                       "--disable-blink-features=AutomationControlled",
                       "--lang=zh-CN"]}
    if exe:
        kwargs["executable_path"] = exe    # 用系统 Edge/Chrome，免下内核
    proxy = _detect_proxy()
    if proxy:
        kwargs["proxy"] = proxy            # 跟随系统代理，可达性与用户一致
    else:
        # 直连模式必须显式禁掉系统代理：Chromium 默认读 WinINET，
        # 不加这个参数请求仍会被系统代理（可能是失效隧道）劫持
        kwargs["args"].append("--no-proxy-server")
    # 持久化 context：登录态/cookie 落盘（网站操作类任务跨会话复用），
    # 同时带上反爬基线（真实 UA、中文语境）。
    stealth = {"user_agent": (
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 "
                   "Safari/537.36 Edg/140.0.0.0"),
               "locale": "zh-CN", "timezone_id": "Asia/Shanghai",
               "viewport": {"width": 1280, "height": 1600}}
    ctx = pw.chromium.launch_persistent_context(_profile_dir(),
                                                **kwargs, **stealth)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    # 弹窗自动确认（登录确认框不阻塞）；新开窗口自动跟随为当前页
    page.on("dialog", lambda d: _safe_accept(d))
    ctx.on("page", lambda p: _follow_popup(p))
    st = {"browser": ctx, "page": page}
    _worker_loop._st = st                  # noqa: SLF001  模块内挂载状态
    return st


def _safe_accept(dialog):
    try:
        dialog.accept()
    except Exception:                      # noqa: BLE001  已消失
        pass


def _follow_popup(page):
    """新窗口（登录后弹出的看板等）自动成为当前操作页。"""
    st = getattr(_worker_loop, "_st", None)
    if st is not None:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:                  # noqa: BLE001
            pass
        st["page"] = page


def reset():
    """整组销毁（测试隔离 / 异常恢复）。"""
    global _QUEUE, _THREAD

    def job(pw):
        st = getattr(_worker_loop, "_st", None)
        if st is not None:
            try:
                st["browser"].close()
            except Exception:              # noqa: BLE001  已关闭忽略
                pass
        _worker_loop._st = None            # noqa: SLF001
        return True

    if _THREAD is not None and _THREAD.is_alive():
        try:
            _run_in_worker(job, timeout=15)
        except Exception:                  # noqa: BLE001  尽力而为
            pass
        _QUEUE.put(None)
    _QUEUE = None
    _THREAD = None


# ---------------- URL 容错 ----------------

def normalize_url(url: str) -> str:
    """裸域名补 https://；其余原样返回。空/明显非 URL 抛 BrowserError。"""
    u = (url or "").strip()
    if u.lower().startswith(("http://", "https://", "file://", "about:")):
        return u
    if u and "." in u and " " not in u:
        return "https://" + u
    raise BrowserError(f"URL 不合法（需 http(s):// 开头或裸域名）：{url!r}")


# ---------------- 工具入口（供 tools.py 调用） ----------------

def open_url(url: str) -> str:
    """新开导航并等加载，返回「标题 + 链接 + 正文前段」。"""
    target = normalize_url(url)

    def job(pw):
        page = _ensure_state(pw)["page"]
        page.goto(target, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("load", timeout=12000)
        except Exception:                  # noqa: BLE001  长轮询站点 load 不完
            pass
        page.wait_for_timeout(400)         # 首屏渲染余量
        title = page.title()
        text = page.inner_text("body")[:1200] if _has_body(page) else ""
        return f"已打开：{title}\n链接：{page.url}\n\n{text}"

    return _run_in_worker(job, timeout=60)


def _has_body(page) -> bool:
    try:
        return page.evaluate("document.body !== null")
    except Exception:                      # noqa: BLE001
        return False


def pages() -> str:
    """列出上下文中全部打开的页面（含新弹窗/OAuth 窗口），返回编号+URL。"""
    def job(pw):
        st = _ensure_state(pw)
        out = []
        for i, p in enumerate(st["page"].context.pages):
            try:
                t = p.title()
            except Exception:              # noqa: BLE001  未加载页
                t = ""
            out.append("[%d] %s %s" % (i, p.url, t))
        return "\n".join(out) or "(无页面)"

    return _run_in_worker(job, timeout=30)


def switch_to(index: int) -> str:
    """把后续操作切换到指定编号的页面（browser_pages 里看到的编号）。"""
    index = int(index)

    def job(pw):
        st = _ensure_state(pw)
        pages = st["page"].context.pages
        if not 0 <= index < len(pages):
            raise BrowserError(
                f"页面编号 {index} 不存在（当前 {len(pages)} 个页面，"
                "先用 browser_pages 列表查看）")
        st["page"] = pages[index]
        return f"已切换到 [{index}] {st['page'].url}"

    return _run_in_worker(job, timeout=30)


def read_page(max_chars: int = 6000) -> str:
    """当前页正文（innerText），按 max_chars 截断并提示全文长度。"""
    n = max(500, min(int(max_chars or 6000), 50000))

    def job(pw):
        page = _ensure_state(pw)["page"]
        title = page.title()
        text = page.inner_text("body") if _has_body(page) else ""
        if len(text) > n:
            text = (text[:n]
                    + f"\n…（已截断，全文 {len(text)} 字符；可加大 max_chars"
                      " 或用 browser_eval 精取）")
        return f"[{title}]\n{text}" if title else text

    return _run_in_worker(job, timeout=45)


def click(selector: str) -> str:
    """点击 CSS 选择器元素（真实鼠标事件 + 自动滚动），返回点击后页面标题。"""
    selector = (selector or "").strip()
    if not selector:
        raise BrowserError("缺少 CSS 选择器")

    def job(pw):
        page = _ensure_state(pw)["page"]
        try:
            page.click(selector, timeout=8000)
        except Exception as e:         # noqa: BLE001
            # 异步跳转站点：点击已生效、仅「等待导航」超时 → 视为成功
            if "click action done" not in str(e):
                raise
        try:
            page.wait_for_load_state("load", timeout=10000)
        except Exception:              # noqa: BLE001  无导航的点击
            pass
        page.wait_for_timeout(300)
        return f"已点击 {selector}；当前页：{page.title()}"

    return _run_in_worker(job, timeout=45)


def fill(selector: str, text: str) -> str:
    """清空并填入输入框（Playwright fill 兼容 React 受控组件）。"""
    selector = (selector or "").strip()
    if not selector:
        raise BrowserError("缺少 CSS 选择器")

    def job(pw):
        page = _ensure_state(pw)["page"]
        page.fill(selector, text or "", timeout=8000)
        return f"已填入 {selector}（{len(text or '')} 字符）"

    return _run_in_worker(job, timeout=45)


def eval_js(expression: str) -> str:
    """在当前页执行 JS，返回 JSON 序列化结果（研究/取数逃生舱）。"""
    expression = (expression or "").strip()
    if not expression:
        raise BrowserError("缺少 JS 表达式")

    def job(pw):
        page = _ensure_state(pw)["page"]
        val = page.evaluate(expression)
        return json_dumps(val)

    return _run_in_worker(job, timeout=45)


def json_dumps(val) -> str:
    import json
    out = json.dumps(val, ensure_ascii=False, default=str)
    return out if len(out) <= 20000 else out[:20000] + "…（已截断）"


def screenshot(out_path: str) -> str:
    """当前页整页截图，落盘 PNG（路径由工具层保证在工作区内）。"""

    def job(pw):
        page = _ensure_state(pw)["page"]
        page.screenshot(path=out_path, full_page=True, timeout=30000)
        return out_path

    return _run_in_worker(job, timeout=60)


def close() -> str:
    """关闭浏览器（保留 Playwright 实例，下次打开更快）。"""

    def job(pw):
        st = getattr(_worker_loop, "_st", None)
        if st is None:
            return "浏览器未在运行"
        st["browser"].close()
        _worker_loop._st = None            # noqa: SLF001
        return "浏览器已关闭"

    return _run_in_worker(job, timeout=30)
