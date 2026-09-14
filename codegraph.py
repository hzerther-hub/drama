# -*- coding: utf-8 -*-
"""代码知识图谱（CodeGraph）：AST → 节点/边 → SQLite，供 agent 直接查询。

与 `codeindex.py`（TF-IDF 文本块检索）互补，本模块回答的是**结构问题**：
「这个函数定义在哪」「谁调用了它」「这个文件里有什么」「它的上下游是什么」。
模型不必再 grep→读整文件→再猜，直接查图，省 token 也少走弯路。

设计要点：
- 解析分层：Python 用标准库 `ast` 精确取（定义/导入/调用/继承）；
  其它语言用轻量正则启发式（可识别 func/function/fn/class 等常见声明），
  识别不出就只记文件、不硬猜——宁缺毋滥。
- 存储：`CONFIG_DIR/codegraph/<工作目录哈希>.db`，SQLite；节点名/文档走 FTS5，
  环境不支持 FTS5 时自动退化为 LIKE（并在 stats 里如实标注）。
- 增量：按 mtime/size 跳过未变文件；删除的文件从图里摘掉。
- 失败静默：图不可用不影响业务（与 codeindex / codera 同一哲学）。
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sqlite3
import threading
import time

import codeindex
import config

# 图库放在 index/ 同级，便于一起清理
_DIR = "codegraph"

# 要纳入图的文件：复用 codeindex 的扩展名白名单（含 .md 之外的代码件）
EXTS = codeindex.EXTS

# 常见语言的声明启发式（非 Python 用）：只认「行首/缩进后出现关键字 + 名字」
_LANG_PATTERNS = {
    ".js": ("js", r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)",
            r"^\s*(?:export\s+)?class\s+(\w+)"),
    ".ts": ("ts", r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)",
            r"^\s*(?:export\s+)?class\s+(\w+)"),
    ".go": ("go", r"^\s*func\s+(?:\([^)]*\)\s*)?(\w+)",
            r"^\s*type\s+(\w+)\s+struct"),
    ".java": ("java", r"^\s*(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\(",
              r"^\s*(?:public|private|protected)?\s*(?:final\s+)?class\s+(\w+)"),
    ".rs": ("rust", r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)",
            r"^\s*(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)"),
    ".c": ("c", r"^[\w\*\s]+?\b(\w+)\s*\([^;]*\)\s*\{", r"^\s*(?:typedef\s+)?struct\s+(\w+)"),
    ".h": ("c", r"^[\w\*\s]+?\b(\w+)\s*\([^;]*\)\s*\{", r"^\s*(?:typedef\s+)?struct\s+(\w+)"),
}
_LANG_PATTERNS[".cpp"] = _LANG_PATTERNS[".c"]
_LANG_PATTERNS[".cc"] = _LANG_PATTERNS[".c"]
_LANG_PATTERNS[".hpp"] = _LANG_PATTERNS[".c"]
_LANG_PATTERNS[".jsx"] = _LANG_PATTERNS[".js"]
_LANG_PATTERNS[".tsx"] = _LANG_PATTERNS[".ts"]
_LANG_PATTERNS[".mjs"] = _LANG_PATTERNS[".js"]

_SKIP_DIRS = {"node_modules", "dist", "build", "target", "out"}

_lock = threading.RLock()


# ---------------- 库 ----------------

def _db_path(workspace: str) -> str:
    d = os.path.join(config.CONFIG_DIR, _DIR)
    key = hashlib.md5(os.path.abspath(workspace).encode("utf-8")).hexdigest()[:12]
    return os.path.join(d, key + ".db")


def _conn(workspace: str) -> sqlite3.Connection:
    path = _db_path(workspace)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS files ("
        " path TEXT PRIMARY KEY, mtime REAL, size INTEGER, lang TEXT,"
        " n_nodes INTEGER DEFAULT 0);"
        "CREATE TABLE IF NOT EXISTS nodes ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, kind TEXT,"
        " path TEXT, lineno INTEGER, endline INTEGER, sig TEXT, doc TEXT,"
        " parent TEXT);"
        "CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);"
        "CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);"
        "CREATE TABLE IF NOT EXISTS edges ("
        " src_id INTEGER, dst_name TEXT, dst_id INTEGER, kind TEXT);"
        "CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id);"
        "CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_id);"
        "CREATE INDEX IF NOT EXISTS idx_edges_dstname ON edges(dst_name);")
    try:                                   # FTS5 可用则建全文索引
        conn.executescript(
            "CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5("
            " name, doc, sig, content='nodes', content_rowid='id');")
    except sqlite3.OperationalError:
        pass                               # 不支持 FTS5：search 退化为 LIKE
    return conn


def _has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='nodes_fts'"
    ).fetchone()
    return row is not None


# ---------------- 解析 ----------------

def _iter_files(workspace: str):
    """遍历工作区代码文件（跳过 .git/依赖目录与超大文件）。"""
    for root, dirs, names in os.walk(workspace):
        dirs[:] = [d for d in dirs
                   if d not in _SKIP_DIRS and not d.startswith(".")]
        for n in names:
            ext = os.path.splitext(n)[1].lower()
            if ext in EXTS:
                yield os.path.join(root, n)


def _rel(workspace: str, path: str) -> str:
    try:
        return os.path.relpath(path, workspace).replace("\\", "/")
    except ValueError:
        return path.replace("\\", "/")


def _first_doc(node) -> str:
    """取 docstring 首行（节点说明，给模型看的短描述）。"""
    d = ast.get_docstring(node) if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) else None
    if not d:
        return ""
    return d.strip().splitlines()[0][:120]


def _signature(node) -> str:
    """函数签名文本（不含函数体），供模型判断参数形状。"""
    try:
        a = node.args
        parts = [x.arg for x in getattr(a, "posonlyargs", []) + a.args]
        if a.vararg:
            parts.append("*" + a.vararg.arg)
        elif a.kwonlyargs:
            parts.append("*")
        parts += [x.arg for x in a.kwonlyargs]
        if a.kwarg:
            parts.append("**" + a.kwarg.arg)
        return f"({', '.join(parts)})"
    except Exception:                      # noqa: BLE001
        return "(…)"


def _parse_python(path: str, rel: str) -> tuple[list, list]:
    """返回 (nodes, edges)。nodes 为 dict 列表，edges 为 (src 索引, 名字, 类型)。"""
    with open(path, "rb") as f:
        src = f.read()
    tree = ast.parse(src, filename=path)
    nodes, edges = [], []
    index: dict[str, int] = {}             # 限定名 → nodes 下标

    def add(name, kind, lineno, endline, sig, doc, parent):
        index[name] = len(nodes)
        nodes.append({"name": name, "kind": kind, "lineno": lineno,
                      "endline": endline, "sig": sig, "doc": doc,
                      "parent": parent})

    def walk(body, parent=""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qn = f"{parent}.{node.name}" if parent else node.name
                add(qn, "function", node.lineno,
                    getattr(node, "end_lineno", node.lineno),
                    _signature(node), _first_doc(node), parent)
                for dec in node.decorator_list:      # 装饰器也是引用
                    for nm in _names_in(dec):
                        edges.append((index[qn], nm, "decorates"))
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        nm = _dotted(child.func)
                        if nm:
                            edges.append((index[qn], nm, "calls"))
                walk(node.body, qn)
            elif isinstance(node, ast.ClassDef):
                qn = f"{parent}.{node.name}" if parent else node.name
                add(qn, "class", node.lineno,
                    getattr(node, "end_lineno", node.lineno),
                    "", _first_doc(node), parent)
                for base in node.bases:
                    for nm in _names_in(base):
                        edges.append((index[qn], nm, "inherits"))
                walk(node.body, qn)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", None) or ""
                for alias in node.names:
                    tgt = f"{mod}.{alias.name}" if mod else alias.name
                    edges.append((-1, tgt, "imports"))   # -1 = 文件级
    walk(tree.body)
    return nodes, edges


def _names_in(node) -> list[str]:
    """从调用/装饰器/基类表达式里取出被引用的名字（支持 a.b.c 与嵌套）。"""
    out = []
    if isinstance(node, ast.Name):
        out.append(node.id)
    elif isinstance(node, ast.Attribute):
        out.extend(_names_in(node.value))
        out.append(node.attr)
    elif isinstance(node, ast.Call):
        out.extend(_names_in(node.func))
    elif isinstance(node, ast.Subscript):
        out.extend(_names_in(node.value))
    elif isinstance(node, (ast.Tuple, ast.List)):
        for e in node.elts:
            out.extend(_names_in(e))
    return [x for x in out if x]


def _dotted(node) -> str:
    """把调用目标还原为**点分名**：sqlite3.connect / self._conn → _conn。

    只记点分名而非逐个前缀，是为了避免同名误连：`sqlite3.connect(...)` 若
    按最后一段 `connect` 连边，会错连到仓库里另一个叫 connect 的函数。
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        if not base or base == "self":     # self.xxx → 本类方法，取方法名
            return node.attr
        return f"{base}.{node.attr}"
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    if isinstance(node, ast.Subscript):
        return _dotted(node.value)
    return ""


