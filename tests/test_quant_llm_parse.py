# -*- coding: utf-8 -*-
"""quant RAG/LLM 解析兜底测试（mock chat_fn，无需网络/key）。"""

import json

import pytest

from products.quant import kb
from products.quant.emitters import emit
from products.quant.llm_parse import (build_messages, extract_json,
                                      parse_with_llm)
from products.quant.parsers import ParseError, parse_code
from products.quant.translate import translate
from products.quant.validate import validate

# 非模板结构的手写策略：确定性解析器认不出（属性名非基准签名）
HANDWRITTEN = """\
def initialize(context):
    context.security = '600519.XSHG'
    context.short_window = 10
    context.long_window = 30
    run_daily(handle, time='open')

def handle(context):
    pass
"""

GOOD_IR_JSON = json.dumps({
    "name": "手写双均线",
    "universe": ["600519.XSHG"],
    "schedule": {"freq": "daily", "time": "open"},
    "signals": [{"kind": "ma_cross",
                 "params": {"fast": 10, "slow": 30, "price": "close"},
                 "condition": "MA10 上穿 MA30 买入"}],
    "order": {"style": "target_pct", "pct": 0.8},
    "risk": {}, "source_platform": "joinquant",
}, ensure_ascii=False)


def _mock_chat_ok(_messages):
    return GOOD_IR_JSON


def _mock_chat_fenced(_messages):
    return "好的，解析结果如下：\n```json\n" + GOOD_IR_JSON + "\n```\n以上。"


# ---- 知识库 ----

def test_kb_loads_api_map_and_fewshot():
    from products.quant.benchmark import BENCHMARKS, PLATFORMS
    docs = kb.load_documents()
    kinds = {d["kind"] for d in docs}
    assert "api_map" in kinds and "fewshot" in kinds
    # 基准策略数 × 4 平台 = few-shot 条数（6 基准 × 4 = 24）；3 份平台对照表
    assert sum(1 for d in docs if d["kind"] == "fewshot") == len(BENCHMARKS) * len(PLATFORMS)
    assert sum(1 for d in docs if d["kind"] == "api_map") == 3


def test_kb_retrieve_relevant_first():
    hits = kb.retrieve("RSI 超买超卖 rsi_period", k=2, kind="fewshot")
    assert hits and "rsi" in hits[0]["id"]


# ---- prompt 组装 / JSON 提取 ----

def test_build_messages_contains_context_and_source():
    msgs = build_messages(HANDWRITTEN, "joinquant")
    assert msgs[0]["role"] == "system"
    user = msgs[1]["content"]
    assert "待解析策略" in user and HANDWRITTEN in user
    assert "平台 API 对照表" in user  # RAG 上下文已注入


def test_extract_json_plain_and_fenced():
    assert extract_json(GOOD_IR_JSON)["universe"] == ["600519.XSHG"]
    assert extract_json(_mock_fenced_text := "废话\n```json\n"
                       + GOOD_IR_JSON + "\n```\n再见")["name"] == "手写双均线"
    with pytest.raises(ParseError, match="未找到 JSON"):
        extract_json("没有对象")


# ---- LLM 解析（mock）----

def test_parse_with_llm_mock_ok():
    ir = parse_with_llm(HANDWRITTEN, "joinquant", chat_fn=_mock_chat_ok)
    assert ir.universe == ["600519.XSHG"]
    sig = ir.signals[0]
    assert sig.kind == "ma_cross"
    assert sig.params["fast"] == 10 and sig.params["slow"] == 30
    assert ir.order.pct == 0.8
    assert ir.source_platform == "joinquant"


def test_parse_with_llm_retry_then_ok():
    calls = {"n": 0}

    def flaky(_messages):
        calls["n"] += 1
        return "垃圾输出" if calls["n"] == 1 else GOOD_IR_JSON

    ir = parse_with_llm(HANDWRITTEN, "joinquant", chat_fn=flaky)
    assert calls["n"] == 2 and ir.name == "手写双均线"


def test_parse_with_llm_gives_up():
    with pytest.raises(ParseError, match="重试"):
        parse_with_llm(HANDWRITTEN, "joinquant",
                       chat_fn=lambda _m: "永远不对", max_retries=1)


def test_parse_with_llm_rejects_empty_ir():
    bad = json.dumps({"name": "x", "universe": [], "signals": []})
    with pytest.raises(ParseError, match="重试"):
        parse_with_llm(HANDWRITTEN, "joinquant",
                       chat_fn=lambda _m: bad, max_retries=0)


# ---- translate 集成：确定性失败 → LLM 兜底 → 发射 → 校验 ----

def test_translate_llm_fallback_end_to_end():
    # 确定性解析确实认不出这个结构
    with pytest.raises(ParseError):
        parse_code(HANDWRITTEN, "joinquant")
    r = translate(HANDWRITTEN, "joinquant", "ptrade",
                  chat_fn=_mock_chat_ok)
    assert r["ir"].signals[0].params == {"fast": 10, "slow": 30,
                                         "price": "close"}
    assert "run_daily(context, trade, time='09:30')" in r["code"]
    assert r["validation"].ok


def test_translate_without_chat_fn_raises():
    with pytest.raises(ParseError):
        translate(HANDWRITTEN, "joinquant", "ptrade")


def test_translate_deterministic_path_ignores_chat_fn():
    """能确定性解析的代码不触发 LLM（chat_fn 被调用即失败）。"""
    from products.quant.ir import demo_ma_cross
    code = emit(demo_ma_cross(), "joinquant")

    def forbidden(_m):
        raise AssertionError("不应调用 LLM")

    r = translate(code, "joinquant", "ptrade", chat_fn=forbidden)
    assert r["validation"].ok
