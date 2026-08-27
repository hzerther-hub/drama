# -*- coding: utf-8 -*-
"""context.py：token 估算 + 渐进式上下文压缩。"""

import context
import config


def _msg(role, text):
    return {"role": role, "content": text}


TEST_MODEL_SMALL = config.ModelConfig(
    key="t/m", provider_name="t", model_id="m", display_name="M",
    base_url="http://x", api_key="k", context_window=8192)


def _tool_round(call_id, name, result):
    """一轮工具调用：assistant(tool_calls) + tool 结果。"""
    return [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": call_id, "type": "function",
                         "function": {"name": name, "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": call_id, "content": result},
    ]


class TestEstimateTokens:
    def test_plain_text_scales_with_length(self):
        short = context.estimate_tokens([_msg("user", "x" * 100)])
        long = context.estimate_tokens([_msg("user", "x" * 200)])
        assert short >= 20 and long > short

    def test_cjk_counts_more_than_half_length(self):
        # 中文在分词器里约 1 字 1 token：旧的 len//2 粗算会低估一半
        n = context.estimate_tokens([_msg("user", "你好世界" * 25)])   # 100 个汉字
        assert n >= 80, f"中文 token 估算偏低：{n}"

    def test_ascii_code_not_overcounted(self):
        # ASCII 代码约 4 字符 1 token：旧粗算（len//2）会高估一倍
        n = context.estimate_tokens([_msg("user", "a" * 400)])
        assert n <= 220, f"ASCII token 估算偏高：{n}"

    def test_image_part_uses_fixed_estimate(self):
        m = {"role": "user", "content": [
            {"type": "text", "text": "看图"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ]}
        n = context.estimate_tokens([m])
        assert n >= context.IMAGE_TOKEN_ESTIMATE

    def test_tool_calls_counted(self):
        m = {"role": "assistant", "content": "",
             "tool_calls": [{"id": "1", "type": "function",
                             "function": {"name": "f", "arguments": "x" * 200}}]}
        assert context.estimate_tokens([m]) >= 40

    def test_empty(self):
        assert context.estimate_tokens([]) == 0
        assert context.estimate_text_tokens("") == 0


class TestTruncate:
    def test_short_string_untouched(self):
        assert context._truncate("abc", 10) == "abc"

    def test_keeps_head_and_tail(self):
        s = "H" * 500 + "M" * 500 + "T" * 500
        out = context._truncate(s, 300)
        assert out.startswith("H" * 100)
        assert out.endswith("T" * 100)
        assert "已压缩" in out
        assert "1500" in out           # 标记原长度
        assert len(out) < len(s)


class TestEffectiveBudget:
    def test_no_model_uses_global(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 24000)
        assert context.effective_budget() == 24000

    def test_small_window_clamps(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 24000)
        monkeypatch.setattr(config, "MAX_TOKENS", 4096)
        # 8192 窗口 - 4096 - 1024 余量 = 3072
        assert context.effective_budget(TEST_MODEL_SMALL) == 3072

    def test_zero_window_means_unknown(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 24000)
        model = config.ModelConfig(key="t/m", provider_name="t", model_id="m",
                                   display_name="M", base_url="http://x",
                                   api_key="k")
        assert context.effective_budget(model) == 24000

    def test_budget_never_above_global(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 8000)
        monkeypatch.setattr(config, "MAX_TOKENS", 4096)
        # 大窗口模型：win_budget 远超预算，结果应被全局预算封顶
        big = config.ModelConfig(key="t/m", provider_name="t", model_id="m",
                                 display_name="M", base_url="http://x",
                                 api_key="k", context_window=32768)
        assert context.effective_budget(big) == 8000


class TestMaybeCompact:
    def test_under_budget_returns_same_list(self):
        msgs = [_msg("system", "sys"), _msg("user", "hi")]
        assert context.maybe_compact(msgs) is msgs

    def test_old_tool_results_truncated(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 1000)
        msgs = [_msg("system", "sys"), _msg("user", "q" * 100)]
        # 足够多的轮次：旧轮工具结果应按 400 字符截断
        for i in range(6):
            msgs += _tool_round(f"c{i}", "read_file", "R" * 3000)
            msgs.append(_msg("user", "u" * 300))
        out = context.maybe_compact(msgs)
        # 旧轮的长工具结果要么被截断、要么随中间轮折叠消失
        leftovers = [m for m in out
                     if m.get("role") == "tool"
                     and isinstance(m.get("content"), str)
                     and len(m["content"]) > 3000]
        assert not leftovers

    def test_middle_rounds_collapsed(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 800)
        monkeypatch.setattr(config, "CONTEXT_KEEP_ROUNDS", 2)
        msgs = [_msg("system", "sys"), _msg("user", "第一个问题")]
        for i in range(8):
            msgs += _tool_round(f"c{i}", "grep_search", "R" * 800)
            msgs.append(_msg("user", f"问题{i}" + "u" * 200))
        before = context.estimate_tokens(msgs)
        out = context.maybe_compact(msgs)
        after = context.estimate_tokens(out)
        assert after < before
        # 结构合法：system 仍在开头，首个 user 原文保留
        assert out[0]["role"] == "system"
        assert out[1]["content"] == "第一个问题"
        # 中间轮折叠为摘要
        summaries = [m for m in out if m.get("role") == "assistant"
                     and isinstance(m.get("content"), str)
                     and "历史对话已压缩" in m["content"]]
        assert summaries

    def test_emit_reports_before_after(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 500)
        events = []
        msgs = [_msg("system", "s"), _msg("user", "q" * 200)]
        for i in range(5):
            msgs += _tool_round(f"c{i}", "read_file", "R" * 900)
        context.maybe_compact(msgs, emit=events.append)
        assert events and events[0]["type"] == "context_compact"
        assert events[0]["after"] < events[0]["before"]

    def test_old_images_stripped(self, monkeypatch):
        monkeypatch.setattr(config, "CONTEXT_BUDGET", 500)
        msgs = [_msg("system", "s"),
                {"role": "user", "content": [
                    {"type": "text", "text": "看图"},
                    {"type": "image_url",
                     "image_url": {"url": "data:image/png;base64,AAAA"}},
                ]}]
        for i in range(5):
            msgs += _tool_round(f"c{i}", "read_file", "R" * 900)
        out = context.maybe_compact(msgs)
        # 旧图片被换成占位文本（要么就地替换，要么随折叠消失）
        imgs = [p for m in out if isinstance(m.get("content"), list)
                for p in m["content"]
                if isinstance(p, dict) and p.get("type") == "image_url"]
        assert not imgs
