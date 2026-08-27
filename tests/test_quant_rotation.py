# -*- coding: utf-8 -*-
"""quant v2.0：多标的动量轮动（momentum_rotation）四平台互转测试。

覆盖：发射结构、解析往返、桩运行时逐日持有集合一致率、白名单校验、
往返一致性、以及"轮动确实发生"（持有集合随时间变化）。
"""

import pytest

from products.quant.benchmark import PLATFORMS, run_one
from products.quant.data import load_bars, synthetic_bars
from products.quant.emitters import emit
from products.quant.ir import ETF_ROTATION_UNIVERSE, demo_etf_rotation
from products.quant.parsers import parse_code
from products.quant.sim import consistency, run_code
from products.quant.translate import roundtrip, translate
from products.quant.validate import validate

BARS = load_bars("")
ROT = demo_etf_rotation()


def _semantic(ir):
    ir.source_platform = ""
    ir.name = ""
    for s in ir.signals:
        s.condition = ""
    return ir.to_json()


def _bars_map(ir=None):
    ir = ir or ROT
    bm = synthetic_bars(ir.universe, n=200)
    return bm, bm[ir.universe[0]]


# ---- 发射结构（四平台）----

def test_emit_rotation_all_platforms_structure():
    for p in PLATFORMS:
        code = emit(ROT, p)
        assert ".universe" in code
        assert "lookback" in code and "top_n" in code
        assert "drop_threshold" in code
        assert "_momentum_score" in code
        assert "import math" in code


def test_emit_rotation_universe_mapped():
    # 掘金/QMT 标的格式应已转换
    gm = emit(ROT, "gm")
    assert "SHSE.513100" in gm and "SZSE.159509" in gm
    qmt = emit(ROT, "qmt")
    assert "513100.SH" in qmt and "159509.SZ" in qmt


def test_emit_rotation_jq_uses_history_security_list():
    code = emit(ROT, "joinquant")
    assert "history(context.lookback + 1, unit='1d'" in code
    assert "security_list=context.universe" in code


def test_emit_rotation_gm_loops_history_n():
    code = emit(ROT, "gm")
    assert "history_n(sym, '1d', context.lookback + 1" in code


def test_emit_rotation_rejects_empty_universe():
    from products.quant.ir import StrategyIR, Signal, Schedule, OrderSpec
    bad = StrategyIR(name="空", universe=[], schedule=Schedule(),
                     signals=[Signal(kind="momentum_rotation", params={})],
                     order=OrderSpec())
    with pytest.raises(ValueError, match="universe"):
        emit(bad, "joinquant")


# ---- 解析往返 ----

@pytest.mark.parametrize("platform", PLATFORMS)
def test_rotation_roundtrip(platform):
    ir2 = parse_code(emit(ROT, platform), platform)
    assert ir2.signals[0].kind == "momentum_rotation"
    assert ir2.universe == ETF_ROTATION_UNIVERSE
    assert ir2.signals[0].params == ROT.signals[0].params
    assert ir2.order.pct == ROT.order.pct
    assert _semantic(ir2) == _semantic(ROT)


# ---- 桩运行时 + 一致率 ----

def test_rotation_sim_all_platforms_trade():
    bm, refb = _bars_map()
    for p in PLATFORMS:
        r = run_code(emit(ROT, p), p, refb, bars_map=bm)
        assert r.error == "", f"{p}: {r.error}"
        assert r.multi is True
        assert len(r.daily_held) == len(refb)
        assert len(r.orders) > 0, f"{p} 应有轮动交易"
        # 轮动应真的发生：持有集合随时间变化（不止一个状态）
        assert len({tuple(h) for h in r.daily_held}) > 1, \
            f"{p} 持有集合从未变化，未真正轮动"


def test_rotation_sim_single_month_timeline_shared():
    """窗口来自同一时间轴（state.i），历史窗口长度充足，top_n=1 持仓不超 1 只。"""
    bm, refb = _bars_map()
    r = run_code(emit(ROT, "joinquant"), "joinquant", refb, bars_map=bm)
    assert len(r.daily_held) == len(refb)
    assert len(r.orders) > 0
    # 每日持有集合都应为 0 或 1 只（top_n=1）
    assert all(len(h) <= 1 for h in r.daily_held)


@pytest.mark.parametrize("src,dst",
                         [("joinquant", "ptrade"), ("ptrade", "joinquant"),
                          ("joinquant", "gm"), ("gm", "qmt"),
                          ("qmt", "joinquant"), ("ptrade", "qmt")])
def test_rotation_consistency_pairs(src, dst):
    r = run_one(ROT, src, dst, BARS)
    assert r["valid"], f"{src}→{dst} 校验失败: {r['errors']}"
    assert not r["error"], f"{src}→{dst} 模拟错误: {r['error']}"
    assert r["rate"] >= 0.9, f"{src}→{dst} 一致率 {r['rate']:.1%}"


def test_rotation_full_matrix_all_pass():
    for src in PLATFORMS:
        for dst in PLATFORMS:
            if src == dst:
                continue
            r = run_one(ROT, src, dst, BARS)
            assert r["valid"] and not r["error"] and r["rate"] >= 0.9, \
                f"{src}→{dst}: {r.get('error') or r['errors']} rate={r['rate']:.1%}"


# ---- 白名单 ----

def test_rotation_passes_whitelist_all_platforms():
    for p in PLATFORMS:
        v = validate(emit(ROT, p), p)
        assert v.ok, f"{p}: {v.errors}"


# ---- 主流程互转（translate / roundtrip）----

def test_rotation_translate_jq_to_qmt():
    src_code = emit(ROT, "joinquant")
    t = translate(src_code, "joinquant", "qmt")
    assert t["validation"].ok
    assert t["ir"].signals[0].kind == "momentum_rotation"
    assert "handlebar(C)" in t["code"]
    assert "passorder" in t["code"]           # QMT 下单助手（人工确认注释）


def test_rotation_roundtrip_jq_ptrade():
    code = emit(ROT, "joinquant")
    rt = roundtrip(code, "joinquant", "ptrade")
    assert rt["validation"].ok
    assert _semantic(rt["ir_src"]) == _semantic(rt["ir_back"])
