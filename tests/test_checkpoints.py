# -*- coding: utf-8 -*-
"""checkpoints：write_file 覆盖前快照 + /undo 回滚。"""

import checkpoints
import tools


def test_write_file_snapshot_and_undo(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoints, "_root", lambda: str(tmp_path / "ck"))
    ws = tmp_path / "ws"
    ws.mkdir()
    f = ws / "a.txt"
    f.write_text("v1", encoding="utf-8")
    with tools.push_workspace(str(ws)):
        tools.execute_tool("write_file", {"path": "a.txt", "content": "v2"})
    assert f.read_text(encoding="utf-8") == "v2"
    assert checkpoints.list_recent()[0]["path"] == str(f)

    ok, _msg = checkpoints.restore_latest()
    assert ok
    assert f.read_text(encoding="utf-8") == "v1"

    # 检查点已耗尽 → 明确提示而非静默
    ok2, msg2 = checkpoints.restore_latest()
    assert not ok2 and "没有可回滚" in msg2


def test_new_file_no_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoints, "_root", lambda: str(tmp_path / "ck"))
    ws = tmp_path / "ws"
    ws.mkdir()
    with tools.push_workspace(str(ws)):
        tools.execute_tool("write_file", {"path": "new.txt", "content": "x"})
    assert checkpoints.list_recent() == []
    ok, _msg = checkpoints.restore_latest()
    assert not ok


def test_restore_picks_latest_across_files(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoints, "_root", lambda: str(tmp_path / "ck"))
    ws = tmp_path / "ws"
    ws.mkdir()
    a, b = ws / "a.txt", ws / "b.txt"
    a.write_text("a1", encoding="utf-8")
    b.write_text("b1", encoding="utf-8")
    with tools.push_workspace(str(ws)):
        tools.execute_tool("write_file", {"path": "a.txt", "content": "a2"})
        tools.execute_tool("write_file", {"path": "b.txt", "content": "b2"})
    # 指定文件只回滚该文件
    ok, _ = checkpoints.restore_latest(str(a))
    assert ok and a.read_text(encoding="utf-8") == "a1"
    assert b.read_text(encoding="utf-8") == "b2"
    # 全局回滚最近一次（b 的覆盖）
    ok, _ = checkpoints.restore_latest()
    assert ok and b.read_text(encoding="utf-8") == "b1"
    assert a.read_text(encoding="utf-8") == "a1"


def test_prune_keeps_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoints, "_root", lambda: str(tmp_path / "ck"))
    monkeypatch.setattr(checkpoints, "KEEP_PER_FILE", 3)
    f = tmp_path / "f.txt"
    f.write_text("0", encoding="utf-8")
    for i in range(1, 6):
        checkpoints.snapshot(str(f))
        f.write_text(str(i), encoding="utf-8")
    d = checkpoints._ckpt_dir(str(f))
    snaps = checkpoints._snapshots(d)
    assert len(snaps) == 3
    # 最旧的快照对应较早内容：回滚应得到倒数第二次写入的内容
    ok, _ = checkpoints.restore_latest(str(f))
    assert ok and f.read_text(encoding="utf-8") == "4"