def _parse_heuristic(path: str, rel: str) -> tuple[list, list]:
    """非 Python：按语言模式抓声明（找不准就不记，避免污染图）。"""
    ext = os.path.splitext(path)[1].lower()
    lang, fn_pat, cls_pat = _LANG_PATTERNS.get(ext, (ext.lstrip("."), None, None))
    if not fn_pat:
        return [], []
    nodes = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if len(line) > 400 and not line.strip().startswith(("func", "fn", "def")):
                    continue
                m = re.match(cls_pat, line) if cls_pat else None
                kind, name = ("class", m.group(1)) if m else (None, None)
                if not name:
                    m = re.match(fn_pat, line)
                    kind, name = ("function", m.group(1)) if m else (None, None)
                if name:
                    nodes.append({"name": name, "kind": kind, "lineno": i,
                                  "endline": i, "sig": "", "doc": "", "parent": ""})
    except OSError:
        return [], []
    return nodes, []


# ---------------- 真实 CodeGraph 库（外部后端，只读） ----------------
# CodeGraph（Rust 版）把图存在工作区 <ws>/.codegraph/codegraph.db，schema 为
# nodes(id,kind,name,qualified_name,file_path,language,start_line,end_line,
#       docstring,signature,…) / edges(id,source,target,kind,…) /
# files(path,…) / unresolved_refs(…)。
# 只要工作区里有这个库就直接读它——用户已有的图零成本复用，不必再建一份。
CODEGRAPH_DIR = ".codegraph"
CODEGRAPH_DB = "codegraph.db"


