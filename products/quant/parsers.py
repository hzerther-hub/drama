# -*- coding: utf-8 -*-
"""解析器：平台策略代码 → StrategyIR。

确定性 AST 解析，覆盖发射器在 4 平台（joinquant/ptrade/gm/qmt）
生成的 5 种基准信号。任意手写策略走 LLM 兜底（llm_parse.py）。

平台差异处理：
  - 入口函数：initialize（聚宽/PTrade）/ init（掘金/QMT）
  - 上下文变量名：取入口函数第一个形参（context / C / 任意名）
  - 调度：run_daily(time=..) / schedule(time_rule=..) / handlebar（bar 驱动）
  - 标的代码：统一转聚宽规范形（symbols.to_canonical）
  - 时间：各平台时间串归一化为 IR 规范时间（open/close/HH:MM）

kind 识别靠入口函数的属性签名（与 emitters._INIT_ATTRS 互逆）。
"""

from __future__ import annotations

import ast

from .ir import OrderSpec, Schedule, Signal, StrategyIR
from .symbols import to_canonical

# 平台时间串 → IR 规范时间（emitters._TIME_OUT 的逆映射）
_TIME_IN = {
    "joinquant": lambda t: t,
    "ptrade": lambda t: {"09:30": "open", "14:55": "close"}.get(t, t),
    "gm": lambda t: {"09:31": "open", "14:56": "close"}.get(
        t[:5] if len(t) >= 5 else t, (t[:5] if len(t) >= 5 else t)),
    "qmt": lambda t: "open",                     # bar 驱动，归一为 open
}

_ENTRY_NAMES = ("initialize", "init")

# kind 识别签名：按优先级匹配入口函数中出现的上下文属性
_KIND_SIGNATURES = [
    ("grid", {"stock", "grid_step"},
     lambda a: {"step": a["grid_step"]}),
    ("rsi", {"stock", "rsi_period", "rsi_buy", "rsi_sell"},
     lambda a: {"period": a["rsi_period"], "buy_below": a["rsi_buy"],
                "sell_above": a["rsi_sell"]}),
    ("bollinger", {"stock", "boll_period", "boll_mult"},
     lambda a: {"period": a["boll_period"], "std_mult": a["boll_mult"]}),
    ("threshold", {"stock", "buy_below", "sell_above"},
     lambda a: {"buy_below": a["buy_below"], "sell_above": a["sell_above"]}),
    ("ma_cross", {"stock", "fast", "slow"},
     lambda a: {"fast": a["fast"], "slow": a["slow"], "price": "close"}),
]

_CONDITIONS = {
    "ma_cross": lambda p: f"MA{p['fast']} 上穿 MA{p['slow']} 买入，下穿卖出",
    "threshold": lambda p: f"价格 ≤ {p['buy_below']} 买入，≥ {p['sell_above']} 卖出",
    "rsi": lambda p: f"RSI{p['period']} ≤ {p['buy_below']} 买入，≥ {p['sell_above']} 卖出",
    "bollinger": lambda p: f"价格跌破布林下轨({p['period']},{p['std_mult']}σ) 买入，突破上轨卖出",
    "grid": lambda p: f"价格每跌 {p['step']:.1%} 买入一格，涨 {p['step']:.1%} 卖出一格",
    "momentum_rotation": lambda p: (
        f"{p['lookback']} 日加权动量×R² 打分，取 Top{p['top_n']} 等权持有，"
        f"近{p['drop_days']}日跌幅≥{1 - p['drop_threshold']:.0%} 归零"),
}

_NAMES = {
    "ma_cross": "双均线 MA Cross",
    "threshold": "价格阈值 Threshold",
    "rsi": "RSI 超买超卖",
    "bollinger": "布林带 Bollinger",
    "grid": "网格 Grid",
    "momentum_rotation": "多标的动量轮动",
}

_PLATFORMS = ("joinquant", "ptrade", "gm", "qmt")


class ParseError(ValueError):
    """代码结构超出确定性解析能力时抛出（应转 LLM 解析）。"""


def _const(node: ast.AST):
    """取字面量节点的值；取不到返回 None。"""
    return node.value if isinstance(node, ast.Constant) else None


def _list_const(node: ast.AST) -> list | None:
    """取列表字面量（元素均为标量字面量）；否则返回 None。"""
    if not isinstance(node, ast.List):
        return None
    out: list = []
    for e in node.elts:
        c = _const(e)
        if not isinstance(c, (str, int, float, bool)):
            return None
        out.append(c)
    return out


class _InitVisitor(ast.NodeVisitor):
    """扫入口函数：<ctx>.属性赋值 + 调度注册（run_daily / schedule）。"""

    def __init__(self, ctx_name: str) -> None:
        self.ctx = ctx_name
        self.attrs: dict[str, object] = {}
        self.sched_time: str | None = None

    def visit_Assign(self, node: ast.Assign) -> None:
        for t in node.targets:
            if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == self.ctx):
                v = _const(node.value)
                if v is None:
                    v = _list_const(node.value)
                if v is not None:
                    self.attrs[t.attr] = v
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        fname = node.func.id if isinstance(node.func, ast.Name) else ""
        time_kw = {"run_daily": "time", "schedule": "time_rule"}.get(fname)
        if time_kw:
            for kw in node.keywords:
                if kw.arg == time_kw:
                    v = _const(kw.value)
                    if isinstance(v, str):
                        self.sched_time = v
        self.generic_visit(node)


