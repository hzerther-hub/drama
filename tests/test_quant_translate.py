# -*- coding: utf-8 -*-
"""quant v0.1：双均线 聚宽 ↔ PTrade 互转测试。"""

import pytest

from products.quant.emitters import emit
from products.quant.ir import demo_ma_cross
from products.quant.parsers import ParseError, parse_code
from products.quant.translate import roundtrip, translate
from products.quant.validate import validate


@pytest.fixture
def ir():
    return demo_ma_cross()


def _semantic(ir):
    ir.source_platform = ""
    return ir.to_json()


# ---- 发射器 ----

def test_emit_joinquant_contains_core_calls(ir):
    code = emit(ir, "joinquant")
    assert "run_daily(trade, time='open')" in code
    assert "history(" in code
    assert "order_target_percent(context.stock, 0.95)" in code


def test_emit_ptrade_time_mapped(ir):
    code = emit(ir, "ptrade")
    # 对照表已知差异：聚宽 'open' → PTrade '09:30'；且 run_daily 带 context
    assert "run_daily(context, trade, time='09:30')" in code
    assert "get_history(" in code


def test_emit_rejects_unsupported_signal(ir):
    ir.signals[0].kind = "macd"      # v0.5 仍未支持的信号
    with pytest.raises(ValueError, match="暂不支持"):
        emit(ir, "joinquant")


def test_emit_rejects_fast_ge_slow(ir):
    ir.signals[0].params["fast"] = 20
    ir.signals[0].params["slow"] = 5
    with pytest.raises(ValueError, match="fast < slow"):
        emit(ir, "ptrade")


def test_emit_unknown_platform(ir):
    with pytest.raises(ValueError, match="未知平台"):
        emit(ir, "no-such-platform")


# ---- 双向互转 + 往返一致 ----

def test_roundtrip_jq_to_ptrade(ir):
    code = emit(ir, "joinquant")
    rt = roundtrip(code, "joinquant", "ptrade")
    assert rt["validation"].ok
    assert _semantic(rt["ir_src"]) == _semantic(rt["ir_back"])


def test_roundtrip_ptrade_to_jq(ir):
    code = emit(ir, "ptrade")
    rt = roundtrip(code, "ptrade", "joinquant")
    assert rt["validation"].ok
    assert _semantic(rt["ir_src"]) == _semantic(rt["ir_back"])


def test_translate_time_roundtrip(ir):
    """open → 09:30 → open 时间语义不漂移。"""
    jq = emit(ir, "joinquant")
    fwd = translate(jq, "joinquant", "ptrade")
    assert fwd["ir"].schedule.time == "open"  # 解析 ptrade 后归一化回 open


# ---- 解析器边界 ----

def test_parse_missing_initialize_raises():
    with pytest.raises(ParseError, match="initialize"):
        parse_code("x = 1\n", "joinquant")


def test_parse_syntax_error_raises():
    with pytest.raises(ParseError, match="语法错误"):
        parse_code("def broken(:\n", "ptrade")


def test_parse_unconstrained_strategy_raises():
    """无法识别的手写结构应抛 ParseError（留给 LLM 解析兜底）。"""
    src = "def initialize(context):\n    g.x = 1\n"
    with pytest.raises(ParseError):
        parse_code(src, "joinquant")


# ---- 校验器 ----

def test_validate_clean_code_passes(ir):
    r = validate(emit(ir, "ptrade"), "ptrade")
    assert r.ok, r.errors


def test_validate_syntax_error():
    r = validate("def broken(:\n", "joinquant")
    assert not r.ok
    assert any("语法错误" in e for e in r.errors)


@pytest.mark.parametrize("bad,frag", [
    ("import os\n", "os"),
    ("import subprocess\n", "subprocess"),
    ("import requests\n", "requests"),
    ("from urllib import request\n", "urllib"),
    ("open('f.txt')\n", "open()"),
    ("eval('1+1')\n", "eval()"),
])
def test_validate_whitelist_blocks(bad, frag):
    r = validate(bad, "joinquant")
    assert not r.ok
    assert any(frag in e for e in r.errors)
