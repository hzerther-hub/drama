# -*- coding: utf-8 -*-
"""codegraph：代码知识图谱（原生 AST 建图 + 真实 CodeGraph 库只读复用）。"""

import os
import sqlite3

import pytest

import codegraph


@pytest.fixture()
def ws(tmp_path):
    """小型工作区：两个 Python 文件 + 一个 JS 文件，含调用/继承/导入关系。"""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "core.py").write_text(
        '"""核心模块。"""\n'
        "import os\n\n\n"
        "class Base:\n"
        '    """基类。"""\n'
        "    def run(self):\n"
        "        return helper(1)\n\n\n"
        "class Child(Base):\n"
        "    def go(self):\n"
        "        return run_all()\n\n\n"
        "def helper(x):\n"
        '    """干活的。"""\n'
        "    return os.path.join(str(x))\n\n\n"
        "def run_all():\n"
        "    b = Base()\n"
        "    return b.run()\n",
        encoding="utf-8")
    (tmp_path / "app.js").write_text(
        "export function main() { return 1; }\n"
        "class Panel {}\n",
        encoding="utf-8")
    return str(tmp_path)


def test_build_extracts_nodes_and_edges(ws):
    st = codegraph.build(ws)
    assert st["files"] == 3 and st["nodes"] > 5
    names = {n["name"] for n in codegraph.search(ws, "helper", 5)}
    assert "helper" in names
    kinds = {n["name"]: n["kind"] for n in codegraph.search(ws, "Base", 5)}
    assert kinds.get("Base") == "class"


def test_outline_lists_file_structure(ws):
    codegraph.build(ws)
    out = codegraph.outline(ws, "pkg/core.py")
    names = [r["name"] for r in out]
    assert "Base" in names and "Child" in names and "helper" in names
    assert [r["line"] for r in out] == sorted(r["line"] for r in out)


def test_callers_and_callees(ws):
    codegraph.build(ws)
    who = {c["name"] for c in codegraph.callers(ws, "helper")}
    assert "Base.run" in who or "run" in str(who)   # run() 调用了 helper
    deps = {c["name"] for c in codegraph.callees(ws, "run_all")}
    assert any("run" in d for d in deps)            # run_all 调用了 b.run()


def test_callers_matches_dotted_call(ws):
    """点分调用（tools.execute_tool）也要能被 callers 命中。"""
    (os.path.join(ws, "caller.py") if False else None)
    with open(os.path.join(ws, "caller.py"), "w", encoding="utf-8") as f:
        f.write("import pkg.core as core\n\n\n"
                "def entry():\n    return core.helper(1)\n")
    codegraph.build(ws, force=True)
    names = {c["name"] for c in codegraph.callers(ws, "helper")}
    assert "entry" in names


def test_incremental_skips_unchanged(ws):
    codegraph.build(ws)
    again = codegraph.build(ws)
    assert again["skipped"] == 3 and again["parsed"] == 0


def test_deleted_file_removed_from_graph(ws):
    codegraph.build(ws)
    os.remove(os.path.join(ws, "app.js"))
    codegraph.build(ws)
    assert codegraph.outline(ws, "app.js") == []
    assert "main" not in {n["name"] for n in codegraph.search(ws, "main", 5)}


def test_stats_reports_native_backend(ws):
    codegraph.build(ws)
    st = codegraph.stats(ws)
    assert st["built"] is True and st["nodes"] > 0
    assert st.get("backend", "native") == "native"


def test_non_python_uses_heuristic(ws):
    """JS 文件按启发式抓函数/类（不做全语言 AST）。"""
    codegraph.build(ws)
    kinds = {r["name"]: r["kind"] for r in codegraph.outline(ws, "app.js")}
    assert kinds.get("main") == "function"
    assert kinds.get("Panel") == "class"


# ---------------- 真实 CodeGraph 库（外部后端，只读） ----------------

