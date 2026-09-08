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
    "chapter_plan": "节奏拆章",
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

# 书稿目录布局（对齐 webnovel-writer 生态惯例：书名作目录名，按内容类型分目录）：
#   novels/<书名>/大纲/总纲.md          ← 全书规划（framing→chapter_plan）
#   novels/<书名>/设定集/世界观.md       ← 世界/角色/硬约束
#   novels/<书名>/正文/第0001章-标题.md  ← 每章独立 md，章号补零便于排序
#   novels/<书名>/审查报告/第0001章.md   ← 每章审校问题留档
_DIR_OUTLINE = "大纲"
_DIR_SETTING = "设定集"
_DIR_TEXT = "正文"
_DIR_REVIEW = "审查报告"
_OUTLINE_FILE = "总纲.md"
_README_FILE = "说明.md"
_NOVELS_DIRNAME = "novels"

_SYS_PLANNER = "你是资深网文主编，只输出规划本身，不写正文，不解释。"
_SYS_WRITER = "你是网文作者，直接输出章节正文，正文前第一行是章节标题。硬约束条款不得违反。"

# 结构化产出模板（对齐 webnovel-writer 生态的固定字段约定）。
# 用法：把模板原文作为「骨架」塞进提示词，要求模型逐字段填写；
# 模型输出的文档天然结构化，可直接落盘、可被后续阶段稳定解析。
_TEMPLATE_OUTLINE = """# 总纲

## 故事一句话
（一句话概括主线矛盾与成长方向）

## 创意约束
- 反套路规则：
- 硬约束（世界/能力/行为）：
- 主角缺陷：
- 反派镜像：

## 核心主线
- 主线目标：
- 主要阻力：

## 核心暗线
- 暗线主题：
- 回收节点：

## 反派分层（概要）
- 小反派（前期）：
- 中反派（中期）：
- 大反派（后期）：

## 世界观/力量体系简介
- 世界观要点：
- 力量体系要点：

## 卷划分
| 卷号 | 卷名 | 章节范围 | 核心冲突 | 卷末高潮 |
|------|------|----------|----------|----------|
| 1 | | | | |

## 主角成长线
- 起点状态：
- 关键跃迁节点：
- 终局定位：

## 关键爽点里程碑
- 第X章：

## 伏笔表
| 伏笔内容 | 埋设章 | 回收章 | 层级 |
|----------|--------|--------|------|
| | | | |
"""

_TEMPLATE_WORLD = """# 世界观设定

## 世界一句话
（一句话概括世界的规则与核心矛盾）

## 世界结构
- 大陆/位面数量：
- 核心区域：
- 边缘区域：

## 势力格局
- 核心势力：
- 次级势力：
- 敌对/中立关系：
- 宗门/组织层级：

## 社会结构
- 社会阶层：
- 资源分配规则：
- 信仰/意识形态：

## 核心规则
- 资源稀缺性：
- 政治/宗门规则：
- 社会常识/禁忌：
- 硬约束（不可违背）：

## 世界运转机制
- 能量/资源循环：
- 技术/法术基础：
- 公平性与代价规则：

## 货币与经济
- 货币体系：
- 兑换规则：
- 主要流通形态：
"""

_TEMPLATE_CHARACTER = """# 主角卡

## 基本信息
- 姓名：
- 年龄：
- 身份：
- 起点状态：

## 核心标签
- 3个关键词：
- 读者第一印象：

## 性格与底色
- 核心性格：
- 行为底线：
- 情绪触发点：
- 易激怒点：
- 容易心软点：

## 动机与目标
- 短期目标：
- 中期目标：
- 长期目标：
- 真正渴望（可能不自知）：

## 缺陷与代价
- 性格缺陷：
- 能力限制：
- 心理阴影：
- 代价承受底线：

## 关键关系
- 重要盟友：
- 主要对手：
- 情感关系：
- 关键债务/牵绊：

## 当前能力
- 境界/等级：
- 代表技能：
- 资源/装备：

## 金手指
- 类型：
- 代价/限制：
- 核心卖点：

## 行为模式
- 常用解决方式（战斗/谈判/计谋）：
- 失败时的本能反应：
- 破局特长：

## 成长弧线（阶段）
- 阶段1（起点）：
- 阶段2（变化）：
- 阶段3（蜕变）：

## OOC 警戒
- 绝不该做的事：
- 需要提前铺垫的事：
"""