class _OrderVisitor(ast.NodeVisitor):
    """扫全文件：提取买入目标仓位。

    识别两种下单形态：
      - order_target_percent(stock, pct)   （聚宽/PTrade/掘金）
      - passorder(23, 1123, account, stock, 5, -1, pct, ...)  （QMT 买入，
        23=股票买入/1123=可用比例；passorder(24, ...)=卖出记 0）
    """

    def __init__(self) -> None:
        self.pcts: list[float] = []

    def visit_Call(self, node: ast.Call) -> None:
        fname = node.func.id if isinstance(node.func, ast.Name) else ""
        if fname == "order_target_percent" and len(node.args) >= 2:
            v = _const(node.args[1])
            if isinstance(v, (int, float)):
                self.pcts.append(float(v))
        elif fname == "passorder" and len(node.args) >= 7:
            op = _const(node.args[0])
            if op == 23:                       # 股票买入
                v = _const(node.args[6])
                if isinstance(v, (int, float)):
                    self.pcts.append(float(v))
            elif op == 24:                     # 股票卖出 → 目标仓位 0
                self.pcts.append(0.0)
        else:
            # _buy(C, stock, pct) / _sell(C, stock)（本工具 QMT 模板助手）
            if fname == "_buy" and len(node.args) >= 3:
                v = _const(node.args[2])
                if isinstance(v, (int, float)):
                    self.pcts.append(float(v))
            elif fname == "_sell":
                self.pcts.append(0.0)
        self.generic_visit(node)


def _detect(attrs: dict) -> tuple[str, dict]:
    keys = set(attrs)
    for kind, required, build in _KIND_SIGNATURES:
        if required <= keys:
            return kind, build(attrs)
    raise ParseError(
        "入口函数中的上下文属性组合不在 5 种基准信号签名内，"
        "超出确定性解析范围（此类策略将走 LLM 解析兜底）")


def parse_code(source: str, platform: str) -> StrategyIR:
    """把 4 平台策略源码解析为 IR。解析不了时抛 ParseError。"""
    if platform not in _PLATFORMS:
        raise ValueError(f"未知平台 {platform!r}，可选：{list(_PLATFORMS)}")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise ParseError(f"源码语法错误: {e}") from e

    entry = next(
        (n for n in tree.body
         if isinstance(n, ast.FunctionDef) and n.name in _ENTRY_NAMES), None)
    if entry is None:
        raise ParseError("缺少 initialize/init 入口函数，不符合平台策略结构")
    ctx_name = entry.args.args[0].arg if entry.args.args else "context"

    iv = _InitVisitor(ctx_name)
    iv.visit(entry)

    raw_time = iv.sched_time or ""
    time_canon = _TIME_IN[platform](raw_time) if raw_time else "open"

    universe = iv.attrs.get("universe")
    if isinstance(universe, list) and universe:
        return _rotation_ir(universe, iv.attrs, time_canon, platform)

    if not isinstance(iv.attrs.get("stock"), str):
        raise ParseError("入口函数中未找到标的代码字面量赋值（ctx.stock）")
    kind, params = _detect(iv.attrs)

    ov = _OrderVisitor()
    ov.visit(tree)
    buy_pcts = [p for p in ov.pcts if p > 0]
    if not buy_pcts:
        raise ParseError("未找到 order_target_percent 买入调用")

    return StrategyIR(
        name=_NAMES[kind],
        universe=[to_canonical(iv.attrs["stock"])],
        schedule=Schedule(freq="daily", time=time_canon),
        signals=[Signal(kind=kind, params=params,
                        condition=_CONDITIONS[kind](params))],
        order=OrderSpec(style="target_pct", pct=buy_pcts[0]),
        risk={"max_position_pct": buy_pcts[0]},
        source_platform=platform,
    )


_ROTATION_PARAM_KEYS = ("lookback", "top_n", "min_score", "max_score",
                        "drop_days", "drop_threshold")


def _rotation_ir(universe, attrs, time_canon, platform) -> StrategyIR:
    """由初始化属性构造动量轮动 IR（universe + 轮动参数 + 等权持仓）。"""
    params = {k: (attrs[k] if k in attrs else default)
              for k, default in {
                  "lookback": 25, "top_n": 1, "min_score": 0.0,
                  "max_score": 6.0, "drop_days": 3, "drop_threshold": 0.95,
              }.items()}
    params["r2_weight"] = attrs.get("r2_weight", True)
    top_n = int(params["top_n"])
    pct = 1.0 / top_n if top_n else 1.0
    return StrategyIR(
        name=_NAMES["momentum_rotation"],
        universe=[to_canonical(s) for s in universe],
        schedule=Schedule(freq="daily", time=time_canon),
        signals=[Signal(kind="momentum_rotation", params=params,
                        condition=_CONDITIONS["momentum_rotation"](params))],
        order=OrderSpec(style="target_pct", pct=pct),
        risk={"max_position_pct": 1.0},
        source_platform=platform,
    )