def external_db(workspace: str) -> str:
    """真实 CodeGraph 库路径（不存在返回空串）。"""
    p = os.path.join(os.path.abspath(workspace), CODEGRAPH_DIR, CODEGRAPH_DB)
    return p if os.path.isfile(p) else ""


def backend(workspace: str) -> str:
    """当前用哪个后端：'external'（真实 CodeGraph 库）/ 'native'（自建图）。"""
    return "external" if external_db(workspace) else "native"


def _ext_conn(workspace: str) -> sqlite3.Connection:
    """只读打开真实 CodeGraph 库（绝不写入别人的库）。"""
    conn = sqlite3.connect(f"file:{external_db(workspace)}?mode=ro&immutable=0",
                           uri=True, timeout=15)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _ext_search(ws: str, query: str, top_k: int) -> list[dict]:
    """符号检索：精确 → 前缀 → 包含 → FTS，逐级升级。

    实测（真实 CodeGraph 库，17.5 万节点）：该库 name 上有索引，LIKE 查询
    0.0x 秒返回；而它的 FTS 索引可能未建完/失效（查询返回 0 行且耗时
    9-38 秒）。所以**不能 FTS 优先**——先走索引友好的 LIKE 三级，
    都空了才用 FTS 兜文档/签名里的词（概念检索）。
    """
    conn = _ext_conn(ws)
    cols = ("name, kind, file_path, start_line, signature, docstring")
    try:
        rows = []
        # 1) 精确同名 / 限定同名
        rows = conn.execute(
            f"SELECT {cols} FROM nodes WHERE name = ? OR qualified_name = ?"
            " ORDER BY length(name) LIMIT ?", (query, query, top_k)).fetchall()
        # 2) 前缀（LIKE 'x%' 可走索引）
        if not rows:
            rows = conn.execute(
                f"SELECT {cols} FROM nodes WHERE name LIKE ? || '%'"
                " OR qualified_name LIKE '%' || ? ORDER BY length(name) LIMIT ?",
                (query, "." + query, top_k)).fetchall()
        # 3) 包含
        if not rows:
            like = f"%{query}%"
            rows = conn.execute(
                f"SELECT {cols} FROM nodes WHERE name LIKE ?"
                " OR qualified_name LIKE ? ORDER BY length(name) LIMIT ?",
                (like, like, top_k)).fetchall()
        # 4) 仍为空 → FTS 兜底（文档/签名里的词；库健康时才快）
        if not rows:
            try:
                toks = [t for t in re.split(r"[^\w\u4e00-\u9fff]+", query) if t]
                if toks:
                    match = "{name qualified_name} : " + " ".join(
                        t + "*" for t in toks[:6])
                    rows = conn.execute(
                        "SELECT n.name, n.kind, n.file_path, n.start_line,"
                        " n.signature, n.docstring FROM nodes_fts f"
                        " JOIN nodes n ON n.id = f.rowid"
                        " WHERE nodes_fts MATCH ? LIMIT ?",
                        (match, top_k)).fetchall()
            except sqlite3.Error:
                rows = []
    finally:
        conn.close()
    return [{"name": r[0], "kind": r[1], "path": r[2], "line": r[3],
             "sig": r[4] or "", "doc": (r[5] or "").splitlines()[0][:120]
             if r[5] else ""} for r in rows]


