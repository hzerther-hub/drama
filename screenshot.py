"""WeChat-style interactive screenshot: region select + annotate + save.

Launched by the TUI hotkey (F2) as its own process:

    python -m qwen_cordis.screenshot [--out PATH]

A single borderless overlay freezes the WHOLE virtual desktop (the union of
every attached monitor), so any region on any screen can be captured —
including regions that span monitors; nothing here assumes a primary /
secondary pair. The user drags a region — WeChat-style: resizable via
corner/edge handles, movable, live size label — then annotates on it
(rectangle / ellipse / straight line / arrow / text / pen / mosaic), and
Enter (or the ✔ button) saves the cropped PNG to the temp dir and prints
its path on stdout. ESC cancels:
empty stdout, exit 0. The TUI reads that path and inserts it into the
composer so the next submit routes the image to the vision flow
(``vision.extract_image_refs`` recognises the quoted path).

Annotations are screen-pinned (WeChat semantics): their vectors are stored in
absolute screen coordinates and translated into the crop only at save time,
so adjusting or even re-dragging the selection after annotating never
detaches or loses them. (Caveat: on mixed-DPI multi-monitor setups tk may
scale a window spanning monitors by one monitor's factor; equal-scale setups
map 1:1.)

tkinter + Pillow are imported lazily so importing this module never breaks a
headless environment; :func:`available` reports whether the tool can run.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

_ARROW_HEAD_RATIO = 0.42  # half-width of the arrowhead vs its length


def available() -> bool:
    """True when tkinter + Pillow's ImageTk are importable (tool can run)."""
    try:
        import tkinter  # noqa: F401
        from PIL import Image, ImageTk  # noqa: F401
    except Exception:  # noqa: BLE001 - any missing tk/Tcl runtime
        return False
    return True


# ---------------- monitors ----------------


