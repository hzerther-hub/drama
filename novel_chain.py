# -*- coding: utf-8 -*-
"""长篇小说生产链（novelwriter）：自动导演式整本生产，参考
AI-Novel-Writing-Assistant 的主链阶段，落成 Tk/stdlib 版。

主链（pipeline.Pipeline 之上的产品级阶段）：
  setup(项目设定) → outline(宏观规划) → world(本书世界) → characters(角色)
  → volume(卷战略) → chapter_plan(节奏拆章) → chapters(逐章执行：
  草稿 → 审校 → 修复 → 事实/伏笔回灌 → RAG 索引)

策略（对齐参考项目的质量门思想）：
- 规划/生成阶段失败 = 结构级失败 → 停链（fail="stop"）；
- 章节审校问题 → 先自动修复一次，残余问题记为该章质量债，不阻断后续章节；
- 每章完成：摘要回灌前情 + 事实/伏笔入台账 + RAG 向量索引（Qdrant 或降级）；
- 衍生：drama_adapt(章节→短剧剧本+分镜)、deconstruct(拆书报告+写法特征)。
"""

from __future__ import annotations

import os
import re
import time
import hashlib

import config
import llm
import tools
import vecstore
from pipeline import Pipeline, Stage, StageStopError

# 阶段中文名（UI 展示用）
STAGE_LABELS = {
    "setup": "项目设定",
    "outline": "宏观规划",
    "world": "本书世界",
    "characters": "角色",
    "volume": "卷战略",
    "chapter_plan": "节奏拆章",
    "chapters": "章节执行",
}

_MAX_CHAPTERS = 12                 # 单条流水线章数上限
_MAX_WORDS = 160                   # 回灌摘要截断
_MAX_LEDGER = 60                   # 事实/伏笔台账上限
_MAX_DECONSTRUCT = 60000           # 拆书输入字符上限

_SYS_PLANNER = "你是资深网文主编，只输出规划本身，不写正文，不解释。"
_SYS_WRITER = "你是网文作者，直接输出章节正文，正文前第一行是章节标题。"
_SYS_REVIEWER = ("你是网文审校。输出格式：问题行以「问题：」开头（可多条）；"
                 "新出现的事实以「事实：」开头；埋下的伏笔以「伏笔：」开头；"
                 "无问题则第一行输出 PASS。不要夸奖，不要解释。")
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
                "请输出书级设定：题材定位、核心卖点（2-3 条）、目标读者感受、"
                "前 30 章承诺（读者前 30 章能期待什么）。")
    if not text:
        raise StageFail("项目设定生成为空")
    _ensure_book(state, text.splitlines()[0].strip()[:24])
    _append_md(state, "\n\n## 项目设定\n\n" + text)
    return {"framing": text}


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
    state["outline"] = text
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
    """逐章执行：草稿 → 审校 → 修复一次 → 事实/伏笔回灌 → RAG 索引。"""
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
        issues, ledger_new = _review(state, text)
        if issues:                     # 审校有问题 → 自动修复一次
            fixed = _ask(state, _SYS_WRITER,
                         f"以下章节正文存在审校问题：\n{chr(10).join(issues)}\n"
                         f"正文：\n{text}\n请输出修订后的完整正文（保持章节标题行）。")
            if len(fixed) >= 50:
                text = fixed
                issues2, ledger_new2 = _review(state, text)
                if issues2:
                    debts.append({"chapter": idx, "detail": "；".join(issues2)})
                ledger_new = ledger_new2 or ledger_new
            else:
                debts.append({"chapter": idx, "detail": "；".join(issues)})
        chap = {"idx": idx, "title": _chapter_title(text, idx),
                "text": text, "summary": text[:_MAX_WORDS].replace("\n", " "),
                "issues": issues}
        chapters.append(chap)
        if ledger_new:
            led = state.setdefault("ledger", [])
            led.extend(x for x in ledger_new if x not in led)
            del led[_MAX_LEDGER:]
        ctx.save_state({"chapters": chapters, "debts": debts,
                        "ledger": state.get("ledger", [])})
        _append_chapter(state, chap)
        _rag_index_chapter(state, chap)
        ctx.emit("chapter_done", idx=idx, title=chap["title"], words=len(text))
    return {}