def _ext_outline(ws: str, path: str) -> list[dict]:
    conn = _ext_conn(ws)
    try:
        rows = conn.execute(
            "SELECT name, kind, start_line, end_line, signature, docstring"
            " FROM nodes WHERE file_path=? AND kind NOT IN ('file','import')"
            " ORDER BY start_line", (path.replace("\\", "/"),)).fetchall()
    finally:
        conn.close()
    return [{"name": r[0], "kind": r[1], "line": r[2], "endline": r[3],
             "sig": r[4] or "", "doc": (r[5] or "").splitlines()[0][:120]
             if r[5] else ""} for r in rows]


def _ext_node_ids(conn, name: str) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM nodes WHERE name=? OR qualified_name=?"
        " OR qualified_name LIKE ?", (name, name, f"%.{name}")).fetchall()
    return [r[0] for r in rows]


def _ext_callers(ws: str, name: str, limit: int) -> list[dict]:
    conn = _ext_conn(ws)
    try:
        ids = _ext_node_ids(conn, name)
        if not ids:
            return []
        qs = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT DISTINCT s.name, s.kind, s.file_path, s.start_line, e.kind"
            f" FROM edges e JOIN nodes s ON s.id = e.source"
            f" WHERE e.target IN ({qs}) AND s.kind != 'file' LIMIT ?",
            (*ids, limit)).fetchall()
    finally:
        conn.close()
    return [{"name": r[0], "kind": r[1], "path": r[2], "line": r[3],
             "via": r[4]} for r in rows]


def _ext_callees(ws: str, name: str, limit: int) -> list[dict]:
    conn = _ext_conn(ws)
    try:
        ids = _ext_node_ids(conn, name)
        if not ids:
            return []
        qs = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT DISTINCT d.name, e.kind, d.file_path, d.start_line"
            f" FROM edges e LEFT JOIN nodes d ON d.id = e.target"
            f" WHERE e.source IN ({qs}) AND e.kind IN"
            f" ('calls','instantiates','references','extends','implements')"
            f" LIMIT ?", (*ids, limit)).fetchall()
    finally:
        conn.close()
    return [{"name": r[0], "kind": r[1], "path": r[2], "line": r[3]}
            for r in rows if r[0]]


def _ext_subgraph(ws: str, name: str, depth: int) -> list[dict]:
    seen, frontier, out = {name}, [name], []
    depth = max(1, min(int(depth or 2), 3))
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for c in _ext_callees(ws, n, 10):
                out.append({"from": n, "to": c["name"], "kind": c["kind"]})
                if c["name"] not in seen:
                    seen.add(c["name"]); nxt.append(c["name"])
            for c in _ext_callers(ws, n, 10):
                out.append({"from": c["name"], "to": n, "kind": c["via"]})
                if c["name"] not in seen:
                    seen.add(c["name"]); nxt.append(c["name"])
        frontier = nxt
        if not frontier:
            break
    return out[:60]


