# -*- coding: utf-8 -*-
"""视频生成：多供应商异步任务 API（stdlib urllib）。

支持两种端点（按 base_url/model 自动识别）：
- 火山方舟 Ark（doubao-seedance 系列）：
    POST {base}/contents/generations/tasks   建任务（content 数组：文本+首帧图）
    GET  {base}/contents/generations/tasks/{id}  轮询
    succeeded 后从 content.video_url 下载；参数以 --resolution/--dur 等
    文本指令写入 prompt 头部，--audio true 启用原生音频（台词口型）。
- Agnes 兼容（默认）：
    POST {base}/videos                       建任务（文生视频/图生视频）
    GET  {root}/agnesapi?video_id=<ID>       轮询（root = base 去掉尾部 /v1；
                                              旧路径 GET {base}/videos/<ID> 兜底）
    status=completed 后从 metadata.url 下载 MP4。

服务来源（优先级从高到低）：
1. 环境变量 LAS_VIDEO_BASE_URL / LAS_VIDEO_MODEL / LAS_VIDEO_API_KEY
2. 供应商管理里带 "video_model" 字段且已填 API Key 的供应商（列表序取先）

失败抛 VidError（内部错误，工具层转为中文错误字符串）。
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request


class VidError(Exception):
    pass


_DEFAULT_SIZE = "1152x768"
_MAX_FRAMES = 441        # Agnes 上限；帧数须为 8n+1
_DEFAULT_SECONDS = 5.0
_DEFAULT_FPS = 24


def _service() -> dict:
    """当前生效的视频服务：env 优先，其次供应商配置。"""
    url = os.environ.get("LAS_VIDEO_BASE_URL", "").strip().rstrip("/")
    mdl = os.environ.get("LAS_VIDEO_MODEL", "").strip()
    if url and mdl:
        return {"base_url": url, "model": mdl,
                "api_key": os.environ.get("LAS_VIDEO_API_KEY", "").strip(),
                "provider_id": ""}
    try:
        import config
        return config.video_service()
    except Exception:                  # noqa: BLE001  config 异常时按未配置降级
        return {}


def available() -> bool:
    svc = _service()
    return bool(svc.get("base_url") and svc.get("model"))


def _root(base: str) -> str:
    """网关根地址：base 去掉尾部 /v1（轮询端点挂在根上）。"""
    b = base.rstrip("/")
    return b[:-3] if b.lower().endswith("/v1") else b


_RETRY_HTTP = (502, 503, 504)        # 网关瞬时过载：短退避
_RETRY_TIMES = 4                     # 含 429 限流：长退避


def _retry(fetch):
    """瞬时错误退避重试：429 限流等 20/40/60s；502/503/504 与连接错误等 4/8s。"""
    import urllib.error
    last = None
    for attempt in range(_RETRY_TIMES):
        if attempt:
            is_429 = (isinstance(last, urllib.error.HTTPError)
                      and last.code == 429)
            time.sleep(20 * attempt if is_429 else 4 * attempt)
        try:
            return fetch()
        except urllib.error.HTTPError as e:
            if e.code in _RETRY_HTTP or e.code == 429:
                last = e
                continue
            raise
        except (urllib.error.URLError, OSError) as e:
            last = e
            continue
    raise last


def _post(url: str, body: dict, api_key: str) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    return _retry(lambda: _read_json(urllib.request.urlopen(req, timeout=60)))


def _get(url: str, api_key: str = "") -> dict:
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    return _retry(lambda: _read_json(urllib.request.urlopen(req, timeout=60)))


def _read_json(resp) -> dict:
    with resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_id(data: dict) -> str:
    """从建任务响应里尽力取任务 ID（id / video_id / task_id，含嵌套 data）。"""
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    for src in (data, inner):
        for k in ("video_id", "task_id", "id"):
            v = str(src.get(k, "") or "").strip()
            if v:
                return v
    return ""


def _pick_url(data: dict) -> str:
    """从轮询响应里尽力取成片地址（metadata.url / url / 嵌套 data / 列表）。"""
    cands = [data.get("url")]
    md = data.get("metadata")
    if isinstance(md, dict):
        cands.append(md.get("url"))
    inner = data.get("data")
    if isinstance(inner, dict):
        cands.append(inner.get("url"))
        cands.append((inner.get("metadata") or {}).get("url")
                     if isinstance(inner.get("metadata"), dict) else "")
    for k in ("output", "videos", "video"):
        v = data.get(k)
        if isinstance(v, dict):
            cands.append(v.get("url"))
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            cands.append(v[0].get("url"))
    for c in cands:
        c = str(c or "").strip()
        if c.startswith(("http://", "https://")):
            return c
    return ""


def _frames(seconds: float, fps: int) -> int:
    """时长 → 帧数（8n+1，钳制到上限内）。"""
    try:
        sec = float(seconds) if seconds else _DEFAULT_SECONDS
    except (TypeError, ValueError):
        sec = _DEFAULT_SECONDS
    n = max(1, round(sec * fps / 8))
    return min(_MAX_FRAMES, 8 * n + 1)


def _parse_size(size: str) -> tuple[int, int]:
    m = f"{size or _DEFAULT_SIZE}".lower().split("x")
    try:
        return int(m[0]), int(m[1])
    except (ValueError, IndexError):
        return 1152, 768


def _is_ark(svc: dict) -> bool:
    """火山方舟 Ark 端点识别：模型名 doubao-* 或地址含 volces.com。"""
    return ("volces.com" in str(svc.get("base_url", ""))
            or str(svc.get("model", "")).startswith("doubao-"))


def _ark_flags(seconds: float) -> str:
    """Seedance 文本指令头：时长钳 4-15s、竖屏 9:16、关水印、开原生音频。"""
    try:
        dur = int(round(float(seconds))) if seconds else 5
    except (TypeError, ValueError):
        dur = 5
    dur = max(4, min(15, dur))
    return (f"--resolution 720p --ratio 9:16 --dur {dur} "
            "--fps 24 --watermark false --audio true")


def _ark_create(prompt: str, image: str, seconds: float, svc: dict) -> str:
    content = [{"type": "text", "text": _ark_flags(seconds) + "\n" + prompt}]
    if image:
        content.append({"type": "image_url", "image_url": {"url": image}})
    data = _post(f"{svc['base_url']}/contents/generations/tasks",
                 {"model": svc["model"], "content": content},
                 svc.get("api_key", ""))
    vid = str(data.get("id", "") or "").strip()
    if not vid:
        raise VidError(f"Ark 未返回任务 ID：{json.dumps(data, ensure_ascii=False)[:300]}")
    return vid


def _ark_query(video_id: str, svc: dict) -> dict:
    data = _get(f"{svc['base_url']}/contents/generations/tasks/{video_id}",
                svc.get("api_key", ""))
    status = str(data.get("status", "") or "").strip().lower()
    err = ""
    e = data.get("error")
    if isinstance(e, dict):
        err = str(e.get("message") or e.get("code") or "")
    elif e:
        err = str(e)
    url = ""
    c = data.get("content")
    if isinstance(c, dict):
        url = str(c.get("video_url", "") or "").strip()
    if status == "succeeded" and url:
        return {"status": "completed", "url": url, "error": ""}
    if status == "failed":
        return {"status": "failed", "url": "", "error": err or "服务端未给出原因"}
    return {"status": status or "unknown", "url": "", "error": err}


def create(prompt: str, image: str = "", size: str = "",
           seconds: float = 0, frame_rate: int = _DEFAULT_FPS) -> str:
    """建任务，返回任务 ID；失败抛 VidError。"""
    svc = _service()
    if not (svc.get("base_url") and svc.get("model")):
        raise VidError("未配置视频生成服务（LAS_VIDEO_BASE_URL / LAS_VIDEO_MODEL，"
                       "或在供应商管理里给视频供应商填 API Key）")
    if _is_ark(svc):
        try:
            return _ark_create(prompt, image, seconds, svc)
        except VidError:
            raise
        except Exception as e:         # noqa: BLE001
            raise VidError(f"视频任务创建失败：{e}") from e
    w, h = _parse_size(size)
    body = {"model": svc["model"], "prompt": prompt,
            "width": w, "height": h,
            "num_frames": _frames(seconds, frame_rate),
            "frame_rate": frame_rate}
    if image:
        body["image"] = image          # 首帧图 URL（图生视频，一致性由关键帧传导）
        body["mode"] = "ti2vid"
    try:
        data = _post(f"{svc['base_url']}/videos", body, svc.get("api_key", ""))
    except Exception as e:             # noqa: BLE001
        raise VidError(f"视频任务创建失败：{e}") from e
    vid = _pick_id(data)
    if not vid:
        raise VidError(f"视频接口未返回任务 ID：{json.dumps(data, ensure_ascii=False)[:300]}")
    return vid


def query(video_id: str) -> dict:
    """查询任务状态：{"status","url","error"}（status 统一小写）。"""
    svc = _service()
    if not svc.get("base_url"):
        raise VidError("未配置视频生成服务")
    if _is_ark(svc):
        try:
            return _ark_query(video_id, svc)
        except Exception as e:         # noqa: BLE001
            raise VidError(f"视频任务查询失败：{e}") from e
    q = urllib.parse.urlencode({"video_id": video_id})
    url = f"{_root(svc['base_url'])}/agnesapi?{q}"
    try:
        try:
            data = _get(url, svc.get("api_key", ""))
        except Exception:              # noqa: BLE001  旧路径兜底
            data = _get(f"{svc['base_url']}/videos/{video_id}",
                        svc.get("api_key", ""))
    except Exception as e:             # noqa: BLE001
        raise VidError(f"视频任务查询失败：{e}") from e
    status = ""
    for src in (data, data.get("data") if isinstance(data.get("data"), dict) else {}):
        status = str(src.get("status", "") or "").strip().lower()
        if status:
            break
    err = ""
    for src in (data, data.get("data") if isinstance(data.get("data"), dict) else {}):
        err = str(src.get("error") or src.get("message") or "").strip()
        if err:
            break
    return {"status": status or "unknown", "url": _pick_url(data), "error": err}


def download(url: str, out_path: str) -> str:
    """下载成片到本地，返回路径。

    先写 .part 临时文件、成功后原子改名：中途失败不留下半截 mp4
    （否则重跑会被「文件存在即跳过」误判为已完成，坏片段还会被
    concat 拼进整集）。
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp = out_path + ".part"
    try:
        with urllib.request.urlopen(url, timeout=300) as r:
            with open(tmp, "wb") as f:
                f.write(r.read())
        os.replace(tmp, out_path)
    except Exception as e:             # noqa: BLE001
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise VidError(f"视频下载失败：{e}") from e
    return out_path


def generate(prompt: str, out_path: str, image: str = "", size: str = "",
             seconds: float = 0, timeout: float = 150.0,
             poll: float = 5.0) -> str:
    """端到端：建任务 → 轮询 → 下载 MP4。超时抛 VidError（附任务 ID 可续查）。"""
    vid = create(prompt, image=image, size=size, seconds=seconds)
    deadline = time.monotonic() + max(10.0, timeout)
    while time.monotonic() < deadline:
        st = query(vid)
        if st["status"] == "failed":
            raise VidError(f"视频生成失败：{st['error'] or '服务端未给出原因'}（任务 {vid}）")
        if st["status"] == "completed" and st["url"]:
            return download(st["url"], out_path)
        time.sleep(max(1.0, poll))
    raise VidError(f"视频生成超时（>{int(timeout)}s）：任务 {vid} 仍在进行，"
                   f"稍后可用 video_status 工具查询并下载。")
