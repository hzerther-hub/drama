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


def test_save_prefers_book_dir(tmp_path, monkeypatch):
    """有书目录：状态与事件日志落 <书目录>/pipelines/，不碰 CONFIG_DIR。"""
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path / "cfg"))
    book = tmp_path / "novels" / "深井之下"
    book.mkdir(parents=True)
    p = make([Stage("a", st_add)], pid="t1", state={"dir": str(book)})
    assert p.run() == "done"
    assert (book / "pipelines" / "t1.json").is_file()
    assert not (tmp_path / "cfg" / "t1.json").exists()


def test_save_falls_back_when_book_dir_missing(tmp_path, monkeypatch):
    """书目录被删（或还没建）：回落 CONFIG_DIR，不复活书目录。"""
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path / "cfg"))
    p = make([Stage("a", st_add)], pid="t1",
             state={"dir": str(tmp_path / "gone")})
    assert p.run() == "done"
    assert (tmp_path / "cfg" / "t1.json").is_file()
    assert not (tmp_path / "gone").exists()


def test_load_and_list_find_book_dir_pipelines(tmp_path, monkeypatch):
    """按 pid 加载与列表都能扫到书目录内的流水线。"""
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path / "cfg"))
    monkeypatch.setattr(pipeline, "_books_root",
                        lambda: str(tmp_path / "novels"))
    book = tmp_path / "novels" / "书A"
    book.mkdir(parents=True)
    p = make([Stage("a", st_add)], pid="t2", state={"dir": str(book)})
    p.save()
    p2 = pipeline.load("t2", [Stage("a", st_add)])
    assert p2 is not None and p2.state["dir"] == str(book)
    rows = pipeline.list_pipelines()
    assert [r["pid"] for r in rows] == ["t2"]


def test_list_migrates_legacy_into_books(tmp_path, monkeypatch):
    """CONFIG_DIR 旧档（state.dir 已存在）在列表时迁入书目录，原档删除。"""
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path / "cfg"))
    monkeypatch.setattr(pipeline, "_books_root",
                        lambda: str(tmp_path / "novels"))
    book = tmp_path / "novels" / "书B"
    p = make([Stage("a", st_add)], pid="t3", state={"dir": str(book)})
    p.save()                           # 书目录还没建 → 落 CONFIG_DIR
    assert (tmp_path / "cfg" / "t3.json").is_file()
    book.mkdir(parents=True)           # 事后建好书目录
    rows = pipeline.list_pipelines()   # 触发幂等迁移
    assert (book / "pipelines" / "t3.json").is_file()
    assert not (tmp_path / "cfg" / "t3.json").exists()
    assert [r["pid"] for r in rows] == ["t3"]
    assert pipeline.load("t3", [Stage("a", st_add)]) is not None


def test_events_log_lands_in_book_dir(tmp_path, monkeypatch):
    """事件日志跟随状态落点：有书目录写书目录，否则回落 CONFIG_DIR。"""
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path / "cfg"))
    book = tmp_path / "novels" / "书C"
    book.mkdir(parents=True)
    p = make([Stage("a", st_add)], pid="t4", state={"dir": str(book)})
    p._log_event({"type": "text"})
    assert (book / "pipelines" / "t4.events.jsonl").is_file()
    p2 = make([Stage("a", st_add)], pid="t5")
    p2._log_event({"type": "text"})
    assert (tmp_path / "cfg" / "t5.events.jsonl").is_file()


def test_save_evicts_other_pids_from_book_dir(tmp_path, monkeypatch):
    """单档约束：书目录 pipelines/ 只留当前 pid，其他直接删除（%APPDATA% 不留存档）。"""
    import os

    import novel_chain
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path / "cfg"))
    monkeypatch.setattr(pipeline, "_books_root",
                        lambda: str(tmp_path / "novels"))
    book = tmp_path / "novels" / "书A"
    (book / "pipelines").mkdir(parents=True)
    (book / "pipelines" / "novel-old.json").write_text(
        '{"pid": "novel-old", "updated": 1}', encoding="utf-8")
    (book / "pipelines" / "novel-old.events.jsonl").write_text(
        "{}\n", encoding="utf-8")
    p = make([Stage("a", st_add)], pid="t9", state={"dir": str(book)})
    assert p.run() == "done"
    # run 过程会写事件日志，t9 的一对文件都该在
    assert set(os.listdir(book / "pipelines")) == {"t9.json",
                                                   "t9.events.jsonl"}
    # %APPDATA% 不留存档：其他 pid 的档案直接删除，不是搬去 CONFIG_DIR
    assert not (tmp_path / "cfg" / "novel-old.json").exists()
    assert not (tmp_path / "cfg" / "novel-old.events.jsonl").exists()
    assert pipeline.load("novel-old", novel_chain.STAGES) is None


def test_migrate_skips_occupied_book_dir(tmp_path, monkeypatch):
    """书目录 pipelines/ 已被别的 pid 占用：迁移跳过，不制造一目录多档。"""
    import json as _json

    import pipeline as _pl
    cfg = tmp_path / "cfg"
    cfg.mkdir(parents=True)
    monkeypatch.setattr(pipeline, "_root", lambda: str(cfg))
    monkeypatch.setattr(pipeline, "_books_root",
                        lambda: str(tmp_path / "novels"))
    book = tmp_path / "novels" / "书B"
    (book / "pipelines").mkdir(parents=True)
    (book / "pipelines" / "holder.json").write_text(
        '{"pid": "holder"}', encoding="utf-8")
    with open(cfg / "t10.json", "w", encoding="utf-8") as f:
        _json.dump({"pid": "t10", "title": "", "state": {"dir": str(book)},
                    "updated": 5}, f)
    rows = pipeline.list_pipelines()
    assert not (book / "pipelines" / "t10.json").exists()
    assert (cfg / "t10.json").is_file()
    assert {r["pid"] for r in rows} >= {"holder", "t10"}   # 仍可见可选


def test_delete_record_removes_json_and_events(tmp_path, monkeypatch):
    """删档：CONFIG_DIR 与书目录两处的 json+事件日志都能删；不存在返回 False。"""
    import os

    import novel_chain
    monkeypatch.setattr(pipeline, "_root", lambda: str(tmp_path / "cfg"))
    monkeypatch.setattr(pipeline, "_books_root",
                        lambda: str(tmp_path / "novels"))
    # 书目录内的档案
    book = tmp_path / "novels" / "书A"
    (book / "pipelines").mkdir(parents=True)
    p = make([Stage("a", st_add)], pid="tA", state={"dir": str(book)})
    p.save()
    assert pipeline.delete_record("tA") is True
    assert not (book / "pipelines" / "tA.json").exists()
    assert not (tmp_path / "cfg" / "tA.json").exists()
    assert pipeline.load("tA", novel_chain.STAGES) is None
    # CONFIG_DIR 内的档案（含事件日志）
    p2 = make([Stage("a", st_add)], pid="tB")
    p2._log_event({"type": "text"})
    p2.save()
    assert (tmp_path / "cfg" / "tB.events.jsonl").is_file()
    assert pipeline.delete_record("tB") is True
    assert not (tmp_path / "cfg" / "tB.json").exists()
    assert not (tmp_path / "cfg" / "tB.events.jsonl").exists()
    # 不存在
    assert pipeline.delete_record("nope") is False
