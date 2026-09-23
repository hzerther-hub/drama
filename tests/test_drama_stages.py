# -*- coding: utf-8 -*-
"""短剧分步模式：stop_after 各阶段的边界与产物门禁。"""

from __future__ import annotations

import pytest

import dramavideo
import novel_chain


@pytest.fixture
def book_tmp(tmp_path, monkeypatch):
    """临时书目录 + 禁用真实出图网络（等效 test_dramavideo 的 book）。"""
    monkeypatch.setattr(dramavideo, "_book_dir", lambda state: str(tmp_path))
    monkeypatch.setattr(dramavideo.imggen, "available", lambda: True)
    state = {"pid": "novel-stage", "title": "分步测试书",
             "characters": "## 主角：林夏\n善良大学生。"}
    return state, tmp_path


def _stage_patches(monkeypatch, order):
    """把各阶段函数打成记录调用顺序的桩，便于断言分步边界。"""
    monkeypatch.setattr(dramavideo, "chapter_assets",
                        lambda *a, **k: (order.append("assets"), {})[1])
    monkeypatch.setattr(dramavideo, "build_cast",
                        lambda st, ev=None, stop=None:
                        (order.append("cast"), {"林夏": {}})[1])
    monkeypatch.setattr(
        dramavideo, "build_shots",
        lambda st, c, ev=None, cast=None:
        (order.append("shots"), [{"title": "t", "scene": "宿舍",
                                  "characters": ["林夏"],
                                  "description": "中景。", "dialogue": "",
                                  "duration": 5}])[1])
    monkeypatch.setattr(
        dramavideo, "keyframe",
        lambda st, cast, shot, ch, i, ev=None:
        (order.append("frame"), ("f.png", "u://f"))[1])
    monkeypatch.setattr(
        dramavideo, "clip",
        lambda st, shot, url, ch, i, ev=None:
        (order.append("clip"), "c.mp4")[1])
    monkeypatch.setattr(
        dramavideo, "concat",
        lambda clips, out: (order.append("concat"), out)[1])


def test_run_stop_after_shots(book_tmp, monkeypatch):
    """分步：shots 阶段完成即停，不产关键帧/视频/合成。"""
    import novel_chain
    state, tmp = book_tmp
    state["chapters"] = [{"idx": 1, "title": "两面三刀", "text": "正文"}]
    order = []
    _stage_patches(monkeypatch, order)
    with pytest.raises(novel_chain.StageStopError) as ei:
        dramavideo.run(state, 1, 1, stop_after="shots")
    assert "分镜" in str(ei.value)
    assert order == ["cast", "shots"]


def test_run_stop_after_keyframes(book_tmp, monkeypatch):
    """分步：keyframes 出关键帧，但不产视频、不合成。"""
    import novel_chain
    state, tmp = book_tmp
    state["chapters"] = [{"idx": 1, "title": "两面三刀", "text": "正文"}]
    order = []
    _stage_patches(monkeypatch, order)
    with pytest.raises(novel_chain.StageStopError) as ei:
        dramavideo.run(state, 1, 1, stop_after="keyframes")
    assert "关键帧" in str(ei.value)
    assert order == ["cast", "shots", "assets", "frame"]
    assert "clip" not in order and "concat" not in order


def test_run_stop_after_clips_skips_compose(book_tmp, monkeypatch):
    """分步：clips 产镜头视频，但不合成整集。"""
    import novel_chain
    state, tmp = book_tmp
    state["chapters"] = [{"idx": 1, "title": "两面三刀", "text": "正文"}]
    order = []
    _stage_patches(monkeypatch, order)
    with pytest.raises(novel_chain.StageStopError) as ei:
        dramavideo.run(state, 1, 1, stop_after="clips")
    assert "clip" in order and "concat" not in order
    assert "镜头视频" in str(ei.value)


def test_run_full_still_composes(book_tmp, monkeypatch):
    """不带 stop_after 的默认行为不变：合成整集。"""
    state, tmp = book_tmp
    state["chapters"] = [{"idx": 1, "title": "两面三刀", "text": "正文"}]
    order = []
    _stage_patches(monkeypatch, order)
    outs = dramavideo.run(state, 1, 1)
    assert outs and "concat" in order
