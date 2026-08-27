# -*- coding: utf-8 -*-
"""模板发射器：StrategyIR → 目标平台代码（确定性，不经过 LLM）。

支持 4 平台：joinquant（聚宽）/ ptrade / gm（掘金）/ qmt（miniQMT xtquant）。
支持 5 种基准信号（单标的、单信号）：
    ma_cross   双均线交叉      params: fast, slow
    threshold  价格阈值        params: buy_below, sell_above
    rsi        RSI 超买超卖    params: period, buy_below, sell_above
    bollinger  布林带          params: period, std_mult
    grid       网格            params: step（价格变动比例，如 0.05）

铁律：LLM 只负责「代码 → IR」的解析兜底；「IR → 代码」必须走这里的确定性模板。
平台差异收敛为四项：入口/上下文变量名、调度注册、K 线获取、时间映射；
信号逻辑四平台同构（用统一的 _mean 辅助函数，不依赖 numpy 语义）。

映射依据：api_maps/*.md（改映射先改对照表；不确定处对照表里标 TBD）。
"""

from __future__ import annotations

from .ir import StrategyIR
from .symbols import from_canonical

# ---- 时间映射：IR 规范时间 → 平台时间串 ----
_TIME_OUT = {
    "joinquant": lambda t: t or "open",          # 聚宽原生接受 open/close/HH:MM
    "ptrade": lambda t: {"open": "09:30", "close": "14:55"}.get(t, t or "09:30"),
    "gm": lambda t: {"open": "09:31", "close": "14:56"}.get(t, t or "09:31"),
    "qmt": lambda t: "",                          # bar 驱动，无定时概念
}

# ---- 平台规格 ----
# fetch 片段约束：产出名为 close 的序列（纯 Python 操作，_mean 辅助）。
# {BUY}/{SELL} 下单片段：jq/ptrade/gm 用原生 order_target_percent；
# qmt 用 passorder（官方文档已核实：opType 23/24 股票买卖，
# orderType 1123 单股单账号可用比例[0~1]，prType 5 最新价）。
_PLATFORMS = {
    "joinquant": {
        "ctx": "context", "init": "initialize", "trade_fn": "trade",
        "schedule": "    run_daily(trade, time={time!r})",
        "fetch": ("    hist = history({count}, unit='1d', field='close', "
                  "security_list=[context.stock])\n"
                  "    close = hist[context.stock].values"),
        "buy": "order_target_percent(context.stock, {pct})",
        "sell": "order_target_percent(context.stock, 0.0)",
    },
    "ptrade": {
        "ctx": "context", "init": "initialize", "trade_fn": "trade",
        "schedule": "    run_daily(context, trade, time={time!r})",
        "fetch": ("    hist = get_history({count}, frequency='1d', field='close', "
                  "security_list=[context.stock])\n"
                  "    close = hist[context.stock].values"),
        "buy": "order_target_percent(context.stock, {pct})",
        "sell": "order_target_percent(context.stock, 0.0)",
    },
    "gm": {
        "ctx": "context", "init": "init", "trade_fn": "algo",
        "schedule": ("    schedule(schedule_func=algo, date_rule='1d', "
                     "time_rule='{time}:00')"),
        "fetch": ("    close = list(history_n(context.stock, '1d', {count}, "
                  "fields='close')['close'])"),
        "buy": "order_target_percent(context.stock, {pct})",
        "sell": "order_target_percent(context.stock, 0.0)",
    },
    "qmt": {
        "ctx": "C", "init": "init", "trade_fn": "handlebar",
        "schedule": None,                          # handlebar(C) bar 驱动
        "fetch": ("    data = C.get_market_data_ex(['close'], [C.stock], "
                  "period='1d', count={count})\n"
                  "    close = list(data[C.stock]['close'])"),
        "buy": "_buy(C, C.stock, {pct})",
        "sell": "_sell(C, C.stock)",
        "init_extra": ("    C.account = ''  # TODO: 填资金账号"
                       "（合规红线：下单强制人工确认）"),
        "helpers": """

def _buy(C, stock, pct):
    # passorder(23=股票买入, 1123=单股单账号可用资金比例[0~1], 5=最新价)
    # ——参数含义见官方文档（kb/qmt_api.md 已镜像）
    passorder(23, 1123, C.account, stock, 5, -1, pct, '', 1, '', C)


def _sell(C, stock):
    # passorder(24=股票卖出)；按可用持仓比例 1.0 清仓
    passorder(24, 1123, C.account, stock, 5, -1, 1.0, '', 1, '', C)
""",
    },
}

