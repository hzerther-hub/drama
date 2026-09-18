# -*- coding: utf-8 -*-
"""图像生成：云端 OpenAI 兼容网关 + 本地 ComfyUI / SD-WebUI（stdlib urllib）。

服务来源（优先级从高到低）：
1. 环境变量 LAS_IMAGE_BASE_URL / LAS_IMAGE_MODEL / LAS_IMAGE_API_KEY
   （本地 SD/ComfyUI 网关等场景，key 可空）
2. 供应商管理里带 "image_model" 字段且已填 API Key 的供应商
   （Agnes / 商汤日日新等 OpenAI 兼容网关，面板填 key 即激活）

- LAS_IMAGE_SIZE   默认 1024x1024（仅环境变量方式使用）

支持 b64_json 与 url 两种返回（url 自动下载）。未配置时 available()=False，
调用方给出明确提示而不是静默失败。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request


class ImgError(Exception):
    pass


def _service() -> dict:
    """当前生效的图像服务：env 优先，其次供应商配置。"""
    url = os.environ.get("LAS_IMAGE_BASE_URL", "").strip().rstrip("/")
    mdl = os.environ.get("LAS_IMAGE_MODEL", "").strip()
    if url:
        # 本地后端（ComfyUI / SD-WebUI）不需要 model：出图模型由工作流或
        # 引擎自身决定；model 仅云端 OpenAI 兼容网关必填。
        return {"base_url": url, "model": mdl,
                "api_key": os.environ.get("LAS_IMAGE_API_KEY", "").strip(),
                "provider_id": "",
                "kind": os.environ.get("LAS_IMAGE_KIND", "").strip().lower()
                        or "auto"}
    try:
        import config
        return config.image_service()
    except Exception:                  # noqa: BLE001  config 异常时按未配置降级
        return {}


def base_url() -> str:
    return _service().get("base_url", "")


def model() -> str:
    return _service().get("model", "")


def api_key() -> str:
    return _service().get("api_key", "")


def default_size() -> str:
    return os.environ.get("LAS_IMAGE_SIZE", "1024x1024")


def available() -> bool:
    """图像服务是否可用。本地后端（ComfyUI / SD-WebUI）不需要 model 字段。"""
    svc = _service()
    if not svc.get("base_url"):
        return False
    if kind_of(svc) in ("comfyui", "a1111"):
        return True
    return bool(svc.get("model"))


def data_uri(path: str) -> str:
    """本地图片 → data:image/png;base64,...（Agnes 图生图参考图格式）。"""
    import base64 as _b64
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "webp": "webp"}.get(ext, "png")
    with open(path, "rb") as f:
        raw = f.read()
    return f"data:image/{mime};base64,{_b64.b64encode(raw).decode()}"


def _retry(fetch):
    """瞬时错误退避重试：429 限流等 20/40/60s；502/503/504 与连接错误等 4/8s。"""
    import time as _time
    import urllib.error
    last = None
    for attempt in range(4):
        if attempt:
            is_429 = (isinstance(last, urllib.error.HTTPError)
                      and last.code == 429)
            _time.sleep(20 * attempt if is_429 else 4 * attempt)
        try:
            return fetch()
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504, 429):
                last = e
                continue
            raise
        except (urllib.error.URLError, OSError) as e:
            last = e
            continue
    raise last


# ---------------- 多后端：ComfyUI 原生 / SD-WebUI(A1111) / OpenAI 兼容 ----------------
# 本地后端（ComfyUI 8188、SD-WebUI 7860）与云端网关协议完全不同：
#   云端   POST {base}/images/generations   （本文档下方原路径）
#   ComfyUI POST {base}/prompt 提交工作流 → 轮询 /history → /view 取图
#   SD-WebUI POST {base}/sdapi/v1/txt2img 或 img2img（有参考图时自动切）
# 未显式指定 kind 时按特征端点探测一次并缓存。

_KIND_CACHE: dict = {}


def probe(base_url: str) -> str:
    """探测图像服务属于哪种协议（特征端点优先）。"""
    base = (base_url or "").rstrip("/")
    if not base:
        return ""
    for path, kind in (("/system_stats", "comfyui"),
                       ("/sdapi/v1/options", "a1111")):
        try:
            with urllib.request.urlopen(base + path, timeout=3) as r:
                if r.status == 200:
                    return kind
        except Exception:              # noqa: BLE001  探测失败继续试下一个
            continue
    return "openai"                    # 兜底：按 OpenAI 兼容形态处理


def kind_of(svc: dict) -> str:
    """服务实际使用的后端协议（显式声明优先，否则探测一次并缓存）。"""
    k = (svc.get("kind") or "").lower()
    if k and k != "auto":
        return k
    if svc.get("provider_id"):          # 供应商配置 = 云端 OpenAI 兼容网关
        return "openai"
    base = svc.get("base_url") or ""
    hit = _KIND_CACHE.get(base)
    if hit is None:
        hit = probe(base)
        _KIND_CACHE[base] = hit
    return hit


def _dims(size: str = "", ratio: str = "") -> tuple:
    """解析目标像素宽高：'1K'/'1024x1024'/ratio '9:16' → (w, h)。

    仅本地后端需要显式宽高；云端走 size/ratio 字段由服务端解释。
    SD 系要求宽高为 8 的倍数，这里统一对齐。
    """
    w = h = 1024
    s = (size or "").strip().lower()
    if "x" in s:
        try:
            a, b = s.split("x", 1)
            w, h = int(a), int(b)
        except ValueError:
            pass
    elif s in ("1k", "1024"):
        w = h = 1024
    elif s in ("2k", "2048"):
        w = h = 2048
    r = (ratio or "").strip()
    if r and ":" in r:
        try:
            a, b = (float(x) for x in r.split(":", 1))
            if a > 0 and b > 0:
                base = max(w, h, 1024)
                if a >= b:                 # 横构图
                    w, h = int(base), int(round(base * b / a))
                else:                      # 竖构图（短剧/条漫）
                    h, w = int(base), int(round(base * a / b))
        except ValueError:
            pass
    w = max(256, (int(w) // 8) * 8)
    h = max(256, (int(h) // 8) * 8)
    return w, h


def _comfy_pick_ckpt(base: str) -> str:
    """取 ComfyUI 里可用的第一个 checkpoint（可用 LAS_IMAGE_CKPT 指定）。"""
    want = os.environ.get("LAS_IMAGE_CKPT", "").strip()
    if want:
        return want
    try:
        with urllib.request.urlopen(
                base + "/object_info/CheckpointLoaderSimple", timeout=8) as r:
            info = json.loads(r.read().decode("utf-8"))
        req = (info.get("CheckpointLoaderSimple", {})
               .get("input", {}).get("required", {})
               .get("ckpt_name", []))
        names = req[0] if req and isinstance(req[0], list) else []
        if names:
            return str(names[0])
    except Exception:                  # noqa: BLE001
        pass
    raise ImgError("ComfyUI 未找到可用 checkpoint（可用 LAS_IMAGE_CKPT 指定）")


def _comfy_workflow(ckpt: str, prompt: str, negative: str,
                    w: int, h: int, seed: int, prefix: str) -> dict:
    """标准 txt2img 工作流（ComfyUI API 格式：节点 id → {class_type, inputs}）。"""
    return {
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": negative or "lowres, bad anatomy, "
                         "extra fingers, watermark, text", "clip": ["4", 1]}},
        "3": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": 28, "cfg": 6.5,
                         "sampler_name": "dpmpp_2m", "scheduler": "karras",
                         "denoise": 1.0, "model": ["4", 0],
                         "positive": ["6", 0], "negative": ["7", 0],
                         "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def _comfy_generate(svc: dict, prompt: str, out_path: str,
                    size: str, ratio: str) -> tuple:
    """ComfyUI：提交工作流 → 轮询 history → /view 取图落盘。

    注：ComfyUI 参考图（角色一致性）需要 IPAdapter/ControlNet 等自定义节点，
    不在此硬编码；角色一致性靠提示词里的形象描述（cast 提供）。
    """
    import time as _time
    import urllib.parse
    base = svc["base_url"]
    w, h = _dims(size, ratio)
    ckpt = svc.get("model") or _comfy_pick_ckpt(base)
    cid = "las-%d" % int(_time.time() * 1000)
    wf = _comfy_workflow(ckpt, prompt, svc.get("negative", ""), w, h,
                         int(_time.time()) % (2 ** 31),
                         os.path.basename(os.path.splitext(out_path)[0]))
    body = json.dumps({"prompt": wf, "client_id": cid}).encode("utf-8")

    def _submit():
        req = urllib.request.Request(base + "/prompt", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    pid = (_retry(_submit) or {}).get("prompt_id")
    if not pid:
        raise ImgError("ComfyUI 未返回 prompt_id")
    deadline = _time.time() + 600              # 本地出图慢，给 10 分钟
    item = None
    while _time.time() < deadline:
        _time.sleep(1.5)
        try:
            with urllib.request.urlopen(f"{base}/history/{pid}",
                                        timeout=15) as r:
                hist = json.loads(r.read().decode("utf-8"))
        except Exception:              # noqa: BLE001  轮询期抖动不致命
            continue
        entry = hist.get(pid) or {}
        for node in (entry.get("outputs") or {}).values():
            imgs = node.get("images") or []
            if imgs:
                item = imgs[-1]
                break
        if item:
            break
        if (entry.get("status") or {}).get("status_str") == "error":
            raise ImgError(f"ComfyUI 出图失败：{str(entry.get('status'))[:200]}")
    if not item:
        raise ImgError("ComfyUI 出图超时（10 分钟内未返回图像）")
    qs = urllib.parse.urlencode({
        "filename": item.get("filename", ""),
        "subfolder": item.get("subfolder", ""),
        "type": item.get("type", "output")})
    with urllib.request.urlopen(f"{base}/view?{qs}", timeout=120) as r:
        raw = r.read()
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(raw)
    return out_path, ""


def _a1111_generate(svc: dict, prompt: str, out_path: str, size: str,
                    ratio: str, image_refs: list) -> tuple:
    """SD-WebUI：有参考图走 img2img（保持人物一致），否则 txt2img。"""
    base = svc["base_url"]
    w, h = _dims(size, ratio)
    body = {"prompt": prompt, "width": w, "height": h,
            "steps": 28, "cfg_scale": 6.5, "sampler_name": "DPM++ 2M Karras",
            "negative_prompt": "lowres, bad anatomy, extra fingers, "
                               "watermark, text"}
    path = "/sdapi/v1/txt2img"
    if image_refs:
        init = []
        for r in image_refs:
            if str(r).startswith("data:"):
                init.append(str(r).split(",", 1)[-1])
            else:
                try:
                    with open(r, "rb") as f:
                        init.append(base64.b64encode(f.read()).decode())
                except OSError:
                    continue
        if init:
            path = "/sdapi/v1/img2img"
            body["init_images"] = init[:3]
            body["denoising_strength"] = 0.55

    def _post():
        req = urllib.request.Request(
            base + path, data=json.dumps(body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        if svc.get("api_key"):
            req.add_header("Authorization", f"Bearer {svc['api_key']}")
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode("utf-8"))

    data = _retry(_post)
    imgs = data.get("images") or []
    if not imgs:
        raise ImgError("SD-WebUI 未返回图像")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(imgs[0]))
    return out_path, ""

def generate_ex(prompt: str, out_path: str, size: str = "", ratio: str = "",
                image_refs: list = None, want_url: bool = False) -> tuple:
    """增强生成：支持图生图/多图合成与 URL 回传。

    image_refs: 参考图（本地路径或 data URI）列表——多图合成保持人物/
    场景一致性（Agnes Image；商汤走同一 OpenAI 兼容形态时也适用）。
    want_url: True 时请求 response_format=url 并把远端 URL 一并返回
    （供 Agnes Video 的 image 参数做图生视频）。
    返回 (本地路径, 远端URL或"")；失败抛 ImgError。
    """
    svc = _service()
    if not svc.get("base_url"):
        raise ImgError("未配置图像生成服务（LAS_IMAGE_BASE_URL / LAS_IMAGE_MODEL，"
                       "或在供应商管理里给 Agnes / 商汤填 API Key）")
    _kind = kind_of(svc)
    if _kind == "comfyui":
        return _comfy_generate(svc, prompt, out_path, size, ratio)
    if _kind == "a1111":
        return _a1111_generate(svc, prompt, out_path, size, ratio, image_refs)
    if not svc.get("model"):
        raise ImgError("未配置图像模型（LAS_IMAGE_MODEL 或供应商的 image_model）")
    body = {"model": svc["model"], "prompt": prompt, "n": 1,
            "size": size or default_size()}
    extra = {}
    if ratio:
        extra["ratio"] = ratio
    if image_refs:
        extra["image"] = [r if r.startswith("data:") else data_uri(r)
                          for r in image_refs]
    if want_url:
        extra["response_format"] = "url"
    if extra:
        body["extra_body"] = extra

    def _do_post():
        req = urllib.request.Request(
            f"{svc['base_url']}/images/generations",
            data=json.dumps(body).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        if svc.get("api_key"):
            req.add_header("Authorization", f"Bearer {svc['api_key']}")
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        data = _retry(_do_post)
        item = (data.get("data") or [{}])[0]
    except Exception as e:             # noqa: BLE001
        raise ImgError(f"图像生成请求失败：{e}") from e
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    remote = str(item.get("url") or "").strip()
    if item.get("b64_json"):
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(item["b64_json"]))
        return out_path, remote
    if remote:
        try:
            with urllib.request.urlopen(remote, timeout=120) as r:
                with open(out_path, "wb") as f:
                    f.write(r.read())
            return out_path, remote
        except Exception as e:         # noqa: BLE001
            raise ImgError(f"图像下载失败：{e}") from e
    raise ImgError("图像接口未返回 b64_json 或 url")


def generate(prompt: str, out_path: str, size: str = "") -> str:
    """文生图兼容入口（publisher/封面等旧调用方）。"""
    return generate_ex(prompt, out_path, size=size)[0]