def monitors() -> list[tuple[int, int, int, int]]:
    """Bounding boxes of the attached monitors as ``(x, y, w, h)``.

    Windows enumerates via ``EnumDisplayMonitors`` (negative coordinates are
    real: a secondary left of/above the primary); anywhere else a single
    primary entry from a probe grab. Always at least one box.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _MONITORINFOEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                    ("szDevice", wintypes.WCHAR * 32),
                ]

            user32 = ctypes.windll.user32
            boxes: list[tuple[int, int, int, int]] = []
            proto = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
            )

            @proto
            def _cb(hmon, _hdc, _rect, _lparam):  # noqa: N803 - WinAPI naming
                info = _MONITORINFOEXW()
                info.cbSize = ctypes.sizeof(_MONITORINFOEXW)
                if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                    r = info.rcMonitor
                    boxes.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                return True

            if user32.EnumDisplayMonitors(None, None, _cb, 0) and boxes:
                return boxes
        except Exception:  # noqa: BLE001 - fall through to the probe
            pass
    from PIL import ImageGrab

    try:
        w, h = ImageGrab.grab().size
        if w > 0 and h > 0:
            return [(0, 0, w, h)]
    except Exception:  # noqa: BLE001 - no display / cannot read pixels
        pass
    # Headless / remote session where the X grab fails (e.g. ``X get_image
    # failed``): fall back to a default desktop box so the overlay still
    # launches and a user can select/annotate rather than crashing at init.
    return [(0, 0, 1920, 1080)]


def _linux_backend_grab(png_path: str) -> bool:
    """用系统截图工具抓全屏到 png_path（按操作系统选择方案）。"""
    import shutil
    import subprocess
    candidates = [
        ("import", ["import", "-window", "root", png_path]),
        ("scrot", ["scrot", png_path]),
        ("maim", ["maim", png_path]),
        ("gnome-screenshot", ["gnome-screenshot", "-f", png_path]),
        ("grim", ["grim", png_path]),
    ]
    for name, cmd in candidates:
        if shutil.which(name):
            try:
                subprocess.run(cmd, check=True, timeout=15,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:            # noqa: BLE001 换下一个工具
                continue
    return False


def _grab_box(box: tuple[int, int, int, int]):
    """按操作系统抓屏：Windows/macOS 用 PIL（all_screens），Linux 优先系统工具，
    失败回退 PIL，最后兜底空图（保证覆盖层能启动，不崩溃）。"""
    from PIL import Image, ImageGrab
    from pathlib import Path
    import tempfile

    if sys.platform.startswith("linux"):
        tmp = tempfile.mktemp(suffix=".png")
        if _linux_backend_grab(tmp) and Path(tmp).exists():
            try:
                img = Image.open(tmp).convert("RGB")
                return img.crop(box) if box and (box[0] or box[1]) else img
            except Exception:            # noqa: BLE001
                pass
    try:
        return ImageGrab.grab(bbox=box, all_screens=sys.platform == "win32")
    except Exception:            # noqa: BLE001 - Wayland/X11 抓不到
        pass
    # 兜底空图：覆盖层照常启动，用户仍可框选/标注（背景黑色）
    try:
        return Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (20, 20, 20))
    except Exception:            # noqa: BLE001
        return None


def virtual_box(boxes: list[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    """Union ``(x, y, w, h)`` of all monitor boxes — the virtual desktop.

    One overlay over this box makes every screen capturable at once and lets
    a selection cross monitor boundaries (no primary/secondary assumption).
    """
    left = min(b[0] for b in boxes)
    top = min(b[1] for b in boxes)
    right = max(b[0] + b[2] for b in boxes)
    bottom = max(b[1] + b[3] for b in boxes)
    return (left, top, right - left, bottom - top)


# ---------------- pure geometry / rendering (unit-testable) ----------------


def _arrow_head(p1: tuple[float, float], p2: tuple[float, float], width: int) -> list[tuple[float, float]]:
    """Triangle polygon for the head of an arrow drawn from ``p1`` to ``p2``.

    The head length scales with the stroke width (WeChat-like weight) and
    points along the shaft direction.
    """
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    ux, uy = (dx / length, dy / length) if length > 1e-6 else (0.0, -1.0)
    h = max(12.0, width * 4.0)
    bx, by = x2 - ux * h, y2 - uy * h  # base center, pulled back along the shaft
    nx, ny = -uy, ux
    half = h * _ARROW_HEAD_RATIO
    return [(x2, y2), (bx + nx * half, by + ny * half), (bx - nx * half, by - ny * half)]


def _load_font(size: int):
    """A TTF font for the saved image, falling back to Pillow's bitmap one."""
    from PIL import ImageFont

    for name in ("msyh.ttc", "simhei.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:  # noqa: BLE001 - try the next candidate
            continue
    return ImageFont.load_default()


def draw_shapes(draw, shapes: list[dict], *, font_size: int = 18) -> None:
    """Render annotation vectors onto a PIL ``ImageDraw`` (crop coords).

    ``shapes`` entries are dicts with ``tool`` in {rect, ellipse, line,
    arrow, pen, text} and tool-specific geometry, produced by
    :class:`ShotOverlay`. Pure function: the same vectors preview on the
    tkinter Canvas and land in the saved PNG. ``mosaic`` shapes need pixel
    access and are handled by :func:`render_annotated`, not here.
    """
    for s in shapes:
        tool, color, width = s["tool"], s["color"], s.get("width", 4)
        pts = s["pts"]
        if tool == "rect":
            (x0, y0), (x1, y1) = pts
            draw.rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], outline=color, width=width)
        elif tool == "ellipse":
            (x0, y0), (x1, y1) = pts
            draw.ellipse([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], outline=color, width=width)
        elif tool == "line":
            (x0, y0), (x1, y1) = pts
            draw.line([x0, y0, x1, y1], fill=color, width=width)
        elif tool == "arrow":
            (x0, y0), (x1, y1) = pts
            draw.line([x0, y0, x1, y1], fill=color, width=width)
            draw.polygon(_arrow_head((x0, y0), (x1, y1), width), fill=color)
        elif tool == "pen":
            draw.line(pts, fill=color, width=width, joint="curve")
        elif tool == "text":
            x, y = pts[0]
            draw.text((x, y), s["text"], fill=color, font=_load_font(font_size))


_MOSAIC_BRUSH = 20  # stroke diameter, px — chunky enough to read as blocks
_MOSAIC_BLOCK = 10  # pixelation cell size, px


