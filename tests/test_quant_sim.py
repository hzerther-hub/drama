# -*- coding: utf-8 -*-
"""quant v0.5：5 基准信号发射/解析/模拟/一致率 + 数据接入测试。"""

import pytest

from products.quant.benchmark import BENCHMARKS, run_one
from products.quant.data import SAMPLE_CSV, load_bars, load_csv
from products.quant.emitters import emit
from products.quant.ir import demo_ma_cross
from products.quant.parsers import ParseError, parse_code
from products.quant.sim import consistency, run_code
from products.quant.validate import validate

BARS = load_bars("")          # 自带样本行情（200 根日线）


# ---- 5 种信号：发射 → 解析 → IR 语义往返 ----

def _semantic(ir):
    """语义字段比对：排除 name/condition/source_platform 这类展示性字段。"""
    ir.source_platform = ""
    ir.name = ""
    for s in ir.signals:
        s.condition = ""
    return ir.to_json()


@pytest.mark.parametrize("platform", ["joinquant", "ptrade"])
def test_all_benchmarks_roundtrip(platform):
    for ir in BENCHMARKS:
        ir2 = parse_code(emit(ir, platform), platform)
        assert _semantic(ir2) == _semantic(ir), f"{ir.name} 往返不一致"


# ---- 桩运行时模拟 ----

def test_sim_runs_and_trades():
    r = run_code(emit(demo_ma_cross(), "joinquant"), "joinquant", BARS)
    assert r.error == ""
    assert len(r.daily_pct) == len(BARS)
    assert len(r.orders) > 0  # 双均线在样本行情上确有交易


def test_sim_error_reported_not_raised():
    r = run_code("def initialize(context):\n    raise RuntimeError('boom')\n",
                 "joinquant", BARS)
    assert "boom" in r.error


def test_consistency_flags_mismatch():
    a = run_code(emit(BENCHMARKS[0], "joinquant"), "joinquant", BARS)
    b = run_code(emit(BENCHMARKS[2], "joinquant"), "joinquant", BARS)  # 不同策略
    c = consistency(a, b)
    assert c["mismatch"] > 0 and c["rate"] < 1.0


# ---- 一致率基准（PLAN v0.5 验收：≥90%；确定性链路应 100%）----

def test_benchmark_all_pass():
    for ir in BENCHMARKS:
        for src, dst in (("joinquant", "ptrade"), ("ptrade", "joinquant")):
            r = run_one(ir, src, dst, BARS)
            assert r["valid"], f"{ir.name} {src}→{dst} 校验失败: {r['errors']}"
            assert not r["error"], f"{ir.name} {src}→{dst} 模拟错误: {r['error']}"
            assert r["rate"] >= 0.9, f"{ir.name} {src}→{dst} 一致率 {r['rate']:.1%}"


# ---- 新信号的平台差异与校验 ----

def test_new_kinds_pass_sandbox_whitelist():
    for ir in BENCHMARKS:
        for p in ("joinquant", "ptrade"):
            assert validate(emit(ir, p), p).ok


def test_parse_new_kind_signature():
    code = emit(BENCHMARKS[4], "ptrade")   # 网格
    ir = parse_code(code, "ptrade")
    assert ir.signals[0].kind == "grid"
    assert ir.signals[0].params["step"] == 0.05
    assert ir.order.pct == 0.30


def test_parse_unknown_signature_raises():
    src = "def initialize(context):\n    context.stock = '000001.XSHE'\n"
    with pytest.raises(ParseError, match="签名"):
        parse_code(src, "joinquant")


# ---- 数据接入 ----

def test_sample_csv_loads():
    bars = load_csv(SAMPLE_CSV)
    assert len(bars) == 200
    assert {"date", "open", "high", "low", "close", "volume"} <= set(bars[0])
    assert all(isinstance(b["close"], float) for b in bars)


def test_load_bars_default_is_sample():
    assert load_bars("") == load_csv(SAMPLE_CSV)
