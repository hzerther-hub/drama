# -*- coding: utf-8 -*-
"""多标的合成行情：给动量轮动基准/测试提供逐标的、可复现的日线 bars。

轮动策略需要每只标的自己的价格序列（排列不同，Top 才会轮换）。
真实行情源是单标的；这里用确定性伪随机生成，供 benchmark / sim 使用：
  - 每只标的有独立 drift + 噪声，排名会随时间变化
  - 注入若干次大跌（触发动量策略的跌幅保护），让 Top 交替
代价是"非真实"，但它只用于**互转一致性校验**（源/目标在同一份数据上都
跑同一套逻辑），不用于收益回测，故不影响正确性。
"""

from __future__ import annotations

import random

_FIELDS = ("date", "open", "high", "low", "close", "volume")


def _date(n: int) -> str:
    """从 2025-01-01 起逐日推进（周末不跳过，仅作对齐的时间轴）。"""
    month_days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    y, m, d = 2025, 1, 1
    for _ in range(n):
        d += 1
        if d > month_days[m - 1]:
            d = 1
            m += 1
            if m > 12:
                m = 1
                y += 1
    return f"{y:04d}-{m:02d}-{d:02d}"


def synthetic_bars(symbols: list[str], n: int = 200, seed: int = 42,
                   dip_bars: list[int] | None = None) -> dict[str, list[dict]]:
    """为每个 symbol 生成 n 根日线 bars。返回 {symbol: [bar, ...]}。

    每只标的：
      - 基准 drift 按其在 symbols 中的下标线性递增（0.0006 → 0.0046），
        下标越大趋势越强 → 排名会随下标变化
      - 在 dip_bars（默认 [n*3//5]）处给"趋势第 2 强"的标的注入 -8% 大跌，
        使其触发跌幅保护暂时退出 Top → 轮出/轮入发生
    """
    if dip_bars is None:
        dip_bars = [n * 3 // 5]
    symbols = list(symbols)
    out: dict[str, list[dict]] = {}
    for idx, sym in enumerate(symbols):
        drift = 0.0006 + idx * 0.0005 / max(1, len(symbols) - 1) * 0.9
        drift = max(0.0004, min(0.0035, drift))
        rng = random.Random(seed * 1009 + idx * 7919)
        # 趋势第二强的那只会被注入大跌（触发跌幅保护），制造轮动
        dip_target = 1 if len(symbols) > 1 else 0
        price = 8.0 + idx * 3.0
        bars: list[dict] = []
        for i in range(n):
            noise = (rng.random() - 0.5) * 0.018
            ret = drift + noise
            if idx == dip_target and i in dip_bars:
                ret = -0.08
            price = max(0.6, price * (1.0 + ret))
            c = round(price, 3)
            o = round(price * (1.0 + (rng.random() - 0.5) * 0.008), 3)
            h = round(max(o, c) * 1.004, 3)
            l = round(min(o, c) * 0.996, 3)
            bars.append({
                "date": _date(i), "open": o, "high": h, "low": l,
                "close": c, "volume": round(1e6 * (1.0 + rng.random()), 2),
            })
        out[sym] = bars

    # 各标的 bars 对齐到同一时间轴（date 一致由 _date 生成保证）
    return out
