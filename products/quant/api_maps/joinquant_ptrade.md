# 聚宽 JoinQuant ↔ PTrade API 对照表（v0.1 起步）

> 一份三用：① 互转发射模板的映射依据 ② 静态校验白名单 ③ 本地模型微调语料。
> 只收录已核实的等价关系；不确定的留空待补，**不要臆造**。

## 生命周期

| 语义 | 聚宽 | PTrade |
|---|---|---|
| 初始化 | `initialize(context)` | `initialize(context)` |
| 盘前 | `before_trading_start(context, data)` | `before_trading_start(context, data)` |
| 盘后 | `after_trading_end(context, data)` | `after_trading_end(context, data)` |
| 定时-每日 | `run_daily(func, time='open')` | `run_daily(context, func, time='09:35')` |
| 定时-分钟 | `run_interval` / handle_data 每分钟 | `run_interval(context, func, seconds=60)` |
| K 线驱动 | `handle_data(context, data)` | `handle_data(context, data)` |

## 数据

| 语义 | 聚宽 | PTrade |
|---|---|---|
| 历史 K 线 | `history(count, unit='1d', field='close', security_list=...)` | `get_history(count, frequency='1d', field='close', security_list=...)` |
| 当前价 | `data[s].close` | `data[s].close` |
| 基本面 | `get_fundamentals(query(...))` | `get_fundamentals(...)`（参数有差异，待补） |

## 交易

| 语义 | 聚宽 | PTrade |
|---|---|---|
| 市价按股数 | `order(security, amount)` | `order(security, amount)` |
| 按金额 | `order_value(security, value)` | `order_value(security, value)` |
| 目标仓位比例 | `order_target_percent(security, pct)` | `order_target_percent(security, pct)` |
| 目标股数 | `order_target(security, amount)` | `order_target(security, amount)` |
| 当前持仓 | `context.portfolio.positions[s].closeable_amount` | `context.portfolio.positions[s].enable_amount` |

## 沙箱约束（静态校验白名单要点）

- 两平台云端容器均禁止：`import os / sys / subprocess`、文件读写、网络访问
- 聚宽允许：`jqdata`、`numpy`、`pandas`（受限版本）
- PTrade 允许：内置 `numpy`、`pandas`；部分券商环境禁 `talib`

## 已知差异（互转时必须处理）

1. `run_daily` 的 time 参数：聚宽接受 `'open'/'close'/'09:35'`；PTrade 只接受 `'HH:MM'` 字符串 → 发射时把 `open` 映射为 `'09:30'`
2. 持仓可卖字段名不同（`closeable_amount` vs `enable_amount`）
3. PTrade 的 `run_daily` 第一个参数是 context（聚宽不是）
