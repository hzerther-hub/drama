# -*- coding: utf-8 -*-
"""公司多根知识库（企业代码 RAG）：N 个目录（代码 + 文档）→ SQLite → TF-IDF + 可选 embedding。

与工作区 `codeindex` 不同：这里把**多个**固定根目录（公司代码仓库 + 文档目录）建成一个
持久化、可配置的知识库，跨会话复用；检索分两级（混合评分）：
  - TF-IDF 余弦（默认，纯 numpy 免外部依赖，逻辑镜像 codeindex）
  - embedding 增强（配置了 `kb_embedding` 模型才启用；构建时逐块落库向量，查询时
    余弦，混合分 = TF-IDF 余弦 + `EMBED_WEIGHT` × embedding 余弦）。
    embedding 不可用/失败/维度不一致 → 自动退回纯 TF-IDF。

本模块只**复用** codeindex 的分词/分块/常量 helper，私建自己的库表，不污染工作区索引。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time

import codeindex
import config

EMBED_WEIGHT = 0.6          # 混合评分里向量余弦的权重

# 纯文档扩展名（在 codeindex 的代码扩展名之外额外纳入）；.md 已在 codeindex.EXTS 内
DOC_EXTS = {".txt", ".rst", ".adoc", ".tex"}
# 建库纳入的扩展名 = 代码扩展 ∪ 文档扩展
INDEX_EXTS = codeindex.EXTS | DOC_EXTS

CHUNK_LINES = codeindex.CHUNK_LINES
CHUNK_OVERLAP = codeindex.CHUNK_OVERLAP
SKIP_DIRS = codeindex.SKIP_DIRS
MAX_FILE_BYTES = codeindex.MAX_FILE_BYTES

_lock = threading.Lock()
_conns: dict[str, sqlite3.Connection] = {}
_search_cache: dict[str, tuple[float, list]] = {}     # roots_key -> (time, vectors)
_CACHE_TTL = 10.0
AUTO_REFRESH_TTL = 60.0            # 检索前自动增量刷新节流秒数
_last_auto_refresh: dict[str, float] = {}   # roots_key -> last auto time


# ---------------- 路径 / 库 ----------------

def roots_hash(roots: list[str]) -> str:
    """按排序后的绝对路径生成库标识（同一组根目录共享一个库）。"""
    key = json.dumps(sorted(os.path.abspath(r) for r in roots),
                      ensure_ascii=False)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _db_path(roots: list[str]) -> str:
    d = os.path.join(config.CONFIG_DIR, "kb")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{roots_hash(roots)}.db")


def _conn(roots: list[str]) -> sqlite3.Connection:
    key = _db_path(roots)
    with _lock:
        if key not in _conns:
            c = sqlite3.connect(key, check_same_thread=False)
            c.execute("PRAGMA journal_mode=WAL")
            c.execute(
                "CREATE TABLE IF NOT EXISTS files ("
                "  root TEXT, path TEXT, mtime REAL, size INTEGER,"
                "  PRIMARY KEY (root, path))")
            c.execute(
                "CREATE TABLE IF NOT EXISTS chunks ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  root TEXT, file TEXT, start_line INTEGER, end_line INTEGER,"
                "  content TEXT, terms TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS emb ("
                      "  id INTEGER PRIMARY KEY, dim INTEGER, vec BLOB)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_chunks_file ON chunks(file)")
            c.commit()
            _conns[key] = c
        return _conns[key]


# ---------------- 文件收集 ----------------

def _iter_files(roots: list[str]):
    """逐根目录遍历，yield (root_abspath, relpath, abspath)。跳过隐藏/噪音目录。"""
    for root in roots:
        root = os.path.abspath(root)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in INDEX_EXTS:
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    if os.path.getsize(p) <= MAX_FILE_BYTES:
                        yield root, os.path.relpath(p, root), p
                except OSError:
                    continue


# ---------------- 索引构建（增量） ----------------

def build(roots: list[str], force: bool = False, progress=None) -> dict:
    """扫描 roots 建索引，返回统计。progress(done, total) 可选回调。"""
    t0 = time.time()
    if not roots:
        return {"files_indexed": 0, "updated": 0, "skipped_unchanged": 0,
                "seconds": 0.0}
    conn = _conn(roots)
    files = list(_iter_files(roots))

    # 已索引且未变的文件
    known: dict[tuple[str, str], tuple[float, int]] = {}
    for root, path, mtime, size in conn.execute("SELECT root, path, mtime, size FROM files"):
        known[(root, path)] = (mtime, size)

    todo = []
    for root, rel, p in files:
        try:
            st = os.stat(p)
            sig = (st.st_mtime, st.st_size)
        except OSError:
            continue
        if not force and known.get((root, rel)) == sig:
            continue
        todo.append((root, rel, p, sig))

    # 已不在候选里的文件（删除/改名/超限）：清掉对应块与向量
    valid = {(root, rel) for root, rel, _p in files}
    for (root, path) in list(conn.execute("SELECT root, path FROM files")):
        if (root, path) not in valid:
            for (cid,) in conn.execute(
                    "SELECT id FROM chunks WHERE root=? AND file=?",
                    (root, path)):
                conn.execute("DELETE FROM emb WHERE id=?", (cid,))
            conn.execute("DELETE FROM chunks WHERE root=? AND file=?",
                         (root, path))
            conn.execute("DELETE FROM files WHERE root=? AND path=?",
                         (root, path))

    # embedding 增强：配置了模型才尝试；任一块失败则整批跳过（退回纯 TF-IDF）
    emb_model = _embed_model()
    use_embed = bool(emb_model)
    emb_failed = False
    if use_embed:
        try:
            import embed as embed_mod
        except Exception:                 # noqa: BLE001
            use_embed = False
            embed_mod = None
    else:
        embed_mod = None

    done = 0
    for root, rel, p, sig in todo:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        # 先清该文件旧块（重写）
        old_ids = [cid for (cid,) in conn.execute(
            "SELECT id FROM chunks WHERE root=? AND file=?", (root, rel))]
        for cid in old_ids:
            conn.execute("DELETE FROM emb WHERE id=?", (cid,))
        conn.execute("DELETE FROM chunks WHERE root=? AND file=?", (root, rel))
        for start, end in codeindex._chunk_lines(lines):
            content = "\n".join(lines[start - 1:end])
            terms = codeindex.tokenize(content)
            if not terms:
                continue
            cur = conn.execute(
                "INSERT INTO chunks (root, file, start_line, end_line,"
                " content, terms) VALUES (?, ?, ?, ?, ?, ?)",
                (root, rel, start, end, content, json.dumps(terms)))
            if use_embed and not emb_failed and embed_mod is not None:
                vec = embed_mod.embed(emb_model, [content])
                if vec:
                    conn.execute("INSERT OR REPLACE INTO emb (id, dim, vec)"
                                 " VALUES (?, ?, ?)",
                                 (cur.lastrowid, len(vec[0]),
                                  _pack(vec[0])))
                else:
                    use_embed = False            # 后续块不再尝试
                    emb_failed = True
        conn.execute("INSERT OR REPLACE INTO files (root, path, mtime, size)"
                     " VALUES (?, ?, ?, ?)", (root, rel, sig[0], sig[1]))
        done += 1
        if progress and done % 20 == 0:
            progress(done, len(todo))
    conn.commit()
    _search_cache.pop(roots_hash(roots), None)   # 数据变了，作废向量缓存

    return {"files_indexed": len(files), "updated": done,
            "skipped_unchanged": len(files) - len(todo),
            "embedding": "tfidf" if (not use_embed) else "hybrid",
            "seconds": round(time.time() - t0, 2)}


def ensure(roots: list[str], progress=None) -> dict:
    """确保索引存在（为空则构建），返回统计。"""
    if not roots:
        return {"files": 0, "chunks": 0, "db": ""}
    s = stats(roots)
    if s["chunks"] == 0:
        build(roots, progress=progress)
        s = stats(roots)
    return s


def maybe_auto_refresh(roots: list[str]) -> dict:
    """检索路径懒调用的自动增量刷新（供 kb_search / 自动注入检前调用）。

    - `kb_auto` 关闭 → 只在索引为空时构建（退化为 ensure 的行为）。
    - 开启且距上次自动增量 < AUTO_REFRESH_TTL → 跳过（避免每次查询都扫盘）。
    - 到期 → 增量 build(force=False)，只更新变化/删除文件并记录时间。

    返回 build 统计（节流内返回等价统计，updated=0）。
    """
    key = roots_hash(roots)
    if config.get_kb_auto():
        last = _last_auto_refresh.get(key)
        if last is not None and time.time() - last < AUTO_REFRESH_TTL:
            s = stats(roots)
            return {"files_indexed": s["files"], "updated": 0,
                    "skipped_unchanged": s["files"], "embedding": "skip",
                    "seconds": 0.0}
    r = build(roots, force=False)
    if config.get_kb_auto():
        _last_auto_refresh[key] = time.time()
    return r


# ---------------- 向量存取 ----------------

def _pack(vec: list[float]) -> bytes:
    """float 列表 → 二进制（struct double）。"""
    import struct
    return struct.pack(f"{len(vec)}d", *vec)


def _unpack(blob: bytes) -> list[float]:
    import struct
    return list(struct.unpack(f"{len(blob) // 8}d", blob))


def _embed_model():
    """返回 embedding 模型配置（kb_embedding key），未配置/不可用返回 None。"""
    key = config.get_kb_embedding()
    if not key:
        return None
    return config.find_model(key)


# ---------------- 检索（TF-IDF 余弦 + 可选 embedding 混合） ----------------

def _load_vectors(roots: list[str]):
    """载入全部块的 tf 并算 idf；缓存 _CACHE_TTL 秒。返回 (docs, idf, norms)。"""
    conn = _conn(roots)
    key = roots_hash(roots)
    now = time.time()
    cached = _search_cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    rows = conn.execute("SELECT id, root, file, start_line, end_line,"
                        " content, terms FROM chunks").fetchall()
    n_docs = max(len(rows), 1)
    df: dict[str, int] = {}
    docs = []
    for cid, root, file, start, end, content, terms_json in rows:
        terms = json.loads(terms_json)
        tf: dict[str, int] = {}
        for t in terms:
            tf[t] = tf.get(t, 0) + 1
        for t in tf:
            df[t] = df.get(t, 0) + 1
        docs.append((cid, root, file, start, end, content, tf))
    idf = {t: math.log((n_docs + 1) / (d + 1)) + 1.0 for t, d in df.items()}
    norms = []
    for _c, _r, _f, _s, _e, _content, tf in docs:
        s = sum((1 + math.log(c)) ** 2 * idf.get(t, 0) ** 2
                for t, c in tf.items())
        norms.append(math.sqrt(s) if s else 1.0)
    data = [docs, idf, norms]
    _search_cache[key] = (now, data)
    return data


def _load_emb(conn: sqlite3.Connection) -> dict[int, list[float]]:
    """载入全部块的 embedding 向量（id -> vec）。"""
    out: dict[int, list[float]] = {}
    for eid, dim, vec in conn.execute("SELECT id, dim, vec FROM emb"):
        out[eid] = _unpack(bytes(vec))
    return out


def search(query: str, top_k: int | None = None,
           roots: list[str] | None = None) -> list[dict]:
    """相关度检索，返回 top_k 个代码/文档块。

    roots 缺省取 config.get_kb_roots()。返回项：{root, file, start_line,
    end_line, content, score, source}。source = "tfidf" / "hybrid"。
    """
    roots = roots if roots is not None else config.get_kb_roots()
    if not roots:
        return []
    top_k = top_k or config.get_kb_top_k()
    docs, idf, norms = _load_vectors(roots)
    if not docs:
        return []
    q_terms = codeindex.tokenize(query)
    if not q_terms:
        return []
    q_tf: dict[str, int] = {}
    for t in q_terms:
        q_tf[t] = q_tf.get(t, 0) + 1
    q_weights = {t: (1 + math.log(c)) * idf.get(t, 0.0)
                 for t, c in q_tf.items()}
    q_norm = math.sqrt(sum(w * w for w in q_weights.values())) or 1.0

    scored: list[tuple[float, int, dict]] = []
    for i, (cid, root, file, start, end, content, tf) in enumerate(docs):
        dot = 0.0
        for t, w in q_weights.items():
            c = tf.get(t)
            if c:
                dot += w * (1 + math.log(c)) * idf.get(t, 0.0)
        if dot <= 0:
            continue
        score = dot / (q_norm * norms[i])
        scored.append((score, cid,
                       {"root": root, "file": file, "start_line": start,
                        "end_line": end, "content": content}))

    # embedding 混合：配置了模型 + 有落库向量 + 维度一致 → 加分
    source = "tfidf"
    extra, tf_max = _hybrid_extra(query, scored, roots)
    if extra:
        source = "hybrid"
        m = max((s for s, _c, _d in scored), default=1.0) or 1.0
        tf_max = m

    final = []
    for s, cid, meta in scored:
        total = s / (tf_max or 1.0) + extra.get(cid, 0.0)
        final.append({**meta, "score": round(total, 4), "source": source})
    final.sort(key=lambda x: -x["score"])
    return final[:top_k]


def _hybrid_extra(query: str, scored: list, roots: list[str]) -> tuple[dict, float]:
    """尝试给 scored 加分 embedding 余弦；返回 (cid->加成, tfidf_max)。失败返回 ({}, 0)。"""
    key = roots_hash(roots)
    if not scored:
        return {}, 0.0
    model = _embed_model()
    if model is None:
        return {}, 0.0
    try:
        import embed as embed_mod
    except Exception:                  # noqa: BLE001
        return {}, 0.0
    conn = _conn(roots)
    emb = _load_emb(conn)
    if not emb:
        return {}, 0.0
    try:
        qvec = embed_mod.embed(model, [query])
    except Exception:                  # noqa: BLE001
        qvec = None
    if not qvec:
        return {}, 0.0
    qvec = qvec[0]
    # 维度一致才混（否则退回纯 TF-IDF）
    ref_dim = None
    for v in emb.values():
        ref_dim = len(v)
        break
    if ref_dim is None or len(qvec) != ref_dim:
        return {}, 0.0
    qn = math.sqrt(sum(x * x for x in qvec)) or 1.0
    extra = {}
    for _s, cid, _m in scored:
        v = emb.get(cid)
        if not v:
            continue
        dot = sum(a * b for a, b in zip(qvec, v))
        vn = math.sqrt(sum(x * x for x in v)) or 1.0
        cos = dot / (qn * vn)
        extra[cid] = EMBED_WEIGHT * (cos + 1.0) / 2.0   # 归一到 [0,1]
    return extra, 0.0


# ---------------- RAG 上下文 ----------------

def retrieve_context(query: str, top_k: int | None = None,
                     max_chars: int = 4000,
                     roots: list[str] | None = None) -> str:
    """把检索结果格式化成一段可直接注入模型上下文的文本块（无结果返回空串）。"""
    hits = search(query, top_k=top_k, roots=roots)
    if not hits:
        return ""
    lines = ["📚 公司知识库相关片段（检索自企业代码/文档，仅作参考）："]
    for h in hits:
        loc = f"{h['root']}/{h['file']}:{h['start_line']}-{h['end_line']}"
        lines.append(f"### [{h['source']} 相关度 {h['score']}] {loc}")
        lines.append(h["content"])
    out = "\n\n".join(lines)
    if len(out) <= max_chars:
        return out
    return out[:max_chars] + "\n…[片段已截断]"


# ---------------- 统计 ----------------

def stats(roots: list[str]) -> dict:
    """索引统计。"""
    if not roots:
        return {"files": 0, "chunks": 0, "db": ""}
    conn = _conn(roots)
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {"files": files, "chunks": chunks, "db": _db_path(roots)}
