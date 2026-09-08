# -*- coding: utf-8 -*-
"""novel_chain：整本生产链（fake LLM 全流程，不依赖真实模型/网络）。"""

import os

import pytest

import novel_chain
import vecstore


class FakeLLM:
    """按提示词特征返回内容的假流式 LLM；审校可切换「出一次问题」模式。"""

    def __init__(self):
        self.calls = []
        self.review = "PASS"
        self.review_once_issues = None   # 只出一次问题（之后恢复 review）
        self.rewrite_text = "第1章 重写版\n" + "全新正文内容。" * 30

    def stream_chat(self, model, msgs, tools=None):
        user = msgs[-1]["content"]
        self.calls.append(user)
        text = self._reply(user)
        for i in range(0, len(text), 20):
            yield {"type": "text", "delta": text[i:i + 20]}

    def _reply(self, user):
        if "作者意见（必须落实）" in user:                # revise_stage 调定
            return ("修订后设定：题材：悬疑\n卖点：反转再反转\n"
                    "目标读者：爱烧脑的推理读者")
        if "MASTER_SETTING" in user:
            return "1. 称谓固定\n2. 禁止现代词汇"
        if "请重写本章" in user:
            return self.rewrite_text
        if "题材灵感" in user:
            return "书名：测试之书\n题材：都市\n卖点：逆袭"
        if "故事引擎" in user:
            return "引擎：小人物逆袭\n三幕：开局受挫/中段崛起/终局翻盘"
        if "时代与地理背景" in user:
            return "背景：平行都市\n规则：钱即权\n势力：三大家族"
        if "故事合约" in user or "编号列出" in user:
            return "1. 称谓固定\n2. 禁止现代词汇"
        if "成长弧线" in user:
            return "张三：外卖员，想翻身，从谷底到巅峰\n李四：对手"
        if "请划分卷" in user:
            return "第一卷 第1-2章：起步\n第二卷 第3-4章：扩张"
        if "逐章输出任务单" in user:
            return ("第1章《开局》目标：立足 钩子：神秘来电\n"
                    "第2章《接触》目标：结盟 钩子：跟踪者")
        if "请审校" in user:
            if self.review_once_issues:
                out = self.review_once_issues
                self.review_once_issues = None
                return out
            return self.review
        if "修订后的完整正文" in user:
            return self.fixed_text
        if "请写第" in user:
            body = "他推开房门走进房间，窗外的城市灯火通明。" * 6
            return f"第{len(self._wrote()) + 1}章 测试标题\n{body}"
        return "（无匹配输出）"

    def _wrote(self):
        return [c for c in self.calls if "请写第" in c]


@pytest.fixture()
def fake(monkeypatch, tmp_path):
    f = FakeLLM()
    monkeypatch.setattr(novel_chain.llm, "stream_chat", f.stream_chat)
    monkeypatch.setattr(vecstore, "qdrant_url", lambda: "")   # 内存降级
    monkeypatch.setattr(novel_chain.tools, "get_workspace",
                        lambda: str(tmp_path))                # 书稿落 tmp
    vecstore.reset_memory()
    return f


def _start(idea="重生都市逆袭", total=2):
    return novel_chain.new_pipeline(idea, total, model_key="fake-model")


def test_ask_retries_once_on_empty_reply(monkeypatch):
    """空回复自动重试一次（曾被重复定义静默遮蔽，此处锁住行为）。"""
    replies = ["", "第二次才有内容"]
    calls = []

    def stream_chat(model, msgs, tools=None):
        calls.append(msgs)
        out = replies[len(calls) - 1]
        for i in range(0, len(out), 20):
            yield {"type": "text", "delta": out[i:i + 20]}

    monkeypatch.setattr(novel_chain.llm, "stream_chat", stream_chat)
    assert novel_chain._ask({"model_key": "fake-model"}, "sys", "user") == "第二次才有内容"
    assert len(calls) == 2                              # 确实重试了一次


def test_ask_retries_once_on_llm_error(monkeypatch):
    """首次 LLMError 重试，第二次成功即返回（不冒泡）。"""
    calls = []

    def stream_chat(model, msgs, tools=None):
        calls.append(msgs)
        if len(calls) == 1:
            raise novel_chain.llm.LLMError("首次失败")
        yield {"type": "text", "delta": "重试成功"}

    monkeypatch.setattr(novel_chain.llm, "stream_chat", stream_chat)
    assert novel_chain._ask({"model_key": "fake-model"}, "sys", "user") == "重试成功"
    assert len(calls) == 2


