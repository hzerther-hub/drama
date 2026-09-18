# -*- coding: utf-8 -*-
"""imggen.py：图像服务解析（env/供应商）+ 生成落盘（b64 与 url 两种返回）。"""

import base64
import json

import pytest

import imggen


class _Resp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self) -> bytes:
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _no_env(monkeypatch):
    for k in ("LAS_IMAGE_BASE_URL", "LAS_IMAGE_MODEL", "LAS_IMAGE_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_service_env_priority(monkeypatch):
    _no_env(monkeypatch)
    monkeypatch.setattr("config._load_models_data", lambda: {
        "providers": [{"id": "agnes", "base_url": "https://a.cn/v1",
                       "api_key": "sk-x", "image_model": "agnes-image"}]})
    monkeypatch.setenv("LAS_IMAGE_BASE_URL", "https://local:8188/v1")
    monkeypatch.setenv("LAS_IMAGE_MODEL", "sd-xl")
    svc = imggen._service()
    assert svc["base_url"] == "https://local:8188/v1"
    assert svc["model"] == "sd-xl"
    assert svc["provider_id"] == ""


def test_service_from_provider_requires_key(monkeypatch):
    _no_env(monkeypatch)
    data = {"providers": [
        {"id": "agnes", "base_url": "https://a.cn/v1", "api_key": "",
         "image_model": "agnes-image"},                      # 未填 key → 跳过
        {"id": "local", "base_url": "https://b.cn/v1",
         "api_key": "local-noauth", "image_model": "m"},     # 占位 key → 跳过
        {"id": "st", "base_url": "https://c.cn/v1", "api_key": "sk-ok",
         "image_model": "sensenova-u1.5-lite"},              # 有效 → 选中
    ]}
    monkeypatch.setattr("config._load_models_data", lambda: data)
    svc = imggen._service()
    assert svc["provider_id"] == "st"
    assert svc["model"] == "sensenova-u1.5-lite"
    assert imggen.available() is True


def test_service_unavailable(monkeypatch):
    _no_env(monkeypatch)
    monkeypatch.setattr("config._load_models_data",
                        lambda: {"providers": []})
    assert imggen.available() is False
    with pytest.raises(imggen.ImgError):
        imggen.generate("测试", "x/out.png")


def test_generate_b64(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    monkeypatch.setenv("LAS_IMAGE_BASE_URL", "https://a.cn/v1")
    monkeypatch.setenv("LAS_IMAGE_MODEL", "m")
    raw = b"\x89PNG-fake"
    body = {"data": [{"b64_json": base64.b64encode(raw).decode()}]}
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda req, timeout=0: _Resp(json.dumps(body).encode()))
    out = imggen.generate("一只猫", str(tmp_path / "cat.png"))
    assert out.endswith("cat.png")
    assert (tmp_path / "cat.png").read_bytes() == raw


def test_generate_url_download(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    monkeypatch.setenv("LAS_IMAGE_BASE_URL", "https://a.cn/v1")
    monkeypatch.setenv("LAS_IMAGE_MODEL", "m")

    def fake_urlopen(req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else req
        if str(url).endswith("/images/generations"):
            return _Resp(json.dumps({"data": [{"url": "https://cdn/x.png"}]}).encode())
        return _Resp(b"URLBYTES")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    out = imggen.generate("一只狗", str(tmp_path / "dog.png"))
    assert (tmp_path / "dog.png").read_bytes() == b"URLBYTES"


# ---------------- 多后端：ComfyUI / SD-WebUI / OpenAI 兼容 ----------------

def test_dims_parsing():
    """尺寸解析：ratio 竖构图正确、宽高对齐 8 的倍数。"""
    assert imggen._dims("1K", "9:16") == (576, 1024)      # 条漫/短剧竖屏
    assert imggen._dims("1K", "16:9") == (1024, 576)
    assert imggen._dims("1024x1024", "") == (1024, 1024)
    w, h = imggen._dims("2K", "3:4")
    assert w % 8 == 0 and h % 8 == 0 and h > w


def test_comfy_workflow_wiring():
    """ComfyUI 工作流：节点齐全、连线指向正确、尺寸进 EmptyLatentImage。"""
    wf = imggen._comfy_workflow("m.safetensors", "猫", "bad", 832, 1216, 7, "p")
    assert set(wf) == {"3", "4", "5", "6", "7", "8", "9"}
    assert wf["5"]["inputs"] == {"width": 832, "height": 1216, "batch_size": 1}
    assert wf["4"]["inputs"]["ckpt_name"] == "m.safetensors"
    ks = wf["3"]["inputs"]
    assert ks["positive"] == ["6", 0] and ks["negative"] == ["7", 0]
    assert ks["latent_image"] == ["5", 0] and ks["denoise"] == 1.0
    assert wf["9"]["inputs"]["images"] == ["8", 0]         # 存图取 VAE 解码


def test_kind_of_explicit_and_provider(monkeypatch):
    """协议判定：显式声明优先；供应商配置直接判为云端 openai。"""
    assert imggen.kind_of({"base_url": "http://x", "kind": "comfyui"}) == "comfyui"
    assert imggen.kind_of({"base_url": "http://x", "kind": "a1111"}) == "a1111"
    assert imggen.kind_of({"base_url": "https://x/v1",
                           "provider_id": "agnes"}) == "openai"


def test_probe_falls_back_to_openai(monkeypatch):
    """探测不到特征端点时兜底为 openai，不抛异常。"""
    monkeypatch.setattr(imggen.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    assert imggen.probe("http://127.0.0.1:9") == "openai"


def test_local_backend_available_without_model(monkeypatch):
    """本地后端没有 model 也算可用（出图模型由工作流/引擎决定）。"""
    monkeypatch.setenv("LAS_IMAGE_BASE_URL", "http://127.0.0.1:8188")
    monkeypatch.delenv("LAS_IMAGE_MODEL", raising=False)
    monkeypatch.setenv("LAS_IMAGE_KIND", "comfyui")
    assert imggen.available() is True
    monkeypatch.setenv("LAS_IMAGE_KIND", "openai")
    assert imggen.available() is False             # 云端必须给 model


def test_comfy_generate_polls_and_saves(tmp_path, monkeypatch):
    """ComfyUI 全链路：提交 → 轮询 history → /view 取图落盘。"""
    import json
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._p = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.status = 200

        def read(self):
            return self._p

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        calls.append(url)
        if url.endswith("/prompt"):
            return _Resp({"prompt_id": "pid-1"})
        if "/history/pid-1" in url:
            return _Resp({"pid-1": {"outputs": {
                "9": {"images": [{"filename": "a.png", "subfolder": "",
                                  "type": "output"}]}}}})
        if "/view?" in url:
            return _Resp(b"PNGDATA")
        raise AssertionError("意外请求: " + url)

    monkeypatch.setattr(imggen.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)
    out = tmp_path / "p.png"
    path, url = imggen._comfy_generate(
        {"base_url": "http://127.0.0.1:8188", "model": "m.safetensors"},
        "提示词", str(out), "1K", "9:16")
    assert path == str(out) and out.read_bytes() == b"PNGDATA"
    assert any(u.endswith("/prompt") for u in calls)
    assert any("/view?" in u for u in calls)
