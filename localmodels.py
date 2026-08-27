# -*- coding: utf-8 -*-
"""本地 GPU 模型桥接层：把 ../gpulocal 的模型管理接入本程序。

- 模型清单动态导入自 gpulocal/local_model_panel.py 的 MODELS 注册表
  （按文件 mtime 缓存，那边改了注册表，这边下次打开菜单/重启即生效）；
- 启停复用同一套 systemd --user 服务，因此 gpulocal 面板与本程序
  看到的是同一份状态，两边任一侧操作、两侧同步变化；
- sync_to_config() 把注册表同步进 models.json（本地端点整体重建，
  云端 provider 原样保留），qwen-coder 的模型下拉里即可直接选用。

仅标准库；gpulocal 目录缺失时所有函数安全降级（返回空/False）。
"""

from __future__ import annotations

import importlib.util
import os
import sys as _sys
import threading

def _resolve_gpulocal_dir() -> str:
    """按优先级定位内嵌 gpulocal 目录（PyInstaller / 仓库根 / 旧上一级）。"""
    base = os.path.dirname(os.path.abspath(__file__))
    cands = []
    if getattr(_sys, "_MEIPASS", None):            # PyInstaller 解包目录
        cands.append(os.path.join(_sys._MEIPASS, "gpulocal"))
    cands.append(os.path.join(base, "gpulocal"))
    cands.append(os.path.normpath(os.path.join(base, "..", "gpulocal")))
    for c in cands:
        if os.path.isfile(os.path.join(c, "local_model_panel.py")):
            return c
    return os.path.join(base, "gpulocal")          # 兜底（注定不存在）


# gpulocal 目录：本仓库内嵌子目录
_GPULOCAL_DIR = _resolve_gpulocal_dir()
_PANEL_PATH = os.path.join(_GPULOCAL_DIR, "local_model_panel.py")

# 注册表缓存（按 mtime 失效）
_cache_lock = threading.Lock()
_cache = {"mtime": None, "module": None}


# ─────────────────────────────────────────────────────────────────────────────
# 注册表加载
# ─────────────────────────────────────────────────────────────────────────────

def _panel_module():
    """按需导入 local_model_panel 模块（其界面类有守卫，导入无副作用）。"""
    try:
        mtime = os.path.getmtime(_PANEL_PATH)
    except OSError:
        return None
    with _cache_lock:
        if _cache["module"] is not None and _cache["mtime"] == mtime:
            return _cache["module"]
        try:
            spec = importlib.util.spec_from_file_location(
                "gpulocal_local_model_panel", _PANEL_PATH)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:                       # noqa: BLE001
            mod = None
        _cache["mtime"], _cache["module"] = mtime, mod
        return mod


def available() -> bool:
    """gpulocal 面板是否存在且可导入。"""
    return _panel_module() is not None


def list_models() -> dict:
    """返回 {显示名: 配置 dict}（来自 gpulocal 的 MODELS，动态）。"""
    mod = _panel_module()
    if mod is None:
        return {}
    return dict(getattr(mod, "MODELS", {}))


# ─────────────────────────────────────────────────────────────────────────────
# 状态与启停（复用 gpulocal 的实现，保证行为一致）
# ─────────────────────────────────────────────────────────────────────────────

def status_of(cfg: dict) -> tuple:
    """返回 (服务状态, 是否健康)：state 来自 systemctl，健康来自 /v1/models。"""
    mod = _panel_module()
    if mod is None:
        return "unknown", False
    state = mod.service_status(cfg["service"])
    healthy = False
    if state == "active":
        healthy, _ = mod.health_check(cfg["health_url"],
                                       timeout=cfg.get("health_timeout", 3))
    return state, healthy


def stop(name: str) -> tuple:
    """停止单个模型服务，返回 (ok, 消息)。"""
    mod = _panel_module()
    models = list_models()
    if mod is None or name not in models:
        return False, "错误：未找到本地模型 %s" % name
    cfg = models[name]
    if mod.svc_stop(cfg) != 0:
        return False, "停止失败（请查 gpulocal 日志）"
    return True, "已停止 %s" % name


def _stop_others(mod, models: dict, keep: str):
    """串行管理：启动前无条件停掉所有其它模型（显存一次只够跑一个）。

    复用 gpulocal 的 svc_* 跨平台接口（Linux=systemd，Windows=后台进程）；
    对已停止的服务 stop 是安全 no-op，故不先判断状态，防止漏停抢显存。
    """
    for other in models.values():
        if other is not models[keep]:
            mod.svc_stop(other)


