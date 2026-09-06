# -*- coding: utf-8 -*-
"""长篇小说生产链（novelwriter）：自动导演式整本生产。

融合两套参考系统的优点：
- AI-Novel-Writing-Assistant：自动导演主链、质量债策略、检查点恢复、RAG
- webnovel-writer-opencode：故事合约(MASTER_SETTING)、DebtTracker 伏笔追踪、
  分维度审查、卷段记忆压缩、题材约束（针对「遗忘/幻觉/风格漂移」）

主链：setup(项目设定) → outline(宏观规划) → world(本书世界) → contract(故事合约)
  → characters(角色) → volume(卷战略) → chapter_plan(节奏拆章)
  → chapters(逐章：草稿 → 分维度审校 → 修复 → 事实/伏笔回灌 → RAG 索引)

策略：
- 规划/生成阶段失败 = 结构级失败 → 停链；章节审校问题 → 修复一次，残余记债不阻断；
- 逐章循环 ctx.save_state 中间落盘，恢复时跳过已完成章节；
- 硬约束(合约)每章强制注入；未回收伏笔每章提示，审校确认回收后关闭。
"""

from __future__ import annotations

import hashlib
import os
import re
import time

import config
import llm
import tools
import vecstore
from pipeline import Pipeline, Stage, StageStopError

STAGE_LABELS = {
    "setup": "项目设定",
    "outline": "宏观规划",
    "world": "本书世界",
    "contract": "故事合约",
    "characters": "角色",
    "volume": "卷战略",
    "chapters": "章节执行",
}

# 阶段名 → 产出在 state 中的键（adjust 调定用）
STAGE_STATE_KEYS = {
    "setup": "framing", "outline": "outline", "world": "world",
    "contract": "contract", "characters": "characters",
    "volume": "volume", "chapter_plan": "chapter_plan",
}

_DEAD = {
    "chapters": "章节执行",
}

_MAX_CHAPTERS = 999              # 硬上限（长篇连载量级）
_MAX_WORDS = 160
_MAX_LEDGER = 60
_MAX_OPEN_FORESHADOW = 8
_ARC_EVERY = 4                   # 每 4 章压缩一段卷段记忆
_MAX_DECONSTRUCT = 60000

_SYS_PLANNER = "你是资深网文主编，只输出规划本身，不写正文，不解释。"
_SYS_WRITER = "你是网文作者，直接输出章节正文，正文前第一行是章节标题。硬约束条款不得违反。"
_SYS_REVIEWER = (
    "你是网文审校，按五个维度逐项检查：连贯性、角色OOC、设定冲突、"
    "风格漂移、节奏。输出规则：问题行以「问题：」开头（可多条）；"
    "回收了旧伏笔以「偿还：」开头（写伏笔关键词）；全部通过则第一行输出 PASS。")
_SYS_DRAMA = ("你是短剧编剧。把小说章节改编为竖屏短剧：输出「场景」行、"
              "人物对白（角色名：台词）、每场结尾「镜头：」行给出景别与时长。")
_SYS_DECONSTRUCT = ("你是网文拆书分析师。对给定文本输出：1) 题材定位 2) 剧情结构 "
                    "3) 人物系统 4) 世界设定 5) 写法特征（可复制复用的具体技法条目）。")


class StageFail(StageStopError):
    """结构级失败（规划/生成阶段）。"""


# ---------------- 阶段定义 ----------------

def st_setup(state: dict, ctx) -> dict:
    """项目设定：题材/卖点/目标读者/前 30 章承诺（书级 framing）。"""
    if state.get("framing"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"题材灵感：{state['idea']}\n"
                "第一行先声明「题材：xxx」。随后输出书级设定：核心卖点（2-3 条）、"
                "目标读者感受、前 30 章承诺（读者前 30 章能期待什么）。")
    if not text:
        raise StageFail("项目设定生成为空")
    m = re.search(r"题材[:：]\s*(.+)", text)
    updates = {"framing": text}
    if m:
        updates["genre"] = m.group(1).strip()[:24]
    _ensure_book(state, text.splitlines()[0].strip()[:24])
    _append_md(state, "\n\n## 项目设定\n\n" + text)
    return updates


