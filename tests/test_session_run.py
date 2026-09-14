# -*- coding: utf-8 -*-
"""多会话并发隔离：SessionRun + 输出分桶（谁的运行就记到谁的会话）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ui


class _Stub:
    """哑 App：只带记录所需的最小状态，真实方法直接混入（不起 Tk 窗口）。"""

    _rec_run = ui.App._rec_run
    _run_of = ui.App._run_of
    _record = ui.App._record
    _cancel_runs = ui.App._cancel_runs

    def __init__(self, visible_sid):
        self.session_id = visible_sid
        self._runs = {}
        self._rec = type("TLS", (), {"run": None})()


def _mk_run(sid):
    return ui.SessionRun(sid, "标题", "/ws", [], None, False, False, None)


def test_record_goes_to_buffer_and_renders_when_visible():
    """可见会话：输出既进 buffer 也允许渲染（返回 True）。"""
    app, run = _Stub("s1"), _mk_run("s1")
    app._rec.run = run
    assert app._record("你好", "assistant") is True
    assert run.buffer == [("你好", "assistant")]


def test_record_background_session_does_not_render():
    """后台会话：只记 buffer、不渲染（返回 False）——切走时输出不串到当前聊天区。"""
    app, run = _Stub("s1"), _mk_run("s2")
    app._rec.run = run
    assert app._record("后台输出", "assistant") is False
    assert run.buffer == [("后台输出", "assistant")]
    assert app.session_id == "s1"          # 可见会话未被改动


def test_record_without_run_is_passthrough():
    """非运行期（用户手动操作）：行为与改动前一致，始终可渲染。"""
    app = _Stub("s1")
    assert app._record("手动输出", "meta") is True


def test_run_buffer_capped():
    """长跑输出的 buffer 有上限，防止内存无限增长。"""
    run = _mk_run("s1")
    for i in range(500):
        run.record(f"第{i}条", "assistant")
    assert len(run.buffer) <= 400
    assert run.buffer[-1] == ("第499条", "assistant")   # 保留最新


def test_run_keeps_own_identity():
    """run 冻结本次运行的会话身份：worker 之后只读 run，不再读 App 的可见状态。"""
    run = _mk_run("s9")
    run.workspace = "/proj-A"
    run.title = "甲书"
    assert (run.sid, run.title, run.workspace) == ("s9", "甲书", "/proj-A")
    assert run.running is False and run.stop is False


def test_run_of_only_reports_running():
    """_run_of 只对「正在跑」的会话返回记录（侧栏标记与发送闸门都靠它）。"""
    app = _Stub("s1")
    app._runs = {"s1": _mk_run("s1")}
    assert app._run_of("s1") is None          # 尚未置 running
    app._runs["s1"].running = True
    assert app._run_of("s1") is app._runs["s1"]
    assert app._run_of("不存在") is None


def test_cancel_runs_marks_deleted_and_stops():
    """删除会话时取消其运行：标记不得落盘 + 请求停止（否则会话会「复活」）。"""
    app = _Stub("s1")
    run = _mk_run("s1")
    run.running = True
    app._runs = {"s1": run}
    app._cur_run = run
    app._cancel_runs(["s1"])
    assert run.deleted is True          # 结束时不落盘
    assert run.stop is True             # 尽快停下
    assert app._runs == {}              # 记录移除
    assert app._cur_run is None         # 不再指向已删会话


def test_cancel_runs_ignores_unknown_sid():
    """取消不存在的会话：不报错、不影响其它运行。"""
    app = _Stub("s1")
    other = _mk_run("s2")
    other.running = True
    app._runs = {"s2": other}
    app._cancel_runs(["不存在"])
    assert app._runs == {"s2": other}
    assert other.deleted is False


def test_run_helpers_safe_before_init():
    """界面构建期（__init__ 早于并发字段建立）调用这些 helper 不能抛异常。

    回归：_build_ui → _refresh_sidebar 会走 _run_of，而并发字段在
    __init__ 更靠后的位置初始化——曾经因此启动即崩。
    """
    class Bare:
        pass

    bare = Bare()                      # 没有 _runs / _rec 的对象
    assert ui.App._rec_run(bare) is None
    assert ui.App._run_of(bare, "任意") is None
    ui.App._cancel_runs(bare, ["任意"])   # 不抛异常即可
