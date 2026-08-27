# -*- coding: utf-8 -*-
"""voice._StreamRecorder：单按钮录音器的长按落盘 + 自动停顿检测状态机。

sounddevice 用假模块替换（真卡不可用于 CI）；numpy 缺失时整文件跳过。
"""

import sys
import types

import pytest

np = pytest.importorskip("numpy")   # 语音栈可选：无 numpy 的环境整文件跳过


class _FakeInputStream:
    """记录回调供测试直接喂数据块；start/stop/close 全部空操作。"""

    def __init__(self, **kwargs):
        self.callback = kwargs.get("callback")

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


@pytest.fixture
def voice_mod(monkeypatch):
    fake_sd = types.ModuleType("sounddevice")
    fake_sd.InputStream = _FakeInputStream
    import time as _time
    fake_sd.sleep = lambda ms: _time.sleep(min(ms, 10) / 1000)
    fake_sd.write = lambda path, data, sr: open(path, "w").close()
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    import voice
    return voice


def _feed(rec, n, loud):
    """直接驱动录音回调：n 个块，响/静音由 loud 决定。"""
    amp = 0.3 if loud else 0.0
    chunk = np.full((1024, 1), amp, dtype="float32")
    for _ in range(n):
        rec._stream.callback(chunk, 1024, None, None)


class TestStreamRecorderVad:
    def test_auto_stop_after_silence(self, voice_mod, tmp_path, monkeypatch):
        """自动模式：说过话 + 静音达标 → wait_vad_stop 立即收尾。"""
        monkeypatch.chdir(tmp_path)          # mkstemp 落在临时目录
        rec = voice_mod._StreamRecorder().start()
        _feed(rec, 5, loud=True)             # 说话（VAD 未开也先有音频）
        rec.enable_vad()
        _feed(rec, 3, loud=True)             # VAD 下确认有人声
        _feed(rec, 25, loud=False)           # 静音 25 块 > 1.5s 需要的 23 块
        wav, had = rec.wait_vad_stop(silence_sec=1.5, max_sec=30)
        assert had is True
        assert wav is not None

    def test_manual_stop_wakes_waiter(self, voice_mod, tmp_path, monkeypatch):
        """自动模式等待中用户再按一次（手动 stop）→ 等待立即结束。"""
        monkeypatch.chdir(tmp_path)
        rec = voice_mod._StreamRecorder().start()
        rec.enable_vad()
        _feed(rec, 5, loud=True)
        first = rec.stop_and_save()          # 手动提前结束
        assert first is not None
        wav, had = rec.wait_vad_stop()       # 已停止 → 立即返回，不再等
        assert wav is None
        assert had is True                   # 之前确实录到过声音

    def test_double_stop_returns_none(self, voice_mod, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rec = voice_mod._StreamRecorder().start()
        _feed(rec, 2, loud=True)
        assert rec.stop_and_save() is not None
        assert rec.stop_and_save() is None   # 幂等：二次停止无音频

    def test_silence_only_never_speech(self, voice_mod, tmp_path, monkeypatch):
        """全程静音（VAD 开着但没人说话）→ 到时长上限收尾，had_speech False。"""
        monkeypatch.chdir(tmp_path)
        rec = voice_mod._StreamRecorder().start()
        rec.enable_vad()
        # 30s × 16000Hz / 1024帧 ≈ 469 块：喂满时长上限，确定性行退出
        _feed(rec, 470, loud=False)
        wav, had = rec.wait_vad_stop(silence_sec=1.5, max_sec=30)
        assert had is False                  # 上层据此跳过识别
        # 静音但有时长：音频照常落盘（交由调用方决定是否丢弃）
        assert wav is not None

    def test_start_stop_recording_api_kept(self, voice_mod, tmp_path, monkeypatch):
        """旧接口 start_recording/stop_recording（长按路径）仍然可用。"""
        monkeypatch.chdir(tmp_path)
        rec, _ = voice_mod.start_recording()
        _feed(rec, 3, loud=True)
        assert voice_mod.stop_recording(rec) is not None

    def test_record_with_vad_removed(self, voice_mod):
        assert not hasattr(voice_mod, "record_with_vad")