def st_outline(state: dict, ctx) -> dict:
    """宏观规划：故事引擎 + 三幕大纲 + 长期对立。"""
    if state.get("outline"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"灵感：{state['idea']}\n书级设定：\n{state['framing']}\n"
                f"全书共 {state['total_chapters']} 章。请输出：故事引擎、"
                "推进与兑现主线、长期对立力量、开局/中段/终局三幕大纲（每幕 3-5 条）。")
    if not text:
        raise StageFail("宏观规划生成为空")
    _ensure_book(state, text.splitlines()[0].strip()[:24])
    _append_md(state, "\n\n## 宏观规划\n\n" + text)
    return {"outline": text}


def st_world(state: dict, ctx) -> dict:
    """本书世界：背景/规则/势力。"""
    if state.get("world"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n"
                "请输出本书世界：时代与地理背景、力量或社会规则、主要势力 3-5 个。")
    if not text:
        raise StageFail("世界设定生成为空")
    _append_md(state, "\n\n## 本书世界\n\n" + text)
    return {"world": text}


def st_contract(state: dict, ctx) -> dict:
    """故事合约（MASTER_SETTING）：从设定中提炼硬约束，每章强制注入。"""
    if state.get("contract"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n世界：\n{state['world']}\n"
                "请提炼本书的故事合约（MASTER_SETTING）：必须始终一致的硬约束，"
                "编号列出 ≤15 条（力量/规则边界、称谓、地名、禁写内容等），"
                "不要解释，只列条款。")
    if not text:
        raise StageFail("故事合约生成为空")
    _append_md(state, "\n\n## 故事合约（硬约束）\n\n" + text)
    return {"contract": text}


def st_characters(state: dict, ctx) -> dict:
    """角色：主角+主要配角的身份/动机/弧线。"""
    if state.get("characters"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n世界：\n{state['world']}\n"
                "请给出 3-6 名主要角色：姓名、身份、核心动机、成长弧线，每人 2-3 行。")
    if not text:
        raise StageFail("角色生成为空")
    _append_md(state, "\n\n## 角色\n\n" + text)
    return {"characters": text}


def st_volume(state: dict, ctx) -> dict:
    """卷战略：分卷 + 每卷章节范围与阶段目标。"""
    if state.get("volume"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n全书共 {state['total_chapters']} 章。"
                "请划分卷：每卷给出章节范围（如 第1-3章）、卷名、阶段目标与结尾钩子。")
    if not text:
        raise StageFail("卷战略生成为空")
    _append_md(state, "\n\n## 卷战略\n\n" + text)
    return {"volume": text}


def st_chapter_plan(state: dict, ctx) -> dict:
    """节奏拆章：每章标题、章节目标、任务单、结尾钩子。"""
    if state.get("chapter_plan"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n卷战略：\n{state['volume']}\n"
                f"全书共 {state['total_chapters']} 章。请逐章输出任务单："
                "每章一行「第N章《标题》目标：…钩子：…」。")
    if not text:
        raise StageFail("节奏拆章生成为空")
    _append_md(state, "\n\n## 节奏拆章\n\n" + text)
    return {"chapter_plan": text}


