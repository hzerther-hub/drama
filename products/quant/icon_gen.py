# -*- coding: utf-8 -*-
"""量化产品图标生成器（纯 Python 零依赖，不依赖 Pillow）。

画布 256x256 透明底 + 蓝色圆角底 + 上升 K 线 + 白色上行箭头。
产出一份 PNG（Tk 窗口 iconphoto 用）与一份 ICO（Windows 打包 exe 用，
256x256 PNG 压缩条目，Vista+ 原生支持）。

用法：python products/quant/icon_gen.py  → 生成 assets/quant_icon.{png,ico}
这是开发期工具，运行时不导入。
"""

from __future__ import annotations

import os
import struct
import zlib

S = 256
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# 调色板
BLUE = (37, 99, 235)          # #2563eb 主蓝
GREEN = (34, 197, 94)         # #22c55e 上涨
RED = (239, 68, 68)           # #ef4444 下跌
WHITE = (255, 255, 255)

buf = bytearray(S * S * 4)    # RGBA，初始全透明


def set_px(x: int, y: int, color: tuple[int, int, int], alpha: int = 255):
    if 0 <= x < S and 0 <= y < S:
        i = (y * S + x) * 4
        buf[i:i + 4] = bytes((color[0], color[1], color[2], alpha))


def fill_rect(x0: int, y0: int, x1: int, y1: int, color, alpha: int = 255):
    for y in range(max(0, y0), min(S, y1)):
        for x in range(max(0, x0), min(S, x1)):
            set_px(x, y, color, alpha)


def _rrect_inside(x, y, x0, y0, x1, y1, r):
    """圆角矩形命中测试：角点用半径圆判定，其余为矩形内部。"""
    dx = 0
    dy = 0
    if x < x0 + r:
        dx = x0 + r - x
    elif x >= x1 - r:
        dx = x - (x1 - r - 1)
    if y < y0 + r:
        dy = y0 + r - y
    elif y >= y1 - r:
        dy = y - (y1 - r - 1)
    if dx and dy:
        return dx * dx + dy * dy <= r * r
    return True


def fill_rrect(x0, y0, x1, y1, r, color, alpha=255):
    for y in range(max(0, y0), min(S, y1)):
        for x in range(max(0, x0), min(S, x1)):
            if _rrect_inside(x, y, x0, y0, x1, y1, r):
                set_px(x, y, color, alpha)


def fill_circle(cx, cy, rad, color, alpha=255):
    r2 = rad * rad
    for y in range(int(cy - rad), int(cy + rad) + 1):
        for x in range(int(cx - rad), int(cx + rad) + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                set_px(x, y, color, alpha)


def fill_triangle(p0, p1, p2, color, alpha=255):
    """按重心/符号法填充三角形（含闭包）。"""
    ax, ay = p0
    bx, by = p1
    cx_, cy_ = p2
    xs = [ax, bx, cx_]
    ys = [ay, by, cy_]

    def _sign(px, py, qx, qy, rx, ry):
        return (px - rx) * (qy - ry) - (qx - rx) * (py - ry)

    for y in range(max(0, min(ys)), min(S, max(ys) + 1)):
        for x in range(max(0, min(xs)), min(S, max(xs) + 1)):
            d1 = _sign(x, y, ax, ay, bx, by)
            d2 = _sign(x, y, bx, by, cx_, cy_)
            d3 = _sign(x, y, cx_, cy_, ax, ay)
            has_neg = d1 < 0 or d2 < 0 or d3 < 0
            has_pos = d1 > 0 or d2 > 0 or d3 > 0
            if not (has_neg and has_pos):
                set_px(x, y, color, alpha)


def draw_line(x0, y0, x1, y1, color, thick=12, alpha=255):
    """沿直线离散采样、每点画实心圆，得到圆头粗线。"""
    steps = max(abs(x1 - x0), abs(y1 - y0))
    steps = max(1, steps)
    r = thick / 2
    for i in range(steps + 1):
        t = i / steps
        fill_circle(round(x0 + (x1 - x0) * t),
                    round(y0 + (y1 - y0) * t), r, color, alpha)


# ---- 1. 蓝色圆角底 ----
fill_rrect(6, 6, S - 6, S - 6, 40, BLUE)

# ---- 2. 四根 K 线（左低右高，整体上行）----
# (cx, 是否上涨, 最高价, 最低价, 实体上沿, 实体下沿)
candles = [
    (62, True,  150, 212, 172, 200),
    (112, False, 122, 178, 136, 158),
    (162, True,  92,  162, 108, 144),
    (212, True,  62,  130, 78,  108),
]
body_w = 26
wick_w = 8
for cx, up, hi, lo, top, bot in candles:
    color = GREEN if up else RED
    # 影线（高-低 细线）
    fill_rect(cx - wick_w // 2, hi, cx + wick_w // 2 + 1, lo + 1, color)
    # 实体（开-收 粗柱）
    fill_rect(cx - body_w // 2, min(top, bot),
              cx + body_w // 2 + 1, max(top, bot) + 1, color)

# ---- 3. 白色上行箭头（顶右，成长信号）----
draw_line(140, 130, 208, 62, WHITE, thick=12)
fill_triangle((240, 34), (223, 75), (199, 49), WHITE)


# ---- PNG 编码（8-bit RGBA，无滤波）----
def _chunk(typ: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


def png_bytes(w: int, h: int, pixels: bytearray) -> bytes:
    raw = b"".join(b"\x00" + pixels[y * w * 4:(y + 1) * w * 4]
                   for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


def ico_bytes(png: bytes) -> bytes:
    """ICO：单一 256x256 PNG 压缩条目（bWidth/bHeight 取 0 表示 256）。"""
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 6 + 16)
    return header + entry + png


def main():
    os.makedirs(ASSET_DIR, exist_ok=True)
    pixels = bytes(buf)
    png = png_bytes(S, S, bytearray(pixels))
    ico = ico_bytes(png)
    png_path = os.path.join(ASSET_DIR, "quant_icon.png")
    ico_path = os.path.join(ASSET_DIR, "quant_icon.ico")
    with open(png_path, "wb") as f:
        f.write(png)
    with open(ico_path, "wb") as f:
        f.write(ico)
    print(f"生成 {png_path} ({len(png)} 字节)")
    print(f"生成 {ico_path} ({len(ico)} 字节)")


if __name__ == "__main__":
    main()