def _ext_stats(ws: str) -> dict:
    conn = _ext_conn(ws)
    try:
        files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        langs = dict(conn.execute(
            "SELECT language, COUNT(*) FROM files GROUP BY language"
            " ORDER BY 2 DESC LIMIT 8").fetchall())
        unresolved = 0
        try:
            unresolved = conn.execute(
                "SELECT COUNT(*) FROM unresolved_refs").fetchone()[0]
        except sqlite3.Error:
            pass
        state = ""
        try:
            row = conn.execute("SELECT value FROM project_metadata"
                               " WHERE key='index_state'").fetchone()
            state = row[0] if row else ""
        except sqlite3.Error:
            pass
    finally:
        conn.close()
    return {"files": files, "nodes": nodes, "edges": edges, "langs": langs,
            "db": external_db(ws), "built": nodes > 0, "fts": True,
            "backend": "external", "index_state": state,
            "unresolved": unresolved}


# ---------------- 建图 ----------------

def build(workspace: str, force: bool = False, progress=None) -> dict:
    """增量建图：只重解析 mtime/size 变化的文件；已删文件从图中摘除。

    返回 {"files", "nodes", "edges", "parsed", "skipped", "db", "fts"}。
    """
    workspace = os.path.abspath(workspace)
    progress = progress or (lambda *a, **k: None)
    with _lock:
        conn = _conn(workspace)
        try:
            known = {r[0]: (r[1], r[2]) for r in conn.execute(
                "SELECT path, mtime, size FROM files")}
            seen, parsed, skipped = set(), 0, 0
            for full in _iter_files(workspace):
                rel = _rel(workspace, full)
                seen.add(rel)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                old = known.get(rel)
                if not force and old and abs(old[0] - st.st_mtime) < 1 \
                        and old[1] == st.st_size:
                    skipped += 1
                    continue
                _index_one(conn, workspace, full, rel, st)
                parsed += 1
                if parsed % 20 == 0:
                    progress(parsed, len(seen))
            for gone in set(known) - seen:         # 文件已删：摘节点与边
                conn.execute("DELETE FROM nodes WHERE path=?", (gone,))
                conn.execute("DELETE FROM files WHERE path=?", (gone,))
            conn.execute("DELETE FROM edges WHERE src_id NOT IN "
                         "(SELECT id FROM nodes) AND src_id != -1")
            _resolve_edges(conn)
            if _has_fts(conn):
                conn.execute("INSERT INTO nodes_fts(nodes_fts) VALUES('rebuild')")
            conn.commit()
            n_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            n_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            n_files = len(seen)
        finally:
            conn.close()
    return {"files": n_files, "nodes": n_nodes, "edges": n_edges,
            "parsed": parsed, "skipped": skipped,
            "db": _db_path(workspace), "fts": True}


def _index_one(conn, workspace, full, rel, st):
    """解析并写入单个文件（先清旧记录，保证幂等）。"""
    lang = os.path.splitext(rel)[1].lstrip(".").lower() or "txt"
    if lang == "py":
        try:
            nodes, edges = _parse_python(full, rel)
        except (SyntaxError, ValueError, OSError):
            nodes, edges = [], []          # 语法不合法：只登记文件
    else:
        nodes, edges = _parse_heuristic(full, rel)
    conn.execute("DELETE FROM nodes WHERE path=?", (rel,))
    conn.execute("DELETE FROM files WHERE path=?", (rel,))
    conn.execute("INSERT INTO files(path, mtime, size, lang, n_nodes)"
                 " VALUES(?,?,?,?,?)",
                 (rel, st.st_mtime, st.st_size, lang, len(nodes)))
    ids = []
    for n in nodes:
        cur = conn.execute(
            "INSERT INTO nodes(name, kind, path, lineno, endline, sig, doc, parent)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (n["name"], n["kind"], rel, n["lineno"], n["endline"],
             n["sig"], n["doc"], n["parent"]))
        ids.append(cur.lastrowid)
    for src, dst, kind in edges:
        sid = -1 if src < 0 else (ids[src] if src < len(ids) else -1)
        if isinstance(src, int) and 0 <= src < len(ids):
            sid = ids[src]
        conn.execute("INSERT INTO edges(src_id, dst_name, dst_id, kind)"
                     " VALUES(?,?,NULL,?)", (sid, dst, kind))