def st_chapters(state: dict, ctx) -> dict:
    """逐章执行：草稿 → 分维度审校 → 修复 → 回灌 → RAG 索引。"""
    total = int(state.get("total_chapters") or 3)
    chapters: list = state.setdefault("chapters", [])
    debts: list = state.setdefault("debts", [])
    while len(chapters) < total:
        if ctx.is_stopped():
            ctx.pause()
        idx = len(chapters) + 1
        ctx.emit("chapter_start", idx=idx)
        text = _ask(state, _SYS_WRITER, _chapter_prompt(state, idx))
        if len(text) < 50:
            raise StageFail(f"第 {idx} 章正文过短（{len(text)} 字符），疑似生成失败")
        issues, facts, fsh, closes = _review(state, text, idx)
        if issues:                     # 审校有问题 → 自动修复一次
            fixed = _ask(state, _SYS_WRITER,
                         f"以下章节正文存在审校问题：\n{chr(10).join(issues)}\n"
                         f"正文：\n{text}\n请输出修订后的完整正文（保持章节标题行）。")
            if len(fixed) >= 50:
                text = fixed
                issues2, facts2, fsh2, closes2 = _review(state, text, idx)
                issues = issues2                      # 残余问题（可能为空）
                facts = facts2 + [f for f in facts if f not in facts2]
                fsh = fsh2 + [f for f in fsh if f not in fsh2]
                closes = closes + closes2
        title = _planned_title(state, idx) or _chapter_title(text, idx)
        chap = {"idx": idx, "title": title,
                "text": text, "summary": text[:_MAX_WORDS].replace("\n", " "),
                "issues": issues}
        chapters.append(chap)
        _apply_ledger(state, idx, facts, fsh, closes)
        if issues:
            debts.append({"chapter": idx, "detail": "；".join(issues)})
        if idx % _ARC_EVERY == 0 and idx < total:
            _arc_compress(state, ctx, idx)
        ctx.save_state({"chapters": chapters, "debts": debts,
                        "ledger": state.get("ledger", []),
                        "foreshadows": state.get("foreshadows", []),
                        "arc_summaries": state.get("arc_summaries", [])})
        _append_chapter(state, chap)
        _rag_index_chapter(state, chap)
        ctx.emit("chapter_done", idx=idx, title=chap["title"], words=len(text))
    return {}


STAGES = [
    Stage("setup", st_setup, fail="stop"),
    Stage("outline", st_outline, fail="stop"),
    Stage("world", st_world, fail="stop"),
    Stage("contract", st_contract, fail="stop"),
    Stage("characters", st_characters, fail="stop"),
    Stage("volume", st_volume, fail="stop"),
    Stage("chapter_plan", st_chapter_plan, fail="stop"),
    Stage("chapters", st_chapters, fail="stop"),
]


def new_pipeline(idea: str, total: int, model_key: str,
                 style: str = "") -> Pipeline:
    """开一条新书流水线；书稿落在工作区 novels/<pid>.md。"""
    total = max(1, min(int(total or 3), _MAX_CHAPTERS))
    pid = "novel-" + time.strftime("%Y%m%d-%H%M%S")
    ws = tools.get_workspace() or os.getcwd()
    state = {"idea": idea, "total_chapters": total, "model_key": model_key,
             "style": (style or "").strip(), "chapters": [], "debts": [],
             "ledger": [], "foreshadows": [], "arc_summaries": [],
             "pid": pid, "file": os.path.join(ws, "novels", pid + ".md")}
    return Pipeline(pid, idea[:20], STAGES, state)


def extend_total(p: Pipeline, n: int):
    """加写 n 章：调大总数；已完成流水线回到可续跑状态。"""
    n = max(1, int(n))
    p.state["total_chapters"] = min(
        int(p.state.get("total_chapters", 0)) + n, _MAX_CHAPTERS)
    if p.pipeline_status == "done" and p.cursor is None \
            and len(p.state.get("chapters", [])) < p.state["total_chapters"]:
        p.pipeline_status = "paused"
        p.cursor = "chapters"
    p.updated = time.time()
    p.save()


# ---------------- 衍生：重写 / 短剧 / 拆书 ----------------

