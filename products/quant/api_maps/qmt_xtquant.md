# QMT / miniQMT（xtquant）对照表（v1.5 起步）

> 一份三用：① 互转发射模板的映射依据 ② 静态校验白名单 ③ 本地模型微调语料。
> 只收录已核实的等价关系；不确定的标 **TBD**，**不要臆造**。
> QMT 探活见 `qmt.py`（进程检测 + xtquant SDK 检测）。

## 生命周期

| 语义 | QMT（miniQMT 策略文件） | 聚宽/PTrade |
|---|---|---|
| 入口 | `init(C)`（C 为 ContextInfo） | `initialize(context)` |
| K 线驱动 | `handlebar(C)` 每根 K 线触发 | `handle_data(context, data)` |
| 定时 | **TBD**（bar 驱动为主；定时任务用 C.schedule? 待核实） | `run_daily(...)` |

## 数据

| 语义 | QMT xtquant | 聚宽 | PTrade |
|---|---|---|---|
| 历史 K 线 | `C.get_market_data_ex(['close'], [stock], period='1d', count=N)` → `{stock: DataFrame}` | `history(...)` | `get_history(...)` |
| 标的格式 | `000001.SZ` / `600519.SH` | `000001.XSHE` | 同聚宽 |

## 交易（passorder 签名已据官方文档核实，镜像见 kb/qmt_api.md）

| 语义 | QMT | 聚宽/PTrade |
|---|---|---|
| 综合下单 | `passorder(opType, orderType, accountid, orderCode, prType, modelprice, volume[, strategyName, quickTrade, userOrderId], ContextInfo)` | — |
| 股票买入 | `opType=23` | `order_target_percent(...)` |
| 股票卖出 | `opType=24` | `order_target_percent(..., 0)` |
| 目标仓位（比例） | `orderType=1123`（单股、单账号、可用、比例 [0~1] 下单）；`prType=5` 最新价（此时 modelprice 传 -1） | `order_target_percent(...)` |

发射的 QMT 代码用 `_buy(C, stock, pct)` / `_sell(C, stock)` 助手封装
`passorder(23/24, 1123, C.account, stock, 5, -1, pct, '', 1, '', C)`；
`C.account` 资金账号留空待用户填（合规红线：下单动作强制人工确认）。

## 已知差异（互转时必须处理）

1. 标的代码格式：`000001.SZ` ↔ `000001.XSHE`（见 `symbols.py`）
2. 上下文变量约定为 `C`（ContextInfo），属性直接挂 `C.xxx`
3. 无 run_daily；IR 的 daily/open 语义对应 handlebar 的 1d bar 驱动
4. **TBD**：1123 卖出方向的「比例」是可用资金还是可用持仓口径，需实盘环境验证
5. **TBD**：`get_market_data_ex` 的复权参数（dividend_type）、count 语义边界
6. **TBD**：QMT 终端需登录并运行 miniQMT 才能取数（探活面板只检测进程与 SDK）