def test_ask_raises_after_second_llm_error(monkeypatch):
    """两次都失败则 LLMError 冒泡，交由引擎按阶段策略分级。"""
    calls = []

    def stream_chat(model, msgs, tools=None):
        calls.append(msgs)
        raise novel_chain.llm.LLMError("一直失败")
        yield  # pragma: no cover

    monkeypatch.setattr(novel_chain.llm, "stream_chat", stream_chat)
    with pytest.raises(novel_chain.llm.LLMError):
        novel_chain._ask({"model_key": "fake-model"}, "sys", "user")
    assert len(calls) == 2


def test_parse_start_args_variants():
    """/novel start 参数解析（自 ui 抽出的纯函数）。"""
    assert novel_chain.parse_start_args("重生逆袭 12") == {
        "idea": "重生逆袭", "total": 12, "auto": False}
    assert novel_chain.parse_start_args("重生逆袭 12 auto")["auto"] is True
    assert novel_chain.parse_start_args("重生逆袭 12 自动")["auto"] is True
    assert novel_chain.parse_start_args("重生逆袭") == {
        "idea": "重生逆袭", "total": 3, "auto": False}
    assert novel_chain.parse_start_args("重生逆袭 999")["total"] == 999
    # 章数解析只认 1-3 位数；4 位不匹配 → 整串当灵感、章数回落默认 3
    four = novel_chain.parse_start_args("重生逆袭 1234")
    assert four["total"] == 3 and four["idea"] == "重生逆袭 1234"
    assert novel_chain.parse_start_args("  重生逆袭  7  ")["idea"] == "重生逆袭"
    assert novel_chain.parse_start_args("") == {"error": "need_idea"}
    assert novel_chain.parse_start_args("   ") == {"error": "need_idea"}
    # 单独的 auto 无前置空白，不视为标志位 → 当作灵感（与原 UI 行为一致）
    assert novel_chain.parse_start_args("auto")["idea"] == "auto"


def test_full_run_two_chapters(fake, tmp_path):
    p = _start()
    assert p.run() == "done"
    assert len(p.state["chapters"]) == 2
    assert all(len(c["text"]) >= 50 for c in p.state["chapters"])
    assert p.state["contract"].startswith("1.")           # 故事合约已生成
    # 新目录布局：大纲/总纲.md + 正文/第NNNN章-标题.md + 设定集/
    book = tmp_path / "novels" / p.pid
    plan = book / "大纲" / "总纲.md"
    assert plan.exists() and "## " in plan.read_text(encoding="utf-8")
    chapters = sorted((book / "正文").glob("第*章-*.md"))
    assert len(chapters) == 2
    assert chapters[0].name.startswith("第0001章-")
    assert (book / "设定集" / "世界观.md").exists()
    assert len(vecstore._MEM.get(p.pid, [])) >= 2         # RAG 内存降级入桶


def test_chapter_files_are_independent_and_numbered(fake, tmp_path):
    """每章独立 md，章号补零便于排序，标题（拆章预定优先）在文件名里。"""
    p = _start(total=2)
    p.run()
    files = sorted((tmp_path / "novels" / p.pid / "正文").glob("*.md"))
    # FakeLLM 的拆章任务单预定了《开局》《接触》两个标题
    assert [f.name for f in files] == [
        "第0001章-开局.md", "第0002章-接触.md"]
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert text.startswith("# ")              # 首行是章节标题（md 一级标题）
        assert len(text) > 100                    # 含正文，不是空壳
    # state 里记录了每章的落盘路径，且路径与文件名一致
    assert all(c.get("path") for c in p.state["chapters"])
    assert all(os.path.basename(c["path"]) in
               {f.name for f in files} for c in p.state["chapters"])


def test_contract_injected_into_chapter_prompt(fake, tmp_path):
    p = _start(total=1)
    assert p.run() == "done"
    prompt = novel_chain._chapter_prompt(p.state, 2)
    assert "【硬约束·违反即失败】" in prompt
    assert "1. 称谓固定" in prompt


