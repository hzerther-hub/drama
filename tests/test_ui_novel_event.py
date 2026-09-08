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


# ---------------- /novel 子命令：内存态自动恢复 ----------------

class CmdStub:
    """只提供 _novel_command 依赖的最小接口。"""

    _novel_command = ui.App._novel_command
    _novel_pick = ui.App._novel_pick

    def __init__(self):
        self.lines = []
        self.status = []
        self._novel_pipe = None
        self._novel_busy = False
        self._running = False
        self.current_model = None
        self._novel_stepwise = False
        self._novel_last_done = None

    def _append(self, text, tag=None):
        self.lines.append(text)

    def _set_status(self, text, *a, **k):
        self.status.append(text)

    def _novel_run(self, p, until=None):
        self.ran = p.pid


def test_subcommand_recovers_pipeline_after_restart(monkeypatch):
    """重启后 _novel_pipe 是 None；extend 等命令应自动载入最近一本书。

    否则用户必须手动 /novel resume，且 extend/rewrite/drama 全报「还没有流水线记录」。
    """
    import novel_chain
    import pipeline as pl

    loaded = []

    class FakePipe:
        pid = "novel-test-0001"
        pipeline_status = "done"
        state = {"total_chapters": 3}

    monkeypatch.setattr(pl, "list_pipelines",
                        lambda: [{"pid": "novel-test-0001"}])
    monkeypatch.setattr(pl, "load",
                        lambda pid, stages: (loaded.append(pid), FakePipe())[1])
    monkeypatch.setattr(novel_chain, "extend_total",
                        lambda p, n: p.state.__setitem__("total_chapters", 3 + n))

    app = CmdStub()
    app._novel_command("extend 5")
    assert loaded == ["novel-test-0001"]          # 自动载入了
    assert app._novel_pipe.pid == "novel-test-0001"
    assert app.lines and "8" in app.lines[0]      # 总数已 3+5=8


def test_status_does_not_auto_load(monkeypatch):
    """status 只列清单，不该有副作用（不自动载入）。"""
    import pipeline as pl
    monkeypatch.setattr(pl, "list_pipelines", lambda: [])
    app = CmdStub()
    app._novel_command("status")
    assert app._novel_pipe is None


# ---------------- /novel 多书切换 ----------------

def _fake_pipes(monkeypatch, pids):
    """把 list_pipelines/load 替换成给定的多本书。"""
    import pipeline as pl

    class P:
        def __init__(self, pid):
            self.pid = pid
            self.title = "书" + pid
            self.pipeline_status = "done"
            self.state = {"total_chapters": 3, "chapters": []}

    monkeypatch.setattr(pl, "list_pipelines",
                        lambda: [{"pid": p, "title": "书" + p,
                                  "pipeline_status": "done", "debts": 0,
                                  "updated": 0} for p in pids])
    monkeypatch.setattr(pl, "load", lambda pid, stages: P(pid))
    return P


def test_use_switches_current_book(monkeypatch):
    """use <pid> 切换当前书（不自动开始跑）。"""
    _fake_pipes(monkeypatch, ["novel-a-0001", "novel-b-0002"])
    app = CmdStub()
    app._novel_command("use novel-b-0002")
    assert app._novel_pipe.pid == "novel-b-0002"
    assert not hasattr(app, "ran")            # 没有触发运行


def test_use_accepts_pid_prefix(monkeypatch):
    """pid 前缀唯一时可直接用前缀，省得敲完整时间戳。"""
    _fake_pipes(monkeypatch, ["novel-20260908-200622", "novel-20260906-234119"])
    app = CmdStub()
    app._novel_command("use novel-20260908")
    assert app._novel_pipe.pid == "novel-20260908-200622"


def test_use_unknown_pid_reports_notfound(monkeypatch):
    _fake_pipes(monkeypatch, ["novel-a-0001"])
    app = CmdStub()
    app._novel_command("use novel-nope")
    assert app._novel_pipe is None
    # 断言用的是「找不到」这条文案，不依赖当前语言（i18n 是全局状态）
    import i18n
    expected = {i18n.t("novel.notfound"), i18n.t("novel.none")}
    assert app.status and app.status[0] in expected
    assert app.status[0] != i18n.t("novel.none")   # 明确报 notfound，而非笼统 none


def test_use_ambiguous_prefix_reports(monkeypatch):
    """前缀匹配到多本 → 提示更完整 pid，不随便选一本。"""
    _fake_pipes(monkeypatch, ["novel-2026-aaa", "novel-2026-bbb"])
    app = CmdStub()
    app._novel_command("use novel-2026")
    assert app._novel_pipe is None
    import i18n
    assert app.status and app.status[0] == i18n.t("novel.ambiguous")


def test_extend_accepts_at_pid(monkeypatch):
    """extend 30 @pid 可指定操作哪本书。"""
    import novel_chain
    _fake_pipes(monkeypatch, ["novel-a-0001", "novel-b-0002"])
    monkeypatch.setattr(novel_chain, "extend_total",
                        lambda p, n: p.state.__setitem__("total_chapters", 3 + n))
    app = CmdStub()
    app._novel_command("extend 30 @novel-a-0001")
    assert app._novel_pipe.pid == "novel-a-0001"
    assert app._novel_pipe.state["total_chapters"] == 33


def test_status_marks_current_book(monkeypatch):
    """status 用 ▶ 标出当前书，避免多书时看错。"""
    _fake_pipes(monkeypatch, ["novel-a-0001", "novel-b-0002"])
    app = CmdStub()
    app._novel_command("use novel-b-0002")
    app.lines.clear()
    app._novel_command("status")
    marked = [l for l in app.lines if l.startswith("▶")]
    assert len(marked) == 1 and "novel-b-0002" in marked[0]