def rewrite_chapter(state: dict, idx: int, feedback: str = "") -> dict:
    """重写指定章节（保留编号），全书 md 同步重建；返回更新后的章。"""
    chapters = state.get("chapters", [])
    if not 1 <= idx <= len(chapters):
        raise StageStopError(f"第 {idx} 章不存在或尚未生成")
    fb = f"\n作者反馈（必须落实）：{feedback}\n" if feedback else ""
    old = chapters[idx - 1]
    text = _ask(state, _SYS_WRITER,
                f"以下是需要重写的第 {idx} 章。{fb}\n"
                f"原正文：\n{old['text']}\n\n"
                + _chapter_prompt(state, idx)
                + "\n请重写本章：修复原正文问题、落实反馈，输出完整新正文。")
    if len(text) < 50:
        raise StageFail("重写正文过短，已保留原章")
    issues, facts, fsh, closes = _review(state, text, idx)
    old.update({"text": text, "summary": text[:_MAX_WORDS].replace("\n", " "),
                "issues": issues})
    _apply_ledger(state, idx, facts, fsh, closes)
    state["chapters"][idx - 1] = old
    _rebuild_md(state)
    _rag_index_chapter(state, old)
    return old


def drama_adapt(state: dict, ch_start: int, ch_end: int,
                on_event=None) -> str:
    """把已完成章节改编为竖屏短剧剧本+分镜；返回输出文件路径。"""
    on_event = on_event or (lambda e: None)
    chapters = [c for c in state.get("chapters", [])
                if ch_start <= c["idx"] <= ch_end]
    if not chapters:
        raise StageStopError("所选范围没有已完成章节")
    out_path = _book_path(state).replace(".md", "-短剧.md")
    with open(out_path, "a", encoding="utf-8") as f:
        for c in chapters:
            script = _ask(state, _SYS_DRAMA,
                          f"小说正文（第 {c['idx']} 章《{c['title']}》）：\n"
                          f"{c['text']}\n请改编为竖屏短剧剧本：分场、对白、"
                          "每场结尾镜头行（景别/时长）。")
            f.write(f"\n\n## 第 {c['idx']} 章《{c['title']}》短剧改编\n\n{script}\n")
            on_event({"type": "drama_chapter", "idx": c["idx"]})
    return out_path


def deconstruct(txt_path: str, model_key: str) -> str:
    """拆书：外部文本 → 题材/结构/人物/世界/写法特征报告；返回报告路径。"""
    with open(txt_path, encoding="utf-8", errors="ignore") as f:
        text = f.read(_MAX_DECONSTRUCT)
    if len(text.strip()) < 50:
        raise StageStopError("拆书文本过短")
    report = _ask({"model_key": model_key}, _SYS_DECONSTRUCT,
                  f"待拆文本（可能截断）：\n{text}\n请按五个部分输出拆书报告。")
    base = os.path.splitext(os.path.basename(txt_path))[0]
    out = os.path.join(os.path.dirname(txt_path) or ".", f"{base}-拆书.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 拆书报告：{base}\n\n{report}\n")
    return out


def _ask(state: dict, system: str, user: str) -> str:
    """一次流式调用，收集完整文本；空回复自动重试一次；LLMError 冒泡分级。"""
    model = _resolve_model(state.get("model_key"))
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": user}]
    out = ""
    for attempt in (1, 2):
        out = ""
        try:
            for ev in llm.stream_chat(model, msgs):
                if ev.get("type") == "text":
                    out += ev.get("delta") or ""
        except llm.LLMError:
            if attempt == 2:
                raise
            continue
        if out.strip():
            break
    return out.strip()


def rag_recall(state: dict, query: str, k: int = 3) -> str:
    """按语义召回本书已有片段；任何失败返回空（回退到摘要回灌）。"""
    try:
        name = state.get("pid")
        if not name:
            return ""
        vecstore.ensure_collection(name)
        qv = vecstore.embed_texts([query])[0]
        hits = vecstore.search(name, qv, k)
        return "\n".join(f"- {(h['payload'] or {}).get('text', '')[:200]}"
                         for h in hits if h.get("payload"))
    except Exception:                  # noqa: BLE001
        return ""


def _rag_index_chapter(state: dict, chap: dict):
    """章节入向量索引；失败静默（RAG 不阻断生产）。"""
    try:
        name = state.get("pid")
        if not name:
            return
        chunks = vecstore.chunk_text(chap["text"])
        vecs = vecstore.embed_texts(chunks)
        vecstore.ensure_collection(name)
        base = int(hashlib.md5(
            f"{name}-{chap['idx']}".encode("utf-8")).hexdigest()[:12], 16)
        vecstore.upsert(name, [base + i for i in range(len(chunks))], vecs,
                        [{"book": name, "chapter": chap["idx"], "text": c}
                         for i, c in enumerate(chunks)])
    except Exception:                  # noqa: BLE001
        pass