def test_foreshadow_tracker_lifecycle():
    state = {"foreshadows": [], "ledger": []}
    novel_chain._apply_ledger(state, 1, [], ["伏笔：神秘U盘的来历"], [])
    assert state["foreshadows"][0]["closed_ch"] is None
    novel_chain._apply_ledger(state, 3, [], [], ["偿还：神秘U盘"])
    assert state["foreshadows"][0]["closed_ch"] == 3


def test_review_prompt_parser_contract():
    """提示词必须逐条声明 _review 解析器期待的每个前缀。

    回归护栏：commit 45805a8 曾单方面从提示词删掉「事实/伏笔」两行，
    导致模型不再输出、台账与伏笔追踪静默失效——而旧测试因硬编码
    「事实：…」字符串绕过提示词，完全没发现。
    """
    for name, prefix in novel_chain._REVIEW_PREFIX.items():
        assert f"{prefix}：" in novel_chain._SYS_REVIEWER, \
            f"审校提示词缺少「{prefix}：」声明，解析器分支 {name} 将永远收不到输入"


def test_review_parses_what_prompt_asks_for(monkeypatch):
    """端到端契约：模型严格照「提示词」格式输出 → 四类信息都被解析出来。

    回复由 _SYS_REVIEWER 里**实际声明的**前缀拼成（而非直接读常量），
    因此提示词一旦丢掉某个前缀，模型就不会输出它、断言随即失败——
    这正是 45805a8 那次退化的形态。
    """
    pfx = novel_chain._REVIEW_PREFIX
    declared = {name: p for name, p in pfx.items()
                if f"{p}：" in novel_chain._SYS_REVIEWER}
    lines = [f"{declared['issue']}：第2章称呼不一致"]
    if "fact" in declared:
        lines.append(f"{declared['fact']}：主角拿到神秘U盘")
    if "foreshadow" in declared:
        lines.append(f"{declared['foreshadow']}：U盘来历未解")
    if "close" in declared:
        lines.append(f"{declared['close']}：神秘U盘")
    reply = "\n".join(lines)

    def stream_chat(model, msgs, tools=None):
        for i in range(0, len(reply), 20):
            yield {"type": "text", "delta": reply[i:i + 20]}

    monkeypatch.setattr(novel_chain.llm, "stream_chat", stream_chat)
    issues, facts, fsh, closes = novel_chain._review(
        {"model_key": "fake-model"}, "章节正文" * 30, 2)
    assert issues, "问题行未解析"
    assert facts, "提示词未要求「事实：」→ 台账将永远为空"
    assert fsh, "提示词未要求「伏笔：」→ 伏笔追踪将永远为空"
    assert closes, "偿还行未解析"
    assert "U盘" in facts[0] and "U盘" in fsh[0] and "U盘" in closes[0]


def test_review_repair_and_ledger(fake, tmp_path):
    fake.review_once_issues = "问题：节奏拖沓\n事实：主角拿到神秘U盘"
    fake.fixed_text = "第1章 修订后\n" + "修订后的正文内容。" * 30
    p = _start(total=1)
    assert p.run() == "done"
    chap = p.state["chapters"][0]
    assert chap["issues"] == []                      # 复审 PASS → 残余问题清空
    assert "U盘" in "".join(p.state["ledger"])       # 首轮事实不丢失，入台账
    assert "修订" in chap["text"]                    # 正文已被修复替换
    assert p.state["debts"] == []                    # 无残余债


def test_residual_issues_become_debts(fake, tmp_path):
    fake.review = "问题：节奏拖沓"                    # 每次审校都出问题
    fake.fixed_text = "第1章 修复失败版\n" + "内容。" * 40
    p = _start(total=1)
    assert p.run() == "done"                          # 质量债不阻断
    assert p.state["debts"] and "节奏拖沓" in p.state["debts"][0]["detail"]


def test_pause_mid_chapters_and_resume_without_rewrite(fake, tmp_path):
    p = _start(total=2)

    def stop_after_ch1(e):
        if e.get("type") == "chapter_done" and e.get("idx") == 1:
            p.request_stop()

    assert p.run(on_event=stop_after_ch1) == "paused"
    assert len(p.state["chapters"]) == 1
    before = list(p.state["chapters"])
    calls_before = len(fake.calls)
    assert p.run() == "done"
    assert len(p.state["chapters"]) == 2
    assert p.state["chapters"][0] == before[0]        # 第一章未重写
    assert not any("请写第 1 章" in c for c in fake.calls[calls_before:])


