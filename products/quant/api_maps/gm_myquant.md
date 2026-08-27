# 掘金量化 gm.api 对照表（v1.5 起步）

> 一份三用：① 互转发射模板的映射依据 ② 静态校验白名单 ③ 本地模型微调语料。
> 只收录已核实的等价关系；不确定的标 **TBD**，**不要臆造**。

## 生命周期

| 语义 | 掘金 gm.api | 聚宽/PTrade |
|---|---|---|
| 入口 | `init(context)` | `initialize(context)` |
| 定时-每日 | `schedule(schedule_func=algo, date_rule='1d', time_rule='09:31:00')` | `run_daily(...)` |
| K 线驱动 | `algo(context)` 由 schedule 驱动 | `handle_data(context, data)` |

## 数据

| 语义 | 掘金 gm.api | 聚宽 | PTrade |
|---|---|---|---|
| 历史 K 线 | `history_n(symbol, '1d', count, fields='close')` → DataFrame | `history(count, unit='1d', ...)` | `get_history(count, frequency='1d', ...)` |
| 标的格式 | `SZSE.000001` / `SHSE.600519` | `000001.XSHE` / `600519.XSHG` | 同聚宽 |

## 交易

| 语义 | 掘金 gm.api | 聚宽/PTrade |
|---|---|---|
| 目标仓位比例 | `order_target_percent(symbol, percent=...)` | `order_target_percent(security, pct)` |

## 已知差异（互转时必须处理）

1. 标的代码格式：`SZSE.000001` ↔ `000001.XSHE`（见 `symbols.py`，发射/解析双向自动转换）
2. `schedule` 的 time_rule 是 `'HH:MM:SS'`；IR 的 `open` 映射为 `09:31:00`（掘金无 open 语义）
3. `history_n` 返回 DataFrame，取收盘价序列：`history_n(...)['close']`
4. **TBD**：掘金实盘需先 `subscribe()` 订阅行情（回测环境部分场景可省略），发射模板暂未生成 subscribe 调用
5. **TBD**：掘金回测入口是 `run()` 函数（strategy_id/filename/mode 等参数），发射代码为策略文件本体，run 配置留用户侧
