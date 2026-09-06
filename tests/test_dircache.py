# -*- coding: utf-8 -*-
"""dircache：工作区文件清单快照（@ 候选联想用）。"""

import dircache


def test_list_files_walks_and_marks_dirs(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    files = dircache.list_files(str(tmp_path))
    assert "src/" in files
    assert "src/a.py" in files
    assert "README.md" in files


def test_ttl_cache_hides_changes_until_invalidate(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    files1 = dircache.list_files(str(tmp_path))
    assert "a.txt" in files1
    # TTL 内新增文件 → 快照不变
    (tmp_path / "b.txt").write_text("x", encoding="utf-8")
    assert "b.txt" not in dircache.list_files(str(tmp_path))
    # 手动失效 → 重建可见
    dircache.invalidate(str(tmp_path))
    assert "b.txt" in dircache.list_files(str(tmp_path))


def test_skip_dirs_excluded(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("x", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    files = dircache.list_files(str(tmp_path))
    assert not any("node_modules" in f or ".git" in f for f in files)


def test_workspace_switch_isolated(tmp_path):
    w1 = tmp_path / "w1"
    w2 = tmp_path / "w2"
    w1.mkdir()
    w2.mkdir()
    (w1 / "one.txt").write_text("x", encoding="utf-8")
    (w2 / "two.txt").write_text("x", encoding="utf-8")
    assert "one.txt" in dircache.list_files(str(w1))
    assert "two.txt" in dircache.list_files(str(w2))
    # 全局失效后两者仍可重建
    dircache.invalidate()
    assert "one.txt" in dircache.list_files(str(w1))
    assert "two.txt" in dircache.list_files(str(w2))
