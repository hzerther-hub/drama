# -*- coding: utf-8 -*-
"""媒体工具：图片加载（含 GIF 动画）、音频播放、视频缩略图、外部打开。

优先使用 Pillow（缩放/JPEG/WebP/动图帧）；未安装时退回 tk.PhotoImage
（仅 PNG/GIF）。音频用系统播放器子进程（ffplay/paplay/aplay），
视频用 ffmpeg 抽首帧做缩略图 + 外部播放器打开。
全部零第三方强依赖：缺什么就优雅降级。
"""

from __future__ import annotations
import os
import shutil
import subprocess
import uuid

import config

# Pillow 可选
try:
    from PIL import Image, ImageTk, ImageSequence  # type: ignore
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

IMAGE_EXTS = {".png", ".gif", ".jpg", ".jpeg", ".bmp", ".webp", ".ico",
              ".tif", ".tiff", ".avif", ".heif", ".heic"}
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma",
              ".opus"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv",
              ".m4v", ".ts"}

THUMB_DIR = os.path.join(config.MEDIA_DIR, "thumbs")


def classify(path: str) -> str:
    """按扩展名判断媒体类型：image / audio / video / 其他返回空串。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in VIDEO_EXTS:
        return "video"
    return ""


def file_size_str(path: str) -> str:
    try:
        n = float(os.path.getsize(path))
    except OSError:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


# ---------- 图片 ----------

def load_image(path: str, max_pix: int | None = None):
    """加载图片用于 Tk 显示。

    返回 dict：
      {"photo": ImageTk.PhotoImage|tk.PhotoImage, "frames": [photo...], "delay": [ms...]}
      frames 非空表示 GIF 动画。
    失败抛异常（调用方显示占位文字）。
    """
    import tkinter as tk
    max_pix = max_pix or config.ATTACH_IMAGE_MAX_PIX

    if HAS_PIL:
        img = Image.open(path)
        if getattr(img, "is_animated", False):
            frames, delays = [], []
            for frame in ImageSequence.Iterator(img):
                f = frame.copy()
                f.thumbnail((max_pix, max_pix))
                frames.append(ImageTk.PhotoImage(f))
                d = frame.info.get("duration", 80)
                delays.append(d if isinstance(d, int) and d > 0 else 80)
            return {"photo": frames[0], "frames": frames, "delays": delays}
        img = img.convert("RGBA") if img.mode == "P" else img
        img.thumbnail((max_pix, max_pix))
        return {"photo": ImageTk.PhotoImage(img), "frames": [], "delays": []}

    # 无 Pillow：tk.PhotoImage 仅支持 PNG/GIF（GIF 动画只显示第一帧）
    photo = tk.PhotoImage(file=path)
    zoom = max(1, max(photo.width(), photo.height()) // max_pix)
    if zoom > 1:
        for _ in range(zoom):
            photo = photo.subsample(2, 2)
    return {"photo": photo, "frames": [], "delays": []}


def image_to_data_url(path: str, max_pix: int | None = None) -> str:
    """图片文件 → data:image/...;base64,...（发给识图模型）。

    超过 max_pix 时用 Pillow 等比缩小；Pillow 缺失或转换失败则发原图。
    """
    import base64
    import mimetypes
    max_pix = max_pix or config.ATTACH_IMAGE_MAX_PIX
    data = None
    if HAS_PIL:
        try:
            img = Image.open(path)
            if getattr(img, "is_animated", False):
                img.seek(0)      # 动图取第一帧
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            img.thumbnail((max_pix, max_pix))
            import io
            buf = io.BytesIO()
            fmt = "PNG" if img.has_transparency_data else "JPEG"
            if fmt == "JPEG":
                img = img.convert("RGB")
            img.save(buf, format=fmt)
            data = buf.getvalue()
            mime = "image/png" if fmt == "PNG" else "image/jpeg"
        except Exception:  # noqa: BLE001  转换失败 → 原图直发
            data = None
    if data is None:
        with open(path, "rb") as f:
            data = f.read()
        mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


# ---------- GIF 动画 ----------

class GifAnimator:
    """在 tk.Label 上循环播放 GIF 帧；必须由调用方持有引用防止 GC。"""

    def __init__(self, label, frames, delays):
        self.label = label
        self.frames = frames
        self.delays = delays
        self.idx = 0
        self._after_id = None
        label.configure(image=frames[0])
        self._schedule()

    def _schedule(self):
        if not self.frames:
            return
        delay = self.delays[self.idx % len(self.delays)]
        self._after_id = self.label.after(delay, self._tick)

    def _tick(self):
        if not self.label.winfo_exists():
            return
        self.idx = (self.idx + 1) % len(self.frames)
        self.label.configure(image=self.frames[self.idx])
        self._schedule()

    def stop(self):
        if self._after_id is not None:
            try:
                self.label.after_cancel(self._after_id)
            except Exception:  # noqa: BLE001
                pass
            self._after_id = None


# ---------- 音频 ----------

def find_audio_player(path: str = "") -> list[str]:
    """返回播放该音频文件的完整命令行（按优先级），找不到返回 []。

    Windows：ffplay → PowerShell SoundPlayer（仅 wav，隐藏窗口可停止）
    → cmd start（系统默认播放器，start 后立即返回、无法远程停止）。
    Linux/macOS：paplay → ffplay → aplay → cvlc。
    """
    import sys as _sys
    if _sys.platform == "win32":
        if shutil.which("ffplay"):
            return ["ffplay", "-nodisp", "-autoexit", path]
        if (path.lower().endswith(".wav")
                and shutil.which("powershell") is not None):
            p = path.replace("'", "''")   # PowerShell 单引号转义
            return ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                    "-Command",
                    f"(New-Object Media.SoundPlayer '{p}').PlaySync()"]
        if path:
            return ["cmd", "/c", "start", "", path]
        return []
    for cmd in (["paplay"], ["ffplay", "-nodisp", "-autoexit"],
                ["aplay"], ["cvlc", "--play-and-exit"]):
        exe = shutil.which(cmd[0])
        if exe:
            return cmd + [path] if path else cmd
    return []


class AudioPlayer:
    """封装一次音频播放（子进程），可停止。"""

    def __init__(self, path: str):
        self.path = path
        self.proc: subprocess.Popen | None = None
        self.cmd = find_audio_player(path)

    def play(self) -> bool:
        """开始播放；返回是否成功启动。"""
        if not self.cmd:
            return False
        try:
            self.proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            self.proc = None
            return False

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    @property
    def playing(self) -> bool:
        return self.proc is not None and self.proc.poll() is None


# ---------- 视频 ----------

def _run_quiet(cmd: list[str], timeout: float = 30) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def video_thumbnail(path: str) -> str | None:
    """用 ffmpeg 抽视频第一帧存到媒体目录；失败（或无 ffmpeg）返回 None。"""
    if not has_ffmpeg():
        return None
    os.makedirs(THUMB_DIR, exist_ok=True)
    out = os.path.join(THUMB_DIR, f"{uuid.uuid4().hex[:8]}.png")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", path,
             "-frames:v", "1", "-vf", "scale=480:-1", out],
            capture_output=True, timeout=30)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            return out
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def probe_duration(path: str) -> str:
    """ffprobe 取时长/分辨率（仅展示用，失败返回空串）。"""
    exe = shutil.which("ffprobe")
    if not exe:
        return ""
    try:
        out = _run_quiet([exe, "-v", "error", "-show_entries",
                          "format=duration:stream=width,height,codec_type",
                          "-of", "default=noprint_wrappers=1", path])
    except (subprocess.TimeoutExpired, OSError):
        return ""
    dur, size = "", ""
    for line in out.splitlines():
        if line.startswith("duration="):
            try:
                secs = float(line.split("=", 1)[1])
                m, s = divmod(int(secs), 60)
                dur = f"{m:d}分{s:02d}秒" if m else f"{s}秒"
            except ValueError:
                pass
        elif line.startswith("width=") and not size:
            pass
        elif line.startswith("height=") and not size:
            try:
                h_idx = out.splitlines().index(line)
                w_line = out.splitlines()[h_idx - 1]
                if w_line.startswith("width="):
                    size = f"{w_line.split('=')[1]}x{line.split('=')[1]}"
            except (ValueError, IndexError):
                pass
    parts = [p for p in (size, dur) if p]
    return "，".join(parts)


# ---------- 外部打开 ----------

def external_open(path: str) -> bool:
    """用系统默认程序打开文件（Linux/macOS=xdg-open/open；Windows=os.startfile）。"""
    import sys as _sys
    if _sys.platform == "win32":
        try:
            os.startfile(path)          # noqa: S606  系统默认关联程序打开
            return True
        except OSError:
            return False
    opener = shutil.which("xdg-open") or shutil.which("open")
    if not opener:
        return False
    try:
        subprocess.Popen([opener, path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False