_TEMPLATE_CONTRACT = """# 故事合约（硬约束）

## 必须始终一致的条款
1. 
2. 
3. 

## 禁写内容
- 

## 称谓与地名约定
- 主角称谓：
- 关键地名：
- 力量体系称谓：
"""

_TEMPLATE_VOLUME = """# 卷战略

## 卷总览
| 卷号 | 卷名 | 章节范围 | 核心冲突 | 卷末高潮 |
|------|------|----------|----------|----------|
| 1 | | | | |

## 各卷节拍
### 第 1 卷：（第X-Y章）
- 开卷承诺：
- 催化事件：
- 升级危机链：1) … 2) … 3) …
- 中段反转：
- 卷末最低谷：
- 卷末兑现与新钩子：
"""

# 阶段 → (提示词模板, 产出落盘文件名)；None 表示沿用默认落盘逻辑
_STAGE_TEMPLATE = {
    "outline": _TEMPLATE_OUTLINE,
    "world": _TEMPLATE_WORLD,
    "characters": _TEMPLATE_CHARACTER,
    "contract": _TEMPLATE_CONTRACT,
    "volume": _TEMPLATE_VOLUME,
}

# 审校输出的行前缀契约：提示词与 _review() 解析器共用同一份定义，
# 改一处即两处同时生效（曾因提示词单方面删掉「事实/伏笔」而静默废掉台账）。
_REVIEW_PREFIX = {
    "issue": "问题",
    "fact": "事实",
    "foreshadow": "伏笔",
    "close": "偿还",
}
_SYS_REVIEWER = (
    "你是网文审校，按五个维度逐项检查：连贯性、角色OOC、设定冲突、"
    "风格漂移、节奏。输出规则："
    f"问题行以「{_REVIEW_PREFIX['issue']}：」开头（可多条）；"
    f"新事实以「{_REVIEW_PREFIX['fact']}：」开头；"
    f"新埋伏笔以「{_REVIEW_PREFIX['foreshadow']}：」开头；"
    f"回收了旧伏笔以「{_REVIEW_PREFIX['close']}：」开头（写伏笔关键词）；"
    "全部通过则第一行输出 PASS。")
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
    if m:
        state["genre"] = m.group(1).strip()[:24]
    _ensure_book(state, text.splitlines()[0].strip()[:24])
    _write_plan_section(state, "项目设定", text)
    return {"framing": text, "genre": state.get("genre", "")}


def st_outline(state: dict, ctx) -> dict:
    """宏观规划：按总纲模板逐字段填写。首行「# 《书名》总纲」提供书名。"""
    if state.get("outline"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"灵感：{state['idea']}\n书级设定：\n{state['framing']}\n"
                f"全书共 {state['total_chapters']} 章。\n"
                "输出第一行必须是「# 《书名》总纲」——《》里写这本书的正式书名。\n"
                "随后严格按下面的骨架逐字段填写（保留全部标题与字段名，"
                "把每一项都写实，不要留空、不要增删章节）：\n\n"
                + _TEMPLATE_OUTLINE)
    if not text:
        raise StageFail("宏观规划生成为空")
    book = _book_title_from(state, text)
    if book:
        state["title"] = book
    _ensure_book(state, state.get("title") or "总纲")
    _write_plan_section(state, "宏观规划", text)   # 重建时顺带 _sync_book_dir
    _write_readme(state)
    return {"outline": text, "title": state.get("title", "")}


def st_world(state: dict, ctx) -> dict:
    """本书世界：按世界观模板逐字段填写。"""
    if state.get("world"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n"
                "请严格按下面的骨架逐字段填写世界观（保留全部标题与字段名，"
                "把每一项都写实，不要留空）：\n\n"
                + _TEMPLATE_WORLD)
    if not text:
        raise StageFail("世界设定生成为空")
    _append_setting(state, "世界观", text)
    return {"world": text}