STAGES = [
    Stage("setup", st_setup, fail="stop"),
    Stage("outline", st_outline, fail="stop"),
    Stage("world", st_world, fail="stop"),
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
             "ledger": [], "pid": pid,
             "file": os.path.join(ws, "novels", pid + ".md")}
    return Pipeline(pid, idea[:20], STAGES, state)


# ---------------- 衍生：短剧改编 ----------------

def drama_adapt(state: dict, ch_start: int, ch_end: int,
                on_event=None) -> str:
    """把已完成章节改编为竖屏短剧剧本+分镜；返回输出文件路径。"""
    on_event = on_event or (lambda e: None)
    chapters = [c for c in state.get("chapters", [])
                if ch_start <= c["idx"] <= ch_end]
    if not chapters:
        raise StageStopError("所选范围没有已完成章节")
    out_path = _book_path(state).replace(".md", "-短剧.md")
    model = _resolve_model(state.get("model_key"))
    with open(out_path, "a", encoding="utf-8") as f:
        for c in chapters:
            script = _ask(state, _SYS_DRAMA,
                          f"小说正文（第 {c['idx']} 章《{c['title']}》）：\n"
                          f"{c['text']}\n请改编为竖屏短剧剧本：分场、对白、"
                          "每场结尾镜头行（景别/时长）。")
            f.write(f"\n\n## 第 {c['idx']} 章《{c['title']}》短剧改编\n\n{script}\n")
            on_event({"type": "drama_chapter", "idx": c["idx"]})
    return out_path


# ---------------- 衍生：拆书 ----------------

def deconstruct(txt_path: str, model_key: str) -> str:
    """拆书：外部文本 → 题材/结构/人物/世界/写法特征报告；返回报告路径。"""
    with open(txt_path, encoding="utf-8", errors="ignore") as f:
        text = f.read(_MAX_DECONSTRUCT)
    if len(text.strip()) < 50:
        raise StageStopError("拆书文本过短")
    report = _ask({"model_key": model_key}, _SYS_DECONSTRUCT,
                  f"待拆文本（可能截断）：\n{text}\n请按五个部分输出拆书报告。")
    base = os.path.splitext(os.path.basename(txt_path))[0]
    out = os.path.join(os.path.dirname(txt_path) or ".",
                       f"{base}-拆书.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 拆书报告：{base}\n\n{report}\n")
    return out


# ---------------- RAG（Qdrant 或降级） ----------------

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


def _chapter_prompt(state: dict, idx: int) -> str:
    plan = state.get("chapter_plan", "")
    task_line = ""
    m = re.search(rf"第{idx}章.*", plan)
    if m:
        task_line = f"本章任务单：{m.group(0)}\n"
    prev = [f"第{c['idx']}章《{c['title']}》：{c['summary']}"
            for c in state["chapters"][-3:]]
    prev_text = "\n".join(prev) if prev else "（本章为第一章）"
    ledger = state.get("ledger", [])
    led_text = "\n".join(ledger[-12:]) if ledger else "（暂无）"
    recall = rag_recall(state, task_line or prev_text, 3)
    recall_text = f"\n相关前文片段（RAG 召回）：\n{recall}\n" if recall else ""
    return (f"书名与主线：\n{state['outline']}\n世界：\n{state['world']}\n"
            f"角色：\n{state['characters']}\n卷战略：\n{state['volume']}\n"
            f"{_style_block(state)}"
            f"前情提要：\n{prev_text}\n事实与伏笔台账：\n{led_text}\n"
            f"{recall_text}{task_line}\n"
            f"请写第 {idx} 章，1500-2500 字：承接前情与台账，"
            "不得与事实矛盾，结尾留钩子。")


def _review(state: dict, text: str) -> tuple[list, list]:
    """审校：返回 (问题列表, 新增事实/伏笔)。审校不可用记债不阻断。"""
    try:
        out = _ask(state, _SYS_REVIEWER, f"章节正文：\n{text}\n请审校。")
    except Exception as e:             # noqa: BLE001
        return [f"审校不可用：{e}"], []
    issues, ledger = [], []
    if not out or out.strip().upper().startswith("PASS"):
        return [], []
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("问题"):
            issues.append(ln[:120])
        elif ln.startswith("事实") or ln.startswith("伏笔"):
            ledger.append(ln[:120])
    return issues[:5], ledger[:5]


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
