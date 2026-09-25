# -*- coding: utf-8 -*-
"""视频生成：多供应商异步任务 API（stdlib urllib）。

支持的供应商（按 base_url/model 自动识别）：
- 火山方舟 Ark（doubao-seedance 系列）：
    POST {base}/contents/generations/tasks   建任务（content 数组：文本+首帧图）
    GET  {base}/contents/generations/tasks/{id}  轮询
    succeeded 后从 content.video_url 下载；参数以 --resolution/--dur 等
    文本指令写入 prompt 头部，--audio true 启用原生音频（台词口型）。
- MiniMax H3（MiniMax/MiniMax）：
    POST {base}/video_generation             建任务（model + prompt + duration + resolution + image_url?）
    GET  {base}/video_generation/{id}        轮询；返回 status / file_url
- 阿里百炼 Wan 3.0（dashscope / bailian / aliyuncs / wan-* 模型）：
    POST {base}/api/v1/services/aigc/video-generation/video-synthesis
                                             建任务（input.media[] + parameters.duration/resolution）
    GET  {base}/api/v1/tasks/{id}            轮询；返回 task_status / results[].url
- Agnes 兼容（默认）：
    POST {base}/videos                       建任务（文生视频/图生视频）
    GET  {root}/agnesapi?video_id=<ID>       轮询（root = base 去掉尾部 /v1；
                                              旧路径 GET {base}/videos/<ID> 兜底）
    status=completed 后从 metadata.url 下载 MP4。

服务来源（优先级从高到低）：
1. preferred_provider_id（UI 顶栏 Combobox 当前选择）
2. globals.video_provider（/novel drama config 切换）
3. 环境变量 LAS_VIDEO_BASE_URL / LAS_VIDEO_MODEL / LAS_VIDEO_API_KEY
4. 供应商管理里带 "video_model" 字段且已填 API Key 的供应商（列表序取先）

分辨率按供应商分级（_PROVIDER_RESOLUTION_TIERS）：
- Ark/Seedance: "480p" / "720p"
- MiniMax H3: "768P" / "2K"
- Wan 3.0: "480P" / "720P" / "1080P"
- Agnes 兼容: "WxH" 像素串（1152x768 / 1280x720 等）

失败抛 VidError（内部错误，工具层转为中文错误字符串）。
错误分类：classify_error() 把错误字符串拆成 moderation / rate_limit / auth / server / other，
UI 顶栏可据此提示「切模型重试」（moderation）等。
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

# 每供应商原生分辨率档位（顶栏 Combobox 选项来源；与 _ark_flags 等旗标对应）
_PROVIDER_RESOLUTION_TIERS = {
    "ark":     ("480p", "720p"),
    "minimax": ("768P", "2K"),
    "bailian": ("480P", "720P", "1080P"),
    "agnes":   ("1152x768", "1280x720", "720x1280", "1024x1024"),
}


def provider_resolution_tiers(provider_kind: str) -> tuple:
    """某 provider 的分辨率档位元组（provider_kind ∈ ark/minimax/bailian/agnes）。"""
    return _PROVIDER_RESOLUTION_TIERS.get(
        (provider_kind or "").lower(),
        _PROVIDER_RESOLUTION_TIERS["agnes"])


def _service(preferred_provider_id: str = "") -> dict:
    """当前生效的视频服务。

    preferred_provider_id 非空 → 先按 provider 找；其次 globals.video_provider；
    再其次环境变量；最后供应商列表序第一个。
    """
    # 1. UI 顶栏 / 调用方指定的 provider 优先
    if preferred_provider_id:
        try:
            import config
            for s in config.video_services():
                if s.get("provider_id") == preferred_provider_id and s.get("base_url"):
                    return s
        except Exception:                  # noqa: BLE001
            pass
    # 2. 环境变量
    url = os.environ.get("LAS_VIDEO_BASE_URL", "").strip().rstrip("/")
    mdl = os.environ.get("LAS_VIDEO_MODEL", "").strip()
    if url and mdl:
        return {"base_url": url, "model": mdl,
                "api_key": os.environ.get("LAS_VIDEO_API_KEY", "").strip(),
                "provider_id": ""}
    # 3. config 兜底（globals.video_provider 优先；再否则第一个）
    try:
        import config
        return config.video_service()
    except Exception:                  # noqa: BLE001  config 异常时按未配置降级
        return {}


def _provider_kind(svc: dict) -> str:
    """当前 svc 属于哪家供应商。返回 ark / minimax / bailian / agnes。"""
    if _is_ark(svc):
        return "ark"
    if _is_minimax(svc):
        return "minimax"
    if _is_bailian(svc):
        return "bailian"
    return "agnes"


def classify_error(err_str: str) -> dict:
    """把视频服务返回的错误字符串分类。

    返回 {"category": str, "hint": str|None}：
    - moderation: 内容审核/敏感/人脸等，UI 应提示切模型重试
    - rate_limit: 请求被限流
    - auth: API Key 失效或缺失
    - server: 服务端 5xx 等临时异常
    - other: 其它（默认）
    """
    s = (err_str or "").lower()
    if any(k in s for k in ("sensitive", "moderation", "policy", "safety",
                            "nsfw", "r18", "compliance",
                            "审核", "敏感", "违规", "真人", "人脸")):
        return {"category": "moderation",
                "hint": "内容疑似敏感/真人脸，模型拒绝生成"}
    if any(k in s for k in ("rate", "limit", "quota", "throttle",
                            "限流", "频率", "超限")):
        return {"category": "rate_limit", "hint": "请求被限流，请稍后重试"}
    if any(k in s for k in ("auth", "apikey", "api_key", "unauthorized",
                            "forbidden", "401", "403",
                            "鉴权", "未授权", "密钥")):
        return {"category": "auth", "hint": "API Key 失效或缺失"}
    if any(k in s for k in ("500", "502", "503", "504", "server", "internal",
                            "服务端", "服务异常", "网关")):
        return {"category": "server", "hint": "服务暂时异常，可稍后重试"}
    return {"category": "other", "hint": None}


def available(svc: dict | None = None) -> bool:
    """视频服务是否可用（base_url + model 非空）。

    svc 为 None 时读 module-level _service()；config._media_service 在 auto
    探测模式下注入候选供应商的 dict 来逐个 ping。
    """
    if svc is None:
        svc = _service()
    return bool(svc.get("base_url") and svc.get("model"))


def _root(base: str) -> str:
    """网关根地址：base 去掉尾部 /v1（轮询端点挂在根上）。"""
    b = base.rstrip("/")
    return b[:-3] if b.lower().endswith("/v1") else b


_RETRY_HTTP = (502, 503, 504)        # 网关瞬时过载：短退避
_RETRY_TIMES = 4                     # 含 429 限流：长退避


def _retry(fetch):
    """瞬时错误退避重试：优先按服务端 Retry-After 头等待（钳 0-120s），
    无头时 429 限流等 20/40/60s；502/503/504 与连接错误等 4/8s。"""
    import urllib.error
    last = None
    retry_after = 0.0
    for attempt in range(_RETRY_TIMES):
        if attempt:
            is_429 = (isinstance(last, urllib.error.HTTPError)
                      and last.code == 429)
            time.sleep(retry_after or (20 * attempt if is_429
                                       else 4 * attempt))
        retry_after = 0.0
        try:
            return fetch()
        except urllib.error.HTTPError as e:
            if e.code in _RETRY_HTTP or e.code == 429:
                last = e
                # 服务端明确给出等待秒数时照办（如 Seedance 队列满），
                # 比固定梯子对双方都省；非数字/HTTP 日期格式按无头处理
                hdrs = getattr(e, "headers", None)
                try:
                    retry_after = float((hdrs or {}).get("Retry-After") or 0)
                except (TypeError, ValueError):
                    retry_after = 0.0
                retry_after = min(max(retry_after, 0.0), 120.0)
                continue
            raise
        except (urllib.error.URLError, OSError) as e:
            last = e
            continue
    raise last


def _err_text(e: Exception) -> str:
    """异常 → 带响应体的短文本：4xx/5xx 的真实原因（审核/配额/过载）都在
    body 里，只报 HTTP Error 503 没法诊断。"""
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300].strip()
        except Exception:              # noqa: BLE001
            pass
        return f"HTTP {e.code}" + (f"｜{detail}" if detail else "")
    return str(e)


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


def _is_minimax(svc: dict) -> bool:
    """MiniMax H3 端点识别：base_url 含 minimaxi.com 或模型名以 MiniMax- 开头。"""
    b = str(svc.get("base_url", "")).lower()
    m = str(svc.get("model", "")).lower()
    return ("minimaxi.com" in b or "MiniMax" in b or "MiniMax" in b
            or m.startswith("MiniMax-") or m.startswith("MiniMax-"))


def _is_bailian(svc: dict) -> bool:
    """阿里百炼 Wan 3.0 端点识别：base_url 含 bailian/dashscope/aliyun，或模型名 wan-* 前缀。"""
    b = str(svc.get("base_url", "")).lower()
    m = str(svc.get("model", "")).lower()
    return any(k in b for k in ("bailian", "dashscope", "aliyuncs", "aliyun")) \
        or m.startswith("wan-") or m.startswith("wan2")


def _ark_flags(seconds: float, resolution: str = "", ratio: str = "") -> str:
    """Seedance 文本指令头：时长钳 4-15s、关水印、开原生音频。

    resolution 非空（480p/720p/1080p）时优先用之；空则走 720p 默认。
    ratio 非空（9:16/16:9/1:1/4:3/3:4）时优先用之；空则走竖屏 9:16 默认。
    """
    try:
        dur = int(round(float(seconds))) if seconds else 5
    except (TypeError, ValueError):
        dur = 5
    dur = max(4, min(15, dur))
    res = (resolution or "720p").strip().lower()
    if res not in ("480p", "720p", "1080p"):
        res = "720p"
    r = (ratio or "9:16").strip()
    if r not in ("9:16", "16:9", "1:1", "4:3", "3:4"):
        r = "9:16"
    return (f"--resolution {res} --ratio {r} --dur {dur} "
            "--fps 24 --watermark false --audio true")


def _ark_create(prompt: str, image: str, seconds: float, svc: dict,
                resolution: str = "", ratio: str = "") -> str:
    content = [{"type": "text",
                "text": _ark_flags(seconds, resolution, ratio) + "\n" + prompt}]
    if image:
        content.append({"type": "image_url", "image_url": {"url": image}})
    data = _post(f"{svc['base_url']}/contents/generations/tasks",
                 {"model": svc["model"], "content": content},
                 svc.get("api_key", ""))
    vid = str(data.get("id", "") or "").strip()
    if not vid:
        raise VidError(f"Ark 未返回任务 ID：{json.dumps(data, ensure_ascii=False)[:300]}")
    return vid


def _minimax_create(prompt: str, image: str, seconds: float, svc: dict,
                    resolution: str = "") -> str:
    """MiniMax H3 建任务。resolution 默认 768P，可选 2K。"""
    try:
        dur = int(round(float(seconds))) if seconds else 5
    except (TypeError, ValueError):
        dur = 5
    dur = max(2, min(15, dur))
    body = {"model": svc["model"], "prompt": prompt,
            "duration": dur,
            "resolution": (resolution or "768P").strip()}
    if image:
        body["image_url"] = image
    base = svc["base_url"].rstrip("/")
    data = _post(f"{base}/video_generation", body, svc.get("api_key", ""))
    return _pick_id(data)


def _minimax_query(video_id: str, svc: dict) -> dict:
    """MiniMax H3 轮询。"""
    base = svc["base_url"].rstrip("/")
    data = _get(f"{base}/video_generation/{video_id}",
                svc.get("api_key", ""))
    status = str(data.get("status", "") or "").strip().lower()
    err = ""
    e = data.get("error")
    if isinstance(e, dict):
        err = str(e.get("message") or e.get("code") or "")
    elif e:
        err = str(e)
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    url = str(inner.get("file_url") or data.get("file_url") or "").strip()
    if status == "succeeded" and url:
        return {"status": "completed", "url": url, "error": ""}
    if status in ("failed", "rejected", "cancelled"):
        return {"status": "failed", "url": "", "error": err or "MiniMax 未给出原因"}
    return {"status": status or "unknown", "url": "", "error": err}


def _bailian_create(prompt: str, image: str, seconds: float, svc: dict,
                    resolution: str = "") -> str:
    """阿里百炼 Wan 3.0 建任务（DashScope 异步视频合成）。"""
    try:
        dur = int(round(float(seconds))) if seconds else 5
    except (TypeError, ValueError):
        dur = 5
    dur = max(3, min(10, dur))         # Wan 3.0 时长档位 3/5/10
    res = (resolution or "720P").strip().upper()
    if res not in ("480P", "720P", "1080P"):
        res = "720P"
    media = []
    if image:
        media.append({"type": "image", "value": image})
    body = {"model": svc["model"],
            "input": {"prompt": prompt, **({"media": media} if media else {})},
            "parameters": {"duration": dur, "resolution": res,
                           "prompt_extend": False}}
    base = svc["base_url"].rstrip("/")
    data = _post(f"{base}/api/v1/services/aigc/video-generation/video-synthesis",
                 body, svc.get("api_key", ""))
    inner = data.get("output") if isinstance(data.get("output"), dict) else data
    return _pick_id(inner) or _pick_id(data)


def _bailian_query(video_id: str, svc: dict) -> dict:
    """阿里百炼轮询（/api/v1/tasks/{id}）。"""
    base = svc["base_url"].rstrip("/")
    data = _get(f"{base}/api/v1/tasks/{video_id}", svc.get("api_key", ""))
    inner = data.get("output") if isinstance(data.get("output"), dict) else data
    status = str(inner.get("task_status") or data.get("task_status") or ""
                 ).strip().lower()
    if status == "succeeded":
        url = ""
        results = inner.get("results") or []
        if isinstance(results, list) and results:
            url = str(results[0].get("url") or "").strip()
        return {"status": "completed" if url else "unknown",
                "url": url, "error": "" if url else "结果为空"}
    if status in ("failed", "canceled"):
        err = (inner.get("message") or data.get("message") or
               inner.get("code") or data.get("code") or "")
        return {"status": "failed", "url": "", "error": str(err).strip()}
    return {"status": status or "pending", "url": "", "error": ""}


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


def create(prompt: str, image: str = "", size: str = "", resolution: str = "",
           ratio: str = "", seconds: float = 0, frame_rate: int = _DEFAULT_FPS,
           preferred_provider_id: str = "") -> str:
    """建任务，返回任务 ID；失败抛 VidError。

    size：Agnes 兼容模式像素串（"1152x768"），新代码走 resolution 即可。
    resolution：按当前 provider 原生档位传入（ark: 480p/720p、minimax: 768P/2K、
                bailian: 480P/720P/1080P）。Agnes 兼容模式下等同 size。
    ratio：画幅，仅 Ark（Seedance）消费（9:16/16:9/1:1/4:3/3:4）；
           空 = 竖屏 9:16。其它 provider 忽略（画幅由 size 像素决定）。
    preferred_provider_id：UI 顶栏当前选中的 provider（覆盖 globals/env）。
    """
    svc = _service(preferred_provider_id=preferred_provider_id)
    if not (svc.get("base_url") and svc.get("model")):
        raise VidError("未配置视频生成服务（LAS_VIDEO_BASE_URL / LAS_VIDEO_MODEL，"
                       "或在供应商管理里给视频供应商填 API Key）")
    res = (resolution or "").strip()
    if _is_ark(svc):
        try:
            return _ark_create(prompt, image, seconds, svc, res, ratio)
        except VidError:
            raise
        except Exception as e:         # noqa: BLE001
            raise VidError(f"视频任务创建失败：{_err_text(e)}") from e
    if _is_minimax(svc):
        try:
            return _minimax_create(prompt, image, seconds, svc, res)
        except VidError:
            raise
        except Exception as e:         # noqa: BLE001
            raise VidError(f"视频任务创建失败：{_err_text(e)}") from e
    if _is_bailian(svc):
        try:
            return _bailian_create(prompt, image, seconds, svc, res)
        except VidError:
            raise
        except Exception as e:         # noqa: BLE001
            raise VidError(f"视频任务创建失败：{_err_text(e)}") from e
    w, h = _parse_size(res or size)
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
        raise VidError(f"视频任务创建失败：{_err_text(e)}") from e
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
    if _is_minimax(svc):
        try:
            return _minimax_query(video_id, svc)
        except Exception as e:         # noqa: BLE001
            raise VidError(f"视频任务查询失败：{e}") from e
    if _is_bailian(svc):
        try:
            return _bailian_query(video_id, svc)
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
             resolution: str = "", ratio: str = "", seconds: float = 0,
             timeout: float = 150.0,
             poll: float = 5.0, preferred_provider_id: str = "") -> str:
    """端到端：建任务 → 轮询 → 下载 MP4。超时抛 VidError（附任务 ID 可续查）。

    resolution：与 create() 同义，按当前 provider 原生档位传入。
    ratio：与 create() 同义（仅 Ark 消费；空 = 9:16 竖屏）。
    preferred_provider_id：与 create() 同义，UI 顶栏 provider 选择优先。
    """
    vid = create(prompt, image=image, size=size, resolution=resolution,
                 ratio=ratio, seconds=seconds,
                 preferred_provider_id=preferred_provider_id)
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


def available_providers() -> list:
    """枚举当前可用的视频 provider 列表（[{provider_id, name, base_url, model, has_key}]）。

    用于 UI 顶栏下拉；供方未填 api_key 时仍列出但 has_key=False，
    让用户看到「未配置」状态而不是默默消失。
    """
    out = []
    try:
        import config
        for s in config.video_services():
            out.append({
                "provider_id": s.get("provider_id", ""),
                "name": s.get("name", s.get("provider_id", "")),
                "base_url": s.get("base_url", ""),
                "model": s.get("model", ""),
                "has_key": bool(s.get("api_key")),
                "kind": _provider_kind(s),
            })
    except Exception:                  # noqa: BLE001
        pass
    # env 直配的也算一项
    env_url = os.environ.get("LAS_VIDEO_BASE_URL", "").strip().rstrip("/")
    env_model = os.environ.get("LAS_VIDEO_MODEL", "").strip()
    if env_url and env_model:
        out.insert(0, {"provider_id": "", "name": "环境变量",
                       "base_url": env_url, "model": env_model,
                       "has_key": bool(os.environ.get("LAS_VIDEO_API_KEY")),
                       "kind": "agnes"})
    return out