def st_contract(state: dict, ctx) -> dict:
    """故事合约（MASTER_SETTING）：按合约模板提炼硬约束，每章强制注入。"""
    if state.get("contract"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n世界：\n{state['world']}\n"
                "请严格按下面的骨架提炼故事合约（保留标题与字段名，条款要具体可判定）：\n\n"
                + _TEMPLATE_CONTRACT)
    if not text:
        raise StageFail("故事合约生成为空")
    _append_setting(state, "故事合约", text)
    return {"contract": text}


def st_characters(state: dict, ctx) -> dict:
    """角色：主角按主角卡模板填写，配角各按精简卡片。"""
    if state.get("characters"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n世界：\n{state['world']}\n"
                "请先按下面的「主角卡」骨架逐字段填写主角（保留全部标题与字段名，"
                "把每一项都写实），随后用同样的字段结构补充 2-5 名主要配角"
                "（每人一个二级标题「## 配角：姓名」）。\n\n"
                + _TEMPLATE_CHARACTER)
    if not text:
        raise StageFail("角色生成为空")
    _append_setting(state, "角色", text)
    return {"characters": text}


def st_volume(state: dict, ctx) -> dict:
    """卷战略：按卷战略模板逐卷填写节拍。"""
    if state.get("volume"):
        return {}
    text = _ask(state, _SYS_PLANNER,
                f"大纲：\n{state['outline']}\n全书共 {state['total_chapters']} 章。\n"
                "请严格按下面的骨架逐字段填写（保留全部标题与字段名；"
                "「卷总览」表按实际卷数逐行填全，各卷节拍逐卷展开）：\n\n"
                + _TEMPLATE_VOLUME)
    if not text:
        raise StageFail("卷战略生成为空")
    _write_plan_section(state, "卷战略", text)
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
    _write_plan_section(state, "节奏拆章", text)
    return {"chapter_plan": text}


def st_chapters(state: dict, ctx) -> dict:
    """逐章执行：草稿 → 分维度审校 → 修复 → 回灌 → RAG 索引。"""
    _sync_book_dir(state)                # 大纲在旧版本生成的存量书在此补改名
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
        text = _strip_title(text, title)      # 去掉正文首行重复的标题
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
        _write_review_report(state, chap)
        _write_readme(state)               # 刷新「已完成 N 章」计数
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


def parse_start_args(rest: str) -> dict:
    """解析 /novel start 的参数串（纯函数，UI 层调用）。

    支持「灵感 [章数] [auto|自动]」，尾部标志位与章数顺序不限：
      "重生逆袭 12"        → {idea, total:12, auto:False}
      "重生逆袭 12 auto"   → {idea, total:12, auto:True}
      "重生逆袭"           → {idea, total:3,  auto:False}
    idea 为空返回 {"error": "need_idea"}；章数夹紧到 [1, _MAX_CHAPTERS]。
    """
    rest = (rest or "").strip()
    auto = bool(re.search(r"\s+(?:auto|自动)\s*$", rest, re.I))
    rest = re.sub(r"\s+(?:auto|自动)\s*$", "", rest).strip()
    m = re.search(r"\s+(\d{1,3})$", rest)
    total = int(m.group(1)) if m else 3
    idea = (rest[:m.start()] if m else rest).strip()
    if not idea:
        return {"error": "need_idea"}
    return {"idea": idea, "total": max(1, min(total, _MAX_CHAPTERS)),
            "auto": auto}


