# -*- coding: utf-8 -*-
"""剧本改写引擎（火宝 script-rewriter 规范移植）。

把章节正文改写为格式化拍摄剧本（S01 场景化分段、对白驱动、不写镜头
语言），落盘 短剧剧本/第N章-拍摄剧本.md。build_shots 检测到拍摄剧本会
优先用它替代原文出分镜。

路径安全：所有写盘目标用 pathlib 构造并 resolve() 后校验必须位于
书目录内（relative_to 包含校验，越界即抛错）。
"""

from __future__ import annotations

import os
import pathlib

import novel_chain


def rewrite_script(state: dict, ch: int, on_event=None,
                   force: bool = False) -> str:
    """改写指定章节为拍摄剧本，返回落盘路径（已存在且非 force 则回缓存）。"""
    on_event = on_event or (lambda e: None)
    ch = int(ch)
    book = pathlib.Path(dramavideo_book_dir(state))
    base = (book / "短剧剧本").resolve()
    base.mkdir(parents=True, exist_ok=True)
    target = (base / f"第{ch}章-拍摄剧本.md").resolve()
    if base not in target.parents:                     # 严格包含校验
        raise novel_chain.StageStopError(f"剧本路径越界：{target}")
    if target.is_file() and not force:
        return str(target)

    chapters = [c for c in state.get("chapters", [])
                if c.get("idx") == ch and c.get("text")]
    if not chapters:
        raise novel_chain.StageStopError(f"第 {ch} 章不存在或还没有正文")
    chapter = chapters[0]
    on_event({"type": "drama_media", "kind": "rewrite",
              "label": chapter["title"]})

    text = _ask(state, chapter)

    header = (f"# 第{ch}章《{chapter['title']}》拍摄剧本\n\n")
    target.write_text(header + text + "\n", encoding="utf-8")
    on_event({"type": "drama_media", "kind": "rewrite",
              "label": f"第{ch}章 拍摄剧本完成"})
    return str(target)


def apply_script(state: dict, ch: int) -> bool:
    """把已改写的拍摄剧本应用到 state（替换该章工作文本，原文存 text_orig）。

    供短剧 worker 在跑分镜前调用：改写本存在 → 分镜/关键帧以改写本为准。
    """
    ch = int(ch)
    base = (pathlib.Path(dramavideo_book_dir(state)) / "短剧剧本").resolve()
    target = (base / f"第{ch}章-拍摄剧本.md").resolve()
    if base not in target.parents or not target.is_file():
        return False
    text = target.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines()
             if ln.strip() and not ln.startswith("# ")]
    body = "\n".join(lines).strip()
    if not body:
        return False
    for c in state.get("chapters", []):
        if c.get("idx") == ch:
            c.setdefault("text_orig", c.get("text", ""))
            c["text"] = body
            return True
    return False


def _ask(state, chapter) -> str:
    """LLM 改写（复用 drama 的模型派发）。"""
    import dramavideo
    return dramavideo._ask(
        state,
        "你是短剧编剧。把小说章节改写为格式化拍摄剧本。"
        "【改写原则】1) 保留核心情节，不改变主线与角色关系；"
        "2) 增强画面感：叙述转为可视化场景描写；"
        "3) 对白驱动：用对白推情节，减少旁白；"
        "4) 每场戏 30-60 秒体量，适合竖屏短剧；"
        "5) 不写镜头语言（景别/角度/运镜属于分镜阶段）。"
        "【格式】每场以「## S01 | 内景 · 地点 | 时段」开头，"
        "先写环境与人物动作的画面段，再写「角色：（神态）台词」对白行。"
        "只输出剧本，不解释。",
        f"小说章节（第 {chapter['idx']} 章《{chapter['title']}》）：\n"
        f"{chapter['text']}")


def dramavideo_book_dir(state: dict) -> str:
    """书目录（转调 dramavideo._book_dir，便于测试打桩）。"""
    import dramavideo
    return dramavideo._book_dir(state)
