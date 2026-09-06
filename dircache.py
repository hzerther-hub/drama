# -*- coding: utf-8 -*-
"""工作区文件清单缓存：@ 候选联想用的目录快照（TTL 失效 + 手动失效）。

原先每敲一个字符就 os.walk 全工作区（扫满 300 条止），大仓库明显卡顿；
现在整棵清单扫一次缓存 TTL 秒，联想只在内存里做子串过滤。
"""

from __future__ import annotations

import os
import time

_TTL = 30.0                     # 秒；超时后下次访问重建快照
_SKIP = {".git", "__pycache__", "node_modules", ".venv", "venv",
         "dist", "build", ".idea", ".vscode", "__MACOSX"}
_MAX_SCAN = 5000                # 单次最多收集条数，防超大仓库首扫过久

_cache: dict[str, tuple[float, list[str]]] = {}


def invalidate(ws: str | None = None):
    """失效缓存；ws 为 None 时全部失效（切工作区/手动刷新用）。"""
    if ws is None:
        _cache.clear()
    else:
        _cache.pop(os.path.abspath(ws), None)


def list_files(ws: str) -> list[str]:
    """工作区相对路径清单（目录带 / 后缀，排序稳定）；带 TTL 缓存。"""
    key = os.path.abspath(ws)
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    files = _scan(key)
    _cache[key] = (now, files)
    return files


def _scan(ws: str) -> list[str]:
    out: list[str] = []
    for root, dirs, files in os.walk(ws):
        rel_root = os.path.relpath(root, ws).replace("\\", "/")
        if rel_root == ".":
            rel_root = ""
        dirs[:] = sorted(d for d in dirs if d not in _SKIP)
        for name in dirs:
            rel = f"{rel_root}/{name}" if rel_root else name
            out.append(rel + "/")
        for name in sorted(files):
            rel = f"{rel_root}/{name}" if rel_root else name
            out.append(rel)
        if len(out) >= _MAX_SCAN:
            break
    return out
