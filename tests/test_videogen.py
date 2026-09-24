# -*- coding: utf-8 -*-
"""videogen.py：服务解析、任务创建/轮询/下载、超时与失败路径。"""

import json

import pytest

import videogen


class _Resp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self) -> bytes:
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _enable(monkeypatch, base="https://apihub.agnes-ai.com/v1"):
    for k in ("LAS_VIDEO_BASE_URL", "LAS_VIDEO_MODEL", "LAS_VIDEO_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LAS_VIDEO_BASE_URL", base)
    monkeypatch.setenv("LAS_VIDEO_MODEL", "agnes-video-v2.0")
    monkeypatch.setenv("LAS_VIDEO_API_KEY", "sk-t")


def test_root_strips_v1():
    assert videogen._root("https://apihub.agnes-ai.com/v1") \
        == "https://apihub.agnes-ai.com"
    assert videogen._root("https://x.cn") == "https://x.cn"


def test_frames_is_8n_plus_1_and_capped():
    assert videogen._frames(5, 24) == 8 * 15 + 1      # 5s × 24fps
    assert videogen._frames(0, 24) == 121             # 默认 5 秒
    assert videogen._frames(999, 24) == videogen._MAX_FRAMES
    assert videogen._frames(5, 24) % 8 == 1


def test_create_builds_task(monkeypatch):
    _enable(monkeypatch)
    seen = {}

    def fake_post(url, body, key):
        seen["url"], seen["body"], seen["key"] = url, body, key
        return {"id": "task-1"}

    monkeypatch.setattr(videogen, "_post", fake_post)
    vid = videogen.create("雨夜街道", seconds=5)
    assert vid == "task-1"
    assert seen["url"].endswith("/v1/videos")
    assert seen["body"]["num_frames"] == 121
    assert seen["body"]["model"] == "agnes-video-v2.0"
    assert seen["key"] == "sk-t"


def test_generate_poll_and_download(monkeypatch, tmp_path):
    _enable(monkeypatch)
    states = iter([
        {"status": "queued"},
        {"status": "in_progress"},
        {"status": "completed", "metadata": {"url": "https://cdn/v.mp4"}},
    ])

    def fake_get(url, key=""):
        assert "video_id=task-9" in url
        return next(states)

    def fake_urlopen(url, timeout=0):
        return _Resp(b"MP4DATA")

    monkeypatch.setattr(videogen, "_get", fake_get)
    monkeypatch.setattr(videogen, "create", lambda *a, **k: "task-9")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr(videogen.time, "sleep", lambda s: None)
    out = videogen.generate("夕阳下的海", str(tmp_path / "sea.mp4"),
                            timeout=60, poll=1)
    assert out.endswith("sea.mp4")
    assert (tmp_path / "sea.mp4").read_bytes() == b"MP4DATA"


def test_generate_failed_task(monkeypatch, tmp_path):
    _enable(monkeypatch)
    monkeypatch.setattr(videogen, "create", lambda *a, **k: "t2")
    monkeypatch.setattr(videogen, "_get",
                        lambda url, key="": {"status": "failed",
                                             "error": "内容不合规"})
    monkeypatch.setattr(videogen.time, "sleep", lambda s: None)
    with pytest.raises(videogen.VidError) as ei:
        videogen.generate("测试", str(tmp_path / "x.mp4"), timeout=30, poll=1)
    assert "内容不合规" in str(ei.value)


def test_generate_timeout_keeps_task_id(monkeypatch, tmp_path):
    _enable(monkeypatch)
    monkeypatch.setattr(videogen, "create", lambda *a, **k: "t3")
    monkeypatch.setattr(videogen, "_get",
                        lambda url, key="": {"status": "in_progress"})
    monkeypatch.setattr(videogen.time, "sleep", lambda s: None)
    ticks = iter(range(0, 100, 20))          # 0,20,40… 每次调用 +20s
    monkeypatch.setattr(videogen.time, "monotonic", lambda: next(ticks))
    with pytest.raises(videogen.VidError) as ei:
        videogen.generate("慢任务", str(tmp_path / "y.mp4"), timeout=6, poll=1)
    assert "t3" in str(ei.value) and "超时" in str(ei.value)


