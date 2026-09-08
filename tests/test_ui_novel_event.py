# -*- coding: utf-8 -*-
"""ui._novel_event：流水线事件 → 聊天区渲染 + 文件树刷新（不启动 Tk）。"""

import ui


class StubApp:
    """只提供 _novel_event 依赖的最小接口。"""

    _novel_event = ui.App._novel_event

    def __init__(self):
        self.lines = []
        self.refreshes = 0
        self._novel_pipe = None
        self._novel_stepwise = False
        self._novel_last_done = None

    def _append(self, text, tag=None):
        self.lines.append((tag, text))

    def _schedule_fs_refresh(self):
        self.refreshes += 1


def test_chapter_done_refreshes_file_tree():
    """每章落盘后必须刷新文件树：流水线直接写磁盘，文件面板不会自己感知。"""
    app = StubApp()
    app._novel_event({"type": "chapter_done", "idx": 1,
                      "title": "开局", "words": 1800})
    assert app.refreshes == 1
    # 渲染的是章节完成行（文案随语言变化，故断言内容而非固定措辞）
    assert any("开局" in t and "1800" in t for _tag, t in app.lines)


def test_stage_done_refreshes_file_tree():
    """规划阶段也会追加书稿 md（不经 write_file 工具），同样要刷新。"""
    app = StubApp()
    app._novel_event({"type": "stage_done", "name": "setup"})
    assert app.refreshes == 1
    assert app._novel_last_done == "setup"


def test_pipeline_done_refreshes_file_tree():
    app = StubApp()
    app._novel_event({"type": "pipeline_done", "pid": "p1"})
    assert app.refreshes == 1


def test_other_events_do_not_refresh():
    """未产出文件的事件不应触发刷新（避免无谓重建文件树）。"""
    app = StubApp()
    app._novel_event({"type": "stage_start", "name": "setup"})
    app._novel_event({"type": "stage_debt", "name": "chapters", "detail": "x"})
    assert app.refreshes == 0