def new_pipeline(idea: str, total: int, model_key: str,
                 style: str = "") -> Pipeline:
    """开一条新书流水线；书稿落在 novels/<书名>/ 目录（每章一个 md）。

    灵感支持《书名》前缀：「/novel start 《井通万界》双界倒爷 30」→
    目录直接叫 井通万界。没写书名时先用 pid 占位，大纲阶段拿到书名后
    由 _sync_book_dir 重命名；仍提取不到则用灵感首段兜底——目录名
    永远不会是「未命名」。
    """
    total = max(1, min(int(total or 3), _MAX_CHAPTERS))
    pid = "novel-" + time.strftime("%Y%m%d-%H%M%S")
    idea = (idea or "").strip()
    title = ""
    m = re.match(r"^\s*《(.+?)》", idea)
    if m:                                # 《书名》前缀 → 目录即刻定名
        title = _safe_name(m.group(1))[:30]
        idea = idea[m.end():].strip() or title
    dirname = title or pid
    book_dir = _unique_dir(os.path.join(_novels_root(), dirname))
    state = {"idea": idea, "total_chapters": total, "model_key": model_key,
             "style": (style or "").strip(), "chapters": [], "debts": [],
             "ledger": [], "foreshadows": [], "arc_summaries": [],
             "pid": pid, "dir": book_dir, "title": title,
             "file": os.path.join(book_dir, _DIR_OUTLINE, _OUTLINE_FILE)}
    return Pipeline(pid, idea[:20], STAGES, state)


def _unique_dir(path: str) -> str:
    """目录已存在则加序号（书名、书名-2、书名-3…），避免覆盖别人的书。"""
    if not os.path.exists(path):
        return path
    n = 2
    while os.path.exists(f"{path}-{n}"):
        n += 1
    return f"{path}-{n}"


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


# ---------------- 衍生：调定 / 重写 / 短剧 / 拆书 ----------------

_REVISE_SYS = {
    "setup": "你是资深网文主编。按作者意见修订项目设定，只输出修订后的完整设定，"
             "不解释、不写正文。第一行保留「题材：xxx」格式。",
    "outline": "你是资深网文主编。按作者意见修订宏观规划，只输出修订后的完整规划，不解释。",
    "world": "你是资深网文主编。按作者意见修订世界设定，只输出修订后的完整设定，不解释。",
    "contract": "你是资深网文主编。按作者意见修订故事合约，编号列出全部硬约束条款，"
                "不要解释、只列条款。",
    "characters": "你是资深网文主编。按作者意见修订角色设定，只输出修订后的完整角色表，不解释。",
    "volume": "你是资深网文主编。按作者意见修订卷战略，只输出修订后的完整分卷方案，不解释。",
    "chapter_plan": "你是资深网文主编。按作者意见修订节奏拆章任务单，每章一行"
                    "「第N章《标题》目标：…钩子：…」，只输出任务单，不解释。",
}


def revise_stage(state: dict, stage: str, key: str, feedback: str) -> str:
    """按作者意见重做某个规划阶段的产出（/novel adjust 用）。

    保留已完成章节不动，只重写该阶段 state[key] 与书稿 md 对应段落；
    返回修订后的文本。stage 不支持调整（如 chapters）时抛 StageStopError。
    """
    old = (state.get(key) or "").strip()
    if not old:
        raise StageStopError(f"阶段「{stage}」尚无产出可调整")
    sys_prompt = _REVISE_SYS.get(stage)
    if not sys_prompt:
        raise StageStopError(f"阶段「{stage}」不支持调定（章节请用 /novel rewrite）")
    new = _ask(state, sys_prompt,
               f"现有产出：\n{old}\n\n作者意见（必须落实）：\n{feedback}\n"
               "请输出修订后的完整产出。")
    if len(new) < 20:
        raise StageStopError("修订产出过短，已保留原产出")
    state[key] = new
    if stage == "setup":
        m = re.search(r"题材[:：]\s*(.+)", new)
        if m:
            state["genre"] = m.group(1).strip()[:24]
    _rebuild_md(state)
    return new


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
    text = _strip_title(text, old["title"])   # 去掉正文首行重复的标题
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
    out_path = os.path.join(_book_dir(state), "短剧改编.md")
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
        if ln.startswith(_REVIEW_PREFIX["issue"]):
            issues.append(ln[:120])
        elif ln.startswith(_REVIEW_PREFIX["fact"]):
            facts.append(ln[:120])
        elif ln.startswith(_REVIEW_PREFIX["foreshadow"]):
            fsh.append(ln[:120])
        elif ln.startswith(_REVIEW_PREFIX["close"]):
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