def start(name: str, log=None, on_ready=None) -> bool:
    """启动模型（后台线程）：先停其它 → systemctl start → 轮询健康检查。

    log/on_ready 均在后台线程回调，UI 侧需自行 root.after 切主线程。
    返回 True 表示已发起启动（不代表已就绪）。
    """
    mod = _panel_module()
    models = list_models()
    if mod is None or name not in models:
        return False
    cfg = models[name]

    def _worker():
        _log(log, "[本地模型] 启动 %s（先停其它模型）…" % name)
        _stop_others(mod, models, name)
        rc = mod.svc_start(cfg)
        if rc != 0:
            _log(log, "[本地模型] 启动失败（rc=%s）：Windows 请确认 llama-server "
                 "在 PATH，Linux 请查 journalctl --user -u %s" % (rc, cfg["service"]))
            return
        _log(log, "[本地模型] 服务已启动，等待模型加载…")
        timeout_s = cfg.get("load_timeout_s", 300)
        poll_s = cfg.get("load_poll_s", 5)
        waited = 0
        while waited < timeout_s:
            healthy, detail = mod.health_check(
                cfg["health_url"], timeout=cfg.get("health_timeout", 3))
            if healthy:
                _log(log, "[本地模型] %s 已就绪（%s，端口 %s）"
                     % (name, detail, cfg["port"]))
                if on_ready:
                    on_ready(name)
                return
            state = mod.service_status(cfg["service"])
            if state in ("failed", "inactive"):
                _log(log, "[本地模型] 服务异常退出（%s），请看 journalctl --user -u %s"
                     % (state, cfg["service"]))
                return
            threading.Event().wait(poll_s)
            waited += poll_s
        _log(log, "[本地模型] 等待超时（%ss），服务仍在加载或异常" % timeout_s)

    threading.Thread(target=_worker, daemon=True).start()
    return True


def restart(name: str, log=None, on_ready=None) -> bool:
    """重启模型（后台线程）。"""
    mod = _panel_module()
    models = list_models()
    if mod is None or name not in models:
        return False
    stop(name)
    return start(name, log=log, on_ready=on_ready)


def _log(log, msg):
    if log:
        try:
            log(msg)
        except Exception:                       # noqa: BLE001
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 同步进 models.json
# ─────────────────────────────────────────────────────────────────────────────

def provider_id(cfg: dict) -> str:
    """本地模型的 provider id：按端口唯一（一个端口一个端点）。"""
    return "gpulocal-%s" % cfg["port"]


def model_id(cfg: dict) -> str:
    """模型 ID 取 systemd 服务名去掉 .service。"""
    svc = cfg["service"]
    # str.removesuffix 是 3.9+ API，这里手动等价实现（兼容 3.8）
    return svc[:-len(".service")] if svc.endswith(".service") else svc


def sync_to_config() -> list:
    """把 gpulocal 注册表同步进 models.json，返回同步后的 provider id 列表。

    规则：base_url 指向 127.0.0.1:<注册表端口> 的本地 provider 整体重建为
    规范条目（因此旧的/改名后的本地模型自动清理），云端 provider 不动；
    default 失效时改为第一个本地模型。
    """
    import config
    models = list_models()
    if not models:
        return []
    ports = {cfg["port"] for cfg in models.values()}

    def _is_local(p: dict) -> bool:
        url = p.get("base_url", "")
        return any("127.0.0.1:%s/" % port in url or
                   "localhost:%s/" % port in url for port in ports)

    data = config._load_models_data()
    providers = [p for p in data.get("providers", []) if not _is_local(p)]

    new_ids = []
    for name, cfg in models.items():
        pid = provider_id(cfg)
        new_ids.append(pid)
        providers.append({
            "id": pid,
            "name": "本地 GPU · %s" % name,
            "base_url": cfg["endpoint"],
            "api_key": "local-noauth",
            "models": [{
                "id": model_id(cfg),
                "name": name,
                # 注册表带 mmproj 即支持图片输入
                "vision": bool(cfg.get("mmproj")),
            }],
        })

    data["providers"] = providers
    # default 指向已不存在的 key → 切到第一个本地模型
    valid_keys = {f"{p['id']}/{m['id']}"
                  for p in providers for m in p.get("models", [])}
    if data.get("default", "") not in valid_keys:
        first = models[next(iter(models))]
        data["default"] = "%s/%s" % (provider_id(first), model_id(first))
    config._save_models_data(data)
    return new_ids


def key_of(name: str) -> str:
    """gpulocal 显示名 → qwen-coder 模型 key（provider_id/model_id）。"""
    models = list_models()
    cfg = models.get(name)
    if cfg is None:
        return ""
    return "%s/%s" % (provider_id(cfg), model_id(cfg))


def open_panel():
    """在新进程里打开 gpulocal 图形面板（两边操作同一批 systemd 服务）。"""
    import subprocess, sys
    if not os.path.exists(_PANEL_PATH):
        return False
    subprocess.Popen([sys.executable, _PANEL_PATH], cwd=_GPULOCAL_DIR,
                     start_new_session=True)
    return True
