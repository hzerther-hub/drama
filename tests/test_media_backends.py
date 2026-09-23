# -*- coding: utf-8 -*-
"""媒体生成后端：即梦 Ark(Seedance) 视频分支、Flux GGUF 工作流、media 段配置。"""

from __future__ import annotations

import pytest

import config
import imggen
import videogen


def _clear_media_env(monkeypatch):
    """清空媒体相关环境变量，避免宿主机配置串进测试。"""
    for k in ("LAS_IMAGE_BASE_URL", "LAS_IMAGE_MODEL", "LAS_IMAGE_API_KEY",
              "LAS_IMAGE_KIND", "LAS_IMAGE_CKPT", "LAS_IMAGE_CLIP1",
              "LAS_IMAGE_CLIP2", "LAS_IMAGE_VAE",
              "LAS_VIDEO_BASE_URL", "LAS_VIDEO_MODEL", "LAS_VIDEO_API_KEY",
              "LAS_VIDEO_KIND"):
        monkeypatch.delenv(k, raising=False)


# ---------------- videogen：ark 协议识别 ----------------

class TestArkKind:
    def test_ark_url_detected(self):
        """火山方舟 URL 自动识别为 ark。"""
        svc = {"base_url": "https://ark.cn-beijing.volces.com/api/v3"}
        assert videogen._provider_kind(svc) == "ark"

    def test_doubao_model_detected(self):
        """doubao-* 模型名也识别为 ark。"""
        assert videogen._provider_kind(
            {"base_url": "https://gw.example/v1",
             "model": "doubao-seedance-1-0-pro"}) == "ark"

    def test_default_agnes(self):
        """其余 URL 按 Agnes 形态处理。"""
        assert videogen._provider_kind(
            {"base_url": "http://x.example/v1"}) == "agnes"


# ---------------- videogen：ark 建任务与轮询 ----------------

class TestArkCreate:
    def test_create_posts_content_array(self, monkeypatch):
        """建任务走 /contents/generations/tasks，文本与首帧图进 content。"""
        seen = {}

        def fake_post(url, body, api_key):
            seen["url"] = url
            seen["body"] = body
            seen["key"] = api_key
            return {"id": "task-1"}

        monkeypatch.setattr(videogen, "_post", fake_post)
        svc = {"base_url": "https://ark.cn-beijing.volces.com/api/v3",
               "model": "doubao-seedance-1-0-pro", "api_key": "k1"}
        vid = videogen._ark_create("雨夜街头", "https://cdn/f.png", 5, svc)
        assert vid == "task-1"
        assert seen["url"] == ("https://ark.cn-beijing.volces.com/api/v3"
                               "/contents/generations/tasks")
        assert seen["key"] == "k1"
        content = seen["body"]["content"]
        assert seen["body"]["model"] == "doubao-seedance-1-0-pro"
        assert content[0]["type"] == "text"
        assert "--resolution 720p" in content[0]["text"]
        assert content[0]["text"].endswith("雨夜街头")
        assert content[1]["image_url"]["url"] == "https://cdn/f.png"

    def test_create_without_image(self, monkeypatch):
        """纯文生视频不带 image_url 段。"""
        seen = {}
        monkeypatch.setattr(
            videogen, "_post",
            lambda url, body, key: seen.update(body=body) or {"id": "t"})
        svc = {"base_url": "https://ark/v3", "model": "m", "api_key": ""}
        videogen._ark_create("提示词", "", 5, svc)
        assert len(seen["body"]["content"]) == 1

    def test_create_no_id_raises(self, monkeypatch):
        """响应缺任务 ID 时抛 VidError。"""
        monkeypatch.setattr(videogen, "_post", lambda url, body, key: {})
        svc = {"base_url": "https://ark/v3", "model": "m", "api_key": ""}
        with pytest.raises(videogen.VidError):
            videogen._ark_create("p", "", 5, svc)


