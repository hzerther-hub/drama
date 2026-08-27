# -*- coding: utf-8 -*-
"""quant v1.5：gm/qmt 平台适配 + 标的转换 + 四平台互转矩阵测试。"""

import pytest

from products.quant import symbols
from products.quant.benchmark import BENCHMARKS, PLATFORMS, run_one
from products.quant.data import load_bars
from products.quant.emitters import emit
from products.quant.parsers import parse_code
from products.quant.sim import run_code
from products.quant.validate import validate

BARS = load_bars("")


# ---- 标的代码转换 ----

@pytest.mark.parametrize("src,canon", [
    ("000001.XSHE", "000001.XSHE"),      # 聚宽原样
    ("SZSE.000001", "000001.XSHE"),      # 掘金
    ("SHSE.600519", "600519.XSHG"),
    ("000001.SZ", "000001.XSHE"),        # QMT
    ("600519.SH", "600519.XSHG"),
])
def test_to_canonical(src, canon):
    assert symbols.to_canonical(src) == canon


@pytest.mark.parametrize("canon,platform,out", [
    ("000001.XSHE", "gm", "SZSE.000001"),
    ("600519.XSHG", "gm", "SHSE.600519"),
    ("000001.XSHE", "qmt", "000001.SZ"),
    ("600519.XSHG", "qmt", "600519.SH"),
    ("000001.XSHE", "joinquant", "000001.XSHE"),   # 原样
    ("000001.XSHE", "ptrade", "000001.XSHE"),
])
def test_from_canonical(canon, platform, out):
    assert symbols.from_canonical(canon, platform) == out


# ---- 新平台发射：结构特征 ----

def test_emit_gm_structure():
    code = emit(BENCHMARKS[0], "gm")
    assert "def init(context):" in code
    assert "schedule(schedule_func=algo, date_rule='1d', time_rule='09:31:00')" in code
    assert "history_n(context.stock, '1d', 21" in code
    assert "SZSE.000001" in code              # 标的格式已转换


def test_emit_qmt_structure():
    code = emit(BENCHMARKS[0], "qmt")
    assert "def init(C):" in code
    assert "def handlebar(C):" in code
    assert "C.get_market_data_ex(['close'], [C.stock]" in code
    assert "000001.SZ" in code
    assert "passorder" in code                # 人工确认提示注释


def test_emit_all_platforms_pass_whitelist():
    for ir in BENCHMARKS:
        for p in PLATFORMS:
            assert validate(emit(ir, p), p).ok, f"{ir.name}@{p}"


# ---- 新平台解析往返 ----

@pytest.mark.parametrize("platform", PLATFORMS)
def test_all_benchmarks_roundtrip_4platforms(platform):
    for ir in BENCHMARKS:
        ir2 = parse_code(emit(ir, platform), platform)
        # 语义字段比对（name/condition/source_platform 是展示性字段）
        assert ir2.universe == ir.universe
        assert ir2.schedule.time == ir.schedule.time
        assert ir2.signals[0].kind == ir.signals[0].kind
        assert ir2.signals[0].params == ir.signals[0].params
        assert ir2.order.pct == ir.order.pct


# ---- 桩运行时：gm/qmt ----

def test_sim_gm_and_qmt_trade():
    for p in ("gm", "qmt"):
        r = run_code(emit(BENCHMARKS[0], p), p, BARS)
        assert r.error == ""
        assert len(r.daily_pct) == len(BARS)
        assert len(r.orders) > 0, f"{p} 应有交易"


# ---- 四平台全矩阵（PLAN v1.5 验收）----

def test_full_matrix_all_pass():
    for ir in BENCHMARKS:
        for src in PLATFORMS:
            for dst in PLATFORMS:
                if src == dst:
                    continue
                r = run_one(ir, src, dst, BARS)
                assert r["valid"], f"{ir.name} {src}→{dst}: {r['errors']}"
                assert not r["error"], f"{ir.name} {src}→{dst}: {r['error']}"
                assert r["rate"] >= 0.9, \
                    f"{ir.name} {src}→{dst} 一致率 {r['rate']:.1%}"

# ---- passorder 解析（QMT 真实下单码） ----

def test_parse_qmt_passorder_pct():
    code = emit(BENCHMARKS[4], "qmt")   # 网格 pct=0.30
    ir = parse_code(code, "qmt")
    assert ir.order.pct == 0.30
    assert "_buy(C, C.stock, 0.3)" in code
    assert "C.account = ''" in code     # 资金账号留空待填


# ---- 官方文档镜像：片段检索 ----

def test_kb_snippet_truncates_large_doc():
    from products.quant import kb
    sep = "\n\n"
    big = sep.join(f"第{i}段 " + "字" * 500 for i in range(50))
    big += sep + "get_market_data_ex 获取行情数据 第二版"
    out = kb._snippet(big, {"get_market_data_ex"})
    assert len(out) <= kb._SNIPPET_MAX + 600
    assert "get_market_data_ex" in out


def test_kb_mirrored_docs_retrievable():
    from products.quant import kb
    hits = kb.retrieve("passorder 综合交易下单", k=1, kind="kb",
                       snippet=True)
    assert hits and "passorder" in hits[0]["text"]
    assert len(hits[0]["text"]) <= kb._SNIPPET_MAX + 600


def test_build_messages_includes_kb_snippet():
    from products.quant.llm_parse import build_messages
    msgs = build_messages("passorder 下单 get_market_data_ex", "qmt")
    assert "官方 API 文档（检索片段）" in msgs[1]["content"]
