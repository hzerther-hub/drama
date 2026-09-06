# -*- coding: utf-8 -*-
"""novel_chain：整本生产链（fake LLM 全流程，不依赖真实模型/网络）。"""

import pytest

import novel_chain
import vecstore


class FakeLLM:
    """按提示词特征返回内容的假流式 LLM；审校可切换「出一次问题」模式。"""

    def __init__(self):
        self.calls = []
        self.review = "PASS"
        self.review_once_issues = None   # 只出一次问题（之后恢复 review）

    def stream_chat(self, model, msgs, tools=None):
        user = msgs[-1]["content"]
        self.calls.append(user)
        text = self._reply(user)
        for i in range(0, len(text), 20):
            yield {"type": "text", "delta": text[i:i + 20]}

    def _reply(self, user):
        if "题材灵感" in user:
            return "书名：测试之书\n题材：都市\n卖点：逆袭"
        if "故事引擎" in user:
            return "引擎：小人物逆袭\n三幕：开局受挫/中段崛起/终局翻盘"
        if "时代与地理背景" in user:
            return "背景：平行都市\n规则：钱即权\n势力：三大家族"
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


def test_full_run_two_chapters(fake, tmp_path):
    p = _start()
    assert p.run() == "done"
    assert len(p.state["chapters"]) == 2
    assert all(len(c["text"]) >= 50 for c in p.state["chapters"])
    md = tmp_path / "novels" / (p.pid + ".md")
    assert md.exists() and "## " in md.read_text(encoding="utf-8")
    # RAG 内存降级：每章 chunk 已入桶
    assert len(vecstore._MEM.get(p.pid, [])) >= 2


def test_review_repair_and_ledger(fake, tmp_path):
    fake.review_once_issues = "问题：节奏拖沓\n事实：主角拿到神秘U盘"
    fake.fixed_text = "第1章 修订后\n" + "修订后的正文内容。" * 30
    p = _start(total=1)
    assert p.run() == "done"
    chap = p.state["chapters"][0]
    assert "节奏拖沓" in chap["issues"][0]          # 首轮问题留档
    assert "U盘" in "".join(p.state["ledger"])      # 事实入台账
    assert "修订" in chap["text"]                    # 正文已被修复替换
    assert p.state["debts"] == []                    # 复审 PASS → 无残余债


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