def _novels_root() -> str:
    """书稿根目录：工作区/novels；工作区本身叫 novels 时不再嵌套。

    根因防护：此前无条件拼 ws/novels，用户把工作区设成 D:/novels 时
    会产生 D:/novels/novels/... 双层嵌套。
    """
    ws = tools.get_workspace() or os.getcwd()
    if os.path.basename(os.path.normpath(ws)) == _NOVELS_DIRNAME:
        return ws
    return os.path.join(ws, _NOVELS_DIRNAME)


def _book_title_from(state: dict, text: str) -> str:
    """从大纲文本提取书名；《书名》或「书名：xxx」行，提取不到返回空。

    不做首行猜测——首行可能是「# 总纲」「引擎：…」任何东西，猜出来的
    会成为目录名垃圾。空返回交由调用方走 fallback（灵感首段）。
    """
    text = text or ""
    m = re.search(r"《(.+?)》", text)
    if m:
        return _safe_name(m.group(1))[:30]
    m = re.search(r"^\s*[#\s]*书名[:：]\s*(.+)$", text, re.M)
    if m:
        return _safe_name(m.group(1))[:30]
    return ""


def _fallback_title(state: dict) -> str:
    """无从提取书名时的目录名兜底：灵感第一段（首个标点前，≤16 字）。"""
    idea = (state.get("idea") or "").strip()
    seg = re.split(r"[，。；;,.！？\n：:]", idea)[0].strip()
    return _safe_name(seg)[:16]


def _book_dir(state: dict) -> str:
    """本书目录。旧布局（单 md 或无 dir 字段）自动升级为目录布局。"""
    d = state.get("dir")
    if not d:
        # 兼容旧检查点：state 里只有 file（<ws>/novels/<pid>.md）→ 推出目录
        old = state.get("file") or ""
        base = os.path.splitext(old)[0] if old else ""
        if base and os.path.basename(base).startswith("novel-"):
            d = base
        else:
            d = os.path.join(_novels_root(), state.get("pid") or "untitled")
        state["dir"] = d
    return d


def _rename_book_dir(state: dict, title: str) -> str:
    """把书稿目录改成书名；书名无效或改不动时保留原目录，绝不让流水线失败。

    根因防护：_safe_name 对空值兜底返回「未命名」，若直接采用会让空书名
    悄悄变成「未命名」目录——这里在 safe 之前判空，并把「未命名」也视为
    无效书名。目标父目录一律归位到 _novels_root()，顺带修复旧数据里
    novels/novels 双层嵌套。同名冲突自动加序号。
    """
    raw = (title or "").strip()
    if not raw:
        return _book_dir(state)
    title = _safe_name(raw)
    if not title or title == "未命名":
        return _book_dir(state)
    cur = _book_dir(state)
    if os.path.basename(os.path.normpath(cur)) == title:
        return cur
    target = os.path.join(_novels_root(), title)
    n = 2
    while os.path.exists(target) and os.path.abspath(target) != os.path.abspath(cur):
        target = os.path.join(_novels_root(), f"{title}-{n}")
        n += 1
    try:
        if os.path.isdir(cur):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.rename(cur, target)
        else:
            os.makedirs(target, exist_ok=True)
    except OSError:
        return cur                       # 改名失败（占用/权限）→ 沿用原目录
    state["dir"] = target
    state["file"] = os.path.join(target, _DIR_OUTLINE, _OUTLINE_FILE)
    # 章节里记录的路径同步搬到新目录
    for c in state.get("chapters", []):
        old = c.get("path") or ""
        if old and old.startswith(cur):
            c["path"] = target + old[len(cur):]
    return target