class TestArkQuery:
    def _svc(self):
        return {"base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "m", "api_key": "k"}

    def test_succeeded_maps_to_completed(self, monkeypatch):
        """succeeded 归一为 completed，video_url 提取为 url。"""
        seen = {}
        monkeypatch.setattr(videogen, "_service", lambda: self._svc())

        def fake_get(url, api_key):
            seen["url"] = url
            return {"status": "succeeded",
                    "content": {"video_url": "https://cdn/out.mp4"}}

        monkeypatch.setattr(videogen, "_get", fake_get)
        st = videogen.query("tid")
        assert seen["url"].endswith("/contents/generations/tasks/tid")
        assert st == {"status": "completed",
                      "url": "https://cdn/out.mp4", "error": ""}

    def test_failed_carries_message(self, monkeypatch):
        """failed 带出 error.message。"""
        monkeypatch.setattr(videogen, "_service", lambda: self._svc())
        monkeypatch.setattr(
            videogen, "_get",
            lambda url, key: {"status": "failed",
                              "error": {"code": "E1", "message": "敏感词"}})
        st = videogen.query("tid")
        assert st["status"] == "failed"
        assert st["error"] == "敏感词"

    def test_running_no_url(self, monkeypatch):
        """running 无地址不误报。"""
        monkeypatch.setattr(videogen, "_service", lambda: self._svc())
        monkeypatch.setattr(
            videogen, "_get",
            lambda url, key: {"status": "running", "content": {}})
        st = videogen.query("tid")
        assert st["status"] == "running"
        assert st["url"] == ""


# ---------------- imggen：Flux GGUF 工作流 ----------------

class TestGgufWorkflow:
    def test_workflow_shape(self):
        """GGUF 工作流节点与连线：cfg=1、正条件经 FluxGuidance、VAE 独立加载。"""
        wf = imggen._comfy_workflow_gguf(
            "flux1-dev-Q5_K_S.gguf", "clip_l.safetensors",
            "t5-v1_1-xxl-encoder-Q5_K_M.gguf", "ae.safetensors",
            "a girl", "", 1024, 1024, 42, "pfx")
        assert wf["4"]["class_type"] == "UnetLoaderGGUF"
        clip = wf["10"]["inputs"]
        assert clip["clip_name1"] == "clip_l.safetensors"
        assert clip["clip_name2"].endswith(".gguf")
        assert clip["type"] == "flux"
        assert wf["11"]["inputs"]["vae_name"] == "ae.safetensors"
        ks = wf["3"]["inputs"]
        assert ks["cfg"] == 1.0
        assert ks["positive"] == ["12", 0]      # FluxGuidance 输出
        assert ks["model"] == ["4", 0]
        assert wf["8"]["inputs"]["vae"] == ["11", 0]


class TestGgufParts:
    def test_picks_safetensors_then_gguf(self, monkeypatch):
        """clip1 选 safetensors、clip2 选 gguf、vae 取第一个候选。"""
        monkeypatch.setattr(
            imggen, "_obj_choices",
            lambda base, cls, field: {
                ("DualCLIPLoaderGGUF", "clip_name1"): ["t5.gguf",
                                                       "clip_l.safetensors"],
                ("DualCLIPLoaderGGUF", "clip_name2"): ["clip_l.safetensors",
                                                       "t5.gguf"],
                ("VAELoader", "vae_name"): ["ae.safetensors"],
            }[(cls, field)])
        c1, c2, vae = imggen._comfy_pick_gguf_parts(
            "http://127.0.0.1:8188", {})
        assert c1 == "clip_l.safetensors"
        assert c2 == "t5.gguf"
        assert vae == "ae.safetensors"

    def test_env_override(self, monkeypatch):
        """LAS_IMAGE_* 覆盖自动探测。"""
        monkeypatch.setenv("LAS_IMAGE_CLIP1", "my_clip.safetensors")
        monkeypatch.setenv("LAS_IMAGE_CLIP2", "my_t5.gguf")
        monkeypatch.setenv("LAS_IMAGE_VAE", "my_vae.safetensors")
        monkeypatch.setattr(imggen, "_obj_choices", lambda *a: [])
        c1, c2, vae = imggen._comfy_pick_gguf_parts("http://x", {})
        assert (c1, c2, vae) == ("my_clip.safetensors", "my_t5.gguf",
                                 "my_vae.safetensors")

    def test_missing_raises(self, monkeypatch):
        """节点/文件全缺时报可操作的中文错误。"""
        monkeypatch.setattr(imggen, "_obj_choices", lambda *a: [])
        with pytest.raises(imggen.ImgError) as ei:
            imggen._comfy_pick_gguf_parts("http://x", {})
        assert "ComfyUI-GGUF" in str(ei.value)

    def test_svc_dict_override(self, monkeypatch):
        """svc 里的 clip1/clip2/vae 优先级最高。"""
        monkeypatch.setattr(imggen, "_obj_choices", lambda *a: ["x"])
        c1, c2, vae = imggen._comfy_pick_gguf_parts(
            "http://x", {"clip1": "a", "clip2": "b", "vae": "c"})
        assert (c1, c2, vae) == ("a", "b", "c")


# ---------------- config：media 段与 kind 透传 ----------------

class TestMediaService:
    def test_media_section_local_backend(self, monkeypatch):
        """media.image 段可配置无模型的本地 ComfyUI（key/model 可空）。"""
        _clear_media_env(monkeypatch)
        monkeypatch.setattr(config, "_load_models_data", lambda: {
            "media": {"image": {"base_url": "http://127.0.0.1:8188",
                                "model": "", "api_key": "",
                                "kind": "comfyui"}}})
        svc = config.image_service()
        assert svc["base_url"] == "http://127.0.0.1:8188"
        assert svc["kind"] == "comfyui"
        assert svc["model"] == ""
        assert imggen.available()

    def test_env_beats_media_section(self, monkeypatch):
        """环境变量优先级高于 media 段。"""
        monkeypatch.setattr(config, "_load_models_data", lambda: {
            "media": {"image": {"base_url": "http://from-file:8188",
                                "kind": "comfyui"}}})
        monkeypatch.setenv("LAS_IMAGE_BASE_URL", "http://from-env:8188")
        monkeypatch.setenv("LAS_IMAGE_MODEL", "")
        monkeypatch.setenv("LAS_IMAGE_KIND", "a1111")
        svc = config.image_service()
        assert svc["base_url"] == "http://from-env:8188"
        assert svc["kind"] == "a1111"

    def test_provider_kind_passthrough(self, monkeypatch):
        """供应商的 image_kind 透传（云端网关显式声明后端协议）。"""
        _clear_media_env(monkeypatch)
        monkeypatch.setattr(config, "_load_models_data", lambda: {
            "providers": [{"id": "p1", "base_url": "https://ark/v3",
                           "api_key": "k", "image_model": "seedream",
                           "image_kind": "openai"}]})
        svc = config.image_service()
        assert svc["provider_id"] == "p1"
        assert svc["kind"] == "openai"

    def test_media_section_ark_video(self, monkeypatch):
        """media.video 段配即梦，videogen._provider_kind 识别为 ark。"""
        _clear_media_env(monkeypatch)
        monkeypatch.setattr(config, "_load_models_data", lambda: {
            "media": {"video": {"base_url": "https://ark.cn-beijing.volces.com/api/v3",
                                "model": "doubao-seedance-1-0-pro",
                                "api_key": "k2", "kind": ""}}})
        svc = config.video_service()
        assert videogen._provider_kind(svc) == "ark"

    def test_empty_media_section_falls_to_providers(self, monkeypatch):
        """media 段为空时不拦截供应商分支。"""
        _clear_media_env(monkeypatch)
        monkeypatch.setattr(config, "_load_models_data", lambda: {
            "media": {},
            "providers": [{"id": "p1", "base_url": "https://g/v1",
                           "api_key": "k", "video_model": "vmodel"}]})
        svc = config.video_service()
        assert svc["model"] == "vmodel"


# ---------------- config：media 段读写 API ----------------

class TestMediaStore:
    def _patch_store(self, monkeypatch, store):
        """get/set 都走同一个内存 store，避免碰真实配置文件。"""
        monkeypatch.setattr(config, "_load_models_data", lambda: dict(store))
        monkeypatch.setattr(config, "_save_models_data",
                            lambda d: store.clear() or store.update(d))

    def test_set_and_get_roundtrip(self, monkeypatch):
        """写入后能原样读回；未知字段被白名单丢弃。"""
        store = {}
        self._patch_store(monkeypatch, store)
        config.set_media("image", {"base_url": "http://127.0.0.1:8188/",
                                   "model": "flux1-dev-Q5_K_S.gguf",
                                   "kind": "comfyui",
                                   "evil": "x"})
        got = config.get_media()["image"]
        assert got["base_url"] == "http://127.0.0.1:8188"   # 去尾斜杠
        assert got["model"] == "flux1-dev-Q5_K_S.gguf"
        assert got["kind"] == "comfyui"
        assert "evil" not in got

    def test_clear_section(self, monkeypatch):
        """cfg=None 删除该段；两段都空时 media 键整体移除。"""
        store = {}
        self._patch_store(monkeypatch, store)
        config.set_media("image", {"base_url": "http://x", "kind": "a1111"})
        config.set_media("video", {"base_url": "https://ark/v3",
                                   "model": "m", "api_key": "k"})
        config.set_media("image", None)
        assert "image" not in config.get_media()
        assert config.get_media()["video"]["model"] == "m"
        config.set_media("video", {"base_url": ""})
        assert config.get_media() == {}
        assert "media" not in store

    def test_bad_section_rejected(self, monkeypatch):
        """未知段名直接拒绝。"""
        with pytest.raises(AssertionError):
            config.set_media("audio", {"base_url": "http://x"})
