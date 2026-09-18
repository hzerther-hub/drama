# -*- coding: utf-8 -*-
"""tts.py：TTS 通道选择（edge-tts 优先 / SAPI 兜底）与降级。"""

import os
import sys
import types

import pytest

import tts


def _no_edge(monkeypatch):
    monkeypatch.setitem(sys.modules, "edge_tts", None)   # import 即失败


def test_provider_prefers_edge_tts(monkeypatch):
    fake = types.ModuleType("edge_tts")
    monkeypatch.setitem(sys.modules, "edge_tts", fake)
    assert tts.provider() == "edge-tts"


def test_provider_falls_back_to_sapi_on_windows(monkeypatch):
    _no_edge(monkeypatch)
    assert tts.provider() == ("sapi" if os.name == "nt" else "")


def test_speak_empty_text_raises():
    with pytest.raises(tts.TTSError):
        tts.speak("", "x.mp3")


def test_speak_sapi_builds_powershell(monkeypatch, tmp_path):
    """SAPI 兜底：走 PowerShell System.Speech（-EncodedCommand 整体编码）。"""
    import base64
    _no_edge(monkeypatch)
    out = tmp_path / "line.wav"
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        out.write_bytes(b"WAV")
        return type("R", (), {"returncode": 0, "stderr": b""})()

    monkeypatch.setattr(tts.subprocess, "run", fake_run)
    tts.speak("你好，观众", str(out), voice="Huihui")
    assert captured["cmd"][1:3] == ["-NoProfile", "-EncodedCommand"]
    script = base64.b64decode(captured["cmd"][3]).decode("utf-16-le")
    assert "System.Speech" in script
    assert "SelectVoice('Huihui')" in script
    assert "SetOutputToWaveFile" in script
    assert "FromBase64String" in script          # 台词经 base64 防编码搅乱
    assert base64.b64encode("你好，观众".encode()).decode() in script
    assert out.exists()


def test_speak_sapi_failure_raises(monkeypatch, tmp_path):
    _no_edge(monkeypatch)
    monkeypatch.setattr(tts.subprocess, "run",
                        lambda cmd, **kw: type("R", (), {"returncode": 1})())
    with pytest.raises(tts.TTSError):
        tts.speak("台词", str(tmp_path / "x.wav"))