def test_unavailable_raises(monkeypatch):
    for k in ("LAS_VIDEO_BASE_URL", "LAS_VIDEO_MODEL", "LAS_VIDEO_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("config._load_models_data",
                        lambda: {"providers": []})
    assert videogen.available() is False
    with pytest.raises(videogen.VidError):
        videogen.create("x")


def test_retry_on_503_then_success(monkeypatch):
    """免费网关瞬时 503 → 退避重试后成功（不再把任务打挂）。"""
    import urllib.error

    class _Err503(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("u", 503, "Service Unavailable", None, None)

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _Err503()
        return {"id": "ok"}

    monkeypatch.setattr(videogen.time, "sleep", lambda s: None)
    assert videogen._retry(flaky) == {"id": "ok"}
    assert calls["n"] == 3


def test_retry_gives_up_after_max(monkeypatch):
    import urllib.error

    def always_503():
        raise urllib.error.HTTPError("u", 503, "Service Unavailable",
                                     None, None)

    monkeypatch.setattr(videogen.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        videogen._retry(always_503)


def test_retry_does_not_swallow_4xx(monkeypatch):
    import urllib.error

    def bad_key():
        raise urllib.error.HTTPError("u", 401, "Unauthorized", None, None)

    with pytest.raises(urllib.error.HTTPError):
        videogen._retry(bad_key)


def test_retry_on_429_with_long_backoff(monkeypatch):
    """429 限流：按 20/40s 长退避重试，且第 429 不属于直接抛出的 4xx。"""
    import urllib.error

    class _429(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("u", 429, "Too Many Requests", None, None)

    calls = {"n": 0}
    sleeps = []

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _429()
        return {"ok": 1}

    monkeypatch.setattr(videogen.time, "sleep", lambda s: sleeps.append(s))
    assert videogen._retry(flaky) == {"ok": 1}
    assert calls["n"] == 2 and sleeps == [20]      # 429 → 20s（不是 4s）


def test_download_atomic_no_partial_on_failure(monkeypatch, tmp_path):
    """下载中途失败：不留半截成片，也不留 .part（重跑才能当作缺失补造）。"""
    out = str(tmp_path / "1-04.mp4")

    class _BrokenResp:
        def read(self):
            raise ConnectionResetError("中断")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(videogen.urllib.request, "urlopen",
                        lambda url, timeout=0: _BrokenResp())
    with pytest.raises(videogen.VidError):
        videogen.download("http://cdn/x.mp4", out)
    import os
    assert not os.path.exists(out)
    assert not os.path.exists(out + ".part")


def test_download_replaces_target_atomically(monkeypatch, tmp_path):
    """成功下载：经 .part 原子改名落盘。"""
    out = str(tmp_path / "1-05.mp4")
    monkeypatch.setattr(videogen.urllib.request, "urlopen",
                        lambda url, timeout=0: _Resp(b"MP4DATA"))
    assert videogen.download("http://cdn/x.mp4", out) == out
    assert open(out, "rb").read() == b"MP4DATA"
    import os
    assert not os.path.exists(out + ".part")


def test_ark_flags_ratio_parameterized():
    """画幅参数化：ratio 空=竖屏 9:16（旧行为），可切 16:9/1:1 等，非法值回退。"""
    f = videogen._ark_flags
    assert "--ratio 9:16" in f(5)
    assert "--ratio 16:9" in f(5, ratio="16:9")
    assert "--ratio 1:1" in f(5, "480p", "1:1")
    assert "--resolution 480p" in f(5, "480p")
    # 非法比例 / 非法分辨率均回退默认
    assert "--ratio 9:16" in f(5, ratio="21:99")
    assert "--resolution 720p" in f(5, "9999p")


def test_ark_create_passes_ratio_to_instruction_header(monkeypatch):
    """create 链路：ratio 经 _ark_create 落进 Seedance 文本指令头。"""
    captured = {}

    def _fake_post(url, body, key):
        captured.update(url=url, body=body)
        return {"id": "task-1"}

    monkeypatch.setattr(videogen, "_post", _fake_post)
    svc = {"base_url": "https://ark.cn-beijing.volces.com/v1",
           "model": "doubao-seedance-2-0", "api_key": "k"}
    vid = videogen._ark_create("prompt", "", 5, svc, "480p", "16:9")
    assert vid == "task-1"
    text = captured["body"]["content"][0]["text"]
    assert "--resolution 480p" in text
    assert "--ratio 16:9" in text