def _mosaic_stroke(crop, pts: list[tuple[int, int]], brush: int = _MOSAIC_BRUSH):
    """Pixelate the crop along a stroke (WeChat 马赛克). ``pts`` are crop coords."""
    from PIL import Image, ImageDraw

    w, h = crop.size
    if not pts:
        return crop
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).line(
        [v for pt in pts for v in pt], fill=255, width=max(2, brush), joint="curve")
    small = crop.resize((max(1, w // _MOSAIC_BLOCK), max(1, h // _MOSAIC_BLOCK)), Image.BILINEAR)
    pixelated = small.resize((w, h), Image.NEAREST)
    out = crop.copy()
    out.paste(pixelated, (0, 0), mask)
    return out


def render_annotated(img, sel: tuple[int, int, int, int], shapes: list[dict], *, font_size: int = 18):
    """Crop ``sel`` from ``img`` and composite the ABSOLUTE-coord ``shapes``.

    Pure save path (unit-tested): shape vectors live in screen coordinates,
    so the selection can be moved or re-dragged after annotating — the
    translation into crop coordinates happens here, at save time, from the
    FINAL selection. Shapes outside the crop are clipped by the overlay.
    """
    from PIL import Image, ImageDraw

    x1, y1, x2, y2 = [int(v) for v in sel]
    crop = img.crop((x1, y1, x2, y2)).convert("RGBA")
    vectors: list[dict] = []
    for s in shapes:
        rel_pts = [(x - x1, y - y1) for x, y in s["pts"]]
        if s["tool"] == "mosaic":
            crop = _mosaic_stroke(crop, rel_pts).convert("RGBA")
        else:
            vectors.append({**s, "pts": rel_pts})
    overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    draw_shapes(ImageDraw.Draw(overlay), vectors, font_size=font_size)
    return Image.alpha_composite(crop, overlay).convert("RGB")


# ---------------- subprocess wrapper (used by the TUI) ----------------


def capture(*, timeout: float = 300.0) -> str | None:
    """Run the interactive overlay; return the saved PNG path, else ``None``.

    Runs ``python -m qwen_cordis.screenshot`` in its own process (tkinter's
    mainloop must not share the TUI's asyncio loop). Returns ``None`` on ESC,
    on any launch failure, or on timeout — callers show a notice, never crash.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "screenshot"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = (proc.stdout or "").strip()
    if not out and proc.stderr:
        # No screenshot AND the child complained: keep the tail for diagnosis
        # (overlay crash, ImageGrab failure…) so support can read it back.
        try:
            import tempfile

            log = Path(tempfile.gettempdir()) / "qwen-cordis-shot-error.log"
            log.write_text(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} exit={proc.returncode}\n{proc.stderr[-2000:]}\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    return out.splitlines()[0] if out else None


def annotate_image(image_path: str, *, timeout: float = 300.0) -> str | None:
    """在独立进程里对已存在的图片做标注（qwen-cordis 风格），返回保存路径；取消返回 None。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "screenshot", "--image", image_path],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = (proc.stdout or "").strip()
    return out.splitlines()[0] if out else None


def _last_error_log() -> str | None:
    """Return the most recent child stderr tail (from a failed capture), else ``None``."""
    try:
        log = Path(tempfile.gettempdir()) / "qwen-cordis-shot-error.log"
        if not log.is_file():
            return None
        return (log.read_text(encoding="utf-8") or "").strip() or None
    except OSError:
        return None


def failure_notice() -> str:
    """A human message for when :func:`capture` returned no path.

    Tries to distinguish a genuinely broken display (which is a bug worth
    reporting) from the user pressing ESC. The lazy import keeps the TUI import
    from pulling tkinter/PIL.
    """
    tail = _last_error_log() or ""
    if any(bad in tail for bad in ("X get_image failed", "Invalid MIT-MAGIC-COOKIE", "cannot open display")):
        return "(截图未完成：无法读取屏幕，当前可能为无显示/远程会话)"
    if any(word in tail.lower() for word in ("tk", "display")):
        return f"(截图未完成：无法显示选区 {tail.splitlines()[-1][:60]})"
    return "(截图未完成：已取消，或截图进程启动失败)"


# ---------------- the overlay app ----------------


class ShotOverlay:
    """Fullscreen select-and-annotate overlay (call :meth:`run`).

    Kept deliberately framework-thin: every geometry decision lives in
    module-level pure functions so the rendering math is testable without a
    display; this class only wires tkinter events to those decisions.
    """

    HANDLE = 7  # hit radius for corner/edge handles, px
    MIN_SEL = 12  # a drag smaller than this is a click, not a selection
    TWO_POINT = ("rect", "ellipse", "line", "arrow")  # press → drag → release
    STROKE = ("pen", "mosaic")  # freehand paths collected point by point

    def __init__(self, *, out: str | None = None, boxes: list | None = None,
                 image: str | None = None) -> None:
        import tkinter as tk
        from PIL import Image, ImageTk

        self.out = out
        self.tk = tk
        if image:
            # 标注已有的截图（Linux：portal 截好图后弹此界面标注/确认）
            self.img = Image.open(image).convert("RGB")
            self.box = (0, 0, self.img.width, self.img.height)
        else:
            # one overlay over the union of ALL monitors: any screen is
            # capturable and a selection may cross monitor boundaries
            self.box = virtual_box(list(boxes) if boxes else monitors())
            self.img = _grab_box(self.box).convert("RGB")

        black = Image.new("RGB", self.img.size, (0, 0, 0))
        self.dimmed = Image.blend(self.img, black, 0.45)

        w, h = self.img.size
        bx, by = self.box[0], self.box[1]
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry(f"{w}x{h}+{bx}+{by}")
        self.root.attributes("-topmost", True)
        self.canvas = tk.Canvas(self.root, width=w, height=h, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        self._photo_dim = ImageTk.PhotoImage(self.dimmed, master=self.root)
        self.canvas.create_image(0, 0, image=self._photo_dim, anchor="nw")
        self._bright: list = []  # keep refs alive or tk gc's the photos

        # state
        self.sel: tuple[int, int, int, int] | None = None  # x1, y1, x2, y2 sorted
        self.action: tuple | None = None  # ("new",ax,ay) | ("move",dx,dy) | ("resize",fx,fy)
        self.tool: str | None = None  # rect / arrow / text / pen once chosen
        self.color = "#ff2e2e"
        self.pen_width = 4
        self.shapes: list[dict] = []  # screen-pinned vectors, ABSOLUTE coords
        self._undo: list[list[int]] = []  # canvas item ids per committed shape
        self._redo: list[dict] = []  # undone shape vectors, newest last
        self._preview_ids: list[int] = []
        self._shape_start: tuple[int, int] | None = None
        self._pen_pts: list[tuple[int, int]] = []
        self._pending_text = None  # (x, y, entry, window item id)
        self._sel_ids: list[int] = []

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Return>", self._on_enter)

        self._build_toolbar()
        self._hint_id = self.canvas.create_text(
            w // 2, 28, text="", fill="#ffffff", font=("Microsoft YaHei", 12))
        self._update_hint()

    def _update_hint(self) -> None:
        self.canvas.itemconfigure(
            self._hint_id, text="拖动选择区域（可跨屏） · 工具标注 · 回车保存 · ESC 取消")

    # -- toolbar ---------------------------------------------------------

    def _build_toolbar(self) -> None:
        tk = self.tk
        self.bar = tk.Frame(self.root, bg="#2b2b2b", bd=1, relief="solid")
        tools = (
            ("▭ 框形", "rect"), ("◯ 椭圆", "ellipse"), ("／ 直线", "line"),
            ("➶ 箭头", "arrow"), ("Ｔ 文字", "text"), ("✎ 画笔", "pen"),
            ("▦ 马赛克", "mosaic"),
        )
        for label, tool in tools:
            b = tk.Button(self.bar, text=label, command=lambda t=tool: self._pick_tool(t),
                          bg="#2b2b2b", fg="#eeeeee", activebackground="#4a4a4a",
                          activeforeground="#ffffff", relief="flat", bd=0, padx=8, pady=4,
                          font=("Microsoft YaHei", 10))
            b.pack(side="left")
        for c in ("#ff2e2e", "#ff9500", "#ffd60a", "#30d158", "#0a84ff", "#ffffff", "#000000"):
            tk.Button(self.bar, text=" ", bg=c, width=2, bd=0, relief="flat",
                      activebackground=c, command=lambda col=c: self._pick_color(col)).pack(side="left", padx=1)
        tk.Button(self.bar, text="⭯ 撤销", command=self._undo_shape, bg="#2b2b2b", fg="#eeeeee",
                  relief="flat", bd=0, padx=8, pady=4, font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Button(self.bar, text="⭰ 重做", command=self._redo_shape, bg="#2b2b2b", fg="#eeeeee",
                  relief="flat", bd=0, padx=8, pady=4, font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Button(self.bar, text="✔ 完成", command=self._save, bg="#0a84ff", fg="#ffffff",
                  relief="flat", bd=0, padx=10, pady=4, font=("Microsoft YaHei", 10, "bold")).pack(side="left", padx=(8, 2))
        tk.Button(self.bar, text="✖ 退出", command=self.root.destroy, bg="#2b2b2b", fg="#ff6b6b",
                  relief="flat", bd=0, padx=8, pady=4, font=("Microsoft YaHei", 10)).pack(side="left")

    def _pick_tool(self, tool: str) -> None:
        self.tool = None if self.tool == tool else tool

    def _pick_color(self, color: str) -> None:
        self.color = color

    def _place_bar(self) -> None:
        if self.sel is None:
            self.bar.place_forget()
            return
        x1, y1, x2, y2 = self.sel
        self.bar.update_idletasks()
        bw, bh = self.bar.winfo_reqwidth(), self.bar.winfo_reqheight()
        bx = min(max((x1 + x2 - bw) // 2, 4), self.img.size[0] - bw - 4)
        by = y2 + 8 if y2 + 8 + bh < self.img.size[1] else y1 - bh - 8
        self.bar.place(x=bx, y=max(by, 4))

    # -- selection -------------------------------------------------------

    def _inside(self, x: int, y: int) -> bool:
        return self.sel is not None and self.sel[0] <= x <= self.sel[2] and self.sel[1] <= y <= self.sel[3]

    def _hit_edges(self, x: int, y: int) -> list[str]:
        """Which selection edges (l/r/t/b) the point is grabbing, if any."""
        if self.sel is None:
            return []
        x1, y1, x2, y2 = self.sel
        h = self.HANDLE
        if not (x1 - h <= x <= x2 + h and y1 - h <= y <= y2 + h):
            return []
        return [
            e for near, e in (
                (x1 + h >= x >= x1 - h, "l"),
                (x2 - h <= x <= x2 + h, "r"),
                (y1 + h >= y >= y1 - h, "t"),
                (y2 - h <= y <= y2 + h, "b"),
            ) if near
        ]

    def _on_press(self, event) -> None:
        x, y = event.x, event.y
        if self._pending_text is not None:
            self._commit_text()
            return  # this click only dismissed the text entry
        edges = self._hit_edges(x, y)
        if edges:
            fx = self.sel[2] if "l" in edges else (self.sel[0] if "r" in edges else None)
            fy = self.sel[3] if "t" in edges else (self.sel[1] if "b" in edges else None)
            self.action = ("resize", fx, fy)
        elif self._inside(x, y) and self.tool:
            if self.tool == "text":
                self._start_text(x, y)
            else:
                self._shape_start = (x, y)
                if self.tool in self.STROKE:
                    self._pen_pts = [(x, y)]
        elif self._inside(x, y):
            self.action = ("move", x - self.sel[0], y - self.sel[1])
        else:
            # A fresh drag re-selects from scratch. Annotations are
            # screen-pinned: they stay put and are simply cropped by the
            # final selection at save time — never silently discarded.
            self.action = ("new", x, y)
            self._hide_sel()
            self.sel = None

    def _on_drag(self, event) -> None:
        x, y = event.x, event.y
        if self._shape_start is not None and self.tool in self.TWO_POINT:
            self._redraw_preview((x, y))
        elif self.tool in self.STROKE and self._pen_pts:
            self._pen_pts.append((x, y))
            self._redraw_preview((x, y))
        elif self.action:
            kind = self.action[0]
            if kind == "new":
                _, ax, ay = self.action
                self.sel = (min(ax, x), min(ay, y), max(ax, x), max(ay, y))
            elif kind == "move" and self.sel:
                _, dx, dy = self.action
                x1, y1, x2, y2 = self.sel
                w, h = x2 - x1, y2 - y1
                nx1 = min(max(x - dx, 0), self.img.size[0] - w)
                ny1 = min(max(y - dy, 0), self.img.size[1] - h)
                self.sel = (nx1, ny1, nx1 + w, ny1 + h)
            elif kind == "resize" and self.sel:
                _, fx, fy = self.action
                x1, y1, x2, y2 = self.sel
                if fx is not None:
                    x1, x2 = min(fx, x), max(fx, x)
                if fy is not None:
                    y1, y2 = min(fy, y), max(fy, y)
                self.sel = (x1, y1, x2, y2)
            self._refresh_sel()

    def _on_release(self, event) -> None:
        if self._shape_start is not None:
            self._commit_shape((event.x, event.y))
            return
        if self.action and self.action[0] == "new" and self.sel:
            x1, y1, x2, y2 = self.sel
            if x2 - x1 < self.MIN_SEL or y2 - y1 < self.MIN_SEL:
                self._hide_sel()  # click, not a drag: back to selecting
                self.sel = None
        self.action = None
        self._refresh_sel()

    def _hide_sel(self) -> None:
        for i in self._sel_ids:
            self.canvas.delete(i)
        self._sel_ids = []
        self._bright = []
        self.bar.place_forget()

    def _refresh_sel(self) -> None:
        from PIL import ImageTk

        self._hide_sel()
        if self.sel is None:
            return
        x1, y1, x2, y2 = [int(v) for v in self.sel]
        if x2 - x1 < 2 or y2 - y1 < 2:
            return
        # bright (undimmed) crop under the selection
        photo = ImageTk.PhotoImage(self.img.crop((x1, y1, x2, y2)), master=self.root)
        self._bright = [photo]
        self._sel_ids.append(self.canvas.create_image(x1, y1, image=photo, anchor="nw"))
        # re-raising keeps screen-pinned annotations visible above the
        # freshly recreated (opaque) bright crop; the border/handles are
        # created after this and so still sit on top of everything
        for ids in self._undo:
            for i in ids:
                self.canvas.tag_raise(i)
        self._sel_ids.append(self.canvas.create_rectangle(
            x1, y1, x2, y2, outline="#ff2e2e", width=2))
        # handles: corners + edge midpoints
        xm, ym = (x1 + x2) // 2, (y1 + y2) // 2
        for hx, hy in ((x1, y1), (xm, y1), (x2, y1), (x1, ym), (x2, ym), (x1, y2), (xm, y2), (x2, y2)):
            self._sel_ids.append(self.canvas.create_rectangle(
                hx - 4, hy - 4, hx + 4, hy + 4, fill="#0a84ff", outline="#ffffff"))
        label = f"{x2 - x1} × {y2 - y1}"
        ly = y1 - 14 if y1 - 14 > 4 else y2 + 14
        self._sel_ids.append(self.canvas.create_text(
            (x1 + x2) // 2, ly, text=label, fill="#ffffff", font=("Microsoft YaHei", 10)))
        self._place_bar()

    # -- annotation ------------------------------------------------------

    def _clamp(self, x: int, y: int) -> tuple[int, int]:
        if self.sel is None:
            return x, y
        x1, y1, x2, y2 = self.sel
        return min(max(x, x1), x2), min(max(y, y1), y2)

    def _redraw_preview(self, at: tuple[int, int]) -> None:
        c = self.canvas
        for i in self._preview_ids:
            c.delete(i)
        self._preview_ids = []
        if self.tool in self.STROKE:
            flat = [v for pt in self._pen_pts for v in pt]
            if self.tool == "mosaic":
                # gray blocks hint at the pixelation the save applies
                self._preview_ids.append(c.create_line(
                    flat, fill="#a0a0a0", width=_MOSAIC_BRUSH, smooth=True, stipple="gray50"))
            else:
                self._preview_ids.append(c.create_line(
                    flat, fill=self.color, width=self.pen_width, smooth=True))
            return
        x0, y0 = self._shape_start
        x1, y1 = self._clamp(*at)
        if self.tool == "rect":
            self._preview_ids.append(c.create_rectangle(x0, y0, x1, y1, outline=self.color, width=self.pen_width))
        elif self.tool == "ellipse":
            self._preview_ids.append(c.create_oval(x0, y0, x1, y1, outline=self.color, width=self.pen_width))
        elif self.tool == "line":
            self._preview_ids.append(c.create_line(x0, y0, x1, y1, fill=self.color, width=self.pen_width))
        elif self.tool == "arrow":
            self._preview_ids.append(c.create_line(x0, y0, x1, y1, fill=self.color, width=self.pen_width))
            head = _arrow_head((x0, y0), (x1, y1), self.pen_width)
            self._preview_ids.append(c.create_polygon(head, fill=self.color))

    def _canvas_ids_for(self, s: dict) -> list[int]:
        """Canvas items for a committed shape vector (ABSOLUTE coords)."""
        c = self.canvas
        tool, color, width, pts = s["tool"], s["color"], s.get("width", 4), s["pts"]
        if tool == "rect":
            (x0, y0), (x1, y1) = pts
            return [c.create_rectangle(x0, y0, x1, y1, outline=color, width=width)]
        if tool == "ellipse":
            (x0, y0), (x1, y1) = pts
            return [c.create_oval(x0, y0, x1, y1, outline=color, width=width)]
        if tool == "line":
            (x0, y0), (x1, y1) = pts
            return [c.create_line(x0, y0, x1, y1, fill=color, width=width)]
        if tool == "arrow":
            (x0, y0), (x1, y1) = pts
            return [
                c.create_line(x0, y0, x1, y1, fill=color, width=width),
                c.create_polygon(_arrow_head((x0, y0), (x1, y1), width), fill=color),
            ]
        if tool == "pen":
            return [c.create_line([v for pt in pts for v in pt], fill=color, width=width, smooth=True)]
        if tool == "mosaic":
            return [c.create_line([v for pt in pts for v in pt], fill="#a0a0a0",
                                  width=_MOSAIC_BRUSH, smooth=True, stipple="gray50")]
        if tool == "text":
            return [c.create_text(pts[0], text=s["text"], fill=color, anchor="nw",
                                  font=("Microsoft YaHei", 12))]
        return []

    def _commit_shape(self, at: tuple[int, int]) -> None:
        for i in self._preview_ids:
            self.canvas.delete(i)
        self._preview_ids = []
        if self.tool in self.STROKE:
            pts = self._pen_pts
            self._pen_pts = []
            self._shape_start = None
            if len(pts) < 2:
                return
            shape = {"tool": self.tool, "color": self.color, "width": self.pen_width, "pts": list(pts)}
        else:
            x0, y0 = self._shape_start
            x1, y1 = self._clamp(*at)
            self._shape_start = None
            if abs(x1 - x0) < 3 and abs(y1 - y0) < 3:
                return
            shape = {"tool": self.tool, "color": self.color, "width": self.pen_width,
                     "pts": [(x0, y0), (x1, y1)]}
        # screen-pinned vectors: ABSOLUTE coords, translated to the crop
        # only inside render_annotated at save time
        self.shapes.append(shape)
        self._redo.clear()  # a fresh edit invalidates the redo branch
        self._undo.append(self._canvas_ids_for(shape))

    def _start_text(self, x: int, y: int) -> None:
        tk = self.tk
        entry = tk.Entry(self.root, bg="#333333", fg="#ffffff", insertbackground="#ffffff",
                         relief="flat", font=("Microsoft YaHei", 12), width=24)
        win = self.canvas.create_window(x, y, window=entry, anchor="nw")
        entry.focus_set()
        self._pending_text = (x, y, entry, win)
        entry.bind("<Return>", lambda e: (self._commit_text(), "break")[1])
        entry.bind("<Escape>", lambda e: (self._destroy_text(), "break")[1])

    def _destroy_text(self) -> None:
        if self._pending_text:
            self.canvas.delete(self._pending_text[3])
            self._pending_text[2].destroy()
            self._pending_text = None

    def _commit_text(self) -> None:
        if not self._pending_text:
            return
        x, y, entry, win = self._pending_text
        text = entry.get().strip()
        self._destroy_text()
        if not text:
            return
        shape = {"tool": "text", "color": self.color, "text": text, "pts": [(x, y)]}
        self.shapes.append(shape)
        self._redo.clear()
        self._undo.append(self._canvas_ids_for(shape))

    def _undo_shape(self) -> None:
        if not self._undo:
            return
        for i in self._undo.pop():
            self.canvas.delete(i)
        if self.shapes:
            self._redo.append(self.shapes.pop())

    def _redo_shape(self) -> None:
        if not self._redo:
            return
        shape = self._redo.pop()
        self.shapes.append(shape)
        self._undo.append(self._canvas_ids_for(shape))

    # -- save / run ------------------------------------------------------

    def _on_enter(self, _event) -> None:
        if self._pending_text is not None:
            return  # the focused entry commits the text itself
        if self.sel is not None:
            self._save()

    def _save(self) -> None:
        if self.sel is None:
            return
        out = render_annotated(self.img, self.sel, self.shapes)

        if self.out:
            path = self.out
        else:
            import os
            import tempfile

            stamp = time.strftime("%Y%m%d-%H%M%S")
            path = str(Path(tempfile.gettempdir()) / f"qwen-cordis-shot-{stamp}.png")
        out.save(path, format="PNG")
        print(path, flush=True)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def _ensure_dpi_aware() -> None:
    """Make the process DPI-aware so tk coords == ImageGrab pixels (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
        except Exception:  # noqa: BLE001 - older Windows
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001 - best-effort only
        pass


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="qwen-cordis interactive screenshot")
    parser.add_argument("--out", default=None, help="save path (default: temp dir PNG)")
    parser.add_argument("--image", default=None, help="annotate this image instead of grabbing the screen")
    args = parser.parse_args(argv)

    _ensure_dpi_aware()
    ShotOverlay(out=args.out, image=args.image).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def portal_capture(timeout: int = 120) -> str | None:
    """XDG Desktop Portal 截图（系统交互选择器，走合成器真抓屏）。

    返回保存的图片路径；未选择/失败返回 None。适用于 Wayland/GNOME。
    """
    if sys.platform.startswith("win32"):
        return None          # Windows 用 PIL 原生即可
    try:
        import dbus
        import dbus.mainloop.glib
        from gi.repository import GLib
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        portal = bus.get_object("org.freedesktop.portal.Desktop",
                                "/org/freedesktop/portal/desktop")
        ss = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")
        token = "shot_%d" % int(time.time() * 1000)
        req_path = ss.Screenshot(
            "", {"interactive": dbus.Boolean(True),
                 "modal": dbus.Boolean(True),
                 "handle_token": token})
        result = {"path": None}
        loop = GLib.MainLoop()

        def _on_response(*args):
            import sys
            # portal Request.Response 信号：各实现参数顺序不同（results/error 或 handle/results），
            # 扫描所有参数找含 'uri' 的 dict，与顺序无关。
            uri = ""
            for a in args:
                if isinstance(a, dict):
                    u = a.get("uri")
                    if u:
                        uri = str(u)
                        break
                elif isinstance(a, (list, tuple)):
                    for x in a:
                        if isinstance(x, dict) and x.get("uri"):
                            uri = str(x["uri"])
                            break
                    if uri:
                        break
            print("DBG portal Response: uri=%r args=%d" % (uri, len(args)), file=sys.stderr)
            if uri.startswith("file://"):
                from urllib.parse import unquote
                result["path"] = unquote(uri[7:])
            if loop.is_running():
                loop.quit()

        bus.add_signal_receiver(_on_response, signal_name="Response",
                                dbus_interface="org.freedesktop.portal.Request",
                                path=req_path, bus_name="org.freedesktop.portal.Desktop")
        # 单线程 GLib 主循环，直到收到 Response 或超时
        import threading
        def _timeout():
            if loop.is_running():
                loop.quit()
        threading.Timer(timeout, _timeout).start()
        loop.run()
        return result["path"]
    except Exception:            # noqa: BLE001
        return None


def grab_fullscreen() -> str | None:
    """抓全屏（Windows/macOS 用 PIL ImageGrab all_screens）到临时 PNG，返回路径。"""
    from PIL import ImageGrab
    import tempfile
    import os
    try:
        img = ImageGrab.grab(all_screens=sys.platform == "win32")
    except Exception:            # noqa: BLE001 - 无显示/远程
        return None
    fd, p = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.convert("RGB").save(p)
    except Exception:            # noqa: BLE001
        return None
    return p