# 各信号的 initialize 属性（attr 名, IR params 键）——与 parsers 签名互逆
_INIT_ATTRS = {
    "ma_cross":  [("stock", "universe0"), ("fast", "fast"), ("slow", "slow")],
    "threshold": [("stock", "universe0"), ("buy_below", "buy_below"),
                  ("sell_above", "sell_above")],
    "rsi":       [("stock", "universe0"), ("rsi_period", "period"),
                  ("rsi_buy", "buy_below"), ("rsi_sell", "sell_above")],
    "bollinger": [("stock", "universe0"), ("boll_period", "period"),
                  ("boll_mult", "std_mult")],
    "grid":      [("stock", "universe0"), ("grid_step", "step")],
}

# 动量轮动：各平台「多标的 K 线获取」片段，产出 closes_by_sym：{symbol: [close...]}。
# {ctx} = 上下文变量名。统一用纯 Python _momentum_score（不依赖 numpy，四平台同构）。
_ROTATION_FETCH = {
    "joinquant": ("    data = history({ctx}.lookback + 1, unit='1d', "
                  "field='close', security_list={ctx}.universe)\n"
                  "    closes_by_sym = {sym: list(data[sym].values) "
                  "for sym in {ctx}.universe}"),
    "ptrade": ("    data = get_history({ctx}.lookback + 1, frequency='1d', "
               "field='close', security_list={ctx}.universe)\n"
               "    closes_by_sym = {sym: list(data[sym].values) "
               "for sym in {ctx}.universe}"),
    "gm": ("    closes_by_sym = {}\n"
           "    for sym in {ctx}.universe:\n"
           "        df = history_n(sym, '1d', {ctx}.lookback + 1, fields='close')\n"
           "        closes_by_sym[sym] = list(df['close'])"),
    "qmt": ("    data = {ctx}.get_market_data_ex(['close'], {ctx}.universe, "
            "period='1d', count={ctx}.lookback + 1)\n"
            "    closes_by_sym = {sym: list(data[sym]['close']) "
            "for sym in {ctx}.universe}"),
}

# 动量轮动：买入/卖出片段（无前导缩进，缩进由 body 模板的 {BUY}/{SELL} 承载）。
# sym 为循环变量；pct 用 1.0 / top_n 等权。qmt 走 _buy/_sell 助手（见上 helpers）。
_ROTATION_ORDER = {
    "joinquant": ("order_target_percent(sym, 1.0 / {ctx}.top_n)",
                  "order_target_percent(sym, 0.0)"),
    "ptrade":    ("order_target_percent(sym, 1.0 / {ctx}.top_n)",
                  "order_target_percent(sym, 0.0)"),
    "gm":        ("order_target_percent(sym, 1.0 / {ctx}.top_n)",
                  "order_target_percent(sym, 0.0)"),
    "qmt":       ("_buy({ctx}, sym, 1.0 / {ctx}.top_n)",
                  "_sell({ctx}, sym)"),
}

# 纯 Python 动量评分：加权(1→2 线性)对数回归斜率 → 年化收益 × R²。
# 近 drop_days 日任一日收盘比 < drop_threshold（跌幅超阈值）→ 分数 0。
# 平台无关（仅用 math 与 list），保证四平台同份行情打分一致。
_ROTATION_HELPERS = """\

import math


def _momentum_score(closes, drop_days, drop_threshold, r2_weight):
    n = len(closes)
    if n < 2:
        return 0.0
    # 跌幅保护：近 drop_days 日任一日暴跌（波动放大风险）→ 归零
    for k in range(max(1, n - drop_days), n):
        if closes[k] <= 0.0 or closes[k - 1] <= 0.0:
            return 0.0
        if closes[k] / closes[k - 1] < drop_threshold:
            return 0.0
    xs = [float(i) for i in range(n)]
    ys = [math.log(c) for c in closes]
    w0, w1 = 1.0, 2.0                    # linspace(1,2,n) 权重
    wsum = sumwx = sumwy = 0.0
    for i in range(n):
        w = w0 + (w1 - w0) * i / (n - 1)
        wsum += w
        sumwx += w * xs[i]
        sumwy += w * ys[i]
    xbar = sumwx / wsum
    ybar = sumwy / wsum
    sxx = sxy = 0.0
    for i in range(n):
        w = w0 + (w1 - w0) * i / (n - 1)
        dx = xs[i] - xbar
        dy = ys[i] - ybar
        sxx += w * dx * dx
        sxy += w * dx * dy
    if sxx == 0.0:
        return 0.0
    slope = sxy / sxx
    intercept = ybar - slope * xbar
    ss_res = ss_tot = 0.0
    for i in range(n):
        w = w0 + (w1 - w0) * i / (n - 1)
        yhat = intercept + slope * xs[i]
        r = ys[i] - yhat
        ty = ys[i] - ybar
        ss_res += w * r * r
        ss_tot += w * ty * ty
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0
    annual_ret = math.exp(slope * 250.0) - 1.0
    return annual_ret * r2 if r2_weight else annual_ret
"""


