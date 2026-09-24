"""huobao 管线移植点单元测试：参考图归一化 / Retry-After / concat 参数 / ffmpeg 验真。"""
import base64
import io
import subprocess
import sys
import urllib.error
from email.message import Message

import pytest

import dramavideo
import videogen


def _http_error(code: int, retry_after=None) -> urllib.error.HTTPError:
    hdrs = Message()
    if retry_after is not None:
        hdrs["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("http://x.test", code, "err", hdrs, None)


# ---------------- videogen._retry：Retry-After ----------------

def test_retry_prefers_retry_after_header(monkeypatch):
    """服务端给了 Retry-After 时按头等待，不用固定梯子。"""
    sleeps = []
    monkeypatch.setattr(videogen.time, "sleep", sleeps.append)
    n = {"i": 0}

    def fetch():
        n["i"] += 1
        if n["i"] <= 2:
            raise _http_error(503, retry_after=37)
        return {"ok": 1}

    assert videogen._retry(fetch) == {"ok": 1}
    assert n["i"] == 3
    assert sleeps == [37.0, 37.0]


def test_retry_429_without_header_keeps_ladder(monkeypatch):
    """无 Retry-After 的 429 仍走 20/40 秒梯子。"""
    sleeps = []
    monkeypatch.setattr(videogen.time, "sleep", sleeps.append)
    n = {"i": 0}

    def fetch():
        n["i"] += 1
        if n["i"] <= 2:
            raise _http_error(429)
        return {"ok": 1}

    assert videogen._retry(fetch) == {"ok": 1}
    assert sleeps == [20.0, 40.0]


def test_retry_bad_header_falls_back_to_ladder(monkeypatch):
    """Retry-After 是 HTTP 日期等非数字格式时按无头处理。"""
    sleeps = []
    monkeypatch.setattr(videogen.time, "sleep", sleeps.append)
    n = {"i": 0}

    def fetch():
        n["i"] += 1
        if n["i"] == 1:
            raise _http_error(429, retry_after="Wed, 21 Oct 2026 07:28:00 GMT")
        return {"ok": 1}

    assert videogen._retry(fetch) == {"ok": 1}
    assert sleeps == [20.0]


def test_retry_clamps_huge_retry_after(monkeypatch):
    """Retry-After 过大时钳到 120 秒。"""
    sleeps = []
    monkeypatch.setattr(videogen.time, "sleep", sleeps.append)
    n = {"i": 0}

    def fetch():
        n["i"] += 1
        if n["i"] == 1:
            raise _http_error(503, retry_after=9999)
        return {"ok": 1}

    assert videogen._retry(fetch) == {"ok": 1}
    assert sleeps == [120.0]


# ---------------- dramavideo._normalize_refs：参考图归一化 ----------------

def test_normalize_refs_dedup_order_and_cap(tmp_path):
    """重复参考图去重保序，超过 6 张截断，空项剔除。"""
    p1 = tmp_path / "a.png"
    p1.write_bytes(b"not-a-real-png")
    p2 = tmp_path / "b.png"
    p2.write_bytes(b"nope")
    refs = ([str(p1), "", str(p1), str(p2)]
            + [str(tmp_path / f"m{i}.png") for i in range(8)])
    out = dramavideo._normalize_refs(refs)
    assert out[0] == str(p1)
    assert out[1] == str(p2)
    assert len(out) == 6


def test_normalize_refs_compresses_with_pil(tmp_path):
    """装了 PIL 时本地图片压成 ≤768px 的 JPEG data URI。"""
    pytest.importorskip("PIL")
    from PIL import Image
    p = tmp_path / "big.png"
    Image.new("RGB", (2000, 1000), (10, 200, 30)).save(p)
    out = dramavideo._normalize_refs([str(p)])
    assert out[0].startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(out[0].split(",", 1)[1])
    with Image.open(io.BytesIO(raw)) as im:
        assert max(im.size) <= 768


def test_normalize_refs_keeps_nonfile_items(tmp_path):
    """data URI 与不存在的路径原样保留，不做压缩。"""
    data = "data:image/png;base64,AAAA"
    missing = str(tmp_path / "gone.png")
    assert dramavideo._normalize_refs([data, missing]) == [data, missing]


# ---------------- dramavideo.concat：重编码参数 ----------------

def test_concat_recode_fallback_uses_broadcast_params(tmp_path, monkeypatch):
    """无损拼接失败回退重编码时带 aac 192k / 48kHz / faststart。"""
    monkeypatch.setattr(dramavideo.shutil, "which", lambda name: "ffmpeg")
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, cmd)
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(dramavideo.subprocess, "run", fake_run)
    c = tmp_path / "1.mp4"
    c.write_bytes(b"x")
    dramavideo.concat([str(c)], str(tmp_path / "out.mp4"))
    recode = calls[1]
    assert "-movflags" in recode and "+faststart" in recode
    assert recode[recode.index("-b:a") + 1] == "192k"
    assert recode[recode.index("-ar") + 1] == "48000"


# ---------------- dramavideo._ffmpeg_exe：捆绑二进制验真 ----------------

def _fake_imageio(monkeypatch, exe_path):
    fake = type("M", (), {"get_ffmpeg_exe": staticmethod(lambda: exe_path)})()
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", fake)


def test_ffmpeg_exe_rejects_broken_imageio_binary(monkeypatch):
    """PATH 无 ffmpeg 时，imageio 兜底二进制要先过 -version，坏的按缺失处理。"""
    monkeypatch.setattr(dramavideo.shutil, "which", lambda name: None)
    _fake_imageio(monkeypatch, "/fake/ffmpeg")

    def boom(cmd, **kw):
        raise FileNotFoundError(1, "corrupt binary")

    monkeypatch.setattr(dramavideo.subprocess, "run", boom)
    assert dramavideo._ffmpeg_exe() == ""


def test_ffmpeg_exe_accepts_working_imageio_binary(monkeypatch):
    """-version 通过的捆绑二进制正常返回。"""
    monkeypatch.setattr(dramavideo.shutil, "which", lambda name: None)
    _fake_imageio(monkeypatch, "/fake/ffmpeg")
    monkeypatch.setattr(dramavideo.subprocess, "run",
                        lambda cmd, **kw: type("R", (), {"returncode": 0})())
    assert dramavideo._ffmpeg_exe() == "/fake/ffmpeg"


def test_ffmpeg_exe_path_result_skips_probe(monkeypatch):
    """PATH 命中的 ffmpeg 不做 -version 探测（用户自装环境自管）。"""
    monkeypatch.setattr(dramavideo.shutil, "which", lambda name: "/usr/bin/ffmpeg")

    def boom(cmd, **kw):
        raise AssertionError("PATH 结果不应被探测")

    monkeypatch.setattr(dramavideo.subprocess, "run", boom)
    assert dramavideo._ffmpeg_exe() == "/usr/bin/ffmpeg"