def test_revise_stage_updates_state_and_md(fake, tmp_path):
    """/novel adjust：按意见重做规划阶段产出（此前 revise_stage 缺失必崩）。"""
    p = _start(total=1)
    assert p.run(until="setup") == "paused"
    old = p.state["framing"]
    novel_chain.revise_stage(p.state, "setup", "framing", "改成悬疑题材")
    assert p.state["framing"] != old
    assert "悬疑" in p.state["framing"]
    assert p.state["genre"] == "悬疑"                  # setup 同步刷新 genre
    # 调定后总纲同步重建（大纲/总纲.md）
    plan = tmp_path / "novels" / p.pid / "大纲" / "总纲.md"
    assert "悬疑" in plan.read_text(encoding="utf-8")


def test_revise_stage_rejects_unknown_stage(fake, tmp_path):
    p = _start(total=1)
    p.run(until="setup")
    with pytest.raises(novel_chain.StageStopError):
        novel_chain.revise_stage(p.state, "chapters", "chapters", "改一下")


def test_revise_stage_requires_existing_output(fake, tmp_path):
    p = _start(total=1)
    with pytest.raises(novel_chain.StageStopError):
        novel_chain.revise_stage(p.state, "setup", "framing", "随便改")


def test_stage_labels_cover_all_stages():
    """每个阶段都要有中文标签，否则进度/暂停提示会露出英文键名。"""
    assert all(s.name in novel_chain.STAGE_LABELS for s in novel_chain.STAGES)


def test_rewrite_updates_chapter_and_md(fake, tmp_path):
    p = _start(total=1)
    p.run()
    fake.rewrite_text = "第1章 重写版\n" + "全新正文内容。" * 30
    chap = novel_chain.rewrite_chapter(p.state, 1, "节奏太慢")
    assert "重写" in chap["text"]
    # 重写后章节文件同步更新（正文目录下）
    files = list((tmp_path / "novels" / p.pid / "正文").glob("*.md"))
    assert len(files) == 1
    assert "重写版" in files[0].read_text(encoding="utf-8")


def test_drama_adapt_writes_script(fake, tmp_path):
    p = _start(total=2)
    p.run()
    out = novel_chain.drama_adapt(p.state, 1, 2)
    text = open(out, encoding="utf-8").read()
    assert "短剧改编" in text and "第 1 章" in text and "第 2 章" in text


def test_deconstruct_writes_report(fake, tmp_path):
    src = tmp_path / "sample.txt"
    src.write_text("这是一个用于拆书的样本文本，" * 20, encoding="utf-8")
    out = novel_chain.deconstruct(str(src), "fake-model")
    assert "拆书报告" in open(out, encoding="utf-8").read()


def test_drama_no_chapters_raises(fake, tmp_path):
    p = _start()
    with pytest.raises(novel_chain.StageStopError):
        novel_chain.drama_adapt(p.state, 1, 2)


def test_extend_total_then_continue(fake, tmp_path):
    p = _start(total=1)
    assert p.run() == "done"
    n_before = len(p.state["chapters"])
    novel_chain.extend_total(p, 2)
    assert p.state["total_chapters"] == 3
    assert p.pipeline_status == "paused" and p.cursor == "chapters"
    assert p.run() == "done"
    assert len(p.state["chapters"]) == 3


def test_chapter_text_has_no_duplicate_title(fake, tmp_path):
    """正文首行与章节标题重复时要剥离（文件已有一级标题，否则显示两遍）。"""
    p = _start(total=1)
    p.run()
    c = p.state["chapters"][0]
    assert not c["text"].lstrip().startswith("#")
    assert not c["text"].splitlines()[0].strip().startswith(c["title"])
    body = open(c["path"], encoding="utf-8").read()
    # 文件里标题只出现一次
    assert body.count(c["title"]) == 1


def test_strip_title_keeps_unrelated_first_line():
    """首行不是标题时不能误删正文。"""
    assert novel_chain._strip_title("他推开门走了进去。", "某章标题") == "他推开门走了进去。"
    assert novel_chain._strip_title("# 某章标题\n\n正文", "某章标题") == "正文"
    assert novel_chain._strip_title("某章标题\n\n正文", "某章标题") == "正文"
    assert novel_chain._strip_title("", "标题") == ""