def _count(p: dict, kind: str) -> int:
    """各信号的 history 窗口长度（K 线根数，emit 时算成字面量）。"""
    if kind == "ma_cross":
        return int(p["slow"]) + 1
    if kind == "rsi":
        return int(p["period"]) + 1
    if kind == "bollinger":
        return int(p["period"])
    return 1  # threshold / grid 只看当前价


# ---- 信号逻辑（4 空格缩进；{ctx} 上下文变量名，{pct} 仓位字面量）----
# close 由平台 fetch 片段产出；统一用 _mean()（见 _HELPER）。
_LOGICS = {
    "ma_cross": """\
    ma_fast_now = _mean(close[-{ctx}.fast:])
    ma_slow_now = _mean(close[-{ctx}.slow:])
    ma_fast_prev = _mean(close[-{ctx}.fast - 1:-1])
    ma_slow_prev = _mean(close[-{ctx}.slow - 1:-1])
    if ma_fast_prev <= ma_slow_prev and ma_fast_now > ma_slow_now:
        {BUY}
    elif ma_fast_prev >= ma_slow_prev and ma_fast_now < ma_slow_now:
        {SELL}
""",
    "threshold": """\
    price = close[-1]
    if price <= {ctx}.buy_below:
        {BUY}
    elif price >= {ctx}.sell_above:
        {SELL}
""",
    "rsi": """\
    closes = list(close)
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas[-{ctx}.rsi_period:]]
    losses = [max(-d, 0.0) for d in deltas[-{ctx}.rsi_period:]]
    avg_gain = sum(gains) / {ctx}.rsi_period
    avg_loss = sum(losses) / {ctx}.rsi_period
    rs = avg_gain / avg_loss if avg_loss else 999999.0
    rsi = 100.0 - 100.0 / (1.0 + rs)
    if rsi <= {ctx}.rsi_buy:
        {BUY}
    elif rsi >= {ctx}.rsi_sell:
        {SELL}
""",
    "bollinger": """\
    window = list(close)[-{ctx}.boll_period:]
    mid = _mean(window)
    var = _mean([(c - mid) ** 2 for c in window])
    sd = var ** 0.5
    upper = mid + {ctx}.boll_mult * sd
    lower = mid - {ctx}.boll_mult * sd
    price = window[-1]
    if price <= lower:
        {BUY}
    elif price >= upper:
        {SELL}
""",
    "grid": """\
    price = close[-1]
    if not hasattr({ctx}, 'last_deal'):
        {ctx}.last_deal = price
    if price <= {ctx}.last_deal * (1.0 - {ctx}.grid_step):
        {BUY}
        {ctx}.last_deal = price
    elif price >= {ctx}.last_deal * (1.0 + {ctx}.grid_step):
        {SELL}
        {ctx}.last_deal = price
""",
}

# _mean 辅助：numpy 数组与 list 通吃（sum/len 两者都支持）
_HELPER = """\

def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float('nan')
"""


def _signal(ir: StrategyIR):
    if not ir.universe or len(ir.universe) != 1:
        raise ValueError("发射器只支持单标的策略")
    if len(ir.signals) != 1:
        raise ValueError("发射器只支持单信号策略")
    sig = ir.signals[0]
    if sig.kind not in _LOGICS:
        raise ValueError(
            f"发射器暂不支持的信号 {sig.kind!r}，可选：{sorted(_LOGICS)}")
    if sig.kind == "ma_cross":
        fast, slow = int(sig.params["fast"]), int(sig.params["slow"])
        if fast >= slow:
            raise ValueError(f"ma_cross 需要 fast < slow，收到 {fast}/{slow}")
    return sig


