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
    _novel_adjust = ui.App._novel_adjust

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


def test_adjust_recovers_stage_after_restart(monkeypatch):
    """重启后 adjust 应自动取书 + 从 cursor 反推要调的阶段。"""
    import novel_chain
    import pipeline as pl

    class P:
        pid = "novel-x"
        title = "t"
        pipeline_status = "paused"
        cursor = "world"                      # outline 已完成
        state = {"framing": "题材：都市",
                 "outline": "# 《书》\n## 故事一句话\n测试"}

    monkeypatch.setattr(pl, "list_pipelines", lambda: [{"pid": "novel-x"}])
    monkeypatch.setattr(pl, "load", lambda pid, stages: P())
    captured = {}
    monkeypatch.setattr(novel_chain, "revise_stage",
                        lambda s, stage, key, fb: captured.update(
                            stage=stage, key=key, fb=fb))

    app = CmdStub()
    app._novel_adjust("加入太阳能面板")
    assert captured.get("stage") == "outline"     # 反推出 outline
    assert captured.get("key") == "outline"
    assert "太阳能" in captured.get("fb", "")
    assert app._novel_last_done == "outline"      # 记录已恢复


# ---------------- 删除会话不得改变工作区状态 ----------------

class _DelStub:
    """哑 App：只提供删除路径用到的属性，用来跑真实的 ui.App 删除方法。"""

    _cancel_runs = ui.App._cancel_runs      # 真实实现（取消运行中会话）

    def __init__(self):
        self.session_id = "cur"
        self.session_title = "当前会话"
        self._runs = {}
        self._cur_run = None
        self.new_persist = None
        self.refreshed = False
        self.status = ""

    def _new_session(self, persist=True):
        self.new_persist = persist          # 记录落盘意图（True 会把分组顶回来）

    def _refresh_sidebar(self):
        self.refreshed = True

    def _set_status(self, s):
        self.status = s


def test_delete_current_session_does_not_persist_new_one(monkeypatch):
    """删当前会话：新会话必须 persist=False，否则工作区分组立刻被顶回来。"""
    import tkinter.messagebox
    import sessions as sess_mod
    import ui

    deleted = []
    monkeypatch.setattr(sess_mod, "delete", lambda sid: deleted.append(sid))
    monkeypatch.setattr(tkinter.messagebox, "askyesno", lambda *a, **k: True)
    stub = _DelStub()
    ui.App._delete_current_session(stub)
    assert deleted == ["cur"]
    assert stub.new_persist is False        # 关键：不落盘 → 分组不会复活


def test_delete_sessions_group_keeps_workspace(monkeypatch):
    """删「工作区分组」：删完当前会话时同样不落盘，工作区状态保持不变。"""
    import tkinter.messagebox
    import sessions as sess_mod
    import ui

    deleted = []
    monkeypatch.setattr(sess_mod, "delete", lambda sid: deleted.append(sid))
    monkeypatch.setattr(tkinter.messagebox, "askyesno", lambda *a, **k: True)
    stub = _DelStub()
    ui.App._delete_sessions(stub, ["cur", "b"], "D:/ws-A")
    assert sorted(deleted) == ["b", "cur"]
    assert stub.new_persist is False


def test_delete_other_session_only_refreshes(monkeypatch):
    """删的不是当前会话：只刷新侧栏，不新建会话、不影响工作区。"""
    import tkinter.messagebox
    import sessions as sess_mod
    import ui

    deleted = []
    monkeypatch.setattr(sess_mod, "delete", lambda sid: deleted.append(sid))
    monkeypatch.setattr(tkinter.messagebox, "askyesno", lambda *a, **k: True)
    stub = _DelStub()
    ui.App._delete_sessions(stub, ["other"], "D:/ws-B")
    assert deleted == ["other"]
    assert stub.new_persist is None         # 没新建会话
    assert stub.refreshed is True
