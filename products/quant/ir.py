# -*- coding: utf-8 -*-
"""策略中间表示（Strategy IR）——策略互转的核心。

铁律：互转走 IR，不做平台 N×N 直译。
    源平台代码 → LLM 解析 → StrategyIR（本文件定义）
              → 模板发射 → 目标平台代码
              → 校验（语法 + API 白名单 + backtrader 信号一致率）

v0.1 范围：聚宽 JoinQuant ↔ PTrade（API 近乎同源），双均线策略双向 demo。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json


@dataclass
class Schedule:
    """触发节奏：daily / minute / tick。"""
    freq: str = "daily"               # daily | minute | tick
    time: str = ""                    # daily 时的触发时刻，如 "09:35" / "open"


@dataclass
class Signal:
    """一个信号：指标 + 参数 + 条件。kind 如 ma_cross / grid / threshold。"""
    kind: str
    params: dict = field(default_factory=dict)
    condition: str = ""               # 人类可读条件描述，如 "fast crosses above slow"


@dataclass
class OrderSpec:
    """下单语义：市价/限价/目标仓位。"""
    style: str = "market"             # market | limit | target_value | target_pct
    pct: float = 0.0                  # target_pct 时的仓位比例（0-1）


@dataclass
class StrategyIR:
    """平台无关的策略语义。"""
    name: str = ""
    universe: list[str] = field(default_factory=list)   # 标的代码列表
    schedule: Schedule = field(default_factory=Schedule)
    signals: list[Signal] = field(default_factory=list)
    order: OrderSpec = field(default_factory=OrderSpec)
    risk: dict = field(default_factory=dict)            # 止损止盈/仓位约束
    source_platform: str = ""                           # 解析来源（jqdatasdk 风格标记）

    # ---- 序列化 ----
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @staticmethod
    def from_json(s: str) -> "StrategyIR":
        d = json.loads(s)
        ir = StrategyIR(
            name=d.get("name", ""),
            universe=list(d.get("universe", [])),
            schedule=Schedule(**d.get("schedule", {})),
            signals=[Signal(**x) for x in d.get("signals", [])],
            order=OrderSpec(**d.get("order", {})),
            risk=dict(d.get("risk", {})),
            source_platform=d.get("source_platform", ""),
        )
        return ir


# ---- v0.1 demo：双均线策略 IR（聚宽/PTrade 互转用） ----
def demo_ma_cross(symbol: str = "000001.XSHE",
                  fast: int = 5, slow: int = 20) -> StrategyIR:
    return StrategyIR(
        name="双均线 MA Cross",
        universe=[symbol],
        schedule=Schedule(freq="daily", time="open"),
        signals=[
            Signal(kind="ma_cross",
                   params={"fast": fast, "slow": slow, "price": "close"},
                   condition=f"MA{fast} 上穿 MA{slow} 买入，下穿卖出"),
        ],
        order=OrderSpec(style="target_pct", pct=0.95),
        risk={"max_position_pct": 0.95},
        source_platform="demo",
    )


# 19 只宽基/行业 ETF（聚宽规范形代码，来自用户提供的聚宽轮动策略）。
# IR 内部统一聚宽规范形；发射到掘金/QMT 时按 symbols.py 自动转换。
ETF_ROTATION_UNIVERSE = [
    "513100.XSHG", "513500.XSHG", "159509.XSHE", "513520.XSHG", "513030.XSHG",
    "518880.XSHG", "159980.XSHE", "159985.XSHE", "159981.XSHE", "501018.XSHG",
    "511090.XSHG", "511360.XSHG", "513130.XSHG", "513690.XSHG", "510180.XSHG",
    "159922.XSHE", "159531.XSHE", "159915.XSHE", "588080.XSHG",
]


def demo_etf_rotation() -> StrategyIR:
    """多标的动量轮动 demo（全球宽基 ETF 轮动核心，可四平台互转）。

    语义：每交易日开盘，对 universe 每只 ETF 取近 lookback+1 根日线收盘，
    纯 Python 加权对数回归（权重 1→2 线性）算年化动量 slope 与 R²，
    分数 = 年化收益 × R²；近 drop_days 日任一日跌幅超阈值者分数置 0。
    取 min_score < score < max_score 者按分数降序（同分按代码升序），
    选前 top_n 等权持有，其余清仓。
    """
    return StrategyIR(
        name="全球宽基ETF轮动",
        universe=list(ETF_ROTATION_UNIVERSE),
        schedule=Schedule(freq="daily", time="open"),
        signals=[
            Signal(kind="momentum_rotation",
                   params={"lookback": 25, "top_n": 1, "min_score": 0.0,
                           "max_score": 6.0, "drop_days": 3,
                           "drop_threshold": 0.95, "r2_weight": True},
                   condition="25 日加权动量×R² 打分后持有 Top1，近3日大跌归零"),
        ],
        order=OrderSpec(style="target_pct", pct=1.0),
        risk={"max_position_pct": 1.0},
        source_platform="demo",
    )


# LLM 解析 prompt 用的已知信号说明（与 emitters._BODIES 同步维护）。
# 清单之外的 kind 也能解析进 IR，但发射阶段会被拒绝（v0.5 只发射这 5 种）。
KNOWN_KINDS_HINT = """已知信号 kind（优先用这些；都不匹配时可用自定义 kind，但会无法自动发射）：
- ma_cross  双均线交叉，params: {fast, slow, price}
- threshold 价格阈值，params: {buy_below, sell_above}
- rsi       RSI 超买超卖，params: {period, buy_below, sell_above}
- bollinger 布林带，params: {period, std_mult}
- grid      网格，params: {step}（价格变动比例）
- momentum_rotation  多标的动量轮动，params:
  {lookback, top_n, min_score, max_score, drop_days, drop_threshold, r2_weight}
  （universe 为多标的列表；近 drop_days 日跌幅超阈值者分数归零，
   按 加权对数回归动量×R² 打分后取 top_n 等权持仓）"""