def _resolve_edges(conn):
    """把边上的名字解析到节点 id（唯一命中才连，避免猜错）。"""
    names = {}
    for nid, name in conn.execute("SELECT id, name FROM nodes"):
        names.setdefault(name.split(".")[-1], []).append(nid)
    for dst in {r[0] for r in conn.execute(
            "SELECT DISTINCT dst_name FROM edges WHERE dst_id IS NULL")}:
        hits = names.get(dst or "")
        if hits and len(hits) == 1:
            conn.execute("UPDATE edges SET dst_id=? WHERE dst_name=? AND dst_id IS NULL",
                         (hits[0], dst))


def ensure(workspace: str, progress=None) -> dict:
    """图不存在（或无节点）时自动建一次；已有则直接返回统计。

    工作区里有真实 CodeGraph 库时**只读复用**，绝不重建（那是别人的图）。
    """
    st = stats(workspace)
    if st.get("backend") == "external":
        return st
    if st.get("nodes"):
        return st
    return build(workspace, progress=progress)


# ---------------- 查询 ----------------

def search(workspace: str, query: str, top_k: int = 8) -> list[dict]:
    """按名字/文档/签名搜符号；有真实 CodeGraph 库则直接读它。"""
    query = (query or "").strip()
    if not query:
        return []
    if backend(workspace) == "external":
        return _ext_search(workspace, query, top_k)
    with _lock:
        conn = _conn(workspace)
        try:
            if _has_fts(conn):
                # 与外部后端一致：FTS 限定 name 列 + 按相关度排序。
                # 不限定列会连 doc/sig 里的任意词一起匹配，噪声大。
                sql = ("SELECT n.name, n.kind, n.path, n.lineno, n.sig, n.doc"
                       " FROM nodes_fts f JOIN nodes n ON n.id = f.rowid"
                       " WHERE nodes_fts MATCH ? ORDER BY rank LIMIT ?")
                try:
                    toks = [t for t in re.split(r"[^\w\u4e00-\u9fff]+", query) if t]
                    match = "{name} : " + " ".join(t + "*" for t in toks[:6])
                    rows = conn.execute(sql, (match, top_k)).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            else:
                rows = []
            if not rows:                   # LIKE 兜底（也覆盖 FTS 语法不匹配）
                like = f"%{query}%"
                rows = conn.execute(
                    "SELECT name, kind, path, lineno, sig, doc FROM nodes"
                    " WHERE name LIKE ? OR doc LIKE ? OR sig LIKE ?"
                    " ORDER BY CASE WHEN name LIKE ? THEN 0 ELSE 1 END, length(name)"
                    " LIMIT ?",
                    (like, like, like, f"{query}%", top_k)).fetchall()
        finally:
            conn.close()
    return [{"name": r[0], "kind": r[1], "path": r[2], "line": r[3],
             "sig": r[4], "doc": r[5]} for r in rows]


def _fts_query(q: str) -> str:
    """把用户输入转成安全的 FTS 前缀查询（去掉语法字符，末项前缀匹配）。"""
    toks = [t for t in re.split(r"[^\w\u4e00-\u9fff]+", q) if t]
    return " ".join(t + "*" for t in toks[:6]) or '""'


def outline(workspace: str, path: str) -> list[dict]:
    """单文件结构：类/函数按行号排序（给模型当「目录」用）。"""
    if backend(workspace) == "external":
        return _ext_outline(workspace, path)
    with _lock:
        conn = _conn(workspace)
        try:
            rows = conn.execute(
                "SELECT name, kind, lineno, endline, sig, doc FROM nodes"
                " WHERE path=? ORDER BY lineno", (path,)).fetchall()
        finally:
            conn.close()
    return [{"name": r[0], "kind": r[1], "line": r[2], "endline": r[3],
             "sig": r[4], "doc": r[5]} for r in rows]


def _named_nodes(conn, name: str) -> list:
    return conn.execute(
        "SELECT id, name, kind, path, lineno, sig FROM nodes"
        " WHERE name=? OR name LIKE ?", (name, f"%.{name}")).fetchall()


