# -*- coding: utf-8 -*-
"""图像生成：OpenAI 兼容 /images/generations（stdlib urllib）。

环境变量（均可选，未配置 available()=False，业务侧明确降级）：
- LAS_IMAGE_BASE_URL   如 https://api.openai.com/v1 或自建 SD/ComfyUI 网关
- LAS_IMAGE_MODEL      图像模型（如 gpt-image-1 / sd-xll）
- LAS_IMAGE_API_KEY    鉴权（本地网关可空）
- LAS_IMAGE_SIZE       默认 1024x1024

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


def base_url() -> str:
    return os.environ.get("LAS_IMAGE_BASE_URL", "").strip().rstrip("/")


def model() -> str:
    return os.environ.get("LAS_IMAGE_MODEL", "")


def api_key() -> str:
    return os.environ.get("LAS_IMAGE_API_KEY", "")


def default_size() -> str:
    return os.environ.get("LAS_IMAGE_SIZE", "1024x1024")


def available() -> bool:
    return bool(base_url() and model())


def generate(prompt: str, out_path: str, size: str = "") -> str:
    """生成一张图并保存为 PNG；失败抛 ImgError。返回输出路径。"""
    if not available():
        raise ImgError("未配置图像生成服务（LAS_IMAGE_BASE_URL / LAS_IMAGE_MODEL）")
    body = {"model": model(), "prompt": prompt, "n": 1,
            "size": size or default_size()}
    req = urllib.request.Request(f"{base_url()}/images/generations",
                                 data=json.dumps(body).encode("utf-8"),
                                 method="POST")
    req.add_header("Content-Type", "application/json")
    if api_key():
        req.add_header("Authorization", f"Bearer {api_key()}")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode("utf-8"))
        item = (data.get("data") or [{}])[0]
    except Exception as e:             # noqa: BLE001
        raise ImgError(f"图像生成请求失败：{e}") from e
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if item.get("b64_json"):
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(item["b64_json"]))
        return out_path
    if item.get("url"):
        try:
            with urllib.request.urlopen(item["url"], timeout=120) as r:
                with open(out_path, "wb") as f:
                    f.write(r.read())
            return out_path
        except Exception as e:         # noqa: BLE001
            raise ImgError(f"图像下载失败：{e}") from e
    raise ImgError("图像接口未返回 b64_json 或 url")