def _write_readme(state: dict):
    """书稿目录下生成「说明.md」：这本书的基本信息与结构导览。"""
    d = _book_dir(state)
    os.makedirs(d, exist_ok=True)
    chapters = state.get("chapters") or []
    lines = [f"# {os.path.basename(d)}", "",
             f"> 灵感：{state.get('idea', '')}", ""]
    if state.get("genre"):
        lines += [f"- 题材：{state['genre']}"]
    lines += [f"- 计划章节：{state.get('total_chapters', 0)} 章",
              f"- 已完成：{len(chapters)} 章",
              f"- 流水线 ID：`{state.get('pid', '')}`",
              f"- 创建时间：{state.get('created', '')}", ""]
    lines += ["## 目录说明", "",
              f"- `{_DIR_OUTLINE}/` — 全书规划（总纲：设定/大纲/卷战略/拆章）",
              f"- `{_DIR_SETTING}/` — 世界观、角色、故事合约等设定",
              f"- `{_DIR_TEXT}/` — 章节正文，每章一个 md（第NNNN章-标题.md）",
              f"- `{_DIR_REVIEW}/` — 各章审校报告（有问题的章节才有）", ""]
    lines += ["## 用法", "",
              "- 继续写：`/novel ok`（逐阶段）或 `/novel resume`",
              "- 加写章节：`/novel extend N`",
              "- 重写某章：`/novel rewrite <章号> [反馈]`",
              "- 导出：`/novel publish txt|md|html|epub`", ""]
    with open(os.path.join(d, _README_FILE), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_review_report(state: dict, chap: dict):
    """把该章审校问题留档到 审查报告/第NNNN章.md（无问题则不落文件）。"""
    issues = chap.get("issues") or []
    if not issues:
        return
    d = os.path.join(_book_dir(state), _DIR_REVIEW)
    os.makedirs(d, exist_ok=True)
    name = re.sub(r"^第[0-9一二三四五六七八九十百千]+章[·\-\s]*", "",
                  chap["title"] or "")
    name = _safe_name(name) or "未命名"
    path = os.path.join(d, f"第{chap['idx']:04d}章-{name}.md")
    lines = [f"# 第 {chap['idx']} 章《{chap['title']}》审校报告", "",
             f"> 章节文件：`{_DIR_TEXT}/{os.path.basename(chap.get('path') or '')}`", "",
             "## 问题清单", ""]
    lines += [f"{i}. {x}" for i, x in enumerate(issues, 1)]
    lines += ["", "## 处理", "",
              "已按提示词自动修复一次；以上为修复后仍存在的问题（质量债）。",
              "可用 `/novel rewrite "
              f"{chap['idx']} <修改意见>` 定向重写。", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _plan_path(state: dict) -> str:
    """全书规划文档：大纲/总纲.md。"""
    return os.path.join(_book_dir(state), _DIR_OUTLINE, _OUTLINE_FILE)


def _book_path(state: dict) -> str:
    """兼容旧接口：返回规划文档路径（publisher 等按「本书文件」派生路径）。"""
    return state.get("file") or _plan_path(state)


def _chapter_path(state: dict, idx: int, title: str) -> str:
    """章节文件路径：正文/第0001章-标题.md（章号补零，便于排序与批量导入）。"""
    name = re.sub(r"^第[0-9一二三四五六七八九十百千]+章[·\-\s]*", "", title or "")
    name = _safe_name(name) or "未命名"
    return os.path.join(_book_dir(state), _DIR_TEXT, f"第{idx:04d}章-{name}.md")


def _safe_name(name: str) -> str:
    """清洗为合法文件名/目录名（去 Windows 非法字符与控制符）。"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (name or "").strip())
    name = name.strip(" .")
    return name[:60] or "未命名"


def _ensure_book(state: dict, title: str):
    """建立本书目录骨架与总纲头（幂等）。"""
    for sub in (_DIR_OUTLINE, _DIR_SETTING, _DIR_TEXT, _DIR_REVIEW):
        os.makedirs(os.path.join(_book_dir(state), sub), exist_ok=True)
    path = _plan_path(state)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n> 灵感：{state['idea']}\n")
    state["file"] = path
    state.setdefault("created", time.strftime("%Y-%m-%d %H:%M:%S"))


# 总纲里各规划段落的顺序（决定 md 中的排版）
_PLAN_SECTIONS = (
    ("framing", "项目设定"),
    ("outline", "宏观规划"),
    ("volume", "卷战略"),
    ("chapter_plan", "节奏拆章"),
)


def _write_plan_section(state: dict, title: str, text: str):
    """把规划产出并入总纲：先更新 state，再按固定顺序整体重建。

    重建（而非追加）保证调定/重跑后不会留下旧版本的重复段落。
    """
    key = next((k for k, t in _PLAN_SECTIONS if t == title), "")
    if key:
        state[key] = text
    _rebuild_plan(state)


def _rebuild_plan(state: dict):
    """从 state 重建「大纲/总纲.md」（按 _PLAN_SECTIONS 顺序）。"""
    _sync_book_dir(state)                # 先定名，避免写完又搬家
    path = _plan_path(state)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    head = state.get("genre") or state.get("idea", "")[:24]
    parts = [f"# {head}", f"\n\n> 灵感：{state.get('idea', '')}"]
    for key, title in _PLAN_SECTIONS:
        if state.get(key):
            parts.append(f"\n\n## {title}\n\n{state[key]}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts) + "\n")
    state["file"] = path


def _sync_book_dir(state: dict):
    """书名已知而目录仍是占位名（pid / 旧数据「未命名」）时，目录改成书名。

    所有规划写入都经过 _rebuild_plan → 这里，是目录定名的单一收口点；
    章节阶段开头也会调一次，兜住「大纲在旧版本生成、目录没改名」的存量书。
    幂等：目录已等于书名时什么都不做。
    存量自愈：旧版本可能把「未命名」当 title 存进检查点——它不算已知书名，
    重新提取覆盖（先《书名》后灵感首段）。
    """
    title = state.get("title") or ""
    if title == "未命名":                # 旧版本写入的垃圾值，不算数
        title = ""
    if not title and state.get("outline"):
        title = _book_title_from(state, state["outline"])
    if not title:
        title = _fallback_title(state)
    if not title:
        return
    state["title"] = title
    base = os.path.basename(os.path.normpath(_book_dir(state)))
    if base == title:
        return
    if base == "未命名" or re.match(r"^novel-\d{8}-\d{6}$", base) \
            or base == _fallback_title(state):
        _rename_book_dir(state, title)


def _append_chapter(state: dict, chap: dict):
    """每章写成独立 md（正文/第NNNN章-标题.md）。"""
    path = _chapter_path(state, chap["idx"], chap["title"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {chap['title']}\n\n{_strip_title(chap['text'], chap['title'])}\n")
    chap["path"] = path


def _strip_title(text: str, title: str) -> str:
    """去掉正文首行与章节标题重复的那一行。

    模型按提示词「正文前第一行是章节标题」输出，而文件本身已有 # 标题，
    不剥离就会出现「# 标题\\n\\n标题」的重复。
    """
    lines = (text or "").splitlines()
    if not lines:
        return text or ""
    first = lines[0].strip().lstrip("#").strip()
    if first and (first == (title or "").strip()
                  or first in (title or "")
                  or (title or "") in first):
        rest = lines[1:]
        while rest and not rest[0].strip():
            rest.pop(0)
        return "\n".join(rest)
    return text


def _append_setting(state: dict, name: str, text: str):
    """设定类产出单独成文（设定集/xxx.md）。"""
    path = os.path.join(_book_dir(state), _DIR_SETTING, _safe_name(name) + ".md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return path


def _rebuild_md(state: dict):
    """重写章节/调定规划后，重建总纲、设定集、说明、章节与审查报告。"""
    _rebuild_plan(state)
    for key, name in (("world", "世界观"), ("contract", "故事合约"),
                      ("characters", "角色")):
        if state.get(key):
            _append_setting(state, name, state[key])
    for c in state.get("chapters", []):
        _append_chapter(state, c)
        _write_review_report(state, c)
    _write_readme(state)
