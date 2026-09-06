# -*- coding: utf-8 -*-
"""写操作检查点：write_file 前快照，/undo 回滚最近一次覆盖。

设计：
- 每个被覆盖的文件在 CONFIG_DIR/checkpoints/<md5(绝对路径)前10位>/ 下
  存一份带时间戳的副本，meta.json 记录原路径；
- restore_latest(path=None) 回滚指定文件（或全局最近）的一次覆盖；
- 每文件最多保留 KEEP_PER_FILE 份，防止检查点目录无限膨胀；
- 只服务 write_file 的"覆盖前"场景：新建文件无旧内容，不做快照。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time

import config

KEEP_PER_FILE = 10           # 每个文件保留的快照上限


def _root() -> str:
    """检查点根目录；惰性取值（测试可 monkeypatch 注入临时目录）。"""
    return os.path.join(config.CONFIG_DIR, "checkpoints")


def _ckpt_dir(path: str) -> str:
    """文件绝对路径对应的快照目录（含 meta.json 记录原路径）。"""
    h = hashlib.md5(os.path.abspath(path).lower().replace("\\", "/")
                    .encode("utf-8")).hexdigest()[:10]
    return os.path.join(_root(), h)


def snapshot(path: str) -> str | None:
    """覆盖前快照；文件不存在/快照失败返回 None（不阻断写入）。"""
    try:
        if not os.path.isfile(path):
            return None
        d = _ckpt_dir(path)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"path": os.path.abspath(path)}, f, ensure_ascii=False)
        dest = os.path.join(d, f"{time.time_ns()}-{os.path.basename(path)}")
        shutil.copy2(path, dest)
        _prune(d)
        return dest
    except Exception:                     # noqa: BLE001  快照失败不阻断写入
        return None


def _prune(d: str):
    """超出 KEEP_PER_FILE 时删除最旧的快照（meta.json 不计）。"""
    snaps = sorted(f for f in os.listdir(d) if f != "meta.json")
    for name in snaps[:-KEEP_PER_FILE] if len(snaps) > KEEP_PER_FILE else []:
        try:
            os.remove(os.path.join(d, name))
        except OSError:
            pass


def _snapshots(d: str) -> list[str]:
    """目录内快照文件，按文件名（时间戳前缀）升序。"""
    try:
        return sorted(f for f in os.listdir(d) if f != "meta.json")
    except OSError:
        return []


def restore_latest(path: str | None = None) -> tuple[bool, str]:
    """回滚最近一次覆盖。path 给定则只看该文件；否则全局最近。

    返回 (是否成功, 提示消息)。
    """
    dirs = ([_ckpt_dir(path)] if path
            else [os.path.join(_root(), name)
                  for name in _safe_listdir(_root())])
    best_dir, best_snap = None, None
    for d in dirs:
        snaps = _snapshots(d)
        if not snaps:
            continue
        cand = os.path.join(d, snaps[-1])
        if best_snap is None or os.path.getmtime(cand) > os.path.getmtime(best_snap):
            meta_path = os.path.join(d, "meta.json")
            try:
                with open(meta_path, encoding="utf-8") as f:
                    json.load(f)          # 校验 meta 可读
                best_dir, best_snap = d, cand
            except Exception:             # noqa: BLE001  meta 缺失/损坏跳过
                continue
    if best_snap is None:
        return False, "没有可回滚的检查点（本次会话没有覆盖过文件）"
    try:
        with open(os.path.join(best_dir, "meta.json"), encoding="utf-8") as f:
            orig = json.load(f)["path"]
        shutil.copy2(best_snap, orig)
        try:
            os.remove(best_snap)   # 消费语义：连续 /undo 可逐步回退
        except OSError:
            pass
        return True, (f"已回滚 {orig} → 覆盖前内容"
                      f"（快照 {os.path.basename(best_snap)}）")
    except Exception as e:                # noqa: BLE001
        return False, f"回滚失败：{e}"


def list_recent(limit: int = 10) -> list[dict]:
    """最近的检查点列表（新→旧）：{path, snapshot, time}。"""
    out = []
    for name in _safe_listdir(_root()):
        d = os.path.join(_root(), name)
        try:
            with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
                orig = json.load(f)["path"]
        except Exception:                 # noqa: BLE001
            continue
        for snap in _snapshots(d):
            p = os.path.join(d, snap)
            out.append({"path": orig, "snapshot": snap,
                        "time": os.path.getmtime(p)})
    out.sort(key=lambda x: -x["time"])
    return out[:limit]


def _safe_listdir(path: str) -> list[str]:
    try:
        return os.listdir(path)
    except OSError:
        return []