def callers(workspace: str, name: str, limit: int = 15) -> list[dict]:
    """谁调用了 name（按边反向查）。

    同时匹配裸名与点分调用（tools.execute_tool）——只按裸名匹配会漏掉
    带模块前缀的调用，这是最初版本的漏配原因。
    """
    if backend(workspace) == "external":
        return _ext_callers(workspace, name, limit)
    with _lock:
        conn = _conn(workspace)
        try:
            targets = [r[0] for r in _named_nodes(conn, name)]
            conds = ["e.dst_name = ?", "e.dst_name LIKE ?"]
            params: list = [name, f"%.{name}"]
            if targets:
                conds.append(f"e.dst_id IN ({','.join('?' * len(targets))})")
                params.extend(targets)
            rows = conn.execute(
                f"SELECT DISTINCT s.name, s.kind, s.path, s.lineno, e.kind"
                f" FROM edges e JOIN nodes s ON s.id = e.src_id"
                f" WHERE e.src_id != -1 AND ({' OR '.join(conds)}) LIMIT ?",
                (*params, limit)).fetchall()
        finally:
            conn.close()
    return [{"name": r[0], "kind": r[1], "path": r[2], "line": r[3],
             "via": r[4]} for r in rows]


def callees(workspace: str, name: str, limit: int = 20) -> list[dict]:
    """name 调用了谁 / 依赖谁（按边正向查）。"""
    if backend(workspace) == "external":
        return _ext_callees(workspace, name, limit)
    with _lock:
        conn = _conn(workspace)
        try:
            srcs = [r[0] for r in _named_nodes(conn, name)]
            if not srcs:
                return []
            qs = ",".join("?" * len(srcs))
            rows = conn.execute(
                f"SELECT DISTINCT e.dst_name, e.kind, d.path, d.lineno"
                f" FROM edges e LEFT JOIN nodes d ON d.id = e.dst_id"
                f" WHERE e.src_id IN ({qs}) AND e.kind != 'imports'"
                # 已解析到本仓库定义的排前面，未解析的（库函数/属性链）靠后
                f" ORDER BY d.path IS NULL, length(e.dst_name) LIMIT ?",
                (*srcs, limit)).fetchall()
            imports = conn.execute(
                f"SELECT DISTINCT e.dst_name FROM edges e JOIN nodes s"
                f" ON s.id = e.src_id WHERE s.path IN"
                f" (SELECT path FROM nodes WHERE id IN ({qs}))"
                f" AND e.kind = 'imports' LIMIT 12", tuple(srcs)).fetchall()
        finally:
            conn.close()
    out = [{"name": r[0], "kind": r[1], "path": r[2], "line": r[3]}
           for r in rows]
    if imports:
        out.append({"name": "imports: " + ", ".join(x[0] for x in imports),
                    "kind": "import", "path": "", "line": 0})
    return out


def subgraph(workspace: str, name: str, depth: int = 2) -> list[dict]:
    """以 name 为中心、depth 层的上下游关系（供模型一次性看清结构）。"""
    if backend(workspace) == "external":
        return _ext_subgraph(workspace, name, depth)
    seen, frontier, out = {name}, [name], []
    depth = max(1, min(int(depth or 2), 3))
    for _ in range(depth):
        nxt = []
        for n in frontier:
            for c in callees(workspace, n, limit=12):
                out.append({"from": n, "to": c["name"], "kind": c["kind"]})
                if c["name"] not in seen:
                    seen.add(c["name"])
                    nxt.append(c["name"])
            for c in callers(workspace, n, limit=12):
                out.append({"from": c["name"], "to": n, "kind": c["via"]})
                if c["name"] not in seen:
                    seen.add(c["name"])
                    nxt.append(c["name"])
        frontier = nxt
        if not frontier:
            break
    return out[:60]


def stats(workspace: str) -> dict:
    """图概况：文件/节点/边数、语言分布、库路径、后端与 FTS 状态。"""
    if backend(workspace) == "external":
        return _ext_stats(workspace)
    if not os.path.isfile(_db_path(workspace)):
        return {"files": 0, "nodes": 0, "edges": 0, "langs": {},
                "db": _db_path(workspace), "built": False}
    with _lock:
        conn = _conn(workspace)
        try:
            files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            langs = dict(conn.execute(
                "SELECT lang, COUNT(*) FROM files GROUP BY lang"
                " ORDER BY 2 DESC LIMIT 8").fetchall())
            fts = _has_fts(conn)
        finally:
            conn.close()
    return {"files": files, "nodes": nodes, "edges": edges, "langs": langs,
            "db": _db_path(workspace), "built": nodes > 0, "fts": fts}
