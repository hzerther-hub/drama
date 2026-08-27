# -*- coding: utf-8 -*-
"""代码库索引：解析 → 分块 → 向量化（TF-IDF）→ SQLite 可检索数据库。

思路同 opencode-codebase-index / @op1/code-intel：不是把全部代码塞进
提示词，而是建立可按相关度检索的代码块库；模型用 index_search 取回
最相关的片段，再精读，大幅省 tokens。

特性：
- 代码感知分词：拆 camelCase / snake_case，保留标识符与关键字
- TF-IDF 向量 + 余弦相关度排序（纯 numpy，无外部依赖）
- SQLite 持久化（按 workspace 哈希分库，放 config.CONFIG_DIR/index/）
- 增量更新：按文件 mtime/size 跳过未变化文件
- 自动跳过 .git / node_modules / __pycache__ / build / dist 等
"""

from __future__ import annotations
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time

import config

# ---------------- 常量 ----------------

CHUNK_LINES = 50          # 每块行数
CHUNK_OVERLAP = 10        # 相邻块重叠行数（保证边界上下文）
MAX_FILE_BYTES = 1_000_000        # 超过 1MB 的文件跳过（多半是生成物/数据）
EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".h", ".cpp", ".hpp",
    ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala",
    ".sh", ".bash", ".zsh", ".sql", ".html", ".css", ".scss", ".vue", ".svelte",
    ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", "venv", ".venv",
    "env", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", "target",
    ".idea", ".vscode", ".next", ".nuxt", "vendor", "bower_components",
}

_index_lock = threading.Lock()
_conns: dict[str, sqlite3.Connection] = {}


# ---------------- 分词（代码感知） ----------------

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_CAMEL_RE = re.compile(
    r"[A-Z]+(?=[A-Z][a-z0-9])|[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z0-9])")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "not", "is", "are", "was", "were", "in",
    "on", "at", "to", "of", "for", "with", "by", "from", "as", "this",
    "that", "it", "be", "been", "has", "have", "had", "do", "does", "did",
    "if", "then", "else", "elif", "return", "def", "class", "import",
    "from", "self", "true", "false", "none", "null", "void", "int", "str",
}


def tokenize(text: str) -> list[str]:
    """把代码文本拆成检索词：标识符 + camelCase/snake_case 子词 + 中文 bigram。"""
    words: list[str] = []
    for ident in _IDENT_RE.findall(text):
        low = ident.lower()
        if low in _STOPWORDS or len(low) < 2:
            continue
        words.append(low)
        if "_" in ident:                       # snake_case → 子词
            for part in ident.split("_"):
                p = part.lower()
                if len(p) >= 2 and p != low:
                    words.append(p)
        if any(c.isupper() for c in ident[1:]):  # camelCase → 子词
            for part in _CAMEL_RE.findall(ident):
                p = part.lower()
                if len(p) >= 2 and p != low:
                    words.append(p)
    for seg in _CJK_RE.findall(text):           # 中文 → bigram（覆盖注释/文档）
        words.append(seg[:2])
        for i in range(len(seg) - 2 + 1):
            words.append(seg[i:i + 2])
    return words


# ---------------- 分块 ----------------

def _chunk_lines(lines: list[str]):
    """把文件切成带重叠的行块，yield (start_line, end_line)。行号从 1 开始。"""
    step = CHUNK_LINES - CHUNK_OVERLAP
    start = 0
    while start < len(lines):
        end = min(start + CHUNK_LINES, len(lines))
        yield start + 1, end
        if end == len(lines):
            break
        start += step


# ---------------- 数据库 ----------------

def _db_path(workspace: str) -> str:
    ws_hash = hashlib.sha256(workspace.encode()).hexdigest()[:16]
    d = os.path.join(config.CONFIG_DIR, "index")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{ws_hash}.db")


def _conn(workspace: str) -> sqlite3.Connection:
    key = _db_path(workspace)
    with _index_lock:
        if key not in _conns:
            c = sqlite3.connect(key, check_same_thread=False)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(
                "CREATE TABLE IF NOT EXISTS files ("
                "  path TEXT PRIMARY KEY, mtime REAL, size INTEGER)")
            c.execute(
                "CREATE TABLE IF NOT EXISTS chunks ("
                "  file TEXT, start_line INTEGER, end_line INTEGER,"
                "  content TEXT, terms TEXT)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_chunks_file ON chunks(file)")
            c.commit()
            _conns[key] = c
        return _conns[key]


# ---------------- 索引构建（增量） ----------------