def _make_external_ws(root):
    """按真实 CodeGraph schema 造一个迷你库，验证只读复用。"""
    d = os.path.join(root, ".codegraph")
    os.makedirs(d, exist_ok=True)
    db = os.path.join(d, "codegraph.db")
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE nodes (id INTEGER PRIMARY KEY, kind TEXT, name TEXT,"
        " qualified_name TEXT, file_path TEXT, language TEXT,"
        " start_line INTEGER, end_line INTEGER, docstring TEXT,"
        " signature TEXT);"
        "CREATE TABLE edges (id INTEGER PRIMARY KEY, source INTEGER,"
        " target INTEGER, kind TEXT);"
        "CREATE TABLE files (path TEXT PRIMARY KEY, language TEXT,"
        " node_count INTEGER);"
        "CREATE TABLE unresolved_refs (id INTEGER PRIMARY KEY);"
        "CREATE TABLE project_metadata (key TEXT, value TEXT);")
    c.execute("INSERT INTO files VALUES('a.php','php',2)")
    c.executemany("INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?)", [
        (1, "function", "orderList", "Order.orderList", "a.php", "php", 10, 20,
         "订单列表", "()"),
        (2, "method", "pay", "Order.pay", "a.php", "php", 25, 40, "", "($id)"),
    ])
    c.execute("INSERT INTO edges VALUES(1,1,2,'calls')")
    c.execute("INSERT INTO project_metadata VALUES('index_state','ready')")
    c.commit()
    c.close()
    return root


def test_external_backend_detected_and_read(tmp_path):
    ws = _make_external_ws(str(tmp_path))
    assert codegraph.backend(ws) == "external"
    st = codegraph.stats(ws)
    assert st["backend"] == "external" and st["nodes"] == 2
    assert st["index_state"] == "ready"
    hits = codegraph.search(ws, "orderList", 5)
    assert hits and hits[0]["name"] == "orderList"
    assert codegraph.outline(ws, "a.php")[0]["name"] == "orderList"
    assert {c["name"] for c in codegraph.callees(ws, "orderList")} == {"pay"}
    assert {c["name"] for c in codegraph.callers(ws, "pay")} == {"orderList"}


def test_external_ensure_does_not_rebuild(tmp_path):
    """有真实库时 ensure 只读复用，绝不重建（那是别人的图）。"""
    ws = _make_external_ws(str(tmp_path))
    before = os.path.getmtime(os.path.join(ws, ".codegraph", "codegraph.db"))
    st = codegraph.ensure(ws)
    assert st["backend"] == "external"
    assert os.path.getmtime(os.path.join(ws, ".codegraph", "codegraph.db")) == before


def test_external_search_prefers_indexed_like(tmp_path, monkeypatch):
    """外部库检索：先走索引友好的 LIKE，不应一上来就查 FTS。

    真实 CodeGraph 库里 FTS 可能未建完/失效（实测查询 0 行却耗时数十秒），
    而 name 列有索引、LIKE 是毫秒级——顺序错了工具就没法用。
    这里让任何 nodes_fts 查询直接抛错：只要结果仍能返回，就证明没依赖 FTS。
    """
    ws = _make_external_ws(str(tmp_path))
    real_conn = codegraph._ext_conn
    seen = []

    class _Proxy:
        def __init__(self, conn):
            self._c = conn

        def execute(self, sql, *a):
            seen.append(sql)
            if "nodes_fts" in sql:
                raise AssertionError("不应该查 FTS：" + sql[:60])
            return self._c.execute(sql, *a)

        def close(self):
            self._c.close()

    monkeypatch.setattr(codegraph, "_ext_conn", lambda w: _Proxy(real_conn(w)))
    rows = codegraph.search(ws, "orderList", 5)
    assert rows and rows[0]["name"] == "orderList"
    assert any("name = ?" in c for c in seen)          # 精确优先


def test_external_search_falls_back_to_contains(tmp_path):
    """精确/前缀都没有时，退到「包含」仍能命中（走索引列）。"""
    ws = _make_external_ws(str(tmp_path))
    rows = codegraph.search(ws, "rder", 5)             # 只匹配中段
    assert any(r["name"] == "orderList" for r in rows)
