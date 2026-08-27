# -*- coding: utf-8 -*-
"""
早小市值 — 聚宽版（干净版：无八星打分，无ETF混合）

「早小市值」核心逻辑（源自 早小市值加ETF.py 的小市值部分，已剔除八星与ETF轮动）：
  - 股票池：中小板综（399101.XSHE）成分股
  - 选股：pe>0，按流通市值升序取候选；过滤 停牌/涨跌停/ST/退市
  - 买卖：09:31 买入目标市值最小 N 只（默认 5 只），14:39 卖出不在目标的持仓
  - 风控：投资组合总市值连续 3 天跌幅超 -2% → 全部清仓，进入 5 天冷静期

注意：本策略依赖聚宽 get_index_stocks / get_fundamentals / get_current_data
（指数成分与基本面），跨平台 API 差异大，互转仅能走 LLM 兜底（不保证一致率）。
八星打分（数理吉凶对）仅作演示、不作有效信号，故本版不含八星。
"""
from jqdata import *
import math
import numpy as np
import pandas as pd

_stock_info = '000300.XSHG'
_universe_index = '399101.XSHE'   # 中小板综
_stock_count = 5
_dail_ope = '9:20'

# 风控（冷静期）
g.last_sell_date = None
g.sell_cooldown_days = 5
g.return_threshold = -0.02
g.cooldown_count = 0
g.cooldown_dates = []
g.days_since_sell = 0
g.portfolio_values = []


def initialize(context):
    set_benchmark(_stock_info)
    set_option('use_real_price', True)
    g.security_universe_index = _universe_index
    g.buy_stock_count = _stock_count
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, min_commission=5),
                   type='stock')
    # 定时：盘前备、9:31 买、14:39 卖、盘后统计
    run_daily(before_trading_start, time='09:25', reference_security=_stock_info)
    run_daily(buy_stocks, time='09:31', reference_security=_stock_info)
    run_daily(sell_stocks, time='14:39', reference_security=_stock_info)
    run_daily(after_market_close, time='after_close', reference_security=_stock_info)
    log.info('早小市值：中小板综流通市值最小%d只' % g.buy_stock_count)


def _pick_smallcap_targets(context):
    """小市值选股（无八星）：中小板综内 pe>0，按流通市值升序，过滤三停/ST。"""
    index_stocks = get_index_stocks(g.security_universe_index)
    q = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.code.in_(index_stocks), valuation.pe_ratio > 0
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(g.buy_stock_count * 6)
    df = get_fundamentals(q)
    check_out_lists = list(df.code)
    # 过滤: 停牌、涨跌停、st/*st/退市
    check_out_lists = filter_st_stock(check_out_lists)
    check_out_lists = filter_limitup_stock(context, check_out_lists)
    check_out_lists = filter_limitdown_stock(context, check_out_lists)
    check_out_lists = filter_paused_stock(check_out_lists)
    return check_out_lists[:g.buy_stock_count]


def calculate_portfolio_return(context):
    """追加当日组合总市值，返回相对昨日的涨跌幅。"""
    g.portfolio_values.append(context.portfolio.total_value)
    if len(g.portfolio_values) > 4:
        g.portfolio_values.pop(0)
    if len(g.portfolio_values) >= 2 and g.portfolio_values[-2] > 0:
        prev = g.portfolio_values[-2]
        ret = (context.portfolio.total_value - prev) / prev
        log.info('今日总市值 %.2f，昨日 %.2f，涨跌幅 %.2f%%' % (
            context.portfolio.total_value, prev, ret * 100))
        return ret
    return 0.0


def check_portfolio_decline(context):
    """组合总市值连续 3 天跌幅超阈值 → 全部清仓并进入冷静期。"""
    if len(g.portfolio_values) < 4:
        return False
    decline_days = 0
    for i in range(3):
        new_val = g.portfolio_values[-(i + 1)]
        old_val = g.portfolio_values[-(i + 2)]
        if old_val > 0 and (new_val - old_val) / old_val <= g.return_threshold:
            decline_days += 1
    if decline_days >= 3:
        log.warning('连续%d天跌幅超 %.2f%%：全部清仓' % (decline_days, g.return_threshold * 100))
        g.cooldown_count += 1
        g.cooldown_dates.append(context.current_dt.strftime('%Y-%m-%d'))
        g.last_sell_date = context.current_dt.strftime('%Y-%m-%d')
        g.days_since_sell = 0
        for stock in list(context.portfolio.positions):
            position = context.portfolio.positions[stock]
            if position.total_amount > 0:
                order_target_value_(stock, 0)
                log.info('紧急卖出: %s' % stock)
        g.portfolio_values.clear()
        return True
    return False


def before_trading_start(context):
    g.buy_executed = False
    g.sell_executed = False
    if g.last_sell_date:
        g.days_since_sell += 1
    calculate_portfolio_return(context)
    if check_portfolio_decline(context):
        log.info('连续跌幅触发紧急卖出')


def sell_stocks(context):
    """卖出不在目标列表中的股票（按最新小市值目标）。"""
    targets = set(_pick_smallcap_targets(context))
    for stock in list(context.portfolio.positions):
        if stock not in targets:
            position = context.portfolio.positions[stock]
            if position.total_amount > 0:
                close_position(position)


def buy_stocks(context):
    """冷却期内不买；否则买入市值最小的 N 只。"""
    if g.last_sell_date and g.days_since_sell < g.sell_cooldown_days:
        log.info('距上次卖出 %d 个交易日，冷静期内跳过买入' % g.days_since_sell)
        return 0
    targets = _pick_smallcap_targets(context)
    if not targets:
        return 0
    position_count = len(context.portfolio.positions)
    if g.buy_stock_count <= position_count:
        return 0
    value = context.portfolio.cash / (g.buy_stock_count - position_count)
    for stock in targets:
        if stock not in context.portfolio.positions and open_position(stock, value):
            if len(context.portfolio.positions) == g.buy_stock_count:
                break


def after_market_close(context):
    log.info('冷静期次数 %d' % g.cooldown_count)
    if g.cooldown_dates:
        log.info('冷静期日期 %s' % g.cooldown_dates)


# 自定义下单
def order_target_value_(security, value):
    try:
        return order_target_value(security, value)
    except Exception as e:
        log.warning('下单失败 %s 原因 %s' % (security, str(e)))
        return None


def open_position(security, value):
    order = order_target_value_(security, value)
    return bool(order and order.filled > 0)


def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    return bool(order and order.status == OrderStatus.held
                and order.filled == order.amount)


def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]


def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [s for s in stock_list
            if not current_data[s].is_st
            and 'ST' not in current_data[s].name
            and '*' not in current_data[s].name
            and '退' not in current_data[s].name]


def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list
            if s in context.portfolio.positions
            or last_prices[s][-1] < current_data[s].high_limit]


def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [s for s in stock_list
            if s in context.portfolio.positions
            or last_prices[s][-1] > current_data[s].low_limit]
