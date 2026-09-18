# -*- coding: utf-8 -*-
"""台词配音（TTS）：edge-tts 优先，Windows 本地语音兜底（stdlib）。

- edge-tts：微软神经网络语音（zh-CN-XiaoxiaoNeural 等），免费高质量；
  需 pip install edge-tts（未装则自动跳过）。
- Windows SAPI：System.Speech 离线合成（中文系统一般自带 Huihui），
  经 PowerShell 调用，零第三方依赖，质量一般但永远可用。
- 都不可用抛 TTSError（调用方降级：视频保留模型原声）。
"""

from __future__ import annotations

import os
import subprocess


class TTSError(Exception):
    pass


DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


def provider() -> str:
    """当前可用通道：edge-tts | sapi | ''（空=不可用）。"""
    try:
        import edge_tts                  # noqa: F401
        return "edge-tts"
    except Exception:                    # noqa: BLE001
        pass
    if os.name == "nt":
        return "sapi"
    return ""


def available() -> bool:
    return bool(provider())


def _speak_edge(text: str, out_path: str, voice: str) -> str:
    import asyncio
    import edge_tts

    async def _run():
        com = edge_tts.Communicate(text, voice or DEFAULT_VOICE)
        await com.save(out_path)

    asyncio.run(_run())
    return out_path


def _speak_sapi(text: str, out_path: str, voice: str) -> str:
    """Windows System.Speech → wav（离线；voice 可空=第一个中文音色）。

    整段脚本走 -EncodedCommand（UTF-16LE base64），台词再单独 base64
    解码——彻底绕开引号/编码在命令行里被搅的问题。
    """
    import base64
    select = ("$v=($s.GetInstalledVoices()|Where-Object"
              "{$_.VoiceInfo.Culture -like 'zh*'}|Select-Object -First 1)"
              ".VoiceInfo.Name; if($v){$s.SelectVoice($v)}") \
        if not voice else f"$s.SelectVoice('{voice}')"
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"{select};"
        "$f=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo"
        " -ArgumentList 24000,16,1;"
        "$s.SetOutputToWaveFile('" + out_path.replace("'", "''") + "',$f);"
        "$t=[Convert]::FromBase64String('"
        + base64.b64encode(text.encode("utf-8")).decode() + "');"
        "$s.Speak([Text.Encoding]::UTF8.GetString($t));"
        "$s.Dispose()"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    r = subprocess.run(
        ["powershell", "-NoProfile", "-EncodedCommand", encoded],
        capture_output=True, timeout=120)
    if r.returncode != 0 or not os.path.exists(out_path):
        err = getattr(r, "stderr", None) or b""
        raise TTSError("Windows 语音合成失败："
                       + err.decode("utf-8", "ignore")[:200])
    return out_path


def speak(text: str, out_path: str, voice: str = "") -> str:
    """合成台词到音频文件；失败抛 TTSError。返回输出路径。"""
    text = (text or "").strip()
    if not text:
        raise TTSError("台词为空")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    p = provider()
    if p == "edge-tts":
        try:
            return _speak_edge(text, out_path, voice)
        except Exception as e:         # noqa: BLE001  网络失败回落本地语音
            if os.name != "nt":
                raise TTSError(f"edge-tts 合成失败：{e}") from e
        return _speak_sapi(text, out_path, voice)
    if p == "sapi":
        return _speak_sapi(text, out_path, voice)
    raise TTSError("没有可用 TTS：建议 pip install edge-tts（免费微软语音）")
