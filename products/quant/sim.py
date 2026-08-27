# -*- coding: utf-8 -*-
"""桩运行时模拟器：把发射出的平台代码在 mocked API 上真实 exec 运行。

支持 4 平台（joinquant/ptrade/gm/qmt）生成的策略代码：
同一份行情、同一语义的 API 桩，逐日比对目标仓位信号。

一致率口径（按策略类型自动选择）：
  - 单标的（daily_pct）：逐日目标仓位序列相等的天数 / 总天数
  - 多标的动量轮动（daily_held）：逐日持有证券集合相等的天数 / 总天数

为什么不用 backtrader：互转校验要验证的是「生成的平台代码」本身。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

from .symbols import to_canonical


class _Vec:
    """最小 numpy 数组替身：切片 / 下标 / 迭代 / .mean()（模板只用到这些）。"""

    def __init__(self, data):
        self.data = list(data)

    def __getitem__(self, k):
        r = self.data[k]
        return _Vec(r) if isinstance(k, slice) else r

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def mean(self):
        return sum(self.data) / len(self.data) if self.data else float("nan")


@dataclass
class SimResult:
    platform: str
    orders: list = field(default_factory=list)          # (date, pct, symbol)
    daily_pct: list = field(default_factory=list)       # 逐日目标仓位（单标的）
    daily_held: list = field(default_factory=list)      # 逐日持有证券集合（轮动）
    multi: bool = False                                 # True=多标的（轮动）
    error: str = ""


def run_code(code: str, platform: str, bars: list[dict],
             bars_map: dict[str, list[dict]] | None = None) -> SimResult:
    """在桩运行时里执行策略代码，回放 bars。

    bars：对齐时间轴的参考日线（其 date 序列作为交易日）。
    bars_map：{规范标的代码: bars}，动量轮动逐标的使用；单标的传 None 即可。
    流程与真实平台一致：exec 代码 → 入口函数注册调度 → 逐根 K 线驱动。
    """
    closes = [float(b["close"]) for b in bars]
    dates = [str(b["date"]) for b in bars]
    result = SimResult(platform=platform, multi=bars_map is not None)
    state = {"i": 0}
    trade_funcs: list = []
    current_pct = {"v": 0.0}
    current_holdings: set = set()

    def _closes_for(sym: str | None) -> list:
        canon = to_canonical(sym) if sym else None
        if bars_map:
            if canon in bars_map:
                return [float(b["close"]) for b in bars_map[canon]]
            # 多标的缺少某标的行情 → 明确报错（不许用单一序列冒充）
            raise RuntimeError(f"缺少 {canon} 的行情数据（bars_map）")
        return closes                                   # 单标的回退：全局序列

    def _window(count, sym: str | None = None) -> list:
        i = state["i"]
        series = _closes_for(sym)
        lo = max(0, i - int(count) + 1)
        return series[lo:i + 1]

    def _record_order(sym, pct: float) -> None:
        canon = to_canonical(sym)                    # 持有集合用规范形，跨平台可比
        p = float(pct)
        if p > 0:
            current_holdings.add(canon)
        else:
            current_holdings.discard(canon)
        result.orders.append((dates[state["i"]], p, sym))
        current_pct["v"] = p

    def order_target_percent(_stock, pct):
        _record_order(_stock, pct)

    # ---- 聚宽 / PTrade 桩 ----
    def run_daily(*args, **_kw):
        func = args[0] if args and callable(args[0]) else args[1]
        trade_funcs.append(func)

    def _hist(count, security_list=None, **_kw):
        syms = security_list or ["_"]
        if len(syms) > 1:
            result.multi = True
        return {s: SimpleNamespace(values=_Vec(_window(count, s)))
                for s in syms}

    # ---- 掘金 gm 桩 ----
    def schedule(schedule_func=None, **_kw):
        if callable(schedule_func):
            trade_funcs.append(schedule_func)

    def history_n(_symbol, _freq, count, fields="close", **_kw):
        return {"close": _Vec(_window(count, _symbol))}          # DataFrame 替身

    # ---- QMT 桩：C.get_market_data_ex ----
    ctx = SimpleNamespace()

    def get_market_data_ex(_fields, stock_codes, period="1d", count=1, **_kw):
        if len(stock_codes) > 1:
            result.multi = True
        return {s: {"close": _Vec(_window(count, s))} for s in stock_codes}

    ctx.get_market_data_ex = get_market_data_ex

    def passorder(op, _otype, _account, _code, _prtype, _price,
                  volume, *_args):
        if op == 23:
            _record_order(_code, float(volume))
        elif op == 24:
            _record_order(_code, 0.0)

    sandbox = {
        "run_daily": run_daily, "history": _hist, "get_history": _hist,
        "schedule": schedule, "history_n": history_n,
        "order_target_percent": order_target_percent,
        "passorder": passorder,
        "math": __import__("math"),                     # 轮动打分用（纯 Python）
    }
    try:
        exec(compile(code, "<strategy>", "exec"), sandbox)  # noqa: S102
        entry = sandbox.get("initialize") or sandbox.get("init")
        if entry is None:
            raise RuntimeError("缺少 initialize/init 入口函数")
        entry(ctx)
        bar_fn = sandbox.get("handlebar")              # QMT bar 驱动
        if bar_fn is not None:
            trade_funcs.append(bar_fn)
        for i in range(len(bars)):
            state["i"] = i
            for f in trade_funcs:
                f(ctx)
            result.daily_pct.append(current_pct["v"])
            result.daily_held.append(frozenset(current_holdings))
    except Exception as e:  # noqa: BLE001 —— 模拟器要吞异常并上报
        result.error = f"{type(e).__name__}: {e}"
    return result


def consistency(a: SimResult, b: SimResult) -> dict:
    """比对两次模拟的信号序列，返回一致率与明细。

    多标的（轮动）比逐日持有集合；单标的比逐日目标仓位。
    """
    if a.error or b.error:
        return {"rate": 0.0, "days": 0, "mismatch": -1,
                "error": a.error or b.error}
    if a.multi or b.multi:
        seq_a, seq_b = list(a.daily_held), list(b.daily_held)
    else:
        seq_a, seq_b = list(a.daily_pct), list(b.daily_pct)
    n = min(len(seq_a), len(seq_b))
    if n == 0:
        return {"rate": 0.0, "days": 0, "mismatch": -1, "error": "无交易日"}
    mismatch = sum(1 for i in range(n)
                   if seq_a[i] != seq_b[i])
    return {"rate": (n - mismatch) / n, "days": n, "mismatch": mismatch,
            "error": ""}