def build(workspace: str, force: bool = False, progress=None) -> dict:
    """扫描 workspace 建索引。返回统计。progress(done, total) 可选回调。"""
    t0 = time.time()
    conn = _conn(workspace)
    workspace = os.path.abspath(workspace)

    # 收集待索引文件
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(workspace):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXTS:
                p = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(p) <= MAX_FILE_BYTES:
                        files.append(p)
                except OSError:
                    continue

    # 已索引且未变的文件
    known: dict[str, tuple[float, int]] = {}
    for path, mtime, size in conn.execute("SELECT path, mtime, size FROM files"):
        known[path] = (mtime, size)

    todo = []
    for p in files:
        try:
            st = os.stat(p)
            sig = (st.st_mtime, st.st_size)
        except OSError:
            continue
        rel = os.path.relpath(p, workspace)
        if not force and known.get(rel) == sig:
            continue
        todo.append((p, rel, sig))
    # 已删除的文件：清掉
    valid = {os.path.relpath(p, workspace) for p in files}
    for (path,) in list(conn.execute("SELECT path FROM files")):
        if path not in valid:
            conn.execute("DELETE FROM files WHERE path=?", (path,))
            conn.execute("DELETE FROM chunks WHERE file=?", (path,))

    done = 0
    for p, rel, sig in todo:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        conn.execute("DELETE FROM chunks WHERE file=?", (rel,))
        for start, end in _chunk_lines(lines):
            content = "\n".join(lines[start - 1:end])
            terms = tokenize(content)
            if not terms:
                continue
            conn.execute(
                "INSERT INTO chunks (file, start_line, end_line, content, terms)"
                " VALUES (?, ?, ?, ?, ?)",
                (rel, start, end, content, json.dumps(terms)))
        conn.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?)",
                     (rel, sig[0], sig[1]))
        done += 1
        if progress and done % 20 == 0:
            progress(done, len(todo))
    conn.commit()

    return {"files_indexed": len(files), "updated": done,
            "skipped_unchanged": len(files) - len(todo),
            "seconds": round(time.time() - t0, 2)}


# ---------------- 检索（TF-IDF 余弦） ----------------

_search_cache: dict[str, tuple[float, list]] = {}   # ws -> (build_time, 全量数据)


def _load_vectors(workspace: str):
    """载入全部块的 tf（词频）并算 idf；缓存 10 秒。"""
    conn = _conn(workspace)
    now = time.time()
    cached = _search_cache.get(workspace)
    if cached and now - cached[0] < 10:
        return cached[1]

    rows = conn.execute(
        "SELECT file, start_line, end_line, content, terms FROM chunks").fetchall()
    n_docs = max(len(rows), 1)
    df: dict[str, int] = {}
    docs = []
    for file, start, end, content, terms_json in rows:
        terms = json.loads(terms_json)
        tf: dict[str, int] = {}
        for t in terms:
            tf[t] = tf.get(t, 0) + 1
        for t in tf:
            df[t] = df.get(t, 0) + 1
        docs.append((file, start, end, content, tf))
    idf = {t: math.log((n_docs + 1) / (d + 1)) + 1.0 for t, d in df.items()}
    # 预计算每块向量的 L2 范数
    norms = []
    for _, _, _, _, tf in docs:
        s = sum((1 + math.log(c)) ** 2 * idf.get(t, 0) ** 2 for t, c in tf.items())
        norms.append(math.sqrt(s) if s else 1.0)
    data = [docs, idf, norms]
    _search_cache[workspace] = (now, data)
    return data


def search(workspace: str, query: str, top_k: int = 5) -> list[dict]:
    """相关度检索，返回 top_k 个代码块。

    返回项：{file, start_line, end_line, content, score}
    """
    docs, idf, norms = _load_vectors(workspace)
    if not docs:
        return []
    q_terms = tokenize(query)
    if not q_terms:
        return []
    q_tf: dict[str, int] = {}
    for t in q_terms:
        q_tf[t] = q_tf.get(t, 0) + 1
    q_weights = {t: (1 + math.log(c)) * idf.get(t, 0.0)
                 for t, c in q_tf.items()}
    q_norm = math.sqrt(sum(w * w for w in q_weights.values())) or 1.0

    scored = []
    for i, (file, start, end, content, tf) in enumerate(docs):
        dot = 0.0
        for t, w in q_weights.items():
            c = tf.get(t)
            if c:
                dot += w * (1 + math.log(c)) * idf.get(t, 0.0)
        if dot <= 0:
            continue
        score = dot / (q_norm * norms[i])
        scored.append({"file": file, "start_line": start, "end_line": end,
                       "content": content, "score": round(score, 4)})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]


def stats(workspace: str) -> dict:
    """索引统计。"""
    conn = _conn(workspace)
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {"files": files, "chunks": chunks, "db": _db_path(workspace)}


def ensure(workspace: str, progress=None) -> dict:
    """确保索引存在（为空则构建），返回统计。"""
    s = stats(workspace)
    if s["chunks"] == 0:
        build(workspace, progress=progress)
        s = stats(workspace)
    return s