# ---------------- 内部工具 ----------------

def _resolve_model(key: str):
    return config.find_model(key) if key else None


def _ask(state: dict, system: str, user: str) -> str:
    """一次流式调用，收集完整文本；LLMError 冒泡由引擎按策略分级。"""
    model = _resolve_model(state.get("model_key"))
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": user}]
    out = []
    for ev in llm.stream_chat(model, msgs):
        if ev.get("type") == "text":
            out.append(ev.get("delta") or "")
    return "".join(out).strip()


def _style_block(state: dict) -> str:
    return f"\n写法要求（必须体现）：\n{state['style']}\n" if state.get("style") else ""


def _contract_block(state: dict) -> str:
    return f"\n【硬约束·违反即失败】\n{state['contract']}\n" if state.get("contract") else ""


def _open_foreshadow_block(state: dict) -> str:
    open_fs = [f for f in state.get("foreshadows", []) if not f.get("closed_ch")]
    if not open_fs:
        return ""
    lines = "\n".join(f"- {f['text']}（第 {f['open_ch']} 章埋下）"
                      for f in open_fs[-_MAX_OPEN_FORESHADOW:])
    return (f"\n【未回收伏笔】如本章自然回收请在正文明确呼应：\n{lines}\n")


def _arc_block(state: dict) -> str:
    arcs = state.get("arc_summaries", [])
    if not arcs:
        return ""
    return "\n更早卷段摘要：\n" + arcs[-1]["text"] + "\n"


def _task_line(state: dict, idx: int) -> str:
    """从节奏拆章任务单里取本章那一行。"""
    plan = state.get("chapter_plan", "")
    m = re.search(rf"第{idx}章.*", plan)
    return m.group(0) if m else ""


def _planned_title(state: dict, idx: int) -> str:
    """拆章阶段预定的本章标题（《》内），未规划返回空。"""
    m = re.search(r"《(.+?)》", _task_line(state, idx))
    return m.group(1) if m else ""


def _chapter_prompt(state: dict, idx: int) -> str:
    task = _task_line(state, idx)
    task_line = f"本章任务单：{task}\n" if task else ""
    planned = _planned_title(state, idx)
    title_line = (f"本章标题（第一行必须一字不差使用）：{planned}\n"
                  if planned else "")
    prev = [f"第{c['idx']}章《{c['title']}》：{c['summary']}"
            for c in state["chapters"][-3:]]
    prev_text = "\n".join(prev) if prev else "（本章为第一章）"
    ledger = state.get("ledger", [])
    led_text = "\n".join(ledger[-12:]) if ledger else "（暂无）"
    recall = rag_recall(state, task_line or prev_text, 3)
    recall_text = f"\n相关前文片段（RAG 召回）：\n{recall}\n" if recall else ""
    genre = f"题材：{state.get('genre', '')}。" if state.get("genre") else ""
    return (f"{genre}\n书名与主线：\n{state['outline']}\n{_contract_block(state)}"
            f"世界：\n{state['world']}\n角色：\n{state['characters']}\n"
            f"卷战略：\n{state['volume']}\n{_style_block(state)}"
            f"{_arc_block(state)}"
            f"前情提要：\n{prev_text}\n事实台账：\n{led_text}\n"
            f"{_open_foreshadow_block(state)}{recall_text}{task_line}"
            f"{title_line}"
            f"请写第 {idx} 章，1500-2500 字：承接前情与台账，"
            "遵守硬约束，不得与事实矛盾，结尾留钩子。")


