# -*- coding: utf-8 -*-
"""sessions.py：多会话保存/加载/删除/检索。"""

import pytest

import sessions


@pytest.fixture(autouse=True)
def sessions_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(sessions, "_DB", str(tmp_path / "sessions.db"))
    monkeypatch.setattr(sessions, "_LEGACY_DIR", str(tmp_path / "sessions"))
    return str(tmp_path)


class TestBasicOps:
    def test_save_load_roundtrip(self):
        sid = sessions.new_id()
        msgs = [{"role": "user", "content": "你好"}]
        sessions.save(sid, msgs, "标题", workspace="/ws/a")
        d = sessions.load(sid)
        assert d["id"] == sid
        assert d["title"] == "标题"
        assert d["messages"] == msgs
        assert d["workspace"] == "/ws/a"
        assert d["created"] > 0 and d["updated"] > 0

    def test_notes_roundtrip(self):
        sid = sessions.new_id()
        notes = [{"kind": "model_switch", "on": "A", "to": "B", "to_key": "k/b"}]
        sessions.save(sid, [{"role": "user", "content": "图"}], "t",
                      notes=notes)
        d = sessions.load(sid)
        assert d["notes"] == notes

    def test_rename_keeps_timestamps_and_messages(self):
        """重命名只改标题：messages/notes 原样，updated 不被刷新。"""
        sid = sessions.new_id()
        notes = [{"kind": "model_switch", "on": "A", "to": "B"}]
        sessions.save(sid, [{"role": "user", "content": "hi"}], "旧标题",
                      notes=notes)
        before = sessions.load(sid)
        assert sessions.rename(sid, "新标题") is True
        d = sessions.load(sid)
        assert d["title"] == "新标题"
        assert d["messages"] == before["messages"]
        assert d["notes"] == notes
        assert d["updated"] == before["updated"]

    def test_rename_rejects_blank_and_missing(self):
        sid = sessions.new_id()
        sessions.save(sid, [{"role": "user", "content": "x"}], "t")
        assert sessions.rename(sid, "   ") is False
        assert sessions.rename("no-such-id", "新标题") is False

    def test_legacy_list_payload_loads(self):
        """旧格式（messages 列直接存 JSON）也能正常读取。"""
        import json as _json
        sid = sessions.new_id()
        msgs = [{"role": "user", "content": "旧"}]
        with sessions._lock:
            conn = sessions._connect()
            try:
                sessions._init_db(conn)
                conn.execute(
                    "INSERT INTO sessions (id, title, created, updated,"
                    " workspace, messages) VALUES (?,?,?,?,?,?)",
                    (sid, "旧", 1.0, 1.0, "", _json.dumps(msgs,
                                                         ensure_ascii=False)))
                conn.commit()
            finally:
                conn.close()
        d = sessions.load(sid)
        assert d["messages"] == msgs
        assert d["notes"] == []

    def test_resave_preserves_created_and_workspace(self):
        sid = sessions.new_id()
        sessions.save(sid, [], "t", workspace="/ws/orig")
        sessions.save(sid, [], "t2")           # 不传 workspace
        d = sessions.load(sid)
        assert d["title"] == "t2"
        assert d["workspace"] == "/ws/orig"    # 原目录保留

    def test_load_missing_returns_none(self):
        assert sessions.load("no-such-id") is None

    def test_delete(self):
        sid = sessions.new_id()
        sessions.save(sid, [], "t")
        assert sessions.delete(sid) is True
        assert sessions.load(sid) is None
        assert sessions.delete(sid) is False


class TestListing:
    def test_filter_by_workspace(self):
        a, b = sessions.new_id(), sessions.new_id()
        sessions.save(a, [], "A", workspace="/ws/1")
        sessions.save(b, [], "B", workspace="/ws/2")
        only1 = sessions.list_sessions(workspace="/ws/1")
        assert [s["id"] for s in only1] == [a]
        assert len(sessions.list_sessions()) == 2

    def test_query_matches_title_and_body(self):
        a, b = sessions.new_id(), sessions.new_id()
        sessions.save(a, [{"role": "user", "content": "讨论一下数据库索引"}],
                      "普通标题")
        sessions.save(b, [{"role": "user", "content": "别的"}],
                      "包含关键词的标题")
        by_title = sessions.list_sessions(query="关键词")
        assert [s["id"] for s in by_title] == [b]
        by_body = sessions.list_sessions(query="数据库")
        assert [s["id"] for s in by_body] == [a]

    def test_sorted_by_updated_desc(self):
        ids = [sessions.new_id() for _ in range(3)]
        for i in ids:
            sessions.save(i, [], i)
        listed = sessions.list_sessions()
        assert len(listed) == 3
        assert listed[0]["updated"] >= listed[-1]["updated"]


class TestTitle:
    def test_long_text_truncated(self):
        t = sessions.make_title("x" * 100)
        assert len(t) == 25 and t.endswith("…")

    def test_whitespace_collapsed(self):
        assert sessions.make_title("a\n\n  b   c") == "a b c"

    def test_empty(self):
        assert sessions.make_title("   ") == "新会话"
