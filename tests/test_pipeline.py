# -*- coding: utf-8 -*-
"""pipeline：阶段状态机引擎（顺序/合并/质量债/停链/暂停恢复/持久化）。"""

import pipeline
from pipeline import Pipeline, Stage, StageDebtError, StageStopError


def st_add(state, ctx):
    return {"v": state.get("v", 0) + 1}


def st_double(state, ctx):
    return {"v": state.get("v", 0) * 2}


def make(stages, pid="t1", state=None):
    return Pipeline(pid, "测试", stages, state)


def test_order_and_merge_and_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))
    p = make([Stage("a", st_add), Stage("b", st_double)])
    assert p.run() == "done"
    assert p.state["v"] == 2
    assert all(p.status[s] == "done" for s in ("a", "b"))
    p2 = pipeline.load("t1", [Stage("a", st_add), Stage("b", st_double)])
    assert p2 is not None and p2.state["v"] == 2
    assert p2.pipeline_status == "done"


def test_debt_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))

    def bad(state, ctx):
        raise StageDebtError("局部问题")

    p = make([Stage("bad", bad, fail="debt"), Stage("b", st_add)])
    assert p.run() == "done"
    assert p.debts and "局部问题" in p.debts[0]["detail"]
    assert p.state["v"] == 1          # 后续阶段照常执行


def test_stop_level_failure_halts(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))

    def fatal(state, ctx):
        raise StageStopError("结构性失败")

    p = make([Stage("a", st_add), Stage("fatal", fatal, fail="stop"),
              Stage("c", st_add)])
    assert p.run() == "failed"
    assert p.status["c"] == "pending"
    assert p.error == "结构性失败"


def test_generic_exception_follows_stage_policy(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))

    def boom(state, ctx):
        raise RuntimeError("网络炸了")

    p = make([Stage("boom", boom, fail="debt"), Stage("b", st_add)])
    assert p.run() == "done"
    assert p.debts and "网络炸了" in p.debts[0]["detail"]


def test_pause_and_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))
    calls = {"n": 0}

    def stopper():
        calls["n"] += 1
        return calls["n"] > 1         # 第一个阶段跑完后停

    p = make([Stage("a", st_add), Stage("b", st_add)])
    assert p.run(on_stop=stopper) == "paused"
    assert p.cursor == "b"
    assert p.run() == "done"          # 恢复后跑完
    assert p.state["v"] == 2


def test_stage_internal_pause_with_save_state(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))
    flag = {"pause_once": True}

    def loop(state, ctx):
        items = state.setdefault("items", [])
        for i in range(1, 4):
            if i <= len(items):       # 恢复时跳过已完成
                continue
            items.append(i)
            ctx.save_state({"items": items})
            if flag["pause_once"]:
                flag["pause_once"] = False
                ctx.pause()

    p = make([Stage("loop", loop), Stage("after", st_add)])
    assert p.run() == "paused"
    assert p.state["items"] == [1]
    assert p.run() == "done"
    assert p.state["items"] == [1, 2, 3]
    assert p.state["v"] == 1


def test_until_runs_partial_then_pauses(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))
    p = make([Stage("a", st_add), Stage("b", st_double)])
    assert p.run(until="a") == "paused"
    assert p.cursor == "b" and p.state["v"] == 1
    assert p.run() == "done"


def test_list_pipelines_sorted(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))
    make([Stage("a", st_add)], pid="p1").run()
    make([Stage("a", st_add)], pid="p2").run()
    rows = pipeline.list_pipelines()
    assert [r["pid"] for r in rows] == ["p2", "p1"]


def test_save_failure_is_recorded_not_silent(tmp_path, monkeypatch):
    """检查点落盘失败要留下健康信号（断点恢复的根基，不能静默吞掉）。"""
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))

    def boom(*_a, **_kw):
        raise TypeError("state 不可序列化")

    monkeypatch.setattr(pipeline.json, "dump", boom)
    p = make([Stage("a", st_add)], pid="bad")
    p.run()                            # 落盘全失败也不阻断执行
    assert p.state["v"] == 1
    assert p.save_errors > 0
    assert "TypeError" in p.save_error


def test_save_health_survives_restore(tmp_path, monkeypatch):
    """健康信号随状态持久化：恢复后仍能读到落盘失败计数。"""
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path))
    p = make([Stage("a", st_add)], pid="p1")
    p.run()
    p.save_errors = 3
    p.save_error = "OSError: 磁盘满"
    p.save()
    p2 = pipeline.load("p1", [Stage("a", st_add)])
    assert p2.save_errors == 3 and "磁盘满" in p2.save_error
    assert pipeline.list_pipelines()[0]["save_errors"] == 3
