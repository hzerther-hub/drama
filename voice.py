# -*- coding: utf-8 -*-
"""语音录入（Linux / Windows / macOS 通用）。

单按钮两种用法（按下即录音）：
- 长按松手停止（按住说话）：stop_and_save() 落盘
- 轻点一下切换自动停顿检测（VAD）：enable_vad() 后静音超时自动停
本地 Whisper 离线识别。

录音基于 PortAudio（sounddevice），三大平台均可用，不再依赖 arecord。
"""

from __future__ import annotations

import os
import tempfile
import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK_SIZE = 1024          # 每次回调的帧数

# ---- Whisper 离线识别 ----
WHISPER_MODEL = "base"          # tiny / base / small / medium / large
WHISPER_DEVICE = "cpu"          # cpu / cuda（GPU 需装对应后端）
WHISPER_COMPUTE_TYPE = "int8"   # int8 / float16 / float32

# 全局单例：避免重复加载 Whisper 模型
_model_lock = threading.Lock()
_model = None
_model_loaded = False

def _import_faster_whisper():
    """导入 faster_whisper，失败时清理重试。

    Windows 上安全软件（如 360 主动防御）可能间歇性锁定其依赖 DLL
    （PyAV 的 av.libs/*.dll），首次加载时表现为「另一个程序正在使用此
    文件」。这类错误在 CPython 中可能以 ImportError 或 OSError 抛出，
    这里统一捕获。失败时清掉半初始化的模块（避免 Cython 状态残留）后
    重试；一旦全部 DLL 加载成功即被系统缓存，之后不再访问文件。
    """
    import sys
    import time
    last_err = None
    for _attempt in range(8):
        try:
            import faster_whisper
            return faster_whisper
        except (ImportError, OSError) as e:
            last_err = e
            for k in [k for k in sys.modules
                      if k == "av" or k.startswith("av.")
                      or k.startswith("faster_whisper")]:
                sys.modules.pop(k, None)
            time.sleep(2)
    raise ImportError(
        f"faster_whisper 导入失败（DLL 被安全软件间歇占用，重试 8 次未通过；"
        f"可将 Python/项目目录加入杀软白名单后重试）: {last_err}") from last_err

def _get_model():
    """懒加载 faster-whisper 模型（单例）。"""
    global _model, _model_loaded
    with _model_lock:
        if not _model_loaded:
            WhisperModel = _import_faster_whisper().WhisperModel
            _model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE,
                                  compute_type=WHISPER_COMPUTE_TYPE)
            _model_loaded = True
        return _model

def transcribe(wav_path, language="zh"):
    """识别 wav 文件，返回文本。失败抛异常。"""
    model = _get_model()
    segments, _info = model.transcribe(wav_path, language=language)
    return "".join(s.text for s in segments).strip()

# ---------------- 流式录音器（跨平台，可选停顿检测） ----------------

# RMS 能量阈值：超过视为有人声（自动停顿检测用）
LEVEL_THRESHOLD = 0.012

class _StreamRecorder:
    """sounddevice 流式录音：回调收集音频块，stop_and_save() 时写 wav。

    可选 VAD：enable_vad() 之后回调内做 RMS 停顿统计，
    wait_vad_stop() 阻塞等待「说过话且连续静音达标 / 到时长上限」。
    提前手动 stop_and_save() 也会让 wait_vad_stop() 立即返回。
    """

    def __init__(self):
        self.chunks = []
        self._lock = threading.Lock()
        self._stream = None
        self._vad_on = False
        self._stopped = False
        self._speech_detected = False
        self._silence_blocks = 0

        def _callback(indata, _frames, _time, _status):
            chunk = indata[:, 0].copy()
            # RMS 在锁外计算（chunk 已是独立副本），尽量缩短持锁时间，
            # 避免阻塞 stop() 等待回调收尾。
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            with self._lock:
                self.chunks.append(chunk)
                if self._vad_on:
                    if rms > LEVEL_THRESHOLD:
                        self._speech_detected = True
                        self._silence_blocks = 0
                    else:
                        self._silence_blocks += 1

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            blocksize=BLOCK_SIZE, callback=_callback)

    def start(self):
        self._stream.start()
        return self

    def enable_vad(self):
        """开启停顿检测（轻点松手后进入自动模式时调用）。"""
        with self._lock:
            self._vad_on = True
            self._speech_detected = False
            self._silence_blocks = 0

    def wait_vad_stop(self, silence_sec=1.5, max_sec=30):
        """阻塞等待自动停止条件，返回 (wav_path, 是否录到声音)。"""
        need = int(silence_sec * SAMPLE_RATE / BLOCK_SIZE)
        while True:
            sd.sleep(100)
            with self._lock:
                stopped = self._stopped
                n_chunks = len(self.chunks)
                has_speech = self._speech_detected
                silence = self._silence_blocks
            if stopped:
                break
            elapsed = n_chunks * BLOCK_SIZE / SAMPLE_RATE
            if elapsed >= max_sec or (has_speech and silence >= need):
                break
        return self.stop_and_save(), self._speech_detected

    def stop_and_save(self):
        """停止录音并把已收集音频写入临时 wav，返回路径。无音频返回 None。

        幂等：第二次调用返回 None（已停止、无新音频）。
        """
        with self._lock:
            if self._stopped:
                return None
            self._stopped = True
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:  # noqa: BLE001
            pass
        with self._lock:
            chunks = list(self.chunks)
            self.chunks = []
        if not chunks:
            return None
        fd, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            sd.write(wav_path, np.concatenate(chunks), SAMPLE_RATE)
        except Exception:  # noqa: BLE001  写盘失败不残留半成品文件
            try:
                os.remove(wav_path)
            except OSError:
                pass
            raise
        return wav_path

def start_recording(out_path=None):
    """启动后台流式录音，返回 (recorder, wav_path占位)。

    兼容旧接口：返回二元组；stop_recording(recorder, path) 时真正落盘。
    """
    rec = _StreamRecorder().start()
    return rec, out_path

def stop_recording(recorder, _out_path=None):
    """停止录音，落盘并返回 wav 路径。"""
    return recorder.stop_and_save()