def _review(state: dict, text: str, idx: int):
    """分维度审校：返回 (残余问题, 新事实, 新伏笔, 回收列表)。审校不可用记债不阻断。"""
    try:
        out = _ask(state, _SYS_REVIEWER, f"章节正文：\n{text}\n请审校。")
    except Exception as e:             # noqa: BLE001
        return [f"审校不可用：{e}"], [], [], []
    issues, facts, fsh, closes = [], [], [], []
    if not out or out.strip().upper().startswith("PASS"):
        return [], [], [], []
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("问题"):
            issues.append(ln[:120])
        elif ln.startswith("事实"):
            facts.append(ln[:120])
        elif ln.startswith("伏笔"):
            fsh.append(ln[:120])
        elif ln.startswith("偿还"):
            closes.append(ln[:120])
    return issues[:5], facts[:5], fsh[:5], closes[:5]


def _apply_ledger(state: dict, idx: int, facts, fsh, closes):
    """事实/伏笔回灌：台账 + DebtTracker 状态更新。"""
    led = state.setdefault("ledger", [])
    for x in facts:
        led.append(f"第{idx}章 {x}")
    for x in fsh:
        led.append(f"第{idx}章 {x}")
        state.setdefault("foreshadows", []).append(
            {"text": x, "open_ch": idx, "closed_ch": None})
    for x in closes:
        for f in reversed(state.get("foreshadows", [])):
            if not f.get("closed_ch") and (
                    x[3:].strip()[:6] in f["text"] or f["text"][3:].strip()[:6] in x):
                f["closed_ch"] = idx
                led.append(f"第{idx}章 偿还伏笔：{f['text']}")
                break
    del led[_MAX_LEDGER:]


def _arc_compress(state: dict, ctx, upto_idx: int):
    """卷段记忆压缩：把最近 _ARC_EVERY 章压成一段摘要（三层记忆的情节层）。"""
    arcs = state.setdefault("arc_summaries", [])
    start = (arcs[-1]["upto"] + 1) if arcs else 1
    seg = [c for c in state["chapters"] if start <= c["idx"] <= upto_idx]
    if not seg:
        return
    text = _ask(state, _SYS_PLANNER,
                "请把以下章节压缩为一段 ≤200 字的卷段摘要（保留关键转折与承诺）：\n"
                + "\n".join(f"第{c['idx']}章：{c['summary']}" for c in seg))
    arcs.append({"upto": upto_idx, "text": text[:600]})
    ctx.save_state({"arc_summaries": arcs})


def _chapter_title(text: str, idx: int) -> str:
    first = text.splitlines()[0].strip() if text else ""
    if re.match(r"^第[0-9一二三四五六七八九十百千]+章", first):
        return first[:40]
    return f"第{idx}章"


def _book_path(state: dict) -> str:
    return state.get("file") or os.path.join(
        tools.get_workspace() or os.getcwd(), "novels", "untitled.md")


def _ensure_book(state: dict, title: str):
    path = _book_path(state)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n> 灵感：{state['idea']}\n")
    state["file"] = path


def _append_md(state: dict, text: str):
    path = _book_path(state)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):       # 恢复场景：书稿丢失则重建头
        head = state.get("outline", "未命名").splitlines()[0][:24]
        _ensure_book(state, head)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def _append_chapter(state: dict, chap: dict):
    _append_md(state, f"\n\n## {chap['title']}\n\n{chap['text']}")


def _rebuild_md(state: dict):
    """重写章节后从 state 全量重建书稿 md。"""
    path = _book_path(state)
    parts = [f"# {state.get('genre', '')}{state['idea'][:24]}",
             f"> 灵感：{state['idea']}"]
    for key, title in (("framing", "项目设定"), ("outline", "宏观规划"),
                       ("world", "本书世界"), ("contract", "故事合约（硬约束）"),
                       ("characters", "角色"), ("volume", "卷战略"),
                       ("chapter_plan", "节奏拆章")):
        if state.get(key):
            parts.append(f"\n\n## {title}\n\n{state[key]}")
    for c in state.get("chapters", []):
        parts.append(f"\n\n## {c['title']}\n\n{c['text']}")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts) + "\n")
