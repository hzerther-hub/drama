#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基准：基准策略 × 4 平台互转矩阵的信号一致率报告。

运行：python -m products.quant.benchmark [csv路径]

每个基准策略 × 每个有序平台对（4×3=12 方向）：
    IR → 发射源平台代码 → AST 解析回 IR → 发射目标平台代码
    两份代码在桩运行时跑同一份行情 → 逐日目标仓位（或持有集合）一致率

前 5 个为单标的（用自带样本行情 CSV）；第 6 个「全球宽基ETF轮动」为
多标的动量轮动，用确定性的多标的合成行情（跨平台同份数据，仍验证一致性）。

验收口径：互转信号一致率 ≥ 90%。
确定性发射/解析下应为 100%；低于 100% 即说明模板或解析有语义漂移。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from products.quant.data import load_bars                     # noqa: E402
from products.quant.data import synthetic_bars                # noqa: E402
from products.quant.emitters import emit                      # noqa: E402
from products.quant.ir import (OrderSpec, Schedule, Signal,   # noqa: E402
                               StrategyIR, demo_etf_rotation)
from products.quant.parsers import parse_code                 # noqa: E402
from products.quant.sim import consistency, run_code          # noqa: E402
from products.quant.validate import validate                  # noqa: E402

STOCK = "000001.XSHE"
PLATFORMS = ("joinquant", "ptrade", "gm", "qmt")


def _ir(name: str, kind: str, params: dict, pct: float = 0.95,
        condition: str = "") -> StrategyIR:
    return StrategyIR(
        name=name, universe=[STOCK],
        schedule=Schedule(freq="daily", time="open"),
        signals=[Signal(kind=kind, params=params, condition=condition)],
        order=OrderSpec(style="target_pct", pct=pct),
        risk={"max_position_pct": pct}, source_platform="benchmark",
    )


# 6 个基准策略（参数按自带样本行情调校，保证有交易发生）。
# 前 5 个为单标的；第 6 个「全球宽基ETF轮动」为多标的动量轮动（用合成行情）。
BENCHMARKS = [
    _ir("双均线 MA5/20", "ma_cross", {"fast": 5, "slow": 20, "price": "close"}),
    _ir("阈值 9/12", "threshold", {"buy_below": 9.0, "sell_above": 12.0}),
    _ir("RSI14 30/70", "rsi", {"period": 14, "buy_below": 30, "sell_above": 70}),
    _ir("布林 20/2σ", "bollinger", {"period": 20, "std_mult": 2.0}),
    _ir("网格 5%", "grid", {"step": 0.05}, pct=0.30),
    demo_etf_rotation(),
]


def run_one(ir: StrategyIR, src: str, dst: str, bars: list[dict],
            bars_map: dict[str, list[dict]] | None = None) -> dict:
    """单策略单方向：src 发射 → 解析 → dst 发射 → 双跑 → 一致率。

    多标的（动量轮动）在 bars_map 缺失时自动生成确定性的多标的合成行情。
    """
    src_code = emit(ir, src)
    ir2 = parse_code(src_code, src)                    # 代码 → IR
    dst_code = emit(ir2, dst)
    v = validate(dst_code, dst)
    if bars_map is None and len(ir.universe) > 1:
        bars_map = synthetic_bars(ir.universe)
        bars = bars_map[ir.universe[0]]
    ra = run_code(src_code, src, bars, bars_map=bars_map)
    rb = run_code(dst_code, dst, bars, bars_map=bars_map)
    c = consistency(ra, rb)
    return {"src_code": src_code, "dst_code": dst_code, "ir": ir2,
            "valid": v.ok, "errors": v.errors, **c}


def matrix(bars: list[dict]) -> dict:
    """全矩阵：{(strategy, src, dst): run_one 结果}。"""
    out = {}
    for ir in BENCHMARKS:
        for src in PLATFORMS:
            for dst in PLATFORMS:
                if src != dst:
                    out[(ir.name, src, dst)] = run_one(ir, src, dst, bars)
    return out


def main() -> int:
    bars = load_bars(sys.argv[1] if len(sys.argv) > 1 else "")
    print(f"行情：{len(bars)} 根日线 "
          f"（{bars[0]['date']} → {bars[-1]['date']}）")
    print(f"矩阵：{len(BENCHMARKS)} 策略 × "
          f"{len(PLATFORMS) * (len(PLATFORMS) - 1)} 方向\n")

    results = matrix(bars)
    # 每策略一行：最差方向
    print(f"{'策略':<14} {'最差方向':<26} {'一致率':>7}")
    print("-" * 52)
    all_ok = True
    for ir in BENCHMARKS:
        worst_key, worst = min(
            ((k, r) for k, r in results.items() if k[0] == ir.name),
            key=lambda kv: kv[1]["rate"])
        ok = worst["valid"] and not worst["error"] and worst["rate"] >= 0.9
        all_ok &= ok
        pair = f"{worst_key[1]} → {worst_key[2]}"
        print(f"{ir.name:<14} {pair:<26} {worst['rate']:>6.1%}  "
              + ("✅" if ok else f"❌ {worst['error'] or worst['errors']}"))

    # 平台对汇总（跨策略平均）
    print("\n平台对（5 策略平均一致率）：")
    print("-" * 52)
    for src in PLATFORMS:
        row = []
        for dst in PLATFORMS:
            if src == dst:
                row.append("   —   ")
            else:
                rates = [results[(b.name, src, dst)]["rate"]
                         for b in BENCHMARKS]
                row.append(f"{sum(rates) / len(rates):>6.1%}")
        print(f"{src:<10} → " + "  ".join(row))
    print(f"\n{'':<10}    " + "      ".join(PLATFORMS))

    print("-" * 52)
    print("结论:", "✅ 全部通过（一致率 ≥ 90%）" if all_ok else "❌ 存在不达标项")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