def _emit(ir: StrategyIR, platform: str) -> str:
    if ir.signals and ir.signals[0].kind == "momentum_rotation":
        return _emit_rotation(ir, platform)
    sig = _signal(ir)
    kind, p = sig.kind, sig.params
    plat = _PLATFORMS[platform]
    ctx = plat["ctx"]
    stock = from_canonical(ir.universe[0], platform)
    pct = ir.order.pct if ir.order.style == "target_pct" else 0.95

    vals = {"universe0": stock, **p}
    init_lines = [f"    {ctx}.{attr} = {vals[key]!r}"
                  for attr, key in _INIT_ATTRS[kind]]
    if plat.get("init_extra"):
        init_lines.append(plat["init_extra"])
    if plat["schedule"]:
        init_lines.append(plat["schedule"].format(
            time=_TIME_OUT[platform](ir.schedule.time)))

    fetch = plat["fetch"].format(count=_count(p, kind))
    buy = plat["buy"].format(pct=repr(pct))
    sell = plat["sell"].format(pct=repr(pct))
    logic = (_LOGICS[kind].replace("{ctx}", ctx)
             .replace("{BUY}", buy).replace("{SELL}", sell))

    return (_HELPER
            + plat.get("helpers", "")
            + f"\ndef {plat['init']}({ctx}):\n"
            + "\n".join(init_lines) + "\n"
            + f"\n\ndef {plat['trade_fn']}({ctx}):\n"
            + fetch + "\n" + logic)


def _emit_rotation(ir: StrategyIR, platform: str) -> str:
    """动量轮动（多标的）：与 _emit 单标的逻辑平行，四平台 + 纯 Python 打分。"""
    if platform not in _PLATFORMS:
        raise ValueError(f"未知平台 {platform!r}，可选：{sorted(_PLATFORMS)}")
    if not ir.universe:
        raise ValueError("momentum_rotation 需要 universe 标的列表")
    sig = ir.signals[0]
    p = sig.params
    top_n = int(p.get("top_n", 1))
    if top_n < 1:
        raise ValueError(f"momentum_rotation 需要 top_n ≥ 1，收到 {top_n}")

    plat = _PLATFORMS[platform]
    ctx = plat["ctx"]
    universe_lit = [from_canonical(s, platform) for s in ir.universe]

    def _fmt(key):
        return repr(p[key])

    init_lines = [
        f"    {ctx}.universe = {universe_lit!r}",
        f"    {ctx}.lookback = {_fmt('lookback')}",
        f"    {ctx}.top_n = {_fmt('top_n')}",
        f"    {ctx}.min_score = {_fmt('min_score')}",
        f"    {ctx}.max_score = {_fmt('max_score')}",
        f"    {ctx}.drop_days = {_fmt('drop_days')}",
        f"    {ctx}.drop_threshold = {_fmt('drop_threshold')}",
        f"    {ctx}.r2_weight = {'True' if p.get('r2_weight', True) else 'False'}",
        f"    {ctx}.held = []",
    ]
    if plat.get("init_extra"):
        init_lines.append(plat["init_extra"])
    if plat["schedule"]:
        init_lines.append(plat["schedule"].format(
            time=_TIME_OUT[platform](ir.schedule.time)))

    buy, sell = _ROTATION_ORDER[platform]
    body = (
        "    scored = []\n"
        "    for sym in {ctx}.universe:\n"
        "        closes = list(closes_by_sym[sym])\n"
        "        score = _momentum_score(closes, {ctx}.drop_days, "
        "{ctx}.drop_threshold, {ctx}.r2_weight)\n"
        "        scored.append((score, sym))\n"
        "    scored.sort(key=lambda t: (-t[0], t[1]))\n"
        "    target = [sym for score, sym in scored "
        "if {ctx}.min_score < score < {ctx}.max_score][:{ctx}.top_n]\n"
        "    target_set = set(target)\n"
        "    old = set(getattr({ctx}, 'held', []))\n"
        "    for sym in sorted(old - target_set):\n"
        "        {SELL}\n"
        "    for sym in sorted(target_set - old):\n"
        "        {BUY}\n"
        "    {ctx}.held = sorted(target_set)\n"
    )
    body = (body.replace("{BUY}", buy).replace("{SELL}", sell)
            .replace("{ctx}", ctx))

    return (_ROTATION_HELPERS
            + plat.get("helpers", "")
            + f"\ndef {plat['init']}({ctx}):\n"
            + "\n".join(init_lines) + "\n"
            + f"\n\ndef {plat['trade_fn']}({ctx}):\n"
            + _ROTATION_FETCH[platform].replace("{ctx}", ctx) + "\n"
            + body)


EMITTERS = {name: (lambda pl: lambda ir: _emit(ir, pl))(name)
            for name in _PLATFORMS}


def emit(ir: StrategyIR, platform: str) -> str:
    if platform not in EMITTERS:
        raise ValueError(f"未知平台 {platform!r}，可选：{sorted(EMITTERS)}")
    return EMITTERS[platform](ir)


def emit_joinquant(ir: StrategyIR) -> str:
    return _emit(ir, "joinquant")


def emit_ptrade(ir: StrategyIR) -> str:
    return _emit(ir, "ptrade")
