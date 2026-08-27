# 掘金(GoldMiner/MyQuant) Python SDK 接口文档

---

> 来源 https://www.myquant.cn/docs2/ · 自动镜像，仅供本地检索/微调语料


---

## 变量约定

> https://www.myquant.cn/docs2/sdk/python/%E5%8F%98%E9%87%8F%E7%BA%A6%E5%AE%9A.html

<!DOCTYPE html>




     变量约定 - 掘金量化












# #  变量约定



## #  symbol - 代码标识

  掘金代码( symbol )是掘金平台用于唯一标识交易标的代码,
  格式为： 交易所代码.交易标代码 , 比如深圳平安的 symbol ，示例： SZSE.000001 （注意区分大小写）。
板块为： BK.板块代码 ，比如鸿蒙概念的 symbol ，示例： BK.007347 ，板块symbol可通过get_symbols(sec_type1=1070)获取。
代码标识表示可以在掘金终端的仿真交易或交易工具中进行查询。



### #  交易所代码

  目前掘金支持国内的 8 个交易所, 各交易所的代码缩写如下：
     市场中文名
  市场代码

     上交所
  SHSE

   深交所
  SZSE

   中金所
  CFFEX

   上期所
  SHFE

   大商所
  DCE

   郑商所
  CZCE

   上海国际能源交易中心
  INE

   广期所
  GFEX




### #  交易标的代码

  交易表代码是指交易所给出的交易标的代码, 包括股票（如 600000）, 期货（如 rb2011）, 期权(如 10002498）, 指数（如 000001）, 基金（如 510300）等代码。
  具体的代码请参考交易所的给出的证券代码定义。


### #  symbol 示例

     市场中文名
  市场代码
  示例代码
  证券简称

     上交所
  SHSE
  SHSE.600000
  浦发银行

   深交所
  SZSE
  SZSE.000001
  平安银行

   中金所
  CFFEX
  CFFEX.IC2011
  中证 500 指数 2020 年 11 月期货合约

   上期所
  SHFE
  SHFE.rb2011
  螺纹钢 2020 年 11 月期货合约

   大商所
  DCE
  DCE.m2011
  豆粕 2020 年 11 月期货合约

   郑商所
  CZCE
  CZCE.FG101
  玻璃 2021 年 1 月期货合约

   上海国际能源交易中心
  INE
  INE.sc2011
  原油 2020 年 11 月期货合约

   广期所
  GFEX
  GFEX.lc2405
  碳酸锂 2024 年 05 月期货合约




### #  虚拟合约

     市场中文名
  市场代码
  示例代码
  证券简称

     上期所
  SHFE
  SHFE.RB
  螺纹钢主力连续合约

   上期所
  SHFE
  SHFE.RB22
  螺纹钢次主力连续合约

   上期所
  SHFE
  SHFE.RB99
  螺纹钢加权指数合约

   上期所
  SHFE
  SHFE.RB00
  螺纹钢当月连续合约

   上期所
  SHFE
  SHFE.RB01
  螺纹钢下月连续合约

   上期所
  SHFE
  SHFE.RB02
  螺纹钢下季连续合约

   上期所
  SHFE
  SHFE.RB03
  螺纹钢隔季连续合约




### #  期货主力连续合约

  仅回测模式下使用， 期货主力连续合约 为量价数据的简单拼接，未做平滑处理， 如 SHFE.RB 螺纹钢主力连续合约，其他主力合约请查看 期货主力连续合约


## #  mode - 模式选择

  策略支持两种运行模式,需要在 run() 里面指定，分别为实时模式和回测模式。


### #  实时模式

  实时模式需指定  mode = MODE_LIVE
  订阅行情服务器推送的实时行情，也就是交易所的实时行情，只在交易时段提供，常用于仿真和实盘。


### #  回测模式

  回测模式需指定  mode = MODE_BACKTEST
  订阅指定时段、指定交易代码、指定数据类型的历史行情，行情服务器将按指定条件全速回放对应的行情数据。适用的场景是策略回测阶段，快速验证策略的绩效是否符合预期。


## #  context - 上下文对象

  context 是策略运行上下文环境对象，该对象将会在你的算法策略的任何方法之间做传递。用户可以通过 context 定义多种自己需要的属性，也可以查看 context 固有属性，context 结构如下图：



### #  context.symbols - 订阅代码集合

  通过 subscribe 行情订阅函数， 订阅代码会生成一个代码集合
   函数原型：


```
context.symbols
```

  返回值：
     类型
  说明

     set(str)
  订阅代码集合


   示例：


```
subscribe(symbols=['SHSE.600519', 'SHSE.600419'], frequency='60s')
context.symbols
```

  返回值：


```
{'SHSE.600519', 'SHSE.600419'}
```

### #  context.now - 当前时间

  实时模式返回当前本地时间, 回测模式返回当前回测时间
   函数原型：


```
context.now
```

  返回值：
     类型
  说明

     datetime.datetime
  当前时间(回测模式下是策略回测的当前历史时间， 实时模式下是用户的系统本地时间)


   示例：


```
context.now
```

  返回:


```
2020-09-01 09:40:00+08:00
```

### #  context.mode - 运行模式

  实时模式为1，回测模式为2
   函数原型：


```
context.mode
```

  返回值：
     类型
  说明

     int
  实时模式为1，回测模式为2


   示例：


```
if context.mode == 1:
    print('执行实时模式:', context.mode)
elif context.mode == 2:
    print('执行回测模式:', context.mode)
else:
    print('未知模式:', context.mode)
```

  返回:


```
执行实时模式:1
```

### #  context.data - 数据滑窗

  获取订阅的 tick 对象  或者  bar 对象 滑窗，数据为包含当前时刻推送 tick 或 bar 的前 count 条 tick 或者 bar 数据
   原型:


```
context.data(symbol,frequency,count,fields)
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码(只允许单个标的的代码字符串)，使用时参考 symbol

   frequency
  str
  频率, 支持 'tick', '1d', '60s' 等, 默认 '1d', 详情见 股票行情数据 和 期货行情数据 ,  实时行情支持的频率

   count
  int
  滑窗大小(正整数)，需小于等于 subscribe 函数中 count 值

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有, 具体字段见: tick 对象  和  bar 对象  ，需在 subscribe 函数中指定的fields范围内，指定字段越少，查询速度越快


   返回值：
   当subscribe的format="df"（默认）时，返回dataframe
     类型
  说明

     dataframe
  tick 的 dataframe 或者 bar 的 dataframe


   示例：


```
def init(context):
    subscribe(symbols='SHSE.600519', frequency='60s', count=50, fields='symbol, close, eob', format='df')

def on_bar(context,bars):
    data = context.data(symbol=bars[0]['symbol'], frequency='60s', count=10)
    print(data.tail())
```

  输出：


```
symbol    close                       eob
5  SHSE.600519  1629.96 2024-01-22 14:56:00+08:00
6  SHSE.600519  1627.25 2024-01-22 14:57:00+08:00
7  SHSE.600519  1627.98 2024-01-22 14:58:00+08:00
8  SHSE.600519  1642.00 2024-01-22 15:00:00+08:00
9  SHSE.600519  1632.96 2024-01-23 09:31:00+08:00
```

  subscribe的format ="row"时，返回list[dict]
     类型
  说明

     list[dict]
  当frequency='tick'时，返回tick列表：[{tick_1}, {tick_2},  ..., {tick_n}]，列表长度等于滑窗大小，即n=count， 当frequency='60s', '300s', '900s', '1800s', '3600s'时，返回bar列表：[{bar_1}, {bar_2}, {bar_n}, ..., ] ，列表长度等于滑窗大小，即n=count


   示例：


```
def init(context):
    subscribe(symbols='SHSE.600519', frequency='tick', count=50, fields='symbol, price, quotes,created_at', format='row')

def on_tick(context, tick):
    data = context.data(symbol=tick['symbol'], frequency='tick', count=3)
    print(data)
```

  输出：


```
[{'symbol': 'SHSE.600519', 'price': 1642.0, 'quotes': [{'bid_p': 1640.0, 'bid_v': 100, 'ask_p': 1642.0, 'ask_v': 4168}, {'bid_p': 1634.52, 'bid_v': 300, 'ask_p': 1642.01, 'ask_v': 100}, {'bid_p': 1633.0, 'bid_v': 100, 'ask_p': 1642.06, 'ask_v': 100}, {'bid_p': 1632.96, 'bid_v': 100, 'ask_p': 1642.08, 'ask_v': 200}, {'bid_p': 1632.89, 'bid_v': 100, 'ask_p': 1642.2, 'ask_v': 200}], 'created_at': datetime.datetime(2024, 1, 22, 15, 1, 51, 286000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))}, {'symbol': 'SHSE.600519', 'price': 1642.0, 'quotes': [{'bid_p': 1640.0, 'bid_v': 100, 'ask_p': 1642.0, 'ask_v': 4168}, {'bid_p': 1634.52, 'bid_v': 300, 'ask_p': 1642.01, 'ask_v': 100}, {'bid_p': 1633.0, 'bid_v': 100, 'ask_p': 1642.06, 'ask_v': 100}, {'bid_p': 1632.96, 'bid_v': 100, 'ask_p': 1642.08, 'ask_v': 200}, {'bid_p': 1632.89, 'bid_v': 100, 'ask_p': 1642.2, 'ask_v': 200}], 'created_at': datetime.datetime(2024, 1, 22, 15, 1, 54, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))}, {'symbol': 'SHSE.600519', 'price': 0.0, 'quotes': [{'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}], 'created_at': datetime.datetime(2024, 1, 23, 9, 14, 1, 91000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))}]
```

  subscribe的format ="col"时，返回dict
     类型
  说明

     dict
  当frequency='tick'时，返回tick数据（symbol为str格式，其余字段为列表，列表长度等于滑窗大小count），当frequency='60s', '300s', '900s', '1800s', '3600s'时，返回bar数据（symbol和frequency为str格式，其余字段为列表，列表长度等于滑窗大小count）


   示例：


```
def init(context):
    subscribe(symbols='SHSE.600519', frequency='tick', count=10, fields='symbol, price, bid_p, created_at', format='col')

def on_tick(context, tick):
    data = context.data(symbol=tick['symbol'], frequency='tick', count=10)
    print(data)
```

  输出：


```
{'symbol': 'SHSE.600519', 'price': [1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 0.0], 'bid_p': [1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 0.0], 'created_at': [datetime.datetime(2024, 1, 22, 15, 1, 12, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 21, 277000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 24, 278000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 33, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 36, 282000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 39, 279000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 48, 283000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 51, 286000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 54, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 23, 9, 14, 1, 91000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))]}
```

  注意：
   1.  只有在 订阅 后，此接口才能取到数据，如未订阅数据，则返回报错。
   2.  symbol 参数只支持输入 一个 标的。
   3.  count 参数必须 小于或等于 订阅函数里面的 count 值。
   4.  fields 参数必须在订阅函数subscribe里面指定的 fields 范围内。指定字段越少，查询速度越快，目前效率是row > col > df。
   5.  当subscribe的format指定col时，tick的quotes字段会被拆分，只返回买卖一档的量和价，即只有bid_p，bid_v, ask_p和ask_v。


### #  context.account - 账户信息

  可通过此函数获取账户资金信息及持仓信息。
   原型:


```
context.account(account_id=None)
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账户信息，默认返回默认账户, 如多个账户需指定 account_id


   返回值：
  返回类型为 account - 账户对象 。
   示例-获取当前持仓：


```
# 所有持仓
Account_positions = context.account().positions()
# 指定持仓
Account_position = context.account().position(symbol='SHSE.600519',side = PositionSide_Long)
```

  返回值：
     类型
  说明

     list[position]
   持仓对象 列表


   注意：
没有持仓的情况下， 用 context.account().positions()查总持仓， 返回空列表， 用 context.account().position()查单个持仓，返回 None
   输出：


```
# 所有持仓输出
[{'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'symbol': 'SHSE.600419', 'side': 1, 'volume': 2200, 'volume_today': 100, 'vwap': 16.43391600830338, 'amount': 36154.61521826744, 'fpnl': -2362.6138754940007, 'cost': 36154.61521826744, 'available': 2200, 'available_today': 100, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 30, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'vwap_diluted': 0.0, 'price': 0.0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_now': 0, 'market_value': 0.0, 'last_price': 0.0, 'last_volume': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0}, {'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'symbol': 'SHSE.600519', 'side': 1, 'volume': 1100, 'vwap': 1752.575242219682, 'amount': 1927832.7664416502, 'fpnl': -110302.84700805641, 'cost': 1927832.7664416502, 'available': 1100, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 15, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'volume_today': 0, 'vwap_diluted': 0.0, 'price': 0.0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'available_now': 0, 'market_value': 0.0, 'last_price': 0.0, 'last_volume': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0}]
# 指定持仓输出
{'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'symbol': 'SHSE.600519', 'side': 1, 'volume': 1100, 'vwap': 1752.575242219682, 'amount': 1927832.7664416502, 'fpnl': -110302.84700805641, 'cost': 1927832.7664416502, 'available': 1100, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 15, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'volume_today': 0, 'vwap_diluted': 0.0, 'price': 0.0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'available_now': 0, 'market_value': 0.0, 'last_price': 0.0, 'last_volume': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0}
```

  示例-获取当前账户资金：


```
context.account().cash
```

  返回值：
     类型
  说明

     dict[cash]
   资金对象 字典


   输出：


```
{'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'nav': 1905248.2789094353, 'pnl': -94751.72109056474, 'fpnl': -94555.35135529494, 'frozen': 1963697.3526980684, 'available': 36106.277566661825, 'cum_inout': 2000000.0, 'cum_trade': 1963697.3526980684, 'cum_commission': 196.3697352698069, 'last_trade': 1536.1536610412597, 'last_commission': 0.153615366104126, 'created_at': datetime.datetime(2020, 9, 1, 8, 0, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 30, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'currency': 0, 'order_frozen': 0.0, 'balance': 0.0, 'market_value': 0.0, 'cum_pnl': 0.0, 'last_pnl': 0.0, 'last_inout': 0.0, 'change_reason': 0, 'change_event_id': ''}
```

  示例-获取账户连接状态：


```
context.account().status
```

  输出：


```
{'state': 3, 'error': {'code': 0, 'type': '', 'info': ''}}
```

### #  context.parameters - 动态参数

  获取所有动态参数
   函数原型：


```
context.parameters
```

  返回值：
     类型
  说明

     dict
  key 为动态参数的 key, 值为动态参数对象， 参见 动态参数


   示例-添加动态参数和查询所有设置的动态参数


```
add_parameter(key='k_value', value=context.k_value, min=0, max=100, name='k值阀值', intro='k值阀值',group='1', readonly=False)

context.parameters
```

  输出：


```
{'k_value': {'key': 'k_value', 'value': 80.0, 'max': 100.0, 'name': 'k值阀值', 'intro': 'k值阀值', 'group': '1', 'min': 0.0, 'readonly': False}}
```

### #  context.xxxxx - 自定义属性

  通过自定义属性设置参数， 随 context 全局变量传入策略各个事件里


```
context.my_value = 100000000
```

  返回值：
     类型
  说明

     any type
  自定义属性


   示例-输出自定义属性


```
print(context.my_value)
```

  输出：


```
100000000
```


      ←

        策略程序架构

        数据结构

      →

---

## 快速开始

> https://www.myquant.cn/docs2/sdk/python/%E5%BF%AB%E9%80%9F%E5%BC%80%E5%A7%8B.html

<!DOCTYPE html>




     快速开始 - 掘金量化












# #  快速开始

  常见的策略结构主要包括 3 类，如下图所示。

  用户可以根据策略需求选择相应的策略结构，具体可以参考 经典策略 。


## #  定时任务示例

  以下代码的内容是：在每个交易日的 14：50：00 市价买入 200 股浦发银行股票：


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):
    # 每天14:50 定时执行algo任务,
    # algo执行定时任务函数，只能传context参数
    # date_rule执行频率，目前暂时支持1d、1w、1m，其中1w、1m仅用于回测，实时模式1d以上的频率，需要在algo判断日期
    # time_rule执行时间， 注意多个定时任务设置同一个时间点，前面的定时任务会被后面的覆盖
    schedule(schedule_func=algo, date_rule='1d', time_rule='14:50:00')

def algo(context):
    # 以市价购买200股浦发银行股票， price在市价类型不生效
    order_volume(symbol='SHSE.600000', volume=200, side=OrderSide_Buy,
                 order_type=OrderType_Market, position_effect=PositionEffect_Open, price=0)

# 查看最终的回测结果
def on_backtest_finished(context, indicator):
    print(indicator)

if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
    '''
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='token_id',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
```

 整个策略需要三步:
  1、设置初始化函数:  init  , 使用  schedule  函数进行定时任务配置
  2、配置任务, 到点会执行该任务
  3、执行策略


## #  数据事件驱动示例

  在用 subscribe()接口订阅标的后，后台会返回 tick 数据或 bar 数据。每产生一个或一组数据，就会自动触发 on_tick()或 on_bar()里面的内容执行。比如以下范例代码片段，订阅浦发银行频率为 1 天和 60s 的 bar 数据，每产生一次 bar，就会自动触发 on_bar()调用，打印获取的 bar 信息：


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):
    # 订阅浦发银行, bar频率为一天和一分钟
    # 订阅订阅多个频率的数据，可多次调用subscribe
    subscribe(symbols='SHSE.600000', frequency='1d')
    subscribe(symbols='SHSE.600000', frequency='60s')

def on_bar(context, bars):

    # 打印bar数据
    print(bars)

if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
    '''
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='token_id',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
```

 整个策略需要三步:
  1、设置初始化函数: init, 使用 subscribe 函数进行数据订阅
  2、实现一个函数: on_bar, 来根据数据推送进行逻辑处理
  3、执行策略


## #  时间序列数据事件驱动示例

  策略订阅代码时指定数据窗口大小与周期, 平台创建数据滑动窗口, 加载初始数据, 并在新的 bar 到来时自动刷新数据。
  on_bar 事件触发时, 策略可以通过 context.data 取到订阅代码的准备好的时间序列数据。
  以下的范例代码片段是一个非常简单的例子， 订阅浦发银行的日线和分钟 bar, bar 数据的更新会自动触发 on_bar 的调用, 每次调用 context.data 来获取最新的 50 条分钟 bar 信息：


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):
    # 订阅浦发银行, bar频率为一天和一分钟
    # 指定数据窗口大小为50
    # 订阅订阅多个频率的数据，可多次调用subscribe
    subscribe(symbols='SHSE.600000', frequency='1d', count=50, format='df', fields='symbol, close, eob')
    subscribe(symbols='SHSE.600000', frequency='60s', count=50, format='df', fields='symbol, close, eob')

def on_bar(context, bars):
    # context.data提取缓存的数据滑窗, 可用于计算指标
    # 注意：context.data里的count要小于或者等于subscribe里的count,fields需要在subscribe的fields范围内
    data = context.data(symbol=bars[0]['symbol'], frequency='60s', count=50, fields='close,eob')
    # 计算均线
    data['ma5'] = data['close'].rolling(window=5).mean()
    # 打印最后5条bar数据（最后一条是最新的bar）
    print(data.tail())

if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
    '''
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='token_id',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
```

 整个策略需要三步:
  1、设置初始化函数:  init  , 使用  subscribe  函数进行数据订阅
  2、实现一个函数:  on_bar  , 来根据数据推送进行逻辑处理, 通过  context.data  获取数据滑窗
  3、执行策略


## #  选择回测模式/实时模式运行示例

  掘金 3 策略只有两种模式, 回测模式(backtest)与实时模式(live)。在加载策略时指定 mode 参数。


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):
    # 订阅浦发银行的tick
    subscribe(symbols='SHSE.600000', frequency='60s')

def on_bar(context, bars):
    # 打印当前获取的bar信息
    print(bars)

if __name__ == '__main__':
    # 在终端仿真交易和实盘交易的启动策略按钮默认是实时模式，运行回测默认是回测模式，在外部IDE里运行策略需要修改成对应的运行模式
    # mode=MODE_LIVE 实时模式, 回测模式的相关参数不生效
    # mode=MODE_BACKTEST  回测模式

    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
    '''
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_LIVE,
        token='token_id',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
```

 整个策略需要三步:
  1、设置初始化函数:  init  , 使用  subscribe  函数进行数据订阅代码
  2、实现一个函数:  on_bar  , 来根据数据推送进行逻辑处理
  3、选择对应模式，执行策略


## #  提取数据研究示例

  如果只想提取数据，无需实时数据驱动策略, 无需交易下单可以直接通过数据查询函数来进行查询。


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

# 可以直接提取数据，掘金终端需要打开，接口取数是通过网络请求的方式，效率一般，行情数据可通过subscribe订阅方式
# 设置token， 查看已有token ID,在用户-密钥管理里获取
set_token('your token_id')

# 查询历史行情, 采用定点复权的方式， adjust指定前复权，adjust_end_time指定复权时间点
data = history(symbol='SHSE.600000', frequency='1d', start_time='2020-01-01 09:00:00', end_time='2020-12-31 16:00:00',
               fields='open,high,low,close', adjust=ADJUST_PREV, adjust_end_time='2020-12-31', df=True)
print(data)
```

 整个过程只需要两步:
  1、set_token 设置用户 token， 如果 token 不正确, 函数调用会抛出异常
  2、调用数据查询函数， 直接进行数据查询


## #  回测模式下高速处理数据示例

  本示例提供一种在 init 中预先取全集数据，规整后索引调用的高效数据处理方式，能够避免反复调用服务器接口导致的低效率问题，可根据该示例思路，应用到其他数据接口以提高效率.


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):
	# 在init中一次性拿到所有需要的instruments信息
    instruments = get_history_symbol(symbol='SZSE.000001', start_date=context.backtest_start_time,end_date=context.backtest_end_time)
	# 将信息按symbol,date作为key存入字典
    context.ins_dict = {(i.symbol, i.trade_date.date()): i for i in instruments}
    subscribe(symbols='SZSE.000001', frequency='1d')

def on_bar(context, bars):
    print(context.ins_dict[(bars[0].symbol, bars[0].eob.date())])

if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
    '''
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='token_id',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
```

 整个策略需要三步:
  1、设置初始化函数:  init  , 一次性拿到所有需要的 instruments 信息， 将信息按 symbol,date 作为 key 存入字典， 使用  subscribe  函数进行数据订阅代码
  2、实现一个函数:  on_bar  , 来根据数据推送进行逻辑处理
  3、执行策略


## #  实时模式下动态参数示例

  本示例提供一种通过策略设置动态参数，可在终端界面显示和修改，在不停止策略的情况下手动修改参数传入策略方法.


```
# coding=utf-8
from __future__ import print_function, absolute_import, unicode_literals
from gm.api import *
import numpy as np
import pandas as pd

'''动态参数，是指在不终止策略的情况下，掘金终端UI界面和策略变量做交互，
    通过add_parameter在策略代码里设置动态参数，终端UI界面会显示对应参数
'''

def init(context):
    # log日志函数，只支持实时模式，在仿真交易和实盘交易界面查看，重启终端log日志会被清除，需要记录到本地可以使用logging库
    log(level='info', msg='平安银行信号触发', source='strategy')
    # 设置k值阀值作为动态参数
    context.k_value = 23
    # add_parameter设置动态参数函数，只支持实时模式，在仿真交易和实盘交易界面查看，重启终端动态参数会被清除，重新运行策略会重新设置
    add_parameter(key='k_value', value=context.k_value, min=0, max=100, name='k值阀值', intro='设置k值阀值',
                  group='1', readonly=False)

    # 设置d值阀值作为动态参数
    context.d_value = 20
    add_parameter(key='d_value', value=context.d_value, min=0, max=100, name='d值阀值', intro='设置d值阀值',
                  group='2', readonly=False)

    print('当前的动态参数有', context.parameters)
    # 订阅行情
    subscribe(symbols='SZSE.002400', frequency='60s', count=120)

def on_bar(context, bars):

    data = context.data(symbol=bars[0]['symbol'], frequency='60s', count=100)

    kdj = KDJ(data, 9, 3, 3)
    k_value = kdj['kdj_k'].values
    d_value = kdj['kdj_d'].values

    if k_value[-1] > context.k_value and d_value[-1] < context.d_value:
        order_percent(symbol=bars[0]['symbol'], percent=0.01, side=OrderSide_Buy, order_type=OrderType_Market, position_effect=PositionEffect_Open)
        print('{}下单买入， k值为{}'.format(bars[0]['symbol'], context.k_value))

# 计算KDJ
def KDJ(data, N, M1, M2):
    lowList= data['low'].rolling(N).min()
    lowList.fillna(value=data['low'].expanding().min(), inplace=True)
    highList = data['high'].rolling(N).max()
    highList.fillna(value=data['high'].expanding().max(), inplace=True)
    rsv = (data['close'] - lowList) / (highList - lowList) * 100
    data['kdj_k'] = rsv.ewm(alpha=1/M1).mean()
    data['kdj_d'] = data['kdj_k'].ewm(alpha=1/M2).mean()
    data['kdj_j'] = 3.0 * data['kdj_k'] - 2.0 * data['kdj_d']
    return data

# 动态参数变更事件
def on_parameter(context, parameter):
    # print(parameter)
    if parameter['name'] == 'k值阀值':
        # 通过全局变量把动态参数值传入别的事件里
        context.k_value = parameter['value']
        print('{}已经修改为{}'.format(parameter['name'], context.k_value))

    if parameter['name'] == 'd值阀值':
        context.d_value = parameter['value']
        print('{}已经修改为{}'.format(parameter['name'], context.d_value))

def on_account_status(context, account):
    print(account)

if __name__ == '__main__':
    '''
    strategy_id策略ID,由系统生成
    filename文件名,请与本文件名保持一致
    mode实时模式:MODE_LIVE回测模式:MODE_BACKTEST
    token绑定计算机的ID,可在系统设置-密钥管理中生成
    backtest_start_time回测开始时间
    backtest_end_time回测结束时间
    backtest_adjust股票复权方式不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
    backtest_initial_cash回测初始资金
    backtest_commission_ratio回测佣金比例
    backtest_slippage_ratio回测滑点比例
    '''
    run(strategy_id='07c08563-a4a8-11ea-a682-7085c223669d',
        filename='main.py',
        mode=MODE_LIVE,
        token='2c4e3c59cde776ebc268bf6d7b4c457f204482b3',
        backtest_start_time='2020-09-01 08:00:00',
        backtest_end_time='2020-10-01 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=500000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
```



## #  level2 数据驱动事件示例

  本示例提供 level2 行情的订阅， 包括逐笔成交、逐笔委托、委托队列
仅券商托管版本支持


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):
    # 查询历史L2 Tick行情
    history_l2tick=get_history_l2ticks('SHSE.600519', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None,
                        skip_suspended=True, fill_missing=None,
                        adjust=ADJUST_NONE, adjust_end_time='', df=False)
    print(history_l2tick[0])

    # 查询历史L2 Bar行情
    history_l2bar=get_history_l2bars('SHSE.600000', '60s', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None,
                       skip_suspended=True, fill_missing=None,
                       adjust=ADJUST_NONE, adjust_end_time='', df=False)
    print(history_l2bar[0])

    # 查询历史L2 逐笔成交
    history_transactions = get_history_l2transactions('SHSE.600000', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None, df=False)
    print(history_transactions[0])

    # 查询历史L2 逐笔委托
    history_order=get_history_l2orders('SZSE.000001', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None, df=False)
    print(history_order[0])

    # 订阅浦发银行的逐笔成交数据
    subscribe(symbols='SHSE.600000', frequency='l2transaction')
    # 订阅平安银行的逐笔委托数据
    subscribe(symbols='SZSE.000001', frequency='l2order')

def on_l2order(context, order):
    # 打印逐笔成交数据
    print(order)

def on_l2transaction(context, transition):
    # 打印逐笔委托数据
    print(transition)

if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
    '''
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='token_id',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
```



## #  可转债数据获取/交易示例

  本示例提供可转债数据获取、可转债交易


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):

    # 获取可转债基本信息，输入可转债代码即可
    infos = get_symbol_infos(sec_type1=1030, symbols='SHSE.113038', df=True)

    # 输入可转债标的代码，可以获取到历史行情
    history_data = history(symbol='SHSE.113038', frequency='60s', start_time='2021-02-24 14:50:00',
                                end_time='2021-02-24 15:30:30', adjust=ADJUST_PREV, df=True)

    # 可转债回售、转股、转股撤销，需要券商实盘环境，仿真回测不可用。
    # bond_convertible_call('SHSE.110051', 100, 0)
    # bond_convertible_put('SHSE.183350', 100, 0)
    # bond_convertible_put_cancel('SHSE.183350', 100)

    # 可转债下单，仅将symbol替换为可转债标的代码即可
    order_volume(symbol='SZSE.128041', volume=100, side=OrderSide_Buy, order_type=OrderType_Limit, position_effect=PositionEffect_Open, price=340)

    # 直接获取委托，可以看到相应的可转债委托，普通买卖通过标的体现可转债交易，转股、回售、回售撤销通过order_business字段的枚举值不同来体现。
    order_list = get_orders()

    # 订阅可转债行情。与股票无异
    subscribe(symbols='SHSE.113038', frequency='tick', count=2)

def on_tick(context, tick):
    # 打印频率为tick，可转债最新tick
    print(tick)

if __name__ == '__main__':
    run(strategy_id='strategy_id',
        filename='main.py',
        mode=MODE_LIVE,
        token='token_id',
        backtest_start_time='2020-12-16 09:00:00',
        backtest_end_time='2020-12-16 09:15:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001
        )
```


        策略程序架构

      →

---

## 数据结构

> https://www.myquant.cn/docs2/sdk/python/%E6%95%B0%E6%8D%AE%E7%BB%93%E6%9E%84.html

<!DOCTYPE html>




     数据结构 - 掘金量化












# #  数据结构



## #  数据类



### #  Tick - Tick 对象

  行情快照数据(包含盘口数据和当天动态日线数据)
     参数名
  类型
  说明

     symbol
  str
   标的代码

   open
  float
  日线开盘价

   high
  float
  日线最高价

   low
  float
  日线最低价

   price
  float
  最新价(集合竞价成交前price为0)

   cum_volume
  long
  最新总成交量,累计值（日线成交量）

   cum_amount
  float
  最新总成交额,累计值 （日线成交金额）

   cum_position
  int
  合约持仓量(只适用于期货),累计值（股票此值为 0）

   trade_type
  int
  交易类型（只适用于期货） 1: '双开', 2: '双平', 3: '多开', 4: '空开', 5: '空平', 6: '多平', 7: '多换', 8: '空换'

   last_volume
  int
  最新瞬时成交量

   last_amount
  float
  最新瞬时成交额（郑商所不支持）

   created_at
  datetime.datetime
  创建时间

   quotes
  [] (list of dict)
  股票提供买卖 5 档数据, list[0]~list[4]分别对应买卖一档到五档, 期货提供买卖 1 档数据, list[0]表示买卖一档；, level2 行情对应的是 list[0]~list[9]买卖一档到十档， 注意： ：可能会有买档或卖档报价缺失，比如跌停时无买档报价（bid_p 和 bid_v 为 0），涨停时无卖档报价(ask_p 和 ask_v 为 0); 其中每档报价 quote 结构如下：

   iopv
  float
  基金份额参考净值，(只适用于基金)




#### #  报价 quote  - (dict 类型)

     参数名
  类型
  说明

     bid_p
  float
  买价

   bid_v
  int
  买量

   ask_p
  float
  卖价

   ask_v
  int
  卖量

   bid_q
  dict
  委买队列 包含（total_orders （int）委托总个数, queue_volumes (list) 委托量队列），仅 level2 行情支持

   ask_q
  dict
  委卖队列 包含（total_orders （int）委托总个数, queue_volumes (list) 委托量队列），仅 level2 行情支持


   注意：
  1、tick 是分笔成交数据，股票频率为 3s, 期货为 0.5s, 指数 5s, 包含集合竞价数据，股票早盘集合竞价数为 09:15:00-09:25:00 的 tick 数据
  2、涨停时， 没有卖价和卖量， ask_p 和 ask_v 用 0 填充，跌停时，没有买价和买量，bid_p 和 bid_v 用 0 填充
  3、queue_volumes 委托量队列，只能获取到最优第一档的前 50 个委托量（不活跃标的可能会不足 50 个）


### #  Bar - Bar 对象

  bar 数据是指各种频率的行情数据
     参数名
  类型
  说明

     symbol
  str
   标的代码

   frequency
  str
  频率, 支持 'tick', '60s', '300s', '900s' 等, 默认'1d', 详情见 股票行情数据 和 期货行情数据 ,  实时行情支持的频率

   open
  float
  开盘价

   close
  float
  收盘价

   high
  float
  最高价

   low
  float
  最低价

   amount
  float
  成交额

   volume
  long
  成交量

   position
  long
  持仓量（仅期货）

   bob
  datetime.datetime
  bar 开始时间

   eob
  datetime.datetime
  bar 结束时间


   注意：
不活跃标的，没有成交量是不生成 bar


### #  L2Order - Level2 逐笔委托

     参数名
  类型
  说明

     symbol
  str
   标的代码

   side
  str
  委托方向 深市：'1'买， '2'卖， 'F'借入， 'G'出借， 沪市：'B'买，'S'卖

   price
  float
  委托价

   volume
  int
  委托量

   order_type
  str
  委托类型 深市：'1'市价， '2'限价， 'U'本方最优，沪市：'A'新增委托订单，'D'删除委托订单

   order_index
  int
  委托编号

   created_at
  datetime.datetime
  创建时间




### #  L2Transaction - Level2 逐笔成交

     参数名
  类型
  说明

     symbol
  str
   标的代码

   side
  str
  委托方向 沪市：B – 外盘,主动买, S – 内盘,主动卖, N – 集合竞价，深市无此字段

   price
  float
  成交价

   volume
  int
  成交量

   exec_type
  str
  成交类型 深市：'4'撤单，'F'成交 ，沪市不支持

   exec_index
  int
  成交编号

   ask_order_index
  int
  叫卖委托编号

   bid_order_index
  int
  叫买委托编号

   created_at
  datetime.datetime
  创建时间




## #  交易类



### #  Account - 账户对象

     属性
  类型
  说明

     id
  str
  账户 id，实盘时用于指定交易账户

   cash
  dict
   资金字典

   positions(symbol='', side=None)
  list
   持仓情况  列表, 默认全部持仓, 可根据单一 symbol（类型 str）, [side](/sdk/python/枚举常量.html#PositionSide - 持仓方向 "PositionSide - 持仓方向") 参数可缩小查询范围

   position(symbol, side)
  dict
   持仓情况  查询指定单一 symbol（类型 str）及持仓方向的持仓情况

   status
  dict
   交易账户状态  查询交易账户连接状态




### #  Order - 委托对象

     属性
  类型
  说明

     strategy_id
  str
  策略 ID

   account_id
  str
  账号 ID

   account_name
  str
  账户登录名

   cl_ord_id
  str
  委托客户端 ID，下单生成，固定不变（掘金维护，下单唯一标识）

   order_id
  str
  委托柜台 ID（系统字段，下单不会立刻生成，委托报到柜台才会生成）

   ex_ord_id
  str
  委托交易所 ID（系统字段，下单不会立刻生成，委托报到柜台才会生成）

   algo_order_id
  str
  算法单 ID

   symbol
  str
  标的代码

   status
  int
  委托状态 取值参考  OrderStatus

   side
  int
  买卖方向 取值参考  OrderSide

   position_effect
  int
  开平标志 取值参考  PositionEffect

   position_side
  int
  持仓方向 取值参考  PositionSide

   order_type
  int
  委托类型 取值参考  OrderType

   order_duration
  int
  委托时间属性

   order_qualifier
  int
  委托成交属性

   order_business
  int
  委托业务属性 取值参考  OrderBusiness

   order_style
  int
  委托风格属性 取值参考  OrderStyle

   ord_rej_reason
  int
  委托拒绝原因 取值参考  OrderRejectReason

   ord_rej_reason_detail
  str
  委托拒绝原因描述

   position_src
  int
  头寸来源（系统字段）

   volume
  int
  委托量

   price
  float
  委托价格

   value
  int
  委托额

   percent
  float
  委托百分比

   target_volume
  int
  委托目标量

   target_value
  int
  委托目标额

   target_percent
  float
  委托目标百分比

   filled_volume
  int
  已成量 （一笔委托对应多笔成交为累计值）

   filled_vwap
  float
  已成均价，公式为 (price*(1+backtest_slippage_ratio))  （期货实盘不支持）

   filled_amount
  float
  已成金额，公式为 (filled_volume*filled_vwap)  （期货实盘不支持）

   filled_commission
  float
  已成手续费，（实盘不支持）

   created_at
  datetime.datetime
  委托创建时间

   updated_at
  datetime.datetime
  委托更新时间

   origin_product
  str
  产品编码

   origin_module
  str
  委托来源，APPUI：终端界面下单，FILE：文件单，API：策略程序化下单，ALGO：算法服务自动委托




### #  ExecRpt - 回报对象

     属性
  类型
  说明

     strategy_id
  str
  策略 ID

   account_id
  str
  账号 ID

   account_name
  str
  账户登录名

   cl_ord_id
  str
  委托客户端 ID

   order_id
  str
  柜台委托 ID

   exec_id
  str
  交易所成交 ID

   symbol
  str
  委托标的

   side
  int
  买卖方向 取值参考  OrderSide

   position_effect
  int
  开平标志 取值参考  PositionEffect

   order_business
  int
  委托业务属性  OrderBusiness

   ord_rej_reason
  int
  委托拒绝原因 取值参考  OrderRejectReason

   ord_rej_reason_detail
  str
  委托拒绝原因描述

   exec_type
  int
  执行回报类型 取值参考  ExecType

   price
  float
  成交价格

   volume
  int
  成交量

   amount
  float
  成交金额

   cost
  float
  成交成本金额（仅期货实盘支持，股票实盘不支持）

   created_at
  datetime.datetime
  回报创建时间




### #  Cash - 资金对象

     属性
  类型
  说明

     account_id
  str
  账号 ID

   account_name
  str
  账户登录名

   currency
  int
  币种

   nav
  float
  总资产

   fpnl
  float
  浮动盈亏

   frozen
  float
  持仓占用资金 （仅期货实盘支持，股票实盘不支持）

   order_frozen
  float
  冻结资金

   available
  float
  可用资金

   market_value
  float
  市值

   balance
  float
  资金余额

   created_at
  datetime.datetime
  资金初始时间

   updated_at
  datetime.datetime
  资金变更时间




### #  Position - 持仓对象

     属性
  类型
  说明

     account_id
  str
  账号 ID

   account_name
  str
  账户登录名

   symbol
  str
  标的代码

   side
  int
  持仓方向 取值参考  PositionSide

   volume
  int
  总持仓量; 如果要得到昨持仓量，公式为  (volume - volume_today)

   volume_today
  int
  今日买入量

   market_value
  float
  持仓市值

   vwap
  float
  持仓均价  new_vwap=((position.vwap * position.volume)+(trade.volume*trade.price))/(position.volume+trade.volume)  （实盘时，期货跨天持仓，会自动变成昨结价，仿真是开仓均价）

   vwap_open
  float
  开仓均价（期货适用，实盘适用）

   vwap_diluted
  float
  摊薄成本（股票适用，实盘适用）

   amount
  float
  持仓额  (volume*vwap*multiplier)

   price
  float
  当前行情价格（回测时值为 0）

   fpnl
  float
  持仓浮动盈亏  ((price - vwap) * volume * multiplier)  （基于效率的考虑，回测模式 fpnl 只有仓位变化时或者一天更新一次,仿真模式 3s 更新一次, 回测的 price 为当天的收盘价） （根据持仓均价计算）

   fpnl_open
  float
  浮动盈亏（期货适用， 根据开仓均价计算）

   fpnl_diluted
  float
  摊薄浮动盈亏（股票适用，实盘适用）

   cost
  float
  持仓成本  (vwap * volume * multiplier * margin_ratio)

   order_frozen
  int
  挂单冻结仓位

   order_frozen_today
  int
  挂单冻结今仓仓位(仅上期所和上海能源交易所标的支持)

   available
  int
  非挂单冻结仓位 ，公式为 (volume - order_frozen) ; 如果要得到可平昨仓位，公式为  (available - available_today (仅适用于期货)

   available_today
  int
  非挂单冻结今仓位，公式为  (volume_today - order_frozen_today) (仅上期所和上海能源交易所标的支持)

   available_now
  int
  当前可用仓位

   credit_position_sellable_volume
  int
  可卖担保品数

   created_at
  datetime.datetime
  建仓时间 （实盘不支持）

   updated_at
  datetime.datetime
  仓位变更时间 （实盘不支持）




### #  Indicator - 绩效指标对象

     属性
  类型
  说明

     account_id
  str
  账号 ID

   pnl_ratio
  float
  累计收益率 (pnl/cum_inout)

   pnl_ratio_annual
  float
  年化收益率 (pnl_ratio/自然天数*365)

   sharp_ratio
  float
  夏普比率 （[E(Rp)-Rf]/δp*sqrt(250),E(Rp) = mean(pnl_ratio),Rf = 0,δp = std(pnl_ratio) )

   max_drawdown
  float
  最大回撤 max_drawdown=max（Di-Dj）/Di；D 为某一天的净值（j>i)

   risk_ratio
  float
  风险比率 （持仓市值/nav）

   calmar_ratio
  float
  卡玛比率 年化收益率/最大回撤

   open_count
  int
  开仓次数

   close_count
  int
  平仓次数

   win_count
  int
  盈利次数（平仓价格大于持仓均价 vwap 的次数）

   lose_count
  int
  亏损次数 （平仓价格小于或者等于持仓均价 vwap 的次数）

   win_ratio
  float
  胜率 (win_count / (win_count + lose_count))

   created_at
  datetime.datetime
  指标创建时间

   updated_at
  datetime.datetime
  指标变更时间




### #  algoOrder - 算法委托母单对象

     属性
  类型
  说明

     strategy_id
  str
  策略 ID

   account_id
  str
  账号 ID

   account_name
  str
  账户登录名

   cl_ord_id
  str
  委托客户端 ID，下单生成，固定不变（掘金维护，下单唯一标识）

   order_id
  str
  委托柜台 ID（系统字段，下单不会立刻生成，委托报到柜台才会生成）

   ex_ord_id
  str
  委托交易所 ID（系统字段，下单不会立刻生成，委托报到柜台才会生成）

   symbol
  str
  标的代码

   status
  int
  委托状态 取值参考  OrderStatus

   side
  int
  买卖方向 取值参考  OrderSide

   position_effect
  int
  开平标志 取值参考  PositionEffect

   position_side
  int
  持仓方向 取值参考  PositionSide

   order_type
  int
  委托类型 取值参考  OrderType

   order_duration
  int
  委托时间属性

   order_qualifier
  int
  委托成交属性

   order_business
  int
  委托业务属性 取值参考  OrderBusiness

   order_style
  int
  委托风格属性 取值参考  OrderStyle

   ord_rej_reason
  int
  委托拒绝原因 取值参考  OrderRejectReason

   ord_rej_reason_detail
  str
  委托拒绝原因描述

   position_src
  int
  头寸来源（系统字段）

   volume
  int
  委托量

   price
  float
  委托价格

   value
  int
  委托额

   percent
  float
  委托百分比

   target_volume
  int
  委托目标量

   target_value
  int
  委托目标额

   target_percent
  float
  委托目标百分比

   filled_volume
  int
  已成量 （一笔委托对应多笔成交为累计值）

   filled_vwap
  float
  已成均价，公式为 (price*(1+backtest_slippage_ratio))  （期货实盘不支持）

   filled_amount
  float
  已成金额，公式为 (filled_volume*filled_vwap)  （期货实盘不支持）

   filled_commission
  float
  已成手续费，（实盘不支持）

   created_at
  datetime.datetime
  委托创建时间

   updated_at
  datetime.datetime
  委托更新时间

   algo_name
  str
  算法名称

   algo_params
  dict
  算法参数

   algo_status
  int
  算法单状态 取值参考  AlgoOrderStatus

   algo_comment
  str
  算法单备注

   origin_product
  str
  产品编码

   origin_module
  str
  委托来源，APPUI：终端界面下单，FILE：文件单，API：策略程序化下单，ALGO：算法服务自动委托




      ←

        变量约定

        基本函数

      →

---

## 枚举常量

> https://www.myquant.cn/docs2/sdk/python/%E6%9E%9A%E4%B8%BE%E5%B8%B8%E9%87%8F.html

<!DOCTYPE html>




     枚举常量 - 掘金量化












# #  枚举常量



## #  OrderStatus委托状态



```
OrderStatus_New = 1                   # 已报
OrderStatus_PartiallyFilled = 2       # 部成
OrderStatus_Filled = 3                # 已成
OrderStatus_Canceled = 5              # 已撤
OrderStatus_Rejected = 8              # 已拒绝
OrderStatus_PendingNew = 10           # 待报
OrderStatus_Expired = 12              # 已过期
OrderStatus_PendingTrigger = 15       # 待触发, CTP条件单
OrderStatus_Triggered = 16            # 已触发, CTP条件单
```

## #  OrderSide委托方向



```
OrderSide_Buy = 1             # 买入
OrderSide_Sell = 2            # 卖出
```

## #  OrderType委托类型



```
用于映射OrderDuration和OrderQualifier的参数组合，推荐下单时直接指定OrderType，可无需额外指定OrderDuration和OrderQualifier

OrderType_Limit = 1            # 限价委托 (全部交易所支持)
OrderType_Market = 2           # 市价委托 （上期所和上能所不支持，中金所远期合约不支持，可转债不支持，上交所需要填上price保护限价）

# 终端3.18.0.0以上新增
# 上交所
OrderType_Limit = 1	       # 限价
OrderType_Market = 2	   # 市价(默认五档即成转限)
OrderType_Market_BOC = 20  # 市价对方最优价格(best of counterparty)
OrderType_Market_BOP = 21  # 市价己方最优价格(best of party)
OrderType_Market_B5TC = 24 # 市价最优五档剩余撤销(best 5 then cancel)
OrderType_Market_B5TL = 25 # 市价最优五档剩余转限价(best 5 then limit)

# 深交所
OrderType_Limit = 1	       # 限价
OrderType_Market = 2	   # 市价（默认对方最优价）
OrderType_Market_BOC = 20  # 市价对方最优价格(best of counterparty)
OrderType_Market_BOP = 21  # 市价己方最优价格(best of party)
OrderType_Market_FAK = 22  # 市价即时成交剩余撤销(fill and kill)
OrderType_Market_FOK = 23  # 市价即时全额成交或撤销(fill or kill)
OrderType_Market_B5TC = 24 # 市价最优五档剩余撤销(best 5 then cancel)

# 大商所
OrderType_Limit = 1	        # 限价
OrderType_Limit_FAK = 10	# 限价即时成交剩余撤销 (fill and kill)
OrderType_Limit_FOK = 11	# 限价即时全额成交或撤销 (fill or kill)
OrderType_Market = 2	    # 市价
OrderType_Market_FAK = 22	# 市价即时成交剩余撤销(fill and kill)
OrderType_Market_FOK = 23	# 市价即时全额成交或撤销(fill or kill)

# 郑商所
OrderType_Limit = 1	        # 限价
OrderType_Market = 2	    # 市价
OrderType_Market_FOK = 23	# 市价即时全额成交或撤销(fill or kill)

# 上期所和上能所
OrderType_Limit = 1	        # 限价
OrderType_Limit_FAK = 10	# 限价即时成交剩余撤销 (fill and kill)
OrderType_Limit_FOK = 11	# 限价即时全额成交或撤销 (fill or kill)

# 中金所
OrderType_Limit = 1	        # 限价
OrderType_Limit_FAK = 10	# 限价即时成交剩余撤销 (fill and kill)
OrderType_Limit_FOK = 11	# 限价即时全额成交或撤销 (fill or kill)
OrderType_Market_B5TC = 24	# 市价最优五档剩余撤销(best 5 then cancel)
OrderType_Market_B5TL = 25	# 市价最优五档剩余转限价(best 5 then limit)
OrderType_Market_BOPC = 27	# 市价最优价即时成交剩余撤销(best of price then cancel)
OrderType_Market_BOPL = 28  # 市价最优价即时成交剩余转限价(best of price then limit)

# 广期所
OrderType_Limit = 1	        # 限价
OrderType_Limit_FAK = 10	# 限价即时成交剩余撤销 (fill and kill)
OrderType_Limit_FOK = 11	# 限价即时全额成交或撤销 (fill or kill)
OrderType_Market = 2	    # 市价
OrderType_Market_FAK = 22	# 市价即时成交剩余撤销(fill and kill)
OrderType_Market_FOK = 23	# 市价即时全额成交或撤销(fill or kill)
```

## #  OrderBusiness委托业务类型

  用于映射OrderSide和PositionEffect的参数组合，新增业务类型


```
OrderBusiness_NORMAL = 0                        # 普通交易。默认值为空，以保持向前兼容

OrderBusiness_STOCK_BUY = 1                     # 股票,基金,可转债买入（映射OrderSide_Buy和PositionEffect_Open）
OrderBusiness_STOCK_SELL = 2	                # 股票,基金,可转债卖出（映射OrderSide_Buy和PositionEffect_Close）

OrderBusiness_FUTURE_BUY_OPEN = 10              # 期货买入开仓（映射OrderSide_Buy和PositionEffect_Open）
OrderBusiness_FUTURE_SELL_CLOSE = 11	        # 期货卖出平仓（映射OrderSide_Sell和PositionEffect_Close）
OrderBusiness_FUTURE_SELL_CLOSE_TODAY = 12      # 期货卖出平仓，优先平今（映射OrderSide_Sell和PositionEffect_CloseToday）
OrderBusiness_FUTURE_SELL_CLOSE_YESTERDAY = 13	# 期货卖出平仓，优先平昨（映射OrderSide_Sell和PositionEffect_CloseYesterday）
OrderBusiness_FUTURE_SELL_OPEN = 14             # 期货卖出开仓（映射OrderSide_Sell和PositionEffect_Open）
OrderBusiness_FUTURE_BUY_CLOSE = 15 	        # 期货买入平仓（映射OrderSide_Buy和PositionEffect_Close）
OrderBusiness_FUTURE_BUY_CLOSE_TODAY = 16       # 期货买入平仓，优先平今（映射OrderSide_Buy和PositionEffect_CloseToday）
OrderBusiness_FUTURE_BUY_CLOSE_YESTERDAY = 17	# 期货买入平仓，优先平昨（映射OrderSide_Buy和PositionEffect_CloseYesterday）

OrderBusiness_FUTURE_CTP_CONDITIONAL_ORDER = 18                # CTP条件单

OrderBusiness_IPO_BUY = 100                     # 新股申购	100

OrderBusiness_CREDIT_BOM = 200                  # 融资买入(buying on margin)
OrderBusiness_CREDIT_SS = 201                   # 融券卖出(short selling)
OrderBusiness_CREDIT_RSBBS = 202                # 买券还券(repay share by buying share)
OrderBusiness_CREDIT_RCBSS = 203                # 卖券还款(repay cash by selling share)
OrderBusiness_CREDIT_DRS = 204                  # 直接还券(directly repay share)

OrderBusiness_CREDIT_BOC = 207                  # 担保品买入(buying on collateral)
OrderBusiness_CREDIT_SOC = 208                  # 担保品卖出(selling on collateral)
OrderBusiness_CREDIT_CI = 209                   # 担保品转入(collateral in)
OrderBusiness_CREDIT_CO = 210                   # 担保品转出(collateral out)
OrderBusiness_CREDIT_DRC = 211	                # 直接还款(directly repay cash)

OrderBusiness_ETF_BUY = 301                     # ETF申购(purchase)
OrderBusiness_ETF_RED = 302                     # ETF赎回(redemption)
OrderBusiness_FUND_SUB = 303	                # 基金认购(subscribing)
OrderBusiness_FUND_BUY = 304	                # 基金申购(purchase)
OrderBusiness_FUND_RED = 305	                # 基金赎回(redemption)
OrderBusiness_FUND_CONVERT = 306                # 基金转换(convert)
OrderBusiness_FUND_SPLIT = 307 	                # 基金分拆(split)
OrderBusiness_FUND_MERGE = 308	                # 基金合并(merge)

OrderBusiness_BOND_RRP = 400 	                # 债券逆回购
OrderBusiness_BOND_CONVERTIBLE_BUY = 401        # 可转债申购(purchase)
OrderBusiness_BOND_CONVERTIBLE_CALL = 402       # 可转债转股
OrderBusiness_BOND_CONVERTIBLE_PUT = 403        # 可转债回售
OrderBusiness_BOND_CONVERTIBLE_PUT_CANCEL = 404	# 可转债回售撤销

OrderBusiness_OPTION_BUY_OPEN = 500             # 期权买入开仓（映射OrderSide_Buy和PositionEffect_Open）
OrderBusiness_OPTION_SELL_CLOSE = 501	        # 期权卖出平仓（映射OrderSide_Sell和PositionEffect_Open）
OrderBusiness_OPTION_SELL_OPEN = 502	        # 期权卖出开仓（映射OrderSide_Sell和PositionEffect_Open）
OrderBusiness_OPTION_BUY_CLOSE = 503	        # 期权买入平仓（映射OrderSide_Buy和PositionEffect_Close）
OrderBusiness_OPTION_COVERED_SELL_OPEN = 504	# 期权备兑开仓(备兑卖出开仓，只适用认购合约)
OrderBusiness_OPTION_COVERED_BUY_CLOSE = 505	# 期权备兑平仓(备兑买入平仓，只适用认购合约)
OrderBusiness_OPTION_EXERCISE = 506             # 期权行权
```

## #  OrderTriggerType期货CTP条件单触发方式



```
# 期货条件单触发方式
OrderTriggerType_Unknown = 0        # 普通单
OrderTriggerType_LastPriceGreaterThanStopPrice = 1        # 条件单，触发条件：最新价大于条件价
OrderTriggerType_LastPriceGreaterEqualStopPrice = 2        # 条件单，触发条件：最新价大于等于条件价
OrderTriggerType_LastPriceLessThanStopPrice = 3        # 条件单，触发条件：最新价小于条件价
OrderTriggerType_LastPriceLessEqualStopPrice = 4        # 条件单，触发条件：最新价小于等于条件价
OrderTriggerType_AskPriceGreaterThanStopPrice = 5        # 条件单，触发条件：卖一价大于条件价
OrderTriggerType_AskPriceGreaterEqualStopPrice = 6        # 条件单，触发条件：卖一价大于等于条件价
OrderTriggerType_AskPriceLessThanStopPrice = 7        # 条件单，触发条件：卖一价小于条件价
OrderTriggerType_AskPriceLessEqualStopPrice = 8        # 条件单，触发条件：卖一价小于等于条件价
OrderTriggerType_BidPriceGreaterThanStopPrice = 9        # 条件单，触发条件：买一价大于条件价
OrderTriggerType_BidPriceGreaterEqualStopPrice = 10        # 条件单，触发条件：买一价大于等于条件价
OrderTriggerType_BidPriceLessThanStopPrice = 11        # 条件单，触发条件：买一价小于条件价
OrderTriggerType_BidPriceLessEqualStopPrice = 12        # 条件单，触发条件：买一价小于等于条件价
```

## #  ExecType执行回报类型



```
ExecType_Trade = 15                            # 成交
ExecType_CancelRejected = 19                   # 撤单被拒绝
```

## #  PositionEffect开平仓类型



```
PositionEffect_Open = 1                        # 开仓
PositionEffect_Close = 2                       # 平仓, 具体语义取决于对应的交易所（实盘上期所和上海能源所不适用，上期所和上海能源所严格区分平今平昨，需要用3和4）
PositionEffect_CloseToday = 3                  # 平今仓
PositionEffect_CloseYesterday = 4              # 平昨仓(只适用于期货，不适用股票，股票用2平仓)
```

## #  PositionSide持仓方向



```
PositionSide_Long = 1                        # 多方向
PositionSide_Short = 2                       # 空方向
```

## #  OrderRejectReason订单拒绝原因

  （仿真有效，实盘需要参考具体的拒绝原因）


```
OrderRejectReason_Unknown = 0                          # 未知原因
OrderRejectReason_RiskRuleCheckFailed = 1              # 不符合风控规则
OrderRejectReason_NoEnoughCash = 2                     # 资金不足
OrderRejectReason_NoEnoughPosition = 3                 # 仓位不足
OrderRejectReason_IllegalAccountId = 4                 # 非法账户ID
OrderRejectReason_IllegalStrategyId = 5                # 非法策略ID
OrderRejectReason_IllegalSymbol = 6                    # 非法交易标的
OrderRejectReason_IllegalVolume = 7                    # 非法委托量
OrderRejectReason_IllegalPrice = 8                     # 非法委托价
OrderRejectReason_AccountDisabled = 10                 # 交易账号被禁止交易
OrderRejectReason_AccountDisconnected = 11             # 交易账号未连接
OrderRejectReason_AccountLoggedout = 12                # 交易账号未登录
OrderRejectReason_NotInTradingSession = 13             # 非交易时段
OrderRejectReason_OrderTypeNotSupported = 14           # 委托类型不支持
OrderRejectReason_Throttle = 15                        # 流控限制
```

## #  CancelOrderRejectReason取消订单拒绝原因



```
CancelOrderRejectReason_OrderFinalized = 101           # 委托已完成
CancelOrderRejectReason_UnknownOrder = 102             # 未知委托
CancelOrderRejectReason_BrokerOption = 103             # 柜台设置
CancelOrderRejectReason_AlreadyInPendingCancel = 104   # 委托撤销中
```

## #  OrderStyle委托风格



```
OrderStyle_Unknown = 0
OrderStyle_Volume = 1                                  # 按指定量委托
OrderStyle_Value = 2                                   # 按指定价值委托
OrderStyle_Percent = 3                                 # 按指定比例委托
OrderStyle_TargetVolume = 4                            # 调仓到目标持仓量
OrderStyle_TargetValue = 5                             # 调仓到目标持仓额
OrderStyle_TargetPercent = 6                           # 调仓到目标持仓比例
```

## #  CashPositionChangeReason仓位变更原因



```
CashPositionChangeReason_Trade = 1            # 交易
CashPositionChangeReason_Inout = 2            # 出入金 / 出入持仓
```

## #  SecType标的类别



```
SEC_TYPE_STOCK = 1                          # 股票
SEC_TYPE_FUND = 2                           # 基金
SEC_TYPE_INDEX = 3                          # 指数
SEC_TYPE_FUTURE = 4                         # 期货
SEC_TYPE_OPTION = 5                         # 期权
SEC_TYPE_CREDIT = 6                         # 信用交易
SEC_TYPE_BOND = 7                           # 债券
SEC_TYPE_BOND_CONVERTIBLE = 8               # 可转债
SEC_TYPE_CONFUTURE = 10                     # 期货连续合约
```

## #  AccountStatus交易账户状态



```
State_CONNECTING = 1                     # 连接中
State_CONNECTED = 2                      # 已连接
State_LOGGEDIN = 3                       # 已登录
State_DISCONNECTING = 4                  # 断开中
State_DISCONNECTED = 5                   # 已断开
State_ERROR = 6                          # 错误
```

## #  PositionSrc头寸来源(仅适用融券)



```
PositionSrc_L1 = 1                      # 普通池
PositionSrc_L2 = 2                      # 专项池
```

## #  AlgoOrderStatus算法单状态,暂停/恢复算法单时有效



```
AlgoOrderStatus_Resume = 1                   # 恢复母单
AlgoOrderStatus_Pause = 2                    # 暂停母单
AlgoOrderStatus_PauseAndCancelSubOrders = 3  # 暂停母单并撤子单
```


      ←

        其他事件

        错误码

      →

---

## 策略程序架构

> https://www.myquant.cn/docs2/sdk/python/%E7%AD%96%E7%95%A5%E7%A8%8B%E5%BA%8F%E6%9E%B6%E6%9E%84.html

<!DOCTYPE html>




     策略程序架构 - 掘金量化












# #  策略程序架构



## #  掘金策略程序初始化

  通过 init 函数 初始化策略,策略启动即会自动执行。在 init 函数中可以：
    定义全局变量
通过添加 context 包含的属性可以定义全局变量，如 context.x,该属性可以在全文中进行传递。

   定义调度任务
可以通过 schedule 配置定时任务，程序在指定时间自动执行策略算法。

   准备历史数据
通过 数据查询函数 获取历史数据

   订阅实时行情
通过 subscribe 订阅行情，用以触发行情事件处理函数。



## #  行情事件处理函数

   处理盘口 tick 数据事件
通过 on_tick 响应 tick 数据事件，可以在该函数中继续添加自己的策略逻辑,如进行数据计算、交易等
  处理分时 bar 数据事件
通过 on_bar 响应 bar 数据事件，可以在该函数中继续添加自己的策略逻辑，如进行数据计算、交易等



## #  交易事件处理函数

    处理回报 execrpt 数据事件
当交易委托被执行后会触发 on_execution_report ，用于监测 委托执行状态 .

   处理委托 order 委托状态变化数据事件
当 订单状态 产生变化时会触发 on_order_status ，用于监测 委托状态 变更.

   处理账户 account 交易账户状态变化数据事件
当 交易账户状态 产生变化时会触发 on_account_status ，用于监测 交易账户委托状态 变更.



## #  其他事件处理函数

    处理 error 错误事件
当发生异常情况时触发 错误事件 ，并返回 错误码和错误信息

   处理动态参数 parameter 动态参数修改事件
当 动态参数 产生变化时会触发 on_parameter ，用于监测动态参数修改.

   处理绩效指标对象 Indicator 回测结束事件
在回测模式下，回测结束后会触发 on_backtest_finished ，并返回回测得到的 绩效指标对象 .

   处理实时行情网络连接成功事件
当实时行情网络连接成功时触发 实时行情网络连接成功事件 .

   处理实时行情网络连接断开事件
当实时行情网络连接断开时触发 实时行情网络连接断开事件 .

   处理交易通道网络连接成功事件
当交易通道网络连接成功时触发 交易通道网络连接成功事件 .

   处理交易通道网络连接断开事件
当交易通道网络连接断开时触发 交易通道网络连接断开事件 .



## #  策略入口

   run 函数 用于启动策略，策略类交易类策略都需要 run 函数。在只需提取数据进行研究（即仅使用数据查询函数时）的情况下可以不调用 run 函数，在策略开始调用 set_token 即可
    用户 token ID
用户身份的唯一标识，token 位置参见终端-系统设置界面-密钥管理（token）

   策略 ID strategy_id
策略文件与终端连接的纽带，是策略的身份标识。每创建一个策略都会对应生成一个策略 id，创建策略时即可看到。

   策略工作模式
策略支持两种运行 模式 , 实时模式和回测模式,实时模式用于仿真交易及实盘交易，回测模式用于策略研究，用户需要在运行策略时选择模式.


      ←

        快速开始

        变量约定

      →

---

## 错误码

> https://www.myquant.cn/docs2/sdk/python/%E9%94%99%E8%AF%AF%E7%A0%81.html

<!DOCTYPE html>




     错误码 - 掘金量化












# #  错误码

     错误码
  描述
  解决方法

     0
  成功


   1000
  错误或无效的 token
  检查下 token 是否有误

   1001
  无法连接到终端服务
  检查是否开启了掘金终端

   1010
  无法获取掘金服务器地址列表
  检查是否开启了掘金终端

   1013
  交易服务调用错误
  检查终端是否正常或重启掘金终端

   1014
  历史行情服务调用错误
  在微信群或者 QQ 群通知技术支持

   1015
  策略服务调用错误
  检查终端是否正常或重启掘金终端

   1016
  动态参数调用错误
  检查 动态参数 设置

   1017
  基本面数据服务调用错误
  在微信群或者 QQ 群通知技术支持

   1018
  回测服务调用错误
  重启掘金终端、重新运行策略

   1019
  交易网关服务调用错误
  检查终端是否正常或重启掘金终端

   1020
  无效的 ACCOUNT_ID
  检查账户 id 是否填写正确

   1021
  非法日期格式
  对照帮助文档修改日期格式， 检查 run()回测日期是否正确

   1025
  无法连接到认证服务
  在微信群或者 QQ 群通知技术支持

   1026
  更新令牌错误
  在微信群或者 QQ 群通知技术支持

   1027
  接口调用错误，无效入参
  例如检查定时任务的频率参数，实时模式只支持 1d

   1028
  不支持的服务
  在微信群或者 QQ 群通知技术支持

   1029
  超出最大限制设置
  检查入参的标的个数和时间范围

   1100
  交易消息服务连接失败
  检查终端是否正常或重启掘金终端

   1101
  交易消息服务断开
  一般不用处理，等待自动重连

   1200
  实时行情服务连接失败
  一般不用处理，等待自动重连

   1201
  实时行情服务连接断开
  一般不用处理，等待自动重连

   1202
  实时行情订阅失败
  订阅代码标的数量超过账户权限，联系商务咨询权限

   1300
  初始化回测失败
  检查终端是否启动或策略是否连接到终端

   1301
  回测时间区间错误
  检查回测时间是否超出范围

   1302
  回测读取缓存数据错误
  在微信群或者 QQ 群通知技术支持

   1303
  回测写入缓存数据错误
  在微信群或者 QQ 群通知技术支持

   2001
  用户无此数据接口权限
  联系商务咨询权限

   2002
  超出业务授权范围
  调整数据日期范围，或者联系商务延长权限

   2003
  实时行情订阅代码数量超过用户权限
  联系商务咨询权限

   3001
  超出数据接口调用频率限制（流控）
  检查程序是否异常运行导致循环取数，增加等待时间再调用




      ←

        枚举常量

        快速开始

      →

---

## 两融交易函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E4%B8%A4%E8%9E%8D%E4%BA%A4%E6%98%93%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     两融交易函数 - 掘金量化












# #  两融交易函数

  python 两融 SDK 包含在 gm3.0.126 版本及以上版本，不需要引入新库
融资融券暂时仅支持实盘委托，不支持仿真交易


## #   credit_buying_on_margin  - 融资买入

   函数原型：


```
credit_buying_on_margin(position_src, symbol, volume, price, order_type=OrderType_Limit, order_duration=OrderDuration_Unknown,
                            order_qualifier=OrderQualifier_Unknown, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   price
  float
  价格

   position_src
  int
  头寸来源 取值参考  PositionSrc

   order_type
  int
  委托类型 取值参考  OrderType

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值：
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_buying_on_margin(position_src=PositionSrc_L1, symbol='SHSE.600000', volume=100, price=10.67)
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status price volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ----- ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b853062-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     10.67 100    datetime.datetime(2020, 6, 6, 15, 41, 44, 863549, tzinfo=tzfile('PRC')) 200                                                          0    0               0              0             0               0         0                                    0          0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
```

## #   credit_short_selling  - 融券卖出

   函数原型：


```
credit_short_selling(position_src, symbol, volume, price, order_type=OrderType_Limit, order_duration=OrderDuration_Unknown,
                         order_qualifier=OrderQualifier_Unknown, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   price
  float
  价格

   position_src
  int
  头寸来源 取值参考  PositionSrc

   order_type
  int
  委托类型 取值参考  OrderType

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值：
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_short_selling(position_src=PositionSrc_L1, symbol='SHSE.600000', volume=100, price=10.67, order_type=OrderType_Limit,
                               order_duration=OrderDuration_Unknown,
                               order_qualifier=OrderQualifier_Unknown, account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status price volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ----- ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b853062-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     10.67 100    datetime.datetime(2020, 6, 6, 15, 41, 44, 863549, tzinfo=tzfile('PRC')) 201                                                          0    0               0              0             0               0         0                                    0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
```

## #   credit_repay_cash_directly  - 直接还款

   函数原型：


```
credit_repay_cash_directly(amount, *, repay_type=0, position_src=PositionSrc_Unknown, contract_id=None, account_id="", sno="", bond_fee_only=False,
)
```

  参数：
     参数名
  类型
  说明

     amount
  float
  还款金额

   repay_type
  int
  0：正常还款（默认）,1：只还利息（如果柜台不支持，设置repay_type=1只还利息委托会被拒绝）

   position_src
  int
  头寸来源 取值参考  PositionSrc

   contract_id
  int
  指定合约编号，用于指定合约的直接还款，默认按负债顺序还款，华鑫柜台必填，顶点/金证/恒生柜台非必填

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值： dict
     字段
  类型
  说明

     actual_repay_amount
  float
  实际还款金额

   account_id
  str
  账号 id

   account_name
  str
  账户名称


   示例代码：


```
credit_repay_cash_directly(amount=10000.00, account_id='')
```

  示例返回值：


```
actual_repay_amount account_id                           account_name
------------------- ------------------------------------ ------------
10000.0             8f30e83f-a7c5-11ea-b510-309c231d28bd 001515018318
```

## #   credit_repay_share_directly  - 直接还券

   函数原型：


```
credit_repay_share_directly(symbol, volume, *, position_src=PositionSrc_Unknown, contract_id=None, account_id="", sno="")
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   position_src
  int
  头寸来源 取值参考  PositionSrc

   contract_id
  int
  指定合约编号，用于指定合约的直接还款，默认按负债顺序还款，华鑫柜台必填，顶点/金证/恒生柜台非必填

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值： [dict]
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_repay_share_directly(symbol='SHSE.600000', volume=100, account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail price stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ----- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b86685e-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     100    datetime.datetime(2020, 6, 6, 15, 41, 44, 871536, tzinfo=tzfile('PRC')) 204                                                          0    0               0             0              0               0         0                                    0.0   0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
........ ......
```

## #   credit_get_collateral_instruments  - 查询担保证券

  查询担保证券，可做担保品的股票列表
   函数原型：


```
credit_get_collateral_instruments(account_id='', df=False)
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号

   df
  bool
  是否返回 dataframe 格式数据。默认 False, 返回 list[dict]


   返回值：
     字段
  类型
  说明

     symbol
  str
  标的

   pledge_rate
  float
  折算率


   示例代码


```
credit_get_collateral_instruments(account_id='', df=False)
```

  示例返回值


```
symbol      pledge_rate
----------- -----------
SHSE.010107  0.9
SHSE.010303  0.9
..........   ...
```

## #   credit_get_borrowable_instruments  - 查询可融标的证券

  查询标的证券，可做融券标的的股票列表
   函数原型：


```
credit_get_borrowable_instruments(position_src, account_id='', df=False)
```

  参数：
     参数名
  类型
  说明

     position_src
  int
  头寸来源 取值参考  PositionSrc

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号

   df
  bool
  是否返回 dataframe 格式数据。默认 False, 返回 list[dict]


   返回值： list[dict]
     字段
  类型
  说明

     symbol
  str
  标的

   margin_rate_for_cash
  float
  融资保证金比率

   margin_rate_for_security
  float
  融券保证金比率


   示例代码


```
credit_get_borrowable_instruments(position_src=PositionSrc_L1, account_id='', df=False)
```

  示例返回值


```
symbol      margin_rate_for_cash margin_rate_for_security
----------- -------------------- ------------------------
SHSE.510050  1.0                  0.6
SHSE.510160  1.0                  0.6
...........  ...                  ...
```

## #   credit_get_borrowable_instruments_positions  - 查询券商融券账户头寸

  查询券商融券账户头寸，可用融券的数量
   函数原型：


```
credit_get_borrowable_instruments_positions(position_src, account_id='', df=False)
```

  参数：
     参数名
  类型
  说明

     position_src
  int
  头寸来源 取值参考  PositionSrc

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号

   df
  bool
  是否返回 dataframe 格式数据。默认 False, 返回 list[dict]


   返回值：
当 df = True 时， 返回 dataframe
当 df = False 时， 返回 list[dict]
     字段
  类型
  说明

     symbol
  str
  标的

   balance
  float
  证券余额

   available
  float
  证券可用金额


   示例代码


```
credit_get_borrowable_instruments_positions(position_src=PositionSrc_L1, account_id='', df=False)
```

  示例返回值


```
symbol      balance available
----------- ------- -----------
SHSE.600166  700.0   700.0
SHSE.688002  2000.0  2000.0
..........   ......  ......
```

## #   credit_get_contracts  - 查询融资融券合约

   函数原型：


```
credit_get_contracts(position_src, account_id='', df=False)
```

  参数：
     参数名
  类型
  说明

     position_src
  int
  头寸来源 取值参考  PositionSrc

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号

   df
  bool
  是否返回 dataframe 格式数据。默认 False, 返回 list[dict]


   返回值：
当 df = True 时， 返回 dataframe
当 df = False 时， 返回 list[dict]
     字段
  类型
  说明

     symbol
  str
  标的

   ordersno
  str
  委 托 号

   creditdirect
  str
  融资融券方向， '0'表示融资， '1'表示融券

   orderqty
  float
  委托数量

   matchqty
  float
  成交数量

   orderamt
  float
  委托金额

   orderfrzamt
  float
  委托冻结金额

   matchamt
  float
  成交金额

   clearamt
  float
  清算金额

   lifestatus
  str
  合约状态

   creditrepay
  float
  T 日之前归还金额

   creditrepayunfrz
  float
  T 日归还金额

   fundremain
  float
  应还金额

   stkrepay
  float
  T 日之前归还数量

   stkrepayunfrz
  float
  T 日归还数量

   stkremain
  float
  应还证券数量

   stkremainvalue
  float
  应还证券市值

   fee
  float
  融资融券息、费

   overduefee
  float
  逾期未偿还息、费

   fee_repay
  float
  己偿还息、费

   punifee
  float
  利息产生的罚息

   punifee_repay
  float
  己偿还罚息

   rights
  float
  未偿还权益金额

   overduerights
  float
  逾期未偿还权益

   rights_repay
  float
  己偿还权益

   lastprice
  float
  最新价

   profitcost
  float
  浮动盈亏

   sno
  str
  合约编号

   punidebts
  float
  逾期本金罚息

   punidebts_repay
  float
  本金罚息偿还

   punidebtsunfrz
  float
  逾期本金罚息

   punifeeunfrz
  float
  逾期息费罚息

   punirights
  float
  逾期权益罚息

   punirights_repay
  float
  权益罚息偿还

   punirightsunfrz
  float
  逾期权益罚息

   feeunfrz
  float
  实时偿还利息

   overduefeeunfrz
  float
  实时偿还逾期利息

   rightsqty
  float
  未偿还权益数量

   overduerightsqty
  float
  逾期未偿还权益数量

   orderdate
  int
  委托日期，时间戳类型

   lastdate
  int
  最后一次计算息费日期，时间戳类型

   closedate
  int
  合约全部偿还日期，时间戳类型

   sysdate
  int
  系统日期，时间戳类型

   enddate
  int
  负债截止日期，时间戳类型

   oldenddate
  int
  原始的负债截止日期，时间戳类型


   示例代码


```
credit_get_contracts(position_src=PositionSrc_L1, account_id='', df=False)
```

  示例返回值


```
symbol      ordersno creditdirect orderqty matchamt clearamt lifestatus enddate  fundremain fee   rights    profitcost sno      rightsqty orderdate matchqty orderamt orderfrzamt oldenddate creditrepay creditrepayunfrz stkrepay stkrepayunfrz stkremain stkremainvalue overduefee fee_repay punifee punifee_repay overduerights rights_repay lastprice sysdate lastdate closedate punidebts punidebts_repay punidebtsunfrz punifeeunfrz punirights punirights_repay punirightsunfrz feeunfrz overduefeeunfrz overduerightsqty
----------- -------- ------------ -------- -------- -------- ---------- -------- ---------- ----- --------- ---------- -------- --------- --------- -------- -------- ----------- ---------- ----------- ---------------- -------- ------------- --------- -------------- ---------- --------- ------- ------------- ------------- ------------ --------- ------- -------- --------- --------- --------------- -------------- ------------ ---------- ---------------- --------------- -------- --------------- ----------------
SZSE.159937 115906   0            59600.0  217957.2 217957.2 0          20200823 220666.32  32.69 220666.32 11112.52   15211131 59600.0   0         0.0      0.0      0.0         0          0.0         0.0              0.0      0.0           0.0       0.0            0.0        0.0       0.0     0.0           0.0           0.0          0.0       0.0     0.0      0.0       0.0       0.0             0.0            0.0          0.0        0.0              0.0             0.0      0.0             0.0
........... ......
```

## #   credit_get_cash  - 查询融资融券资金

   函数原型：


```
credit_get_cash(account_id='')
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值： dict
     字段
  类型
  名称

     fundintrrate
  float
  融资利率

   stkintrrate
  float
  融券利率

   punishintrrate
  float
  罚息利率

   creditstatus
  str
  信用状态

   marginrates
  float
  维持担保比例

   realrate
  float
  实时担保比例

   asset
  float
  总资产

   liability
  float
  总负债

   marginavl
  float
  保证金可用数

   fundbal
  float
  资金余额

   fundavl
  float
  资金可用数

   dsaleamtbal
  float
  融券卖出所得资金

   guaranteeout
  float
  可转出担保资产

   gagemktavl
  float
  担保证券市值

   fdealavl
  float
  融资本金

   ffee
  float
  融资息费

   ftotaldebts
  float
  融资负债合计

   dealfmktavl
  float
  应付融券市值

   dfee
  float
  融券息费

   dtotaldebts
  float
  融券负债合计

   fcreditbal
  float
  融资授信额度

   fcreditavl
  float
  融资可用额度

   fcreditfrz
  float
  融资额度冻结

   dcreditbal
  float
  融券授信额度

   dcreditavl
  float
  融券授信额度

   dcreditfrz
  float
  融券额度冻结

   rights
  float
  红利权益

   serviceuncomerqrights
  float
  红利权益(在途)

   rightsqty
  float
  红股权益

   serviceuncomerqrightsqty
  float
  红股权益(在途)

   acreditbal
  float
  总额度

   acreditavl
  float
  总可用额度

   acashcapital
  float
  所有现金资产（所有资产、包括融券卖出）

   astkmktvalue
  float
  所有证券市值（包含融资买入、非担保品）

   withdrawable
  float
  可取资金

   netcapital
  float
  净资产

   fcreditpnl
  float
  融资盈亏

   dcreditpnl
  float
  融券盈亏

   fcreditmarginoccupied
  float
  融资占用保证金

   dcreditmarginoccupied
  float
  融券占用保证金

   collateralbuyableamt
  float
  可买担保品资金

   repayableamt
  float
  可还款金额

   dcreditcashavl
  float
  融券可用资金


   示例代码


```
credit_get_cash(account_id='')
```

  示例返回值


```
marginrates realrate asset         liability  marginavl         fundbal       fundavl       guaranteeout gagemktavl  fdealavl   ffee   ftotaldebts dfee fcreditbal fcreditavl         dcreditbal dcreditavl acreditbal acreditavl  account_id                           account_name     rid                                  fundintrrate  stkintrrate punishintrrate creditstatus dsaleamtbal dealfmktavl dtotaldebts fcreditfrz dcreditfrz   rights    serviceuncomerqrights rightsqty serviceuncomerqrightsqty acashcapital astkmktvalue withdrawable netcapital fcreditpnl dcreditpnl fcreditmarginoccupied dcreditmarginoccupied collateralbuyableamt repayableamt dcreditcashavl
----------- -------- ------------- ---------- ----------------- ------------- ------------- ------------ ----------- ---------- ------ ----------- ---- ---------- ------------------ ---------- ---------- ---------- ----------- ------------------------------------ ---------------- ------------------------------------ ------------- ----------- -------------- ------------ ----------- ----------- ----------- ---------- ------------ --------- --------------------- --------- ------------------------ ------------ ------------ ------------ ---------- ---------- ---------- --------------------- --------------------- -------------------- ------------ --------------
229.5157    229.5157 1001926287.62 4356531.11 1994995956.360447 1002066280.62 2002149925.25 988838893.26 -4483562.29 4307241.23 668.89 4307910.12  1.28 8000000.0  3683189.8499999996 8000000.0  8000001.0  16000000.0 11683190.85 8f30e83f-a7c5-11ea-b510-309c231d28bd 001515018318     3978e606-0fc0-43ec-87b0-01887fa280c5 0.0           0.0         0.0                         0.0         0.0         0.0         0.0        0.0          0.0       0.0                   0.0       0.0                      0.0          0.0          0.0          0.0        0.0        0.0        0.0                   0.0                   0.0                  0.0          0.0
```

## #   credit_repay_share_by_buying_share  - 买券还券

   函数原型：


```
credit_repay_share_by_buying_share(symbol, volume, price, *, position_src=PositionSrc_Unknown, order_type=OrderType_Limit, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown, contract_id=None, account_id="", sno="",')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   price
  float
  价格

   position_src
  int
  头寸来源 取值参考  PositionSrc

   order_type
  int
  委托类型 取值参考  OrderType

   contract_id
  int
  指定合约编号，用于指定合约的直接还款，默认按负债顺序还款，华鑫柜台必填，顶点/金证/恒生柜台非必填

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值：
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_repay_share_by_buying_share(symbol='SHSE.600000', volume=100, price=10.67, order_type=OrderType_Limit,
                                             order_duration=OrderDuration_Unknown,
                                             order_qualifier=OrderQualifier_Unknown,
                                             account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status price volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ----- ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b857e02-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     10.67 100    datetime.datetime(2020, 6, 6, 15, 41, 44, 865536, tzinfo=tzfile('PRC')) 202                                                          0    0               0             0              0               0         0                                    0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
```

## #   credit_repay_cash_by_selling_share  - 卖券还款

   函数原型：


```
credit_repay_cash_by_selling_share(symbol, volume, price, *, repay_type=0, position_src=PositionSrc_Unknown, order_type=OrderType_Limit, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown, contract_id=None, account_id="", sno="")
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   price
  float
  价格

   repay_type
  int
  0：正常还款（默认）,1：只还利息（如果柜台不支持，设置repay_type=1只还利息委托会被拒绝）

   position_src
  int
  头寸来源 取值参考  PositionSrc

   order_type
  int
  委托类型 取值参考  OrderType

   contract_id
  int
  指定合约编号，用于指定合约的直接还款，默认按负债顺序还款，华鑫柜台必填，顶点/金证/恒生柜台非必填

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值：
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_repay_cash_by_selling_share(symbol='SHSE.600000', volume=100, price=10.67, order_type=OrderType_Limit,
                                             order_duration=OrderDuration_Unknown,
                                             order_qualifier=OrderQualifier_Unknown,
                                             account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status price volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ----- ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b85a50a-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     10.67 100    datetime.datetime(2020, 6, 6, 15, 41, 44, 866535, tzinfo=tzfile('PRC')) 203                                                          0    0               0             0              0               0         0                                    0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
```

## #   credit_buying_on_collateral  - 担保品买入

   函数原型：


```
credit_buying_on_collateral(symbol, volume, price,
                                order_type=OrderType_Limit,
                                order_duration=OrderDuration_Unknown,
                                order_qualifier=OrderQualifier_Unknown, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   price
  float
  价格， (限价委托的委托价格，市价委托的保护价)

   order_type
  int
  委托类型 取值参考  OrderType

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值： list[dict]
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_buying_on_collateral(symbol='SHSE.600000', volume=100, price=10.67, order_type=OrderType_Limit,
                                             order_duration=OrderDuration_Unknown,
                                             order_qualifier=OrderQualifier_Unknown,
                                             account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status price volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ----- ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b861a31-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     10.67 100    datetime.datetime(2020, 6, 6, 15, 41, 44, 869534, tzinfo=tzfile('PRC')) 207                                                          0    0               0             0              0               0         0                                    0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
```

## #   credit_selling_on_collateral  - 担保品卖出

   函数原型：


```
credit_selling_on_collateral(symbol, volume, price,
                                 order_type=OrderType_Limit,
                                 order_duration=OrderDuration_Unknown,
                                 order_qualifier=OrderQualifier_Unknown, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   price
  float
  价格， (限价委托的委托价格，市价委托的保护价)

   order_type
  int
  委托类型 取值参考  OrderType

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值： list[dict]
  请参考 order 对象  返回值字段说明
   示例代码


```
credit_selling_on_collateral(symbol='SHSE.600000', volume=100, price=10.67, order_type=OrderType_Limit,
                                             order_duration=OrderDuration_Unknown,
                                             order_qualifier=OrderQualifier_Unknown,
                                             account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status price volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ----- ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b861a31-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     10.67 100    datetime.datetime(2020, 6, 6, 15, 41, 44, 869534, tzinfo=tzfile('PRC')) 208                                                          0    0               0             0              0               0         0                                    0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
```

## #   credit_collateral_in  - 担保品转入

   函数原型：


```
credit_collateral_in(symbol, volume, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值： list[dict]
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_collateral_in(symbol='SHSE.600000', volume=100, account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail price stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ----- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b868f72-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     100    datetime.datetime(2020, 6, 6, 15, 41, 44, 872536, tzinfo=tzfile('PRC')) 209                                                          0    0               0             0              0               0         0                                    0.0   0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
...... ......
```

## #   credit_collateral_out  - 担保品转出

   函数原型：


```
credit_collateral_out(symbol, volume, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   account_id
  str
  账号 id，不填或留空，表示使用默认账号，否则使用指定账号


   返回值： list[dict]
  请参考  order 对象  返回值字段说明
   示例代码


```
credit_collateral_out(symbol='SHSE.600000', volume=100, account_id='')
```

  示例返回值


```
strategy_id                          account_id                           cl_ord_id                            symbol      order_type status volume created_at                                                              order_business account_name order_id ex_ord_id algo_order_id side position_effect position_side order_duration order_qualifier order_src ord_rej_reason ord_rej_reason_detail price stop_price order_style value percent target_volume target_value target_percent filled_volume filled_vwap filled_amount filled_commission updated_at
------------------------------------ ------------------------------------ ------------------------------------ ----------- ---------- ------ ------ ----------------------------------------------------------------------- -------------- ------------ -------- --------- ------------- ---- --------------- ------------- -------------- --------------- --------- -------------- --------------------- ----- ---------- ----------- ----- ------- ------------- ------------ -------------- ------------- ----------- ------------- ----------------- ----------
3af55cb8-a7c5-11ea-b510-309c231d28bd 8f30e83f-a7c5-11ea-b510-309c231d28bd 2b868f72-a7c9-11ea-b510-309c231d28bd SHSE.600000 1          10     100    datetime.datetime(2020, 6, 6, 15, 41, 44, 872536, tzinfo=tzfile('PRC')) 210                                                          0    0               0             0              0               0         0                                    0.0   0.0        0           0.0   0.0     0             0.0          0.0            0             0.0         0.0           0.0               None
...... ......
```



      ←

        交易查询函数

        算法交易函数

      →

---

## 交易事件

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E4%BA%A4%E6%98%93%E4%BA%8B%E4%BB%B6.html

<!DOCTYPE html>




     交易事件 - 掘金量化












# #  交易事件



## #   on_order_status  - 委托状态更新事件

  响应委托状态更新事件，下单后及委托状态更新时被触发。
   注意：
   1.  撤单拒绝，会推送撤单委托的最终状态。
   2.  回测模式下，交易事件顺序与实时模式一致，委托状态 待报 和 已报 是虚拟状态，不会更新持仓和资金。已成状态后才会更新持仓和资金。
   函数原型：


```
on_order_status(context, order)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文

   order
   order 对象
  委托


   示例：1


```
def on_order_status(context, order):
	print(order)
```

  输出：


```
{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 11.0, 'order_style': 1, 'volume': 18181800, 'value': 200000000.0, 'percent': 0.1, 'target_volume': 18181800, 'target_value': 199999800.0, 'target_percent': 0.1, 'filled_volume': 18181800, 'filled_vwap': 11.0011, 'filled_amount': 200019799.98, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 20001.979998, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}
```

  示例：2


```
def init(context):
	# 记录委托id
	context.cl_ord_id = {}
    order_list = get_orders()
    context.cl_ord_id = {i['cl_ord_id']: {'status': i['status'], 'filled_volume': i['filled_volume']} for i in order_list if order_list}

def on_bar(context, bars):
	# 记录下单后对应的委托id，方便在on_order_status里追踪，实时模式下下单后会立刻返回10待报状态，其他状态需要通过on_order_status事件监控
	order = order_volume(symbol=symbol, volume=volume, side=OrderSide_Sell, order_type=OrderType_Limit,
                             position_effect=PositionEffect_CloseToday,
                             price=price_1)
	context.cl_ord_id[order[0]['cl_ord_id']] = {}
	context.cl_ord_id[order[0]['cl_ord_id']]['status'] = order[0]['status']
	context.cl_ord_id[order[0]['cl_ord_id']]['filled_volume'] = order[0]['filled_volume']

def on_order_status(context, order):
    # 过滤非此策略下单的委托和重复状态的委托
    if order.strategy_id == context.strategy_id and order.cl_ord_id in context.cl_ord_id.keys():
        if order.status != context.cl_ord_id[order.cl_ord_id]['status']:
            context.cl_ord_id[order.cl_ord_id]['status'] = order['status']
            context.cl_ord_id[order.cl_ord_id]['filled_volume'] = order['filled_volume']
        else:
			# 部分成交状态时，根据已成交量判断order是不是最新的
            if order.status == 2 and order.filled_volume != context.cl_ord_id[order.cl_ord_id]['filled_volume']:
                context.cl_ord_id[order.cl_ord_id]['filled_volume'] = order['filled_volume']
            else:
                return

	# 可在后面执行其他处理逻辑
	print(order)
```

  输出：


```
{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 11.0, 'order_style': 1, 'volume': 18181800, 'value': 200000000.0, 'percent': 0.1, 'target_volume': 18181800, 'target_value': 199999800.0, 'target_percent': 0.1, 'filled_volume': 18181800, 'filled_vwap': 11.0011, 'filled_amount': 200019799.98, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 20001.979998, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}
```

## #   on_execution_report  - 委托执行回报事件

  响应委托被执行事件，委托成交或者撤单拒绝后被触发。
   注意：
   1.  撤单拒绝后，会推送撤单拒绝执行回报，可以根据 exec_id 区分
   函数原型：


```
on_execution_report(context, execrpt)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文

   execrpt
   execrpt
  回报


   示例：


```
def init(context):
	# 记录成交id
    context.exec_id = []
    exec_rpt_list = get_execution_reports()

    context.exec_id = [i['exec_id'] for i in exec_rpt_list if exec_rpt_list]

def on_execution_report(context, execrpt):
	# 过滤掉非此策略和成交类型不是15（成交）的回报
    if execrpt.exec_type == 15 and execrpt.exec_id not in context.exec_id and execrpt.strategy_id == context.strategy_id:
		context.exec_id.append(execrpt.exec_id)
		# 后面可以执行其他处理逻辑
		print(execrpt)
```

  输出：


```
{'strategy_id': 'e41dec22-2d72-11eb-b043-00ff5a669ee2', 'cl_ord_id': '000000247', 'symbol': 'SHSE.600000', 'position_effect': 1, 'side': 1, 'exec_type': 15, 'price': 12.640000343322754, 'volume': 200, 'amount': 2528.000068664551, 'account_id': '', 'account_name': '', 'order_id': '', 'exec_id': '', 'order_business': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'commission': 0.0, 'cost': 0.0, 'created_at': None}
```

## #   on_account_status  - 交易账户状态更新事件

  响应交易账户状态更新事件，交易账户状态变化时被触发。
   函数原型：


```
on_account_status(context, account)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文

   account
   account , 包含 account_id(账户 id), account_name(账户名),status( 账户状态 )
  交易账户状态对象，仅响应 已连接，已登录，已断开 和 错误 事件。


   示例：


```
def init(context):
    # 主动查交易账户状态
    if context.account().status.state != 3:
        my_news = '账户未登录，状态：{}， 错误信息：{}'.format(context.account().status.state,
                                                           context.account().status.error.info)
        print(my_news)

# 系统主动推送交易状态
def on_account_status(context, account):
    if account['status']['state'] == 5:
        print('账户已断开')

    elif account['status']['state'] == 3:
        print('账户已连接')

    else:
        print('{}账户状态未知， account:{}'.format(context.now, account))
```

  输出：


```
账户已断开
```



      ←

        债券交易函数

        动态参数

      →

---

## 交易函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E4%BA%A4%E6%98%93%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     交易函数 - 掘金量化












# #  交易函数



## #   order_volume  - 按指定量委托

   函数原型：


```
order_volume(symbol, volume, side, order_type,position_effect, price=0, trigger_type=0, stop_price=0, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown,account='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量(指股数)

   side
  int
  参见 订单委托方向

   order_type
  int
  参见 订单委托类型

   position_effect
  int
  参见 开平仓类型

   price
  float
  价格（限价委托的委托价格；市价委托的保护价，沪市实盘市价单必填字段，股票需要保留两位小数，回测仿真可不填写，参考下文注意点6。）

   trigger_type
  int
  参见 期货条件单触发方式 ，非条件单为0

   stop_price
  float
  期货条件单触发价格，非条件单为0，对已有持仓进行止盈，触发价格为止盈价。对已有持仓进行止损，触发价格为止损价。开仓时，触发价格为开仓触发价。

   account
  account id or account name or None
  帐户


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：


```
order_volume(symbol='SHSE.600000', volume=10000, side=OrderSide_Buy, order_type=OrderType_Limit, position_effect=PositionEffect_Open, price=11)
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 11.0, 'order_style': 1, 'volume': 10000, 'value': 110000.0, 'percent': 5.5e-05, 'target_volume': 10000, 'target_value': 110000.0, 'target_percent': 5.5e-05, 'filled_volume': 10000, 'filled_vwap': 11.0011, 'filled_amount': 110010.99999999999, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 11.0011, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

  注意：
   1.  仅支持一个标的代码，若交易代码输入有误，终端会拒绝此单，并显示 委托代码不正确 。
   2.  若下单数量输入有误，终端会拒绝此单，并显示 委托量不正确 。股票买入最小单位为 100 ，卖出最小单位为 1 ,如存在不足 100 股的持仓一次性卖出;期货买卖最小单位为 1 ， 向下取整 。
   3.  若仓位不足，终端会拒绝此单，显示 仓位不足 。平仓时股票默认 平昨仓 ，期货默认 平今仓 。应研究需要， 股票也支持卖空操作 。
   4.  输入无效参数报 NameError 错误，缺少参数报 TypeError 错误。
   5.  关于 side 与 position_effect 字段的使用说明，（股票，基金和可转债只能做多，买入（填买开），卖出（填卖平））
  做多（买开）： side=OrderSide_Buy ，position_effect=PositionEffect_Open
平仓（卖平）： side=OrderSide_Sell ，position_effect=PositionEffect_Close
  做空（卖开）： side=OrderSide_Sell ，position_effect=PositionEffect_Open
平仓（买平）： side= OrderSide_Buy ，position_effect=PositionEffect_Close
   6.  按交易所规定，沪市市价单，必须填写保护限价。（买入设置保护限价price 的有效范围为当前价~涨停价， 卖出设置保护限价price的有效范围为跌停价~当前价。），终端版本号大于3.21.0.0的，会默认买入填写涨停价，卖出填写跌停价。
   7.   边界处理规则
   8.   期货实盘条件单参数组合示例
   9.  期货条件单注意事项：


```
- 预埋条件单可对已有持仓进行止盈和止损，也可以达到触发价格开仓。

- 预埋条件单状态OrderStatus：待触发、已触发。已触发的条件单不会再继续监控。条件单触发后，触发的普通委托如被CTP拒绝（资金不足、仓位不足等），且交易账户未登出，可通过on_order_status接收推送的普通委托拒绝状态。

- 预埋条件单仅限当日有效，截至收盘仍未触发的条件单在当日收盘后会自动清除。

- 预埋条件单参数trigger_type和stop_price仅支持期货实盘账户可用，account指定仿真账户时填写trigger_type和stop_price无效，视为普通单。
```

## #   order_value  - 按指定价值委托

   函数原型：


```
order_value(symbol, value, side,order_type, position_effect, price=0, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown,account='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   value
  int
  股票价值

   side
  int
  参见 订单委托方向

   order_type
  int
  参见 订单委托类型

   position_effect
  int
  参见 开平仓类型

   price
  float
  价格（限价委托的委托价格；市价委托的保护价，沪市实盘市价单必填字段，股票需要保留两位小数，回测仿真可不填写，参考下文注意点5。）

   account
  account id or account name or None
  帐户


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：
  下限价单，以 11 元每股的价格买入价值为 100000 的 SHSE.600000,根据 volume = value / price,计算并取整得到 volume = 9000


```
order_value(symbol='SHSE.600000', value=100000, price=11, side=OrderSide_Buy, order_type=OrderType_Limit, position_effect=PositionEffect_Open)
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 11.0, 'order_style': 1, 'volume': 9000, 'value': 100000.0, 'percent': 5e-05, 'target_volume': 9000, 'target_value': 99000.0, 'target_percent': 4.95e-05, 'filled_volume': 9000, 'filled_vwap': 11.0011, 'filled_amount': 99009.9, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 9.90099, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

  注意：
   1.  仅支持一个标的代码，若交易代码输入有误，终端会拒绝此单，并显示 委托代码不正确 。
   2.  根据指定价值计算购买标的数量，即 value/price 。股票买卖最小单位为 100 ，不足 100 部分 向下取整 ，如存在不足 100 的持仓一次性卖出;期货买卖最小单位为 1 ， 向下取整 。
   3.  若仓位不足，终端会拒绝此单，显示 仓位不足 。平仓时股票默认 平昨仓 ，期货默认 平今仓 。应研究需要， 股票也支持卖空操作 。
   4.  输入无效参数报 NameError 错误，缺少参数报 TypeError 错误。
   5.  按交易所规定，沪市市价单，必须填写保护限价。（买入设置保护限价price 的有效范围为当前价~涨停价， 卖出设置保护限价price的有效范围为跌停价~当前价。），终端版本号大于3.21.0.0的，会默认买入填写涨停价，卖出填写跌停价。
   6.   边界处理规则


## #   order_percent  - 按总资产指定比例委托

   函数原型：


```
order_percent(symbol, percent, side,order_type, position_effect, price=0, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown, account='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   percent
  double
  委托占总资产比例

   side
  int
  参见 订单委托方向

   order_type
  int
  参见 订单委托类型

   position_effect
  int
  参见 开平仓类型

   price
  float
  价格（限价委托的委托价格；市价委托的保护价，沪市实盘市价单必填字段，股票需要保留两位小数，回测仿真可不填写，参考下文注意点6。）

   account
  account id or account name or None
  帐户


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：
  当前总资产为 1000000。下限价单，以 11 元每股的价格买入 SHSE.600000,期望买入比例占总资产的 10%，根据 volume = nav * precent / price 计算取整得出 volume = 9000


```
order_percent(symbol='SHSE.600000', percent=0.1, side=OrderSide_Buy, order_type=OrderType_Limit, position_effect=PositionEffect_Open, price=11)
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 11.0, 'order_style': 1, 'volume': 18181800, 'value': 200000000.0, 'percent': 0.1, 'target_volume': 18181800, 'target_value': 199999800.0, 'target_percent': 0.0999999, 'filled_volume': 18181800, 'filled_vwap': 11.0011, 'filled_amount': 200019799.98, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 20001.979998, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

  注意：
   1.  仅支持一个标的代码，若交易代码输入有误，终端会拒绝此单，并显示 委托代码不正确 。
   2.  根据指定比例计算购买标的数量,即 (nav*precent)/price ,股票买卖最小单位为 100 ，不足 100 部分 向下取整 ，如存在不足 100 的持仓一次性卖出;期货买卖最小单位为 1 ， 向下取整 。
   3.  若仓位不足，终端会拒绝此单，显示 仓位不足 。平仓时股票默认 平昨仓 ，期货默认 平今仓 。应研究需要， 股票也支持卖空操作 。
   4.  输入无效参数报 NameError 错误，缺少参数报 TypeError 错误。
   5.  期货实盘时，percent 是以合约上市的初始保证金比例计算得到的，并非实时保证金比例。
   6.  按交易所规定，沪市市价单，必须填写保护限价。（买入设置保护限价price 的有效范围为当前价~涨停价， 卖出设置保护限价price的有效范围为跌停价~当前价。），终端版本号大于3.21.0.0的，会默认买入填写涨停价，卖出填写跌停价。
   7.   边界处理规则


## #   order_target_volume  - 调仓到目标持仓量

   函数原型：


```
order_target_volume(symbol, volume, position_side, order_type, price=0, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown, account='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  期望的最终数量

   position_side
  int
  表示将多仓还是空仓调到目标持仓量，参见  持仓方向

   order_type
  int
  参见 订单委托类型

   price
  float
  价格（限价委托的委托价格；市价委托的保护价，沪市实盘市价单必填字段，股票需要保留两位小数，回测仿真可不填写，参考下文注意点5。）

   account
  account id or account name or None
  帐户


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：
  当前 SHSE.600000 多方向持仓量为 0，期望持仓量为 10000，下单量为期望持仓量 - 当前持仓量 = 10000


```
order_target_volume(symbol='SHSE.600000', volume=10000, position_side=PositionSide_Long, order_type=OrderType_Limit, price=13)
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 13.0, 'order_style': 1, 'volume': 10000, 'value': 130000.0, 'percent': 6.5e-05, 'target_volume': 10000, 'target_value': 130000.0, 'target_percent': 6.5e-05, 'filled_volume': 10000, 'filled_vwap': 13.0013, 'filled_amount': 130013.0, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 13.0013, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

  注意：
   1.  仅支持一个标的代码，若交易代码输入有误，订单会被拒绝， 终端无显示，无回报 。回测模式可参看 order_reject_reason。
   2.  根据目标数量计算下单数量，系统判断开平仓类型。若下单数量有误，终端拒绝此单，并显示 委托量不正确 。若实际需要买入数量为 0，则订单会被拒绝， 终端无显示，无回报 。股票买卖最小单位为 100 ，不足 100 部分 向下取整 ，如存在不足 100 的持仓一次性卖出;期货买卖最小单位为 1 ， 向下取整 。
   3.  若仓位不足，终端拒绝此单，显示 仓位不足 。平仓时股票默认 平昨仓 ，期货默认 平今仓 ,上期所昨仓不能平掉。应研究需要，股票也支持卖空操作。
   4.  输入无效参数报 NameError 错误，缺少参数报 Typeerror 错误。
   5.  按交易所规定，沪市市价单，必须填写保护限价。（买入设置保护限价price 的有效范围为当前价~涨停价， 卖出设置保护限价price的有效范围为跌停价~当前价。），终端版本号大于3.21.0.0的，会默认买入填写涨停价，卖出填写跌停价。
   6.   边界处理规则


## #   order_target_value  - 调仓到目标持仓额

   函数原型：


```
order_target_value(symbol, value, position_side, order_type, price=0, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown, account='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   value
  int
  期望的股票最终价值

   position_side
  int
  表示将多仓还是空仓调到目标持仓量，参见  持仓方向

   order_type
  int
  参见 订单委托类型

   price
  float
  价格（限价委托的委托价格；市价委托的保护价，沪市实盘市价单必填字段，股票需要保留两位小数，回测仿真可不填写，参考下文注意点5。）

   account
  account id or account name or None
  帐户


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：
  当前 SHSE.600000 多方向当前持仓量为 0，目标持有价值为 100000 的该股票，根据 value / price 计算取整得出目标持仓量 volume 为 9000，目标持仓量 - 当前持仓量 = 下单量为 9000


```
order_target_value(symbol='SHSE.600000', value=100000, position_side=PositionSide_Long, order_type=OrderType_Limit, price=11)
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 11.0, 'order_style': 1, 'volume': 9000, 'value': 100000.0, 'percent': 5e-05, 'target_volume': 9000, 'target_value': 100000.0, 'target_percent': 5e-05, 'filled_volume': 9000, 'filled_vwap': 11.0011, 'filled_amount': 99009.9, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 9.90099, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

  注意：
   1.  仅支持一个标的代码，若交易代码输入有误，订单会被拒绝， 终端无显示，无回报 。回测模式可参看 order_reject_reason。
   2.  根据目标价值计算下单数量，系统判断开平仓类型。若下单数量有误，终端拒绝此单，并显示 委托量不正确 。若实际需要买入数量为 0，则本地拒绝此单， 终端无显示，无回报 。股票买卖最小单位为 100 ，不足 100 部分 向下取整 ，如存在不足 100 的持仓一次性卖出;期货买卖最小单位为 1 ， 向下取整 。
   3.  若仓位不足，终端拒绝此单，显示 仓位不足 。平仓时股票默认 平昨仓 ，期货默认 平今仓 ，目前不可修改。应研究需要， 股票也支持卖空操作 。
   4.  输入无效参数报 NameError 错误，缺少参数报 Typeerror 错误。
   5.  按交易所规定，沪市市价单，必须填写保护限价。（买入设置保护限价price 的有效范围为当前价~涨停价， 卖出设置保护限价price的有效范围为跌停价~当前价。），终端版本号大于3.21.0.0的，会默认买入填写涨停价，卖出填写跌停价。
   6.   边界处理规则


## #   order_target_percent  - 调仓到目标持仓比例（总资产的比例）

   函数原型：


```
order_target_percent(symbol, percent, position_side, order_type, price=0, order_duration=OrderDuration_Unknown, order_qualifier=OrderQualifier_Unknown, account='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   percent
  double
  期望的最终占总资产比例

   position_side
  int
  表示将多仓还是空仓调到目标持仓量，参见  持仓方向

   order_type
  int
  参见 订单委托类型

   price
  float
  价格（限价委托的委托价格；市价委托的保护价，沪市实盘市价单必填字段，股票需要保留两位小数，回测仿真可不填写，参考下文注意点6。）

   account
  account id or account name or None
  帐户


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：
  当前总资产价值为 1000000，目标为以 11 元每股的价格买入 SHSE.600000 的价值占总资产的 10%，根据 volume = nav * percent / price 计算取整得出应持有 9000 股。当前该股持仓量为零，因此买入量为 9000


```
order_target_percent(symbol='SHSE.600000', percent=0.1, position_side=PositionSide_Long, order_type=OrderType_Limit, price=11)
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 1, 'status': 3, 'price': 11.0, 'order_style': 1, 'volume': 18181800, 'value': 200000000.0, 'percent': 0.1, 'target_volume': 18181800, 'target_value': 199999800.0, 'target_percent': 0.1, 'filled_volume': 18181800, 'filled_vwap': 11.0011, 'filled_amount': 200019799.98, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 20001.979998, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

  注意：
   1.  仅支持一个标的代码，若交易代码输入有误，订单会被拒绝， 终端无显示，无回报 。回测模式可参看 order_reject_reason。
   2.  根据目标比例计算下单数量，为占 总资产(nav） 比例，系统判断开平仓类型。若下单数量有误，终端拒绝此单，并显示 委托量不正确 。若实际需要买入数量为 0，则本地拒绝此单， 终端无显示，无回报 。股票买卖最小单位为 100 ，不足 100 部分 向下取整 ，如存在不足 100 的持仓一次性卖出;期货买卖最小单位为 1 ， 向下取整 。
   3.  若仓位不足，终端拒绝此单， 显示仓位不足 。平仓时股票默认 平昨仓 ，期货默认 平今仓 ，目前不可修改。应研究需要， 股票也支持卖空操作 。
   4.  输入无效参数报 NameError 错误，缺少参数报 Typeerror 错误。
   5.  期货实盘时，percent 是以合约上市的初始保证金比例计算得到的，并非实时保证金比例。
   6.  按交易所规定，沪市市价单，必须填写保护限价。（买入设置保护限价price 的有效范围为当前价~涨停价， 卖出设置保护限价price的有效范围为跌停价~当前价。），终端版本号大于3.21.0.0的，会默认买入填写涨停价，卖出填写跌停价。
   7.   边界处理规则


## #   order_batch  - 批量委托接口

   函数原型：


```
order_batch(orders, combine=False, account='')
```

  参数：
     参数名
  类型
  说明

     orders
  list[order]
  委托对象列表，其中委托至少包含交易接口的必选参数，参见 order 对象

   combine
  bool
  是否是组合单, 默认不是（预留字段，目前无效）

   account
  account id or account name or None
  帐户


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：


```
order_1 = {'symbol': 'SHSE.600000', 'volume': 100, 'price': 11, 'side': 1,
               'order_type': 2, 'position_effect':1}
    order_2 = {'symbol': 'SHSE.600004', 'volume': 100, 'price': 11, 'side': 1,
               'order_type': 2, 'position_effect':1}
    orders = [order_1, order_2]
    batch_orders = order_batch(orders, combine=True)
    for order in batch_orders:
        print(order)
```

  返回：


```
{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 3, 'price': 10.280000686645508, 'order_style': 1, 'volume': 100, 'filled_volume': 100, 'filled_vwap': 10.281028686714173, 'filled_amount': 1028.1028686714174, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 0.10281028686714173, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0}
{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000001', 'symbol': 'SHSE.600004', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 3, 'price': 15.050000190734863, 'order_style': 1, 'volume': 100, 'filled_volume': 100, 'filled_vwap': 15.051505190753936, 'filled_amount': 1505.1505190753935, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 0.15051505190753936, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0}
{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000002', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 3, 'price': 10.180000305175781, 'order_style': 1, 'volume': 100, 'filled_volume': 100, 'filled_vwap': 10.1810183052063, 'filled_amount': 1018.10183052063, 'created_at': datetime.datetime(2020, 9, 2, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 2, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 0.101810183052063, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0}
{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000003', 'symbol': 'SHSE.600004', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 3, 'price': 14.819999694824219, 'order_style': 1, 'volume': 100, 'filled_volume': 100, 'filled_vwap': 14.8214816947937, 'filled_amount': 1482.14816947937, 'created_at': datetime.datetime(2020, 9, 2, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 2, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 0.148214816947937, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0}
```

  注意：
   1.  每个 order 的 symbol 仅支持一个标的代码，若交易代码输入有误，终端会拒绝此单，并显示 委托代码不正确 。
   2.  若下单数量输入有误，终端会拒绝此单，并显示 委托量不正确 。 下单数量严格按照指定数量下单 ，需注意股票买入最小单位为 100。
   3.  若仓位不足，终端会拒绝此单， 显示仓位不足 。应研究需要， 股票也支持卖空操作 。
   4.  输入无效参数报 NameError 错误，缺少参数不报错，可能会出现下单被拒。


## #   order_cancel  - 撤销委托

   函数原型：


```
order_cancel(wait_cancel_orders)
```

  参数：
     参数名
  类型
  说明

     wait_cancel_orders
  list[dict]
  传入单个字典. 或者 list 字典. 每个字典包含 key: cl_ord_id, account_id， 参见 order 对象


   示例：


```
# 先查未结委托，再把未结委托全部撤单，
unfin_order = get_unfinished_orders()
if unfin_order:
    order_cancel(wait_cancel_orders=unfin_order)

# 也可循环未结委托，根据下单时间撤单
unfin_order = get_unfinished_orders()
for order in unfin_order:
    # 下单超过30秒，没有全部成交撤单
    if (abs(context.now - order['created_at'])).seconds > 30:
        # 撤单
        order_cancel(wait_cancel_orders=[{'cl_ord_id': order['cl_ord_id'], 'account_id': order['account_id']}])
```

## #   order_cancel_all  - 撤销所有委托

   函数原型：


```
order_cancel_all()
```

  示例：


```
order_cancel_all()
```

## #   order_close_all  - 平当前所有可平持仓

   注意：  不支持市价委托类型的委托，会被柜台拒绝
   函数原型：


```
order_close_all()
```

  示例：


```
order_close_all()
```

## #   get_unfinished_orders  - 查询日内全部未结委托

   函数原型：


```
get_unfinished_orders()
```

  返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：


```
get_unfinished_orders()
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600519', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 2, 'status': 3, 'price': 1792.0, 'order_style': 1, 'volume': 100, 'value': 179200.0, 'percent': 8.96e-05, 'target_volume': 100, 'target_value': 179200.0, 'target_percent': 8.96e-05, 'filled_volume': 100, 'filled_vwap': 1792.1792, 'filled_amount': 179217.92, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 17.921792000000003, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

## #   get_orders  - 查询日内全部委托

   函数原型：


```
get_orders()
```

  返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：


```
get_orders()
```

  返回：


```
[{'strategy_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'cl_ord_id': '000000000', 'symbol': 'SHSE.600519', 'side': 1, 'position_effect': 1, 'position_side': 1, 'order_type': 2, 'status': 3, 'price': 1792.0, 'order_style': 1, 'volume': 100, 'value': 179200.0, 'percent': 8.96e-05, 'target_volume': 100, 'target_value': 179200.0, 'target_percent': 8.96e-05, 'filled_volume': 100, 'filled_vwap': 1792.1792, 'filled_amount': 179217.92, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'filled_commission': 17.921792000000003, 'account_name': '', 'order_id': '', 'ex_ord_id': '', 'algo_order_id': '', 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0}]
```

## #   get_execution_reports  - 查询日内全部执行回报

   函数原型：


```
get_execution_reports()
```

  返回值：
     类型
  说明

     list[execrpt]
  回报对象列表， 参见 ExecRpt 回报对象


   示例：


```
get_execution_reports()
```

  返回：


```
[{'strategy_id': '004beb61-1282-11eb-9313-00ff5a669ee2', 'account_id': '3acc8b6e-af54-11e9-b2de-00163e0a4100', 'account_name': '3acc8b6e-af54-11e9-b2de-00163e0a4100', 'cl_ord_id': '49764a82-14fb-11eb-89df-00ff5a669ee2', 'order_id': '4a06f925-14fb-11eb-9e8a-00163e0a4100', 'exec_id': '573b108b-14fb-11eb-9e8a-00163e0a4100', 'symbol': 'SHSE.600714', 'position_effect': 1, 'side': 1, 'exec_type': 15, 'price': 5.579999923706055, 'volume': 900, 'amount': 5021.999931335449, 'created_at': datetime.datetime(2020, 10, 23, 14, 45, 29, 776756, tzinfo=tzfile('PRC')), 'commission': 5.0, 'cost': 5021.999931335449, 'ord_rej_reason': 0, 'ord_rej_reason_detail': ''}]
```



      ←

        可转债增值数据函数（付费）

        交易查询函数

      →

---

## 交易查询函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E4%BA%A4%E6%98%93%E6%9F%A5%E8%AF%A2%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     交易查询函数 - 掘金量化












# #  交易查询函数



## #  get_cash - 查询指定交易账户的资金信息

  查询指定交易账户的资金信息, gm SDK 3.0.163 版本新增
   原型：


```
get_cash(account_id=None)
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账户信息，默认返回默认账户, 如多个账户需指定 account_id


   返回值：
     类型
  说明

     dict
   Cash 资金对象


   示例：


```
cash = get_cash()
print(cash)
```

  输出：


```
{'account_id': '8bf2b0cb-9f0d-11ee-bd0b-00163e163353', 'account_name': '8bf2b0cb-9f0d-11ee-bd0b-00163e163353', 'nav': 100049705.54665434, 'pnl': 49705.546654343605, 'fpnl': 5296.038990020825, 'frozen': 138363.60003433225, 'available': 99911315.9466925, 'cum_inout': 100000000.0, 'cum_trade': 6749993.987827301, 'cum_pnl': 44620.012207031454, 'cum_commission': 210.5045427023142, 'last_trade': 30450.0, 'last_commission': 1.5, 'last_inout': 100000000.0, 'created_at': datetime.datetime(2023, 12, 20, 15, 58, 22, 641250, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2024, 1, 23, 14, 53, 16, 670507, tzinfo=tzfile('PRC')), 'balance': 100048365.54669249, 'market_value': 1164370.039024353, 'enable_bail': 99911315.9466925, 'fpnl_diluted': 5296.038990020825, 'channel_id': '', 'currency': 0, 'order_frozen': 0.0, 'last_pnl': 0.0, 'change_reason': 0, 'change_event_id': '', 'market_value_long': 0.0, 'market_value_short': 0.0, 'used_bail': 0.0}
```

  注意：
   1.  account_id不存在时，返回空字典。
   2.  当策略关联一个交易账户时，account_id可不用填，当策略关联多个交易账户时，必须指定account_id，否则会报错。
   3.  get_cash和context.account().cash的区别，get_cash直接查询终端的最新数据，不需要像context.account().cash通过context对象更新。


## #  get_position - 查询指定交易账户的全部持仓信息

  查询指定交易账户的全部持仓信息, gm SDK 3.0.163 版本新增
   原型：


```
get_position(account_id=None)
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账户信息，默认返回默认账户, 如多个账户需指定 account_id


   返回值：
     类型
  说明

     list[position]
   Position 持仓对象 列表


   示例：


```
position = get_position()
print(position)
```

  输出：


```
[{'account_id': '8bf2b0cb-9f0d-11ee-bd0b-00163e163353', 'symbol': 'DCE.m2405', 'side': 1, 'volume': 2, 'vwap': 3200.5, 'amount': 64010.0, 'price': 3072.0, 'fpnl': -2570.0, 'cost': 4480.700000000001, 'available': 2, 'last_price': 3045.0, 'last_volume': 1, 'created_at': datetime.datetime(2023, 12, 27, 10, 37, 54, 801075, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2024, 1, 23, 20, 0, 9, 133899, tzinfo=tzfile('PRC')), 'vwap_diluted': 3200.5, 'market_value': 61440.0, 'available_now': 2, 'vwap_open': 3200.5, 'fpnl_open': -2570.0, 'fpnl_diluted': -2570.0, 'account_name': '', 'channel_id': '', 'volume_today': 0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0, 'covered_flag': 0, 'properties': {}, 'credit_position_sellable_volume': 0}, {'account_id': '8bf2b0cb-9f0d-11ee-bd0b-00163e163353', 'symbol': 'SHSE.600000', 'side': 1, 'volume': 200, 'vwap': 6.57, 'amount': 1314.0000343322754, 'price': 6.71, 'fpnl': 27.99997329711914, 'cost': 1314.0000343322754, 'available': 200, 'last_price': 6.570000171661377, 'last_volume': 200, 'created_at': datetime.datetime(2023, 12, 27, 13, 38, 30, 195484, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2023, 12, 28, 8, 30, 0, 678, tzinfo=tzfile('PRC')), 'vwap_diluted': 6.57, 'market_value': 1342.0000076293945, 'available_now': 200, 'vwap_open': 6.57, 'fpnl_open': 27.99997329711914, 'fpnl_diluted': 27.99997329711914, 'account_name': '', 'channel_id': '', 'volume_today': 0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0, 'covered_flag': 0, 'properties': {}, 'credit_position_sellable_volume': 0}, {'account_id': '8bf2b0cb-9f0d-11ee-bd0b-00163e163353', 'symbol': 'CZCE.RM405', 'side': 1, 'volume': 1, 'vwap': 2717.0, 'amount': 27170.0, 'price': 2555.0, 'fpnl': -1620.0, 'cost': 2445.2999999999997, 'available': 1, 'last_price': 2717.0, 'last_volume': 1, 'created_at': datetime.datetime(2024, 1, 2, 14, 43, 56, 787534, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2024, 1, 2, 20, 0, 7, 245847, tzinfo=tzfile('PRC')), 'vwap_diluted': 2717.0, 'market_value': 25550.0, 'available_now': 1, 'vwap_open': 2717.0, 'fpnl_open': -1620.0, 'fpnl_diluted': -1620.0, 'account_name': '', 'channel_id': '', 'volume_today': 0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0, 'covered_flag': 0, 'properties': {}, 'credit_position_sellable_volume': 0}, {'account_id': '8bf2b0cb-9f0d-11ee-bd0b-00163e163353', 'symbol': 'GFEX.lc2405', 'side': 1, 'volume': 1, 'vwap': 106700.0, 'amount': 106700.0, 'price': 101600.0, 'fpnl': -5100.0, 'cost': 14938.000000000002, 'available': 1, 'last_price': 106700.0, 'last_volume': 1, 'created_at': datetime.datetime(2024, 1, 3, 9, 26, 18, 868588, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2024, 1, 4, 8, 30, 0, 1110, tzinfo=tzfile('PRC')), 'vwap_diluted': 106700.0, 'market_value': 101600.0, 'available_now': 1, 'vwap_open': 106700.0, 'fpnl_open': -5100.0, 'fpnl_diluted': -5100.0, 'account_name': '', 'channel_id': '', 'volume_today': 0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0, 'covered_flag': 0, 'properties': {}, 'credit_position_sellable_volume': 0}, {'account_id': '8bf2b0cb-9f0d-11ee-bd0b-00163e163353', 'symbol': 'CFFEX.IC2402', 'side': 1, 'volume': 1, 'vwap': 4799.4, 'amount': 959879.9999999999, 'price': 4890.2002, 'fpnl': 18160.039062500073, 'cost': 115185.59999999998, 'available': 1, 'last_price': 4799.4, 'last_volume': 1, 'created_at': datetime.datetime(2024, 1, 23, 14, 52, 55, 800533, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2024, 1, 24, 8, 30, 0, 1825, tzinfo=tzfile('PRC')), 'vwap_diluted': 4799.4, 'market_value': 978040.0390625, 'available_now': 1, 'vwap_open': 4799.4, 'fpnl_open': 18160.039062500073, 'fpnl_diluted': 18160.039062500073, 'account_name': '', 'channel_id': '', 'volume_today': 0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0, 'covered_flag': 0, 'properties': {}, 'credit_position_sellable_volume': 0}]
```

  注意：
   1.  account_id不存在时，返回空列表。
   2.  当策略关联一个交易账户时，account_id可不用填，当策略关联多个交易账户时，必须指定account_id，否则会报错。
   3.  get_position和context.account().positions()的区别，get_position直接查询终端的最新数据，不需要像context.account().positions()通过context对象更新。


## #  context.account().cash - 查询当前账户资金

   原型：


```
context.account(account_id=None).cash
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账户信息，默认返回默认账户, 如多个账户需指定 account_id


   返回值：
     类型
  说明

     dict[cash]
   Cash 资金对象 列表


   示例-获取当前账户资金：


```
context.account().cash
```

  输出：


```
{'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'nav': 1905248.2789094353, 'pnl': -94751.72109056474, 'fpnl': -94555.35135529494, 'frozen': 1963697.3526980684, 'available': 36106.277566661825, 'cum_inout': 2000000.0, 'cum_trade': 1963697.3526980684, 'cum_commission': 196.3697352698069, 'last_trade': 1536.1536610412597, 'last_commission': 0.153615366104126, 'created_at': datetime.datetime(2020, 9, 1, 8, 0, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 30, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'currency': 0, 'order_frozen': 0.0, 'balance': 0.0, 'market_value': 0.0, 'cum_pnl': 0.0, 'last_pnl': 0.0, 'last_inout': 0.0, 'change_reason': 0, 'change_event_id': ''}
```

## #  context.account().positions() - 查询当前账户全部持仓

   原型：


```
context.account(account_id=None).positions()
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账户信息，默认返回默认账户, 如多个账户需指定 account_id


   返回值：
     类型
  说明

     list[position]
   Position 持仓对象 列表


   注意：  没有持仓时，返回空列表
   示例-获取当前持仓：


```
# 所有持仓
Account_positions = context.account().positions()
```

  输出：


```
# 所有持仓输出
[{'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'symbol': 'SHSE.600419', 'side': 1, 'volume': 2200, 'volume_today': 100, 'vwap': 16.43391600830338, 'amount': 36154.61521826744, 'fpnl': -2362.6138754940007, 'cost': 36154.61521826744, 'available': 2200, 'available_today': 100, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 30, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'vwap_diluted': 0.0, 'price': 0.0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_now': 0, 'market_value': 0.0, 'last_price': 0.0, 'last_volume': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0}, {'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'symbol': 'SHSE.600519', 'side': 1, 'volume': 1100, 'vwap': 1752.575242219682, 'amount': 1927832.7664416502, 'fpnl': -110302.84700805641, 'cost': 1927832.7664416502, 'available': 1100, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 15, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'volume_today': 0, 'vwap_diluted': 0.0, 'price': 0.0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'available_now': 0, 'market_value': 0.0, 'last_price': 0.0, 'last_volume': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0}]
```

## #  context.account().position(symbol, side) - 查询当前账户指定持仓

   参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   side
  int
  持仓方向，取值参考 PositionSide 持仓方向


   返回值：
     类型
  说明

     dict[position]
   Position 持仓对象 列表


   注意：  当指定标的没有持仓时，返回 None
 示例-获取当前持仓：


```
# 指定持仓
Account_position = context.account().position(symbol='SHSE.600519',side = PositionSide_Long)
```

  输出：


```
# 指定持仓输出
{'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'symbol': 'SHSE.600519', 'side': 1, 'volume': 1100, 'vwap': 1752.575242219682, 'amount': 1927832.7664416502, 'fpnl': -110302.84700805641, 'cost': 1927832.7664416502, 'available': 1100, 'created_at': datetime.datetime(2020, 9, 1, 9, 40, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 9, 15, 9, 40, tzinfo=tzfile('PRC')), 'account_name': '', 'volume_today': 0, 'vwap_diluted': 0.0, 'price': 0.0, 'order_frozen': 0, 'order_frozen_today': 0, 'available_today': 0, 'available_now': 0, 'market_value': 0.0, 'last_price': 0.0, 'last_volume': 0, 'last_inout': 0, 'change_reason': 0, 'change_event_id': '', 'has_dividend': 0}
```



      ←

        交易函数

        两融交易函数

      →

---

## 债券交易函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%80%BA%E5%88%B8%E4%BA%A4%E6%98%93%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     债券交易函数 - 掘金量化












# #  债券交易函数



## #   bond_reverse_repurchase_agreement  - 国债逆回购

  仅在 实盘 中可以使用


```
bond_reverse_repurchase_agreement(symbol, volume, price, order_type=OrderType_Limit,
order_duration=OrderQualifier_Unknown, order_qualifier=OrderQualifier_Unknown, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  认购数量

   price
  float
  价格

   order_type
  int
  委托类型

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict]
   注意：
  逆回购 1 张为 100 元。最少交易 10 张。且数量必须是 10 张的整数倍，也即一千元一个单位的买。


## #   bond_convertible_call  - 可转债转股

  仅在 实盘 中可以使用


```
bond_convertible_call(symbol, volume, price=0.0, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  认购数量

   price
  float
  价格

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict[Text, Any]]


## #   bond_convertible_put  - 可转债回售

  仅在 实盘 中可以使用


```
bond_convertible_put(symbol, volume, price=0.0, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  认购数量

   price
  float
  价格

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict[Text, Any]]


## #   bond_convertible_put_cancel  - 可转债回售撤销

  仅在 实盘 中可以使用


```
bond_convertible_put_cancel(symbol, volume, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  认购数量

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict[Text, Any]]


      ←

        基金交易函数

        交易事件

      →

---

## 其他事件

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%85%B6%E4%BB%96%E4%BA%8B%E4%BB%B6.html

<!DOCTYPE html>




     其他事件 - 掘金量化












# #  其他事件



## #   on_backtest_finished  - 回测结束事件

  描述：
在回测模式下，回测结束后会触发该事件，并返回回测得到的绩效指标对象
   函数原型：


```
on_backtest_finished(context, indicator)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文

   indicator
   indicator
  绩效指标


   示例：


```
def on_backtest_finished(context, indicator):
    print(indicator)
```

  返回：


```
{'account_id': 'd7443a53-f65b-11ea-bb9d-484d7eaefe55', 'pnl_ratio': -0.007426408687162637, 'pnl_ratio_annual': -1.3553195854071813, 'sharp_ratio': -15.034348187048744, 'max_drawdown': 0.0009580714324989177, 'risk_ratio': 0.10010591267452242, 'open_count': 1, 'close_count': 1, 'lose_count': 1, 'calmar_ratio': -1414.6331259164358, 'win_count': 0, 'win_ratio': 0.0, 'created_at': None, 'updated_at': None}
```

## #   on_error  - 错误事件

  描述：
当发生异常情况，比如断网时、终端服务崩溃是会触发
   函数原型：


```
on_error(context, code, info)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文

   code
  int
   错误码

   info
  str
  错误信息


   示例：


```
def on_error(context, code, info):
    print('code:{}, info:{}'.format(code, info))
    stop()
```

  返回：


```
code:1201, info:实时行情服务连接断开
```

## #   on_market_data_connected  - 实时行情网络连接成功事件

  描述：
实时行情网络连接时触发，比如策略实时运行启动后会触发、行情断连又重连后会触发
   函数原型：


```
on_market_data_connected(context)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文


   示例：


```
def on_market_data_connected(context):
    print('实时行情网络连接成功')
```

## #   on_trade_data_connected  - 交易通道网络连接成功事件

  描述：
目前监控 SDK 的交易和终端的链接情况，终端之后部分暂未做在内。账号连接情况可通过终端内账户连接指示灯查看
   函数原型：


```
on_trade_data_connected(context)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文


   示例：


```
def on_trade_data_connected(context):
    print('交易通道网络连接成功')
```

## #   on_market_data_disconnected  - 实时行情网络连接断开事件

   函数原型：
  描述：
实时行情网络断开时触发，比如策略实时运行行情断连会触发


```
on_market_data_disconnected(context)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文


   示例：


```
def on_market_data_disconnected(context):
    print('实时行情网络连接失败')
```

## #   on_trade_data_disconnected  - 交易通道网络连接断开事件

  描述：
目前监控 SDK 的交易和终端的链接情况，终端交易服务崩溃后会触发，终端之后部分暂未做在内。账号连接情况可通过终端内账户连接指示灯查看
   函数原型：


```
on_trade_data_disconnected(context)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文


   示例：


```
def on_trade_data_disconnected(context):
    print('交易通道网络连接失败')
```


      ←

        其他函数

        枚举常量

      →

---

## 其他函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%85%B6%E4%BB%96%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     其他函数 - 掘金量化












# #  其他函数



## #   set_token  - 设置 token

  用户有时只需要提取数据, set_token 后就可以直接调用数据函数, 无需编写策略结构。如果 token 不合法, 访问需要身份验证的函数会抛出异常。
   token 位置参见终端-系统设置界面-密钥管理（token）
   函数原型：


```
set_token(token)
```

  参数：
     参数名
  类型
  说明

     token
  str
  身份标识


   返回值：
   None
   示例：


```
set_token('your token')
history_data = history(symbol='SHSE.000300', frequency='1d', start_time='2010-07-28',  end_time='2017-07-30', df=True)
```

  注意：
token 输入错误会报错“错误或无效的 token”。


## #   set_option  - 系统设置函数

  设置策略单次运行时的系统选项。
   函数原型：


```
set_option(max_wait_time=3600000, backtest_thread_num=1, ctp_md_info={})
```

  参数：
      参数名
   类型
   说明

     max_wait_time
  int
  api 调用触发流控（超出单位时间窗口的调用次数）时，允许系统冷却的最大等待时间（单位：毫秒）。 若系统当次冷却需要的时间>max_wait_time，api 调用失败会返回流控错误，需要策略自行处理（例如捕获错误提示中的需等待时间，自行等待相应时间）。 默认 max_wait_time=3600000 ，即最大 3600000 毫秒，可设范围[0,3600000].

   backtest_thread_num
  int
  回测运行的最大线程个数。默认 backtest_thread_num=1 ，即回测运行最多使用 1 个线程，可设范围[1,32].

   ctp_md_info
  dict
  ctp柜台tick行情设置


   返回值：
   None
   示例：


```
def init(context):
    set_option(max_wait_time=3000)
	set_option(backtest_thread_num=4)
```



```
def init(context):
	set_option(max_wait_time=3000, backtest_thread_num=4)
```

  注意：
   设置 max_wait_time ，在回测模式/实时模式均可生效，与 run()中设定的策略模式 mode 一致。
  用户策略触发流控规则后，掘金系统默认会自动冷却，等待下一时间窗口再请求下一轮，不会中止策略；只有系统当次冷却需要的时间超出 max_wait_time 时，才会返回流控错误并终止策略。
  如果自定义最大等待时间 max_wait_time=0 ，触发流控规则后会返回流控错误并中止策略。如果不想中止策略，可根据流控错误提示中的等待时间，自行冷却，再次发起调用请求。

  设置 backtest_thread_num ，只对回测模式生效。

   示例：
   连CTP柜台tick行情



```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):
    symbols = 'SHSE.600000, SZSE.000001, CFFEX.IC2406, SHFE.rb2409'
    subscribe(symbols=symbols, frequency='tick')

def on_tick(context, tick):
    print('symbol:{}, tick:{}'.format(tick['symbol'], tick))

if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
        backtest_match_mode市价撮合模式，以下一tick/bar开盘价撮合:0，以当前tick/bar收盘价撮合：1
    '''
    # 设置CTP柜台行情地址
    set_option(ctp_md_info={'addr':'101.230.102.238:51213'})

    run(strategy_id='55bdf284-0049-11ee-b9da-00ff15ce52e0',
        filename='main.py',
        mode=MODE_LIVE,
        token='2c4e3c59cde776ebc268bf6d7b4c457f204482b3',
        backtest_start_time='2024-01-01 09:00:00',
        backtest_end_time='2024-05-01 09:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
```

## #  log - 日志函数

   函数原型：


```
log(level, msg, source)
```

  参数：
     参数名
  类型
  说明

     level
  str
  日志级别  debug ,  info ,  warning ,  error

   msg
  str
  信息

   source
  str
  来源


   返回值：
   None
   示例：


```
log(level='info', msg='平安银行信号触发', source='strategy')
```

  注意：
   1.  log 函数仅支持 实时模式 ，输出到终端策略日志处。
   2.  level 输入无效参数不会报错，终端日志无显示。
   3.  参数类型报 NameError 错误,缺少参数报 TypeError 错误。
   4.  重启终端日志记录会自动清除，需要记录日志到本地的，可以使用 Python 的 logging 库


## #   get_strerror  - 查询错误码的错误描述信息

   函数原型：


```
get_strerror(error_code)
```

  参数：
     参数名
  类型
  说明

     error_code
  int
  错误码


  全部  错误码详细信息
   返回值：
  错误原因描述信息字符串
   示例：


```
err = get_strerror(error_code=1010)
print(err)
```

  输出：


```
b'\xe6\x97\xa0\xe6\xb3\x95\xe8\x8e\xb7\xe5\x8f\x96\xe6\x8e\x98\xe9\x87\x91\xe6\x9c\x8d\xe5\x8a\xa1\xe5\x99\xa8\xe5\x9c\xb0\xe5\x9d\x80\xe5\x88\x97\xe8\xa1\xa8'
```

  注意：
  error_code 值输入错误无报错，返回值为空。


## #   get_version  - 查询 api 版本

   函数原型：


```
get_version()
```

  返回值：
  字符串 当前 API 版本号
   示例：


```
version = get_version()
print(version)
```

  输出：


```
3.0.127
```



      ←

        标的池

        其他事件

      →

---

## 动态参数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%8A%A8%E6%80%81%E5%8F%82%E6%95%B0.html

<!DOCTYPE html>




     动态参数 - 掘金量化












# #  动态参数

  动态参数仅在 仿真交易和实盘交易 下生效， 可在终端设置和修改。
  动态参数通过策略调用接口实现策略和掘金界面参数交互， 在不停止策略运行的情况下，界面修改参数（移开光标，修改就会生效）会对策略里的指定变量做修改



## #   add_parameter  - 增加动态参数

   函数原型：


```
add_parameter(key, value, min=0, max=0, name='', intro='', group='', readonly=False)
```

  参数：
     参数名
  类型
  说明

     key
  str
  参数的键

   value
  double
  参数的值

   min
  double
  最小值

   max
  double
  最大值

   name
  str
  参数名称

   intro
  str
  参数说明

   group
  str
  参数的组

   readonly
  bool
  是否为只读参数


   返回值：
   None
   示例：


```
context.k_value = 80
add_parameter(key='k_value', value=context.k_value, min=0, max=100, name='k值阀值', intro='调整k值', group='1', readonly=False)
```

## #   set_parameter  - 修改已经添加过的动态参数

  **注意：**需要保持 key 键名和添加过的动态参数的 key 一致，否则不生效，无报错
   函数原型：


```
set_parameter(key, value, min=0, max=0, name='', intro='', group='', readonly=False)
```

  参数：
     参数名
  类型
  说明

     key
  str
  参数的键

   value
  double
  参数的值

   min
  double
  最小值

   max
  double
  最大值

   name
  str
  参数名称

   intro
  str
  参数说明

   group
  str
  参数的组

   readonly
  bool
  是否为只读参数


   返回值：
   None
   示例：


```
context.k_xl = 0.3
set_parameter(key='k_value', value=context.k_xl, min=0, max=1, name='k值斜率', intro='调整k值斜率', group='1', readonly=False)
```

## #   on_parameter  - 动态参数修改事件推送

   函数原型：


```
on_parameter(context, parameter)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文

   parameter
  dict
  当前被推送的动态参数对象


   示例：


```
def on_parameter(context, parameter):
    print(parameter)
```

  输出：


```
{'key': 'k_value', 'value': 80.0, 'max': 100.0, 'name': 'k值阀值', 'intro': '调整k值', 'group': '1', 'min': 0.0, 'readonly': False}
```

## #  context.parameters - 获取所有动态参数

  返回数据类型为字典, key 为动态参数的 key, 值为动态参数对象
   示例：


```
print(context.parameters)
```

  输出：


```
{'k_value': {'key': 'k_value', 'value': 80.0, 'max': 100.0, 'name': 'k值阀值', 'intro': 'k值阀值', 'group': '1', 'min': 0.0, 'readonly': False}, 'd_value': {'key': 'd_value', 'value': 20.0, 'max': 100.0, 'name': 'd值阀值', 'intro': 'd值阀值', 'group': '1', 'min': 0.0, 'readonly': False}}
```



      ←

        交易事件

        标的池

      →

---

## 可转债增值数据函数（付费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%8F%AF%E8%BD%AC%E5%80%BA%E5%A2%9E%E5%80%BC%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0%EF%BC%88%E4%BB%98%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     可转债增值数据函数(付费) - 掘金量化












# #  可转债增值数据函数(付费)

  python 可转债数据 API 包含在 gm3.0.145 版本及以上版本


## #   bnd_get_conversion_price  - 查询可转债转股价变动信息

  查询可转债一段时间的转股价变动和转股结果
   函数原型：


```
bnd_get_conversion_price(symbol, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  可转债代码
  Y
  无
  必填，只能输入一个可转债的 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（转股价格生效日），%Y-%m-%d 格式， 默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（转股价格生效日），%Y-%m-%d 格式， 默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     pub_date
  str
  公告日期
  %Y-%m-%d 格式

   effective_date
  str
  转股价格生效日期
  %Y-%m-%d 格式

   execution_date
  str
  执行日期
  %Y-%m-%d 格式

   conversion_price
  float
  转股价格
  单位：元

   conversion_rate
  float
  转股比例
  单位：%

   conversion_volume
  float
  本期转股数
  单位：股

   conversion_amount_total
  float
  累计转股金额
  单位：万元，累计转债已经转为股票的金额，累计每次转股金额

   bond_float_amount_remain
  float
  债券流通余额
  单位：万元

   event_type
  str
  事件类型
  初始转股价，调整转股价，修正转股价

   change_reason
  str
  转股价变动原因
  发行，股权激励，股权分置，触发修正条款，其它变动原因，换股吸收合并， 配股，增发，上市，派息，送股，转增股，修正


   示例：


```
bnd_get_conversion_price(symbol='SZSE.123015')
```

  输出：


```
pub_date effective_date execution_date  conversion_price  conversion_rate  conversion_volume  conversion_amount_total  bond_float_amount_remain event_type change_reason
0  2022-07-29     2022-08-01     2022-08-01              2.38          42.0168                0.0                      0.0                       0.0      修正转股价     修正,触发修正条款
```

  注意：
   1.  本期转股数、累计转股金额、债券流通余额在执行日期收盘后才有数据。
   2.  当 start_date == end_date 时，取离 end_date 最近转股价格生效日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   bnd_get_call_info  - 查询可转债赎回信息

  查询可转债一段时间内的赎回情况
   函数原型：


```
bnd_get_call_info(symbol, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  可转债代码
  Y
  无
  必填，只能输入一个可转债的 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（公告日），%Y-%m-%d 格式， 默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（公告日），%Y-%m-%d 格式， 默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     pub_date
  str
  公告日
  赎回公告日，%Y-%m-%d 格式

   call_date
  str
  赎回日
  发行人行权日（实际），%Y-%m-%d 格式

   record_date
  str
  赎回登记日
  理论登记日，%Y-%m-%d 格式

   cash_date
  str
  赎回资金到账日
  投资者赎回款到账日

   call_type
  str
  赎回类型
  部分赎回，全部赎回

   call_reason
  str
  赎回原因
  满足赎回条件，强制赎回，到期赎回

   call_price
  float
  赎回价格
  单位：元/张，每百元面值赎回价格，即债券面值加当期应计利息（含税）

   interest_included
  bool
  是否包含利息
  False-不包含，True-包含


   示例：


```
bnd_get_call_info(symbol='SHSE.110041')
```

  输出：


```
pub_date   call_date record_date cash_date call_type call_reason  call_price  interest_included
0  2021-10-18  2021-11-05  2021-11-04      None      全部赎回        强制赎回     101.307               True
```

  注意：
  当 start_date == end_date 时，取离 end_date 最近公告日的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   bnd_get_put_info  - 查询可转债回售信息

  查询可转债一段时间内的回售情况
   函数原型：


```
bnd_get_put_info(symbol, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  可转债代码
  Y
  无
  必填，只能输入一个可转债的 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（公告日），%Y-%m-%d 格式， 默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（公告日），%Y-%m-%d 格式， 默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     pub_date
  str
  公告日
  回售公告日，%Y-%m-%d 格式

   put_start_date
  str
  赎回日
  投资者行权起始日，%Y-%m-%d 格式

   put_end_date
  str
  赎回登记日
  投资者行权截止日，%Y-%m-%d 格式

   cash_date
  str
  赎回资金到账日
  投资者回售款到账日

   put_reason
  str
  回售原因
  满足回售条款，满足附加回售条款

   put_price
  float
  回售价格
  单位：元/张，每百元面值回售价格（元），即债券面值加当期应计利息（含税）

   interest_included
  bool
  是否包含利息
  False-不包含，True-包含


   示例：


```
bnd_get_put_info(symbol='SZSE.128015')
```

  输出：


```
pub_date put_start_date put_end_date   cash_date put_reason  put_price  interest_included
0  2022-06-09     2022-06-16   2022-06-22  2022-06-29     满足回售条款    100.039               True
```

  注意：
  当 start_date == end_date 时，取离 end_date 最近公告日的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   bnd_get_amount_change  - 查询可转债剩余规模变动

  查询可转债转股、回售、赎回等事件导致的剩余规模变动的情况
   函数原型：


```
bnd_get_amount_change(symbol, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  可转债代码
  Y
  无
  必填，只能输入一个可转债的 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（变动日期），%Y-%m-%d 格式， 默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（变动日期），%Y-%m-%d 格式， 默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     pub_date
  str
  公告日
  %Y-%m-%d 格式

   change_date
  str
  变动日期
  %Y-%m-%d 格式

   change_type
  str
  变动类型
  首发，增发，转股，赎回，回售(注销)，到期

   change_amount
  float
  本次变动金额
  单位：万元

   remain_amount
  float
  剩余金额
  变动后金额，单位：万元


   示例：


```
bnd_get_amount_change(symbol='SZSE.123015')
```

  输出：


```
pub_date change_type change_date  change_amount  remain_amount
0  2022-10-10          转股  2022-09-30           8.91       10004.18
```

  注意：
   1.  变动类型指定为首发时，返回的剩余金额为发行金额。
   2.  当 start_date == end_date 时，取离 end_date 最近变动日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   bnd_get_analysis  - 查询可转债分析指标

  查询可转债分析指标
   gm SDK  3.0.172 版本新增
   函数原型：


```
bnd_get_analysis(symbol, start_date=None, end_date=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  可转债代码
  Y
  无
  必填，只能输入一个可转债的 symbol

   start_date
  str
  开始时间
  N
  None
  开始时间日期，%Y-%m-%d 格式，日期类型为交易日期，默认None表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间日期，%Y-%m-%d 格式，日期类型为交易日期，默认None表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  可转债代码
  查询分析指标的可转债代码

   trade_date
  str
  交易日期
  %Y-%m-%d 格式

   cnv_value
  float
  转股价值
  平价，是指当前每100元转债转换成股票的价值。转股价值=100×当前正股价格/当前转股价格

   cnv_premium
  float
  转股溢价
  转股溢价=转债价格-转股价值

   cnv_premium_rate
  float
  转股溢价率(%)
  转股溢价率=转债价格/转股价值-1，当转股溢价率越低时，转债价格和转股价值越接近，转债股性越强，转债的价格对正股的价格波动越敏感。当转股溢价率越高时，转股债性越强。

   arbitrage
  float
  套利空间
  转股溢价率为负时的折价套利空间

   cur_yield
  float
  当期收益率(%)
  当期收益率=年息票利息/转债价格

   pure_value_cb
  float
  纯债价值(中债基准)
  债底，是指在不考虑转债提前赎回、回售或转股的情况下，将转债各期的现金流，根据同期限、同评级的企业债券到期收益率进行贴现，所得贴现值之和即为当前时点转债的纯债价值。 （中债基准）

   pure_value_csi
  float
  纯债价值(中证基准)
  债底，是指在不考虑转债提前赎回、回售或转股的情况下，将转债各期的现金流，根据同期限、同评级的企业债券到期收益率进行贴现，所得贴现值之和即为当前时点转债的纯债价值。 （中证基准）

   pure_premium
  float
  纯债溢价
  纯债溢价=转债价格-纯债价值

   pure_premium_rate
  float
  纯债溢价率(%)
  纯债溢价率=转债价格/纯债价值-1

   floor_premium_rate
  float
  平价底价溢价率(%)
  平价底价溢价率=转股价值/转债价值，根据平价底价溢价率，可将转债划分成三类风格：平价底价溢价率大于1.2为偏股型转债，介于0.8和1.2之间为混合型转债，小于0.8为偏债型转债。

   cnv_dil_rate
  float
  转股稀释率(%)
  (正股总股本+转股数量)/正股总股本

   circ_dil_rate
  float
  对流通股稀释率(%)
  (正股流通股本+转股数量)/正股流通股本


   示例：


```
bnd_get_analysis(symbol='SHSE.118022', start_date=None, end_date=None)
```

  输出：


```
symbol                 trade_date   cnv_value  cnv_premium  \
0  SHSE.118022  2024-11-25T00:00:00+08:00  40.1802962   60.9697038
   cnv_premium_rate   arbitrage   cur_yield  pure_value_cb  pure_value_csi  \
0      151.74030449 -60.9697038  0.98863075   103.81204257    103.58579086
   pure_premium  pure_premium_rate  floor_premium_rate  cnv_dil_rate  \
0   -2.43579086        -2.35147199        -61.21061019    9.78546274
   circ_dil_rate
0     9.78546274
```

  注意：
   1.  变动类型指定为首发时，返回的剩余金额为发行金额。
   2.  当 start_date == end_date 时，取离 end_date 最近变动日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   get_open_call_auction  - 查询集合竞价开盘成交

  查询可转债开盘成交数据
   gm SDK  3.0.176 版本新增
   函数原型：


```
get_open_call_auction (symbols, trade_date=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  基金代码
  Y
  无
  必填，可输入多个，使用时参考symbol. 采用 str 格式时，多个标的代码必须用英文逗号分割（逗号中间不能有空格），如：'SHSE.113689, SZSE.123100'; 采用 list 格式时，多个标的代码示例：['SHSE.113689', 'SZSE.123100']

   trade_date
  str
  交易日期
  N
  None
  交易日期，YYYY-MM-DD 格式，默认None返回最新交易日


   返回值：返回dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  标的代码
  格式exchange.sec_id（SHSE.600000, SZSE.000001）

   time
  str
  开盘集合竞价撮合时间
  交易日09:25，%Y-%m-%d %H:%M:%S 格式

   current_price
  float
  当前最新价（不复权）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的最新成交价Tick.price，即开盘价

   open_volume
  int
  开盘成交量（张）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的累计成交量Tick.cum_volume

   open_amount
  float
  开盘成交额（元）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的累计成交额Tick.cum_amount

   ask_v1~ask_v5
  float
  五档卖量
  09:25五档卖量Tick.quotes[0].ask_v~Tick.quotes[4].ask_v。

   ask_p1~ask_p5
  float
  五档卖价
  09:25五档卖价Tick.quotes[0].ask_p~Tick.quotes[4].ask_p。

   bid_v1~bid_v5
  float
  五档买量
  09:25五档买量Tick.quotes[0].bid_v~Tick.quotes[4].bid_v。

   bid_p1~bid_p5
  float
  五档买价
  09:25五档买价Tick.quotes[0].bid_p~Tick.quotes[4].bid_p。


   示例：


```
get_open_call_auction(symbols='SHSE.113689, SZSE.123100', trade_date='2025-03-27')
```

  输出：


```
symbol                 time  current_price  open_volume  open_amount  \
0  SHSE.113689  2025-03-27 09:25:00   143.97999573          860     123823.0
1  SZSE.123100  2025-03-27 09:25:00   122.80000305         3310     406468.0
   ask_v1  ask_v2  ask_v3  ask_v4  ask_v5        ask_p1        ask_p2  \
0     280      20      80     260      20  143.97999573  144.00100708
1     140      20      10      10      50  122.80000305  122.92299652
         ask_p3        ask_p4        ask_p5  bid_v1  bid_v2  bid_v3  bid_v4  \
0  144.03999329  144.08799744  144.25599670      10      30     160     860
1  123.00000000  123.00399780  123.09100342     160      90     210     160
   bid_v5        bid_p1        bid_p2  bid_p3        bid_p4        bid_p5
0     340  143.56700134  143.53700256   143.5  143.00300598  143.00199890
1     500  122.58100128  122.57399750   122.5  122.46499634  122.34999847
```

  注意：
   1.  开盘集合竞价的成交数据于每个交易日09:26更新，09:26后可查询当天开盘集合竞价，在09:26前查询当天开盘集合竞价返回空。
   2.  如果输入symbols包含不存在的标的代码，会报错。
   3.  如果开盘集合竞价没有发生成交，curret_price, open_volume, open_amount返回0.
   4.  数据最早为2025-02-21。


      ←

        基金增值数据函数（付费）

        交易函数

      →

---

## 基本函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%9F%BA%E6%9C%AC%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     基本函数 - 掘金量化












# #  基本函数



## #  init - 初始化策略

  初始化策略, 策略启动时自动执行。可以在这里初始化策略配置参数。
   函数原型：


```
init(context)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文，全局变量可存储在这里


   示例：


```
def init(context):
    # 订阅bar
    subscribe(symbols='SHSE.600000,SHSE.600004', frequency='30s', count=5)
	# 增加对象属性，如:设置一个股票资金占用百分比
	context.percentage_stock = 0.8
```

  注意：
   1.  回测模式下init函数里不支持交易操作，仿真模式和实盘模式支持。
   2.  init只会在策略启动时运行一次，如果不是每天重启策略，每天需要查询更新数据，可以通过设置定时任务执行。


## #  schedule - 定时任务配置

  在指定时间自动执行策略算法, 通常用于选股类型策略
   函数原型：


```
schedule(schedule_func, date_rule, time_rule)
```

  参数：
     参数名
  类型
  说明

     schedule_func
  function
  策略定时执行算法

   date_rule
  str
  n + 时间单位， 可选'd/w/m' 表示 n 天/n 周/n 月

   time_rule
  str
  执行算法的具体时间 (%H:%M:%S 格式)


   返回值：
   None
   示例：


```
def init(context):
    #每天的19:06:20执行策略algo_1
    schedule(schedule_func=algo_1, date_rule='1d', time_rule='19:06:20')
	#每月的第一个交易日的09:40:00执行策略algo_2
	schedule(schedule_func=algo_2, date_rule='1m', time_rule='9:40:00')

def algo_1(context):
    print(context.symbols)

def algo_2(context):
    order_volume(symbol='SHSE.600000', volume=200, side=OrderSide_Buy, order_type=OrderType_Market, position_effect=PositionEffect_Open)
```

  注意：
   1.  time_rule 的时,分,秒均不可以只输入个位数，例: '9:40:0' 或 '14:5:0'
   2.  目前暂时支持 1d 、 1w 、 1m ，其中 1w 、 1m 仅用于回测


## #  run - 运行策略

   函数原型：


```
run(strategy_id='', filename='', mode=MODE_UNKNOWN, token='', backtest_start_time='',
    backtest_end_time='', backtest_initial_cash=1000000,
    backtest_transaction_ratio=1, backtest_commission_ratio=0,
    backtest_slippage_ratio=0, backtest_adjust=ADJUST_NONE, backtest_check_cache=1,
    serv_addr='', backtest_match_mode=0, backtest_intraday=0)
```

  参数：
     参数名
  类型
  说明

     strategy_id
  str
  策略 id

   filename
  str
  策略文件名称

   mode
  int
  策略模式 MODE_LIVE(实时)=1 MODE_BACKTEST(回测) =2

   token
  str
  用户标识

   backtest_start_time
  str
  回测开始时间 (%Y-%m-%d %H:%M:%S 格式)

   backtest_end_time
  str
  回测结束时间 (%Y-%m-%d %H:%M:%S 格式)

   backtest_initial_cash
  double
  回测初始资金, 默认 1000000

   backtest_transaction_ratio
  double
  回测成交比例, 默认 1.0, 即下单 100%成交

   backtest_commission_ratio
  double
  回测佣金比例, 默认 0

   backtest_slippage_ratio
  double
  回测滑点比例, 默认 0

   backtest_adjust
  int
  回测复权方式(默认不复权) ADJUST_NONE(不复权)=0 ADJUST_PREV(前复权)=1 ADJUST_POST(后复权)=2

   backtest_check_cache
  int
  回测是否使用缓存：1 - 使用， 0 - 不使用；默认使用

   serv_addr
  str
  终端服务地址, 默认本地地址, 可不填，若需指定应输入 ip+端口号，如"127.0.0.1:7001"

   backtest_match_mode
  int
  回测市价撮合模式： 1-实时撮合：在当前 bar 的收盘价/当前 tick 的 price 撮合，0-延时撮合：在下个 bar 的开盘价/下个 tick 的 price 撮合，默认是模式 0

   backtest_intraday
  int
  回测模式不订阅行情，current 和 current_price 行情数据查询函数返回的日线价格类型：
1 - 当日收盘价:  回测当前交易日的日线收盘价（T日盘中和盘后均为T日收盘价）;
0 - 历史收盘价：回测当前时刻的历史最新日线收盘价（T日盘中为T-1日收盘价，T日盘后为T日收盘价），默认是0


   返回值：
   None
   示例：


```
run(strategy_id='strategy_1', filename='main.py', mode=MODE_BACKTEST, token='token_id',
    backtest_start_time='2016-06-17 13:00:00', backtest_end_time='2017-08-21 15:00:00')
```

  注意：
   1.  run 函数中， mode=1 也可改为 mode=MODE_LIVE ，两者等价， backtest_adjust 同理
   2.  在前复权和后复权回测模式下，是不会处理分红、送股、拆分事件的，因为除权除息产生的变动已经通过复权因子调整反映在前复权/后复权股价中，无需重复处理。不复权会自动处理分红送转。
   3.  filename 指运行的 py 文件名字，如该策略文件名为 Strategy.py,则此处应填"Strategy.py"


## #  stop - 停止策略

  停止策略，退出策略进程
   函数原型：


```
stop()
```

  返回值：
   None
   示例：


```
#若订阅过的代码集合为空，停止策略
if not context.symbols:
   stop()
```

## #  timer - 设置定时器

  设定定时器的间隔秒数，每过设定好的秒数调用一次计时器 timer_func()，直到 timer_stop()结束定时器为止。
（仿真、实盘场景适用，回测模式下不生效）
   函数原型：


```
timer(timer_func, period, start_delay)
```

  参数：
     参数名
  类型
  说明

     timer_func
  function
  在 timer 设置的时间到达时触发的事件函数

   period
  int
  定时事件间隔毫秒数，设定每隔多少毫秒触发一次定时器，范围在 [1,43200000]

   start_delay
  int
  等待秒数(毫秒)，设定多少毫秒后启动定时器，范围在[0,43200000]


   返回值： dict
     字段
  类型
  说明

     timer_status
  int
  定时器设置是否成功，成功=0，失败=非 0 错误码（timer_id 无效）。

   timer_id
  int
  设定好的定时器 id




## #   timer_stop  - 停止定时器

  停止已设置的定时器
   函数原型：


```
timer_stop(timer_id)
```

  参数：
     字段
  类型
  说明

     timer_id
  int
  要停止的定时器 id


   返回值：
     字段
  类型
  说明

     is_stop
  bool
  是否成功停止，True or False


   示例：


```
def init(context):
    # 每隔1分钟执行ontime_1, 即时启动
    context.timerid_1 = timer(timer_func=ontimer_1, period=60000, start_delay=0)
    context.counter_1 = 0

    # 每隔半小时执行ontime_2, 5分钟之后启动
    context.timerid_2 = timer(timer_func=ontimer_2, period=300000, start_delay=0)
    print('启动定时器2：', context.now)
    context.counter_2 = 0

def ontimer_1(context):
    # 定时器执行次数计数
    context.counter_1 += 1
    # 定时器执行逻辑
    print('定时器1：', context.now)

def ontimer_2(context):
    # 定时器执行次数计数
    context.counter_2 += 1
    # 定时器执行逻辑（如查询账户资金）
    cash = context.account().cash

    print('定时器2：', context.now)

    # 按执行次数条件停止定时器
    if context.counter_1 >= 5:
        ret1 = timer_stop(context.timerid_1['timer_id'])
        if ret1:
            print("结束1分钟定时器")

    if context.counter_2 >= 10:
        ret2 = timer_stop(context.timerid_2['timer_id'])
```

  注意：
   1.  仿真、实盘场景适用，回测模式下不生效
   2.  period 从前一次事件函数开始执行时点起算，若下一次事件函数需要执行时，前一次事件函数没运行完毕，等待上一个事件执行完毕再执行下一个事件。


      ←

        数据结构

        数据订阅

      →

---

## 基金交易函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%9F%BA%E9%87%91%E4%BA%A4%E6%98%93%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     基金交易函数 - 掘金量化












# #  基金交易函数



## #   fund_etf_buy  - ETF 申购

  仅在 实盘 中可以使用


```
fund_etf_buy(symbol, volume, price, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  申购数量

   price
  float
  申购价格

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict]


## #   fund_etf_redemption  - ETF 赎回

  仅在 实盘 中可以使用


```
fund_etf_redemption(symbol, volume, price, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  赎回数量

   price
  float
  赎回价格

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict]


## #   fund_subscribing  - 基金认购

  仅在 实盘 中可以使用


```
fund_subscribing(symbol, volume, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  认购数量

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict]


## #   fund_buy  - 基金申购

  仅在 实盘 中可以使用


```
fund_buy(symbol, volume, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  申购数量

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict]


## #   fund_redemption  - 基金赎回

  仅在 实盘 中可以使用


```
fund_redemption(symbol, volume, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  认购数量

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict]


      ←

        新股新债交易函数

        债券交易函数

      →

---

## 基金增值数据函数（付费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E5%9F%BA%E9%87%91%E5%A2%9E%E5%80%BC%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0%EF%BC%88%E4%BB%98%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     基金增值数据函数(付费) - 掘金量化












# #  基金增值数据函数(付费)

  python 基金数据 API 包含在 gm3.0.145 版本及以上版本


## #   fnd_get_etf_constituents  - 查询 ETF 最新成分股

  查询某只 ETF 在最新交易日的成分股持有情况和现金替代信息
   函数原型：


```
fnd_get_etf_constituents(etf)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     etf
  str
  ETF 代码
  Y
  无
  必填，只能输入一个 ETF 的 symbol ，如： 'SZSE.159919'


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     etf
  str
  ETF 代码


   etf_name
  str
  ETF 名称


   trade_date
  str
  交易日期
  %Y-%m-%d 格式

   symbol
  str
  成分股代码
  exchange.sec_id

   amount
  str
  股票数量
  T 日内容中最小申购赎回单位所对应的各成分股数量

   cash_subs_type
  str
  现金替代标志
  基金管理人对于每一只成分股使用现金替代情况的态度 1-禁止 2-允许 3-必须 4-退补

   cash_subs_sum
  float
  固定替代金额
  单位：人民币元

   cash_premium_rate
  float
  现金替代溢价比例
  单位：%


   示例：


```
fnd_get_etf_constituents(etf='SHSE.510050')
```

  输出：


```
etf   etf_name  trade_date       symbol   amount cash_subs_type  cash_subs_sum  cash_premium_rate
0   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601688   2100.0             禁止            0.0               10.0
1   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600809    200.0             禁止            0.0               10.0
2   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600893    500.0             禁止            0.0               10.0
3   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601398  12700.0             禁止            0.0               10.0
4   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601166   5300.0             禁止            0.0               10.0
5   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600196    500.0             禁止            0.0               10.0
6   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600031   2200.0             禁止            0.0               10.0
7   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600585    900.0             禁止            0.0               10.0
8   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600588    600.0             禁止            0.0               10.0
9   SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600900   4100.0             禁止            0.0               10.0
10  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601288  11600.0             禁止            0.0               10.0
11  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601633    400.0             禁止            0.0               10.0
12  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601899   5200.0             禁止            0.0               10.0
13  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600519    200.0             禁止            0.0               10.0
14  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600010   8300.0             禁止            0.0               10.0
15  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600028   4900.0             禁止            0.0               10.0
16  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600030   3500.0             禁止            0.0               10.0
17  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600036   4500.0             禁止            0.0               10.0
18  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600276   1600.0             禁止            0.0               10.0
19  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600436    100.0             禁止            0.0               10.0
20  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600309    600.0             禁止            0.0               10.0
21  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600346    800.0             禁止            0.0               10.0
22  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600104   1700.0             禁止            0.0               10.0
23  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600111    800.0             禁止            0.0               10.0
24  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600690   1400.0             禁止            0.0               10.0
25  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600745    300.0             禁止            0.0               10.0
26  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600837   3500.0             禁止            0.0               10.0
27  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601628    600.0             禁止            0.0               10.0
28  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601318   4000.0             禁止            0.0               10.0
29  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601601   1200.0             禁止            0.0               10.0
30  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600887   1900.0             禁止            0.0               10.0
31  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601857   3500.0             禁止            0.0               10.0
32  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600048   2600.0             禁止            0.0               10.0
33  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601668   7600.0             禁止            0.0               10.0
34  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601888    400.0             禁止            0.0               10.0
35  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601012   2200.0             禁止            0.0               10.0
36  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600570    500.0             禁止            0.0               10.0
37  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600438   1000.0             禁止            0.0               10.0
38  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601088   1200.0             禁止            0.0               10.0
39  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601919   2300.0             禁止            0.0               10.0
40  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.603288    500.0             禁止            0.0               10.0
41  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601211   1600.0             禁止            0.0               10.0
42  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.603986    200.0             禁止            0.0               10.0
43  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.603799    500.0             禁止            0.0               10.0
44  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.603501    300.0             禁止            0.0               10.0
45  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601066    500.0             禁止            0.0               10.0
46  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.603259    700.0             禁止            0.0               10.0
47  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.600905   3100.0             禁止            0.0               10.0
48  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601995    200.0             禁止            0.0               10.0
49  SHSE.510050  华夏上证50ETF  2022-10-20  SHSE.601728   2000.0             禁止            0.0               10.0
```

  注意：
   1.  只返回上交所、深交所的成分股，不提供其余交易所的成分股票。


## #   fnd_get_portfolio  - 查询基金资产组合

  查询某只基金在指定日期的基金资产组合（股票持仓、债券持仓等）
   函数原型：


```
fnd_get_portfolio(fund, report_type, portfolio_type, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     fund
  str
  基金代码
  Y
  无
  必填，只能输入一个基金的 symbol ，如： 'SZSE.161133'

   report_type
  int
  报表类别
  Y
  无
  公布持仓所在的报表类别，必填，可选： 1:第一季度 2:第二季度 3:第三季报 4:第四季度 6:中报 12:年报

   portfolio_type
  str
  投资组合类型
  Y
  无
  必填，可选以下其中一种组合： 'stk' - 股票投资组合 'bnd' - 债券投资组合 'fnd' - 基金投资组合

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（公告日），%Y-%m-%d 格式，默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（公告日），%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
   portfolio_type='stk' 时，返回基金持有的股票投资组合信息 portfolio_stock
     字段名
  类型
  中文名称
  说明

     fund
  str
  基金代码
  查询股票资产组合的基金代码

   fund_name
  str
  基金名称


   pub_date
  str
  公告日期
  在指定时间段内的公告日期，%Y-%m-%d 格式

   period_end
  str
  报告期
  持仓截止日期，%Y-%m-%d 格式

   symbol
  str
  股票代码
  exchange.sec_id

   sec_name
  str
  股票名称


   hold_share
  float
  持仓股数


   hold_value
  float
  持仓市值


   nv_rate
  float
  占净值比例
  单位：%

   ttl_share_rate
  float
  占总股本比例
  单位：%

   clrc_share_rate
  float
  占流通股比例
  单位：%


   portfolio_type='bnd' 时，返回基金持有的债券投资组合信息 portfolio_bond
     字段名
  类型
  中文名称
  说明

     fund
  str
  基金代码
  查询债券资产组合的基金代码

   fund_name
  str
  基金名称


   pub_date
  str
  公告日期
  在指定时间段内的公告日期，%Y-%m-%d 格式

   period_end
  str
  报告期
  持仓截止日期，%Y-%m-%d 格式

   symbol
  str
  债券代码
  exchange.sec_id

   sec_name
  str
  债券名称


   hold_share
  float
  持仓数量


   hold_value
  float
  持仓市值


   nv_rate
  float
  占净值比例
  单位：%


   portfolio_type='fnd' 时，返回基金持有的基金投资组合信息 portfolio_fund
     字段名
  类型
  中文名称
  说明

     fund
  str
  基金代码
  查询基金资产组合的基金代码

   fund_name
  str
  基金名称


   pub_date
  str
  公告日期
  在指定时间段内的公告日期，%Y-%m-%d 格式

   period_end
  str
  报告期
  持仓截止日期，%Y-%m-%d 格式

   symbol
  str
  持仓基金代码
  exchange.sec_id

   sec_name
  str
  持仓基金名称


   hold_share
  float
  持有份额


   hold_value
  float
  期末市值


   nv_rate
  float
  占净值比例
  单位：%


   示例：


```
fnd_get_portfolio(fund='SHSE.510300', start_date='2022-01-01', end_date='2022-10-01', report_type=1, portfolio_type='stk')
```

  输出：


```
fund     fund_name    pub_date  period_end       symbol sec_name  hold_share  hold_value  nv_rate  ttl_share_rate  circ_share_rate
0   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.600519     贵州茅台  1.4424e+06  2.4794e+09     5.54          5.6773           0.1148
1   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.600900     长江电力  2.6245e+07  5.7738e+08     1.29          1.3221           0.1154
2   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SZSE.000333     美的集团  1.1271e+07  6.4247e+08     1.44          1.4711           0.1648
3   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SZSE.301102     兆讯传媒  6.4140e+03  1.9947e+05     0.00          0.0005           0.0149
4   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SZSE.301088     戎美股份  7.0360e+03  1.3434e+05     0.00          0.0003           0.0134
5   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.600036     招商银行  2.8572e+07  1.3372e+09     2.99          3.0618           0.1385
6   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SZSE.300750     宁德时代  3.2106e+06  1.6448e+09     3.68          3.7661           0.1575
7   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.688223     晶科能源  2.1300e+05  2.1620e+06     0.00          0.0050           0.0161
8   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.601166     兴业银行  3.3444e+07  6.9129e+08     1.55          1.5829           0.1705
9   SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.601318     中国平安  2.4996e+07  1.2110e+09     2.71          2.7730           0.2307
10  SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.688282     理工导航  3.1850e+03  1.5119e+05     0.00          0.0003           0.0162
11  SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.603259     药明康德  4.7151e+06  5.2989e+08     1.18          1.2133           0.1851
12  SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.688234     天岳先进  6.7590e+03  3.4451e+05     0.00          0.0008           0.0200
13  SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SHSE.601012     隆基股份  9.9703e+06  7.1976e+08     1.61          1.6481           0.1842
14  SHSE.510300  华泰柏瑞沪深300ETF  2022-04-22  2022-03-31  SZSE.000858      五粮液  4.4720e+06  6.9342e+08     1.55          1.5878           0.1152
```

  注意：
   1.  仅提供场内基金（ETF、LOF、FOF-LOF）的资产组合数据。
   2.  当 start_date == end_date 时，取离 end_date 最近公告日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   fnd_get_net_value  - 查询基金净值数据

  查询某只基金在指定时间段的基金净值数据
   函数原型：


```
fnd_get_net_value(fund, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     fund
  str
  基金代码
  Y
  无
  必填，只能输入一个基金的 symbol ，如： 'SZSE.159919'

   start_date
  str
  开始时间
  N
  ""
  开始时间日期，%Y-%m-%d 格式，默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期，%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     fund
  str
  基金代码
  查询净值的基金代码

   trade_date
  str
  交易日期
  指定时间段内的交易日期，%Y-%m-%d 格式

   unit_nv
  float
  单位净值
  T 日单位净值是每个基金份额截至 T 日的净值（也是申赎的价格）

   unit_nv_accu
  float
  累计单位净值
  T 日累计净值是指，在基金成立之初投资该基金 1 元钱，在现金分红方式下，截至 T 日账户的净值

   unit_nv_adj
  float
  复权单位净值
  T 日复权净值是指，在基金成立之初投资该基金 1 元钱，在分红再投资方式下，截至 T 日账户的净值


   示例：


```
fnd_get_net_value(fund='SHSE.510300')
```

  输出：


```
fund  trade_date  unit_nv  unit_nv_accu  unit_nv_adj
0  SHSE.510300  2022-10-19     3.84        1.6233       1.6579
```

  注意：
   1.  仅提供场内基金（ETF、LOF、FOF-LOF）的净值数据。
   2.  当 start_date == end_date 时，取离 end_date 最近日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   fnd_get_adj_factor  - 查询基金复权因子

  查询某只基金在一段时间内的复权因子
   函数原型：


```
fnd_get_adj_factor(fund, start_date="", end_date="", base_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     fund
  str
  基金代码
  Y
  无
  必填，只能输入一个基金的 symbol ，如： 'SZSE.159919'

   start_date
  str
  开始时间
  N
  ""
  开始时间交易日期，%Y-%m-%d 格式， 默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间交易日期，%Y-%m-%d 格式， 默认 "" 表示最新时间

   base_date
  str
  复权基准日
  N
  ""
  前复权的基准日，%Y-%m-%d 格式， 默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     trade_date
  str
  交易日期
  开始时间至结束时间的交易日期

   adj_factor_bwd_acc
  float
  当日累计后复权因子
  除权日，T 日累计后复权因子= T-1 日累计后复权因子 * 折算比例 * T-1 日价格 / (T- 1日价格 - 本次单位分红), 其余情况，T 日累计后复权因子=T-1 日累计后复权因子

   adj_factor_fwd
  float
  当日前复权因子
  T 日前复权因子=T 日累计后复权因子/复权基准日累计后复权因子


   示例：


```
fnd_get_adj_factor(fund='SZSE.161725', start_date="2021-12-01", end_date="2022-01-01", base_date="")
```

  输出：


```
trade_date  adj_factor_bwd_acc  adj_factor_fwd
0   2021-12-01              3.8359          0.9484
1   2021-12-02              3.8359          0.9484
2   2021-12-03              3.8359          0.9484
3   2021-12-06              3.8359          0.9484
4   2021-12-07              3.8359          0.9484
5   2021-12-08              3.8359          0.9484
6   2021-12-09              3.9113          0.9671
7   2021-12-10              3.9113          0.9671
8   2021-12-13              3.9113          0.9671
9   2021-12-14              3.9113          0.9671
10  2021-12-15              3.9113          0.9671
11  2021-12-16              3.9113          0.9671
12  2021-12-17              3.9113          0.9671
13  2021-12-20              3.9113          0.9671
14  2021-12-21              3.9113          0.9671
15  2021-12-22              3.9113          0.9671
16  2021-12-23              3.9113          0.9671
17  2021-12-24              3.9113          0.9671
18  2021-12-27              3.9113          0.9671
19  2021-12-28              3.9113          0.9671
20  2021-12-29              3.9113          0.9671
21  2021-12-30              3.9113          0.9671
22  2021-12-31              4.0445          1.0000
```

  注意：
   1.  T+1 日复权因子会二次更新，分别在 T 日 19:00 和 T+1 日 19:00 更新。仅提供场内基金（ETF、LOF、FOF-LOF）的复权因子数据。
   2.  复权价格计算：
 T日后复权价格 = T日不复权价格 * T日累计后复权因子   T日前复权价格 = T日不复权价格 * T日前复权因子
   3.  上市首日后复权因子合累计后复权因子为 1，最近一次除权除息日后的交易日前复权因子为 1
   4.  前复权基准日 base_date 应不早于设定的结束日期 end_date ，不晚于最新交易日。若设定的基准日早于 end_date 则等同于 end_date ，若设定的基准日晚于最新交易日则等同于最新交易日。
   5.  当 start_date  小于或等于  end_date  时取指定时间段的数据,当 start_date  >  end_date 时返回报错.


## #   fnd_get_dividend  - 查询基金分红信息

  查询指定基金在一段时间内的分红信息
   函数原型：


```
fnd_get_dividend(fund, start_date, end_date)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     fund
  str
  基金代码
  Y
  无
  必填，只能输入一个基金的 symbol ，如： 'SZSE.159919'

   start_date
  str
  开始时间
  Y
  无
  必填，开始时间日期（场内除息日），%Y-%m-%d 格式

   end_date
  str
  结束时间
  Y
  无
  必填，结束时间日期（场内除息日），%Y-%m-%d 格式


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     fund
  str
  基金代码
  查询分红信息的基金代码

   pub_date
  str
  公告日
  %Y-%m-%d 格式

   event_progress
  str
  方案进度
  正式，预案

   dvd_ratio
  float
  派息比例
  10:X，每 10 份税前分红

   dvd_base_date
  str
  分配收益基准日
  %Y-%m-%d 格式

   rt_reg_date
  str
  权益登记日
  %Y-%m-%d 格式

   ex_act_date
  str
  实际除息日
  %Y-%m-%d 格式

   ex_dvd_date
  str
  场内除息日
  %Y-%m-%d 格式

   pay_dvd_date
  str
  场内红利发放日
  %Y-%m-%d 格式

   trans_dvd_date
  str
  场内红利款账户划出日
  %Y-%m-%d 格式

   reinvest_cfm_date
  str
  红利再投资确定日
  %Y-%m-%d 格式

   ri_shr_arr_date
  str
  红利再投资份额到账日
  %Y-%m-%d 格式

   ri_shr_rdm_date
  str
  红利再投资赎回起始日
  %Y-%m-%d 格式

   earn_distr
  float
  可分配收益
  单位：元

   cash_pay
  float
  本期实际红利发放
  单位：元

   base_unit_nv
  float
  基准日基金份额净值
  单位：元

   dvd_target
  str
  分派对象



   示例：


```
fnd_get_dividend(fund='SZSE.161725', start_date="2000-01-01", end_date="2022-09-07")
```

  输出：


```
fund    pub_date event_progress  dvd_ratio dvd_base_date rt_reg_date ex_act_date ex_dvd_date pay_dvd_date trans_dvd_date reinvest_cfm_date ri_shr_arr_date ri_shr_rdm_date  earn_distr  cash_pay  base_unit_nv
0  SZSE.161725  2021-09-02             正式       0.12    2021-08-27  2021-09-07  2021-09-07  2021-09-08   2021-09-09     2021-09-09        2021-09-07      2021-09-08      2021-09-09  3.7574e+10       0.0        1.1893
1  SZSE.161725  2021-12-07             正式       0.28    2021-12-02  2021-12-09  2021-12-09  2021-12-10   2021-12-13     2021-12-13        2021-12-09      2021-12-10      2021-12-13  3.3549e+10       0.0        1.3696
2  SZSE.161725  2021-12-29             正式       0.45    2021-12-24  2021-12-31  2021-12-31  2022-01-04   2022-01-05     2022-01-05        2021-12-31      2022-01-04      2022-01-05  3.0723e+10       0.0        1.4178
```

  注意：
   1.  仅提供场内基金（ETF、LOF、FOF-LOF）的复权因子数据。
   2.   start_date 小于或等于 end_date 时取指定时间段的数据,当 start_date > end_date 时返回报错。


## #   fnd_get_split  - 查询基金拆分折算信息

  查询指定基金在一段时间内的拆分折算信息
   函数原型：


```
fnd_get_split(fund, start_date, end_date)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     fund
  str
  基金代码
  Y
  无
  必填，只能输入一个基金的 symbol ，如： 'SZSE.159919'

   start_date
  str
  开始时间
  Y
  无
  必填，开始时间日期（场内除权日），%Y-%m-%d 格式

   end_date
  str
  结束时间
  Y
  无
  必填，结束时间日期（场内除权日），%Y-%m-%d 格式


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     fund
  str
  基金代码
  查询分红信息的基金代码

   pub_date
  str
  公告日
  %Y-%m-%d 格式

   split_type
  str
  拆分折算类型
  折算，拆分，特殊折算

   split_ratio
  float
  拆分折算比例
  10:X

   base_date
  str
  拆分折算基准日
  %Y-%m-%d 格式

   ex_date
  str
  拆分折算场内除权日
  %Y-%m-%d 格式

   share_change_reg_date
  str
  基金份额变更登记日
  %Y-%m-%d 格式

   nv_split_pub_date
  str
  基金披露净值拆分折算日
  %Y-%m-%d 格式

   rt_reg_date
  str
  权益登记日
  %Y-%m-%d 格式

   ex_date_close
  str
  场内除权日(收盘价)
  %Y-%m-%d 格式


   示例：


```
fnd_get_split(fund='SZSE.161725', start_date="2000-01-01", end_date="2022-09-07")
```

  输出：


```
fund    pub_date split_type  split_ratio   base_date     ex_date share_change_reg_date nv_split_pub_date rt_reg_date ex_date_close
0  SZSE.161725  2015-12-17         折算      10.1801  2015-12-15  2015-12-17            2015-12-16        2015-12-15        None    2015-12-17
1  SZSE.161725  2016-12-19         折算      10.2300  2016-12-15  2016-12-19            2016-12-16        2016-12-15        None    2016-12-19
2  SZSE.161725  2017-09-28         折算      14.9420  2017-09-26  2017-09-28            2017-09-27        2017-09-26        None    2017-09-28
3  SZSE.161725  2017-12-19         折算      10.0445  2017-12-15  2017-12-19            2017-12-18        2017-12-15        None    2017-12-19
4  SZSE.161725  2018-12-19         折算      10.2547  2018-12-17  2018-12-19            2018-12-18        2018-12-17        None    2018-12-19
5  SZSE.161725  2019-07-04         折算      15.5686  2019-07-02  2019-07-04            2019-07-03        2019-07-02        None    2019-07-04
6  SZSE.161725  2019-12-18         折算      10.1067  2019-12-16  2019-12-18            2019-12-17        2019-12-16        None    2019-12-18
7  SZSE.161725  2020-08-28         折算      14.9817  2020-08-26  2020-08-28            2020-08-27        2020-08-26        None    2020-08-28
8  SZSE.161725  2020-12-17         折算      10.0544  2020-12-15  2020-12-17            2020-12-16        2020-12-15        None    2020-12-17
```

  注意：
   1.  仅提供场内基金（ETF、LOF、FOF-LOF）的复权因子数据。
   2.   start_date 小于或等于 end_date 时取指定时间段的数据,当 start_date > end_date 时返回报错。


## #   fnd_get_share  - 查询基金规模数据

  获取基金规模数据，包含上海和深圳ETF基金
   gm SDK  3.0.172 版本新增
   函数原型：


```
fnd_get_share(fund, start_date=None, end_date=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     fund
  str
  基金代码
  Y
  无
  必填，只能输入一个基金的 symbol ，如： 'SZSE.159919'

   start_date
  str
  开始时间
  N
  None
  开始时间日期，%Y-%m-%d 格式，日期类型为交易日期，默认None表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间日期，%Y-%m-%d 格式，日期类型为交易日期，默认None表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     fund
  str
  基金代码
  查询分红信息的基金代码

   trade_date
  str
  交易（变动）日期
  %Y-%m-%d 格式

   pub_date
  str
  公告日期
  %Y-%m-%d 格式

   share
  float
  当前规模
  单位：份


   示例：


```
fnd_get_share(fund='SHSE.510300', start_date='2024-11-01', end_date='2024-11-24')
```

  输出：


```
fund                 trade_date                   pub_date  \
0   SHSE.510300  2024-11-01T00:00:00+08:00  2024-11-01T00:00:00+08:00
1   SHSE.510300  2024-11-04T00:00:00+08:00  2024-11-04T00:00:00+08:00
2   SHSE.510300  2024-11-05T00:00:00+08:00  2024-11-05T00:00:00+08:00
3   SHSE.510300  2024-11-06T00:00:00+08:00  2024-11-06T00:00:00+08:00
4   SHSE.510300  2024-11-07T00:00:00+08:00  2024-11-07T00:00:00+08:00
5   SHSE.510300  2024-11-08T00:00:00+08:00  2024-11-08T00:00:00+08:00
6   SHSE.510300  2024-11-11T00:00:00+08:00  2024-11-11T00:00:00+08:00
7   SHSE.510300  2024-11-12T00:00:00+08:00  2024-11-12T00:00:00+08:00
8   SHSE.510300  2024-11-13T00:00:00+08:00  2024-11-13T00:00:00+08:00
9   SHSE.510300  2024-11-14T00:00:00+08:00  2024-11-14T00:00:00+08:00
10  SHSE.510300  2024-11-15T00:00:00+08:00  2024-11-15T00:00:00+08:00
11  SHSE.510300  2024-11-18T00:00:00+08:00  2024-11-18T00:00:00+08:00
12  SHSE.510300  2024-11-19T00:00:00+08:00  2024-11-19T00:00:00+08:00
13  SHSE.510300  2024-11-20T00:00:00+08:00  2024-11-20T00:00:00+08:00
14  SHSE.510300  2024-11-21T00:00:00+08:00  2024-11-21T00:00:00+08:00
15  SHSE.510300  2024-11-22T00:00:00+08:00  2024-11-22T00:00:00+08:00
            share
0   94878487700.0
1   94926187700.0
2   95349187700.0
3   95259187700.0
4   95871187700.0
5   95310487700.0
6   94261087700.0
7   93306187700.0
8   92872387700.0
9   92568187700.0
10  92709487700.0
11  92480887700.0
12  92370187700.0
13  91457587700.0
14  91029187700.0
15  90434287700.0
```

  注意：
   1.  仅提供场内基金（ETF、LOF、FOF-LOF）的复权因子数据。
   2.   start_date 小于或等于 end_date 时取指定时间段的数据,当 start_date > end_date 时返回报错。


## #   get_open_call_auction  - 查询集合竞价开盘成交

  查询基金开盘成交数据
   gm SDK  3.0.176 版本新增
   函数原型：


```
get_open_call_auction (symbols, trade_date=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  基金代码
  Y
  无
  必填，可输入多个，使用时参考symbol. 采用 str 格式时，多个标的代码必须用英文逗号分割（逗号中间不能有空格），如：'SHSE.510300,SZSE.159922'; 采用 list 格式时，多个标的代码示例：['SHSE.510300', 'SZSE.159922']

   trade_date
  str
  交易日期
  N
  None
  交易日期，YYYY-MM-DD 格式，默认None返回最新交易日


   返回值：返回dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  标的代码
  格式exchange.sec_id（SHSE.600000, SZSE.000001）

   time
  str
  开盘集合竞价撮合时间
  交易日09:25，%Y-%m-%d %H:%M:%S 格式

   current_price
  float
  当前最新价（不复权）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的最新成交价Tick.price，即开盘价

   open_volume
  int
  开盘成交量（份）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的累计成交量Tick.cum_volume

   open_amount
  float
  开盘成交额（元）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的累计成交额Tick.cum_amount

   ask_v1~ask_v5
  float
  五档卖量
  09:25五档卖量Tick.quotes[0].ask_v~Tick.quotes[4].ask_v。

   ask_p1~ask_p5
  float
  五档卖价
  09:25五档卖价Tick.quotes[0].ask_p~Tick.quotes[4].ask_p。

   bid_v1~bid_v5
  float
  五档买量
  09:25五档买量Tick.quotes[0].bid_v~Tick.quotes[4].bid_v。

   bid_p1~bid_p5
  float
  五档买价
  09:25五档买价Tick.quotes[0].bid_p~Tick.quotes[4].bid_p。


   示例：


```
get_open_call_auction(symbols='SHSE.510300, SZSE.159922', trade_date='2025-03-27')
```

  输出：


```
symbol                 time  current_price  open_volume  open_amount  \
0  SHSE.510300  2025-03-27 09:25:00     4.01100016      1693800    6793832.0
1  SZSE.159922  2025-03-27 09:25:00     2.36899996         3700       8765.3
   ask_v1  ask_v2   ask_v3  ask_v4  ask_v5      ask_p1      ask_p2  \
0  665982  485400  1037400   11800  350600  4.01100016  4.01200008
1  105802  835700      400   43000  210300  2.36899996  2.36999989
       ask_p3      ask_p4      ask_p5  bid_v1  bid_v2  bid_v3  bid_v4  bid_v5  \
0  4.01300001  4.01399994  4.01499987  372200  130800  521400  210400  205100
1  2.37100005  2.37199998  2.37400007    3000    1700   23900     200   22200
       bid_p1      bid_p2      bid_p3      bid_p4      bid_p5
0  4.01000023  4.00899982  4.00799990  4.00699997  4.00600004
1  2.36800003  2.36599994  2.36500001  2.36400008  2.36299992
```

  注意：
   1.  开盘集合竞价的成交数据于每个交易日09:26更新，09:26后可查询当天开盘集合竞价，在09:26前查询当天开盘集合竞价返回空。
   2.  如果输入symbols包含不存在的标的代码，会报错。
   3.  如果开盘集合竞价没有发生成交，curret_price, open_volume, open_amount返回0.
   4.  数据最早为2025-02-21。


      ←

        期货增值数据函数（付费）

        可转债增值数据函数（付费）

      →

---

## 数据事件

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E6%95%B0%E6%8D%AE%E4%BA%8B%E4%BB%B6.html

<!DOCTYPE html>




     数据事件 - 掘金量化












# #  数据事件

   数据事件是阻塞回调事件函数，通过 subscribe 函数订阅， 主动推送


## #   on_tick  - tick 数据推送事件

  接收 tick 分笔数据， 通过 subscribe 订阅 tick 行情，行情服务主动推送 tick 数据
   函数原型：


```
on_tick(context, tick)
```

  参数：
     参数名
  类型
  说明

     context
   context 对象
  上下文

   tick
   tick 对象
  当前被推送的 tick


   示例：


```
def init(context):
    # 订阅600519的tick数据
    subscribe(symbols='SHSE.600519', frequency='tick', count=2)

def on_tick(context,tick):
    print('收到tick行情---', tick)
```

  输出：


```
{'symbol': 'SHSE.600519', 'created_at': datetime.datetime(2020, 9, 2, 14, 7, 23, 620000, tzinfo=tzfile('PRC')), 'price': 1798.8800048828125, 'open': 1825.0, 'high': 1828.0, 'low': 1770.0, 'cum_volume': 2651191, 'cum_amount': 4760586491.0, 'cum_position': 0, 'last_amount': 179888.0, 'last_volume': 100, 'trade_type': 0, 'receive_local_time': 1602751345.262745}
```

## #   on_bar  - bar 数据推送事件

  接收固定周期 bar 数据， 通过 subscribe 订阅 bar 行情，行情服务主动推送 bar 数据
   函数原型：


```
on_bar(context, bars)
```

  参数：
     参数名
  类型
  说明

     context
   context 对象
  上下文对象

   bars
  list( bar )
  当前被推送的 bar 列表


   示例：


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *
from datetime import datetime, timedelta

def init(context):
    # 订阅600519和000001的分钟数据
    subscribe(symbols='SHSE.600519,SZSE.000001', frequency='60s', count=2)

def on_bar(context,bars):
    print('收到bars行情---', bars)

if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
        backtest_match_mode市价撮合模式，以下一tick/bar开盘价撮合:0，以当前tick/bar收盘价撮合：1
    '''
    backtest_start_time = str(datetime.now() - timedelta(weeks=1))[:19]
    backtest_end_time = str(datetime.now())[:19]
    run(strategy_id='xxxxxx',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='xxxxxxx',
        backtest_start_time=backtest_start_time,
        backtest_end_time=backtest_end_time,
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)
```

  输出：


```
收到bars行情--- [{'symbol': 'SHSE.600519', 'frequency': '60s', 'open': 1786.0, 'high': 1786.0, 'low': 1786.0, 'close': 1786.0, 'volume': 20200, 'amount': 36077200.0, 'pre_close': 0.0, 'position': 0, 'bob': datetime.datetime(2023, 11, 23, 14, 59, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'eob': datetime.datetime(2023, 11, 23, 15, 0, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))}]
```

  注意：
   1.  若在 subscribe 函数中订阅了多个标的的 bar，但 wait_group 参数值为 False,则多次触发 On_bar,每次返回只包含单个标的 list 长度为 1 的 bars;若参数值为 True,则只会触发一次 On_bar,返回包含多个标的的 bars。
   2.  bar 在本周期结束时间后才会推送，标的在这个周期内无交易则不推送 bar。


## #   on_l2transaction  - 逐笔成交事件

  接收逐笔成交数据(L2 行情时有效)
仅特定券商付费提供
   函数原型：


```
on_l2transaction(context, transaction)
```

  参数：
     参数名
  类型
  说明

     context
   context 对象
  上下文对象

   transaction
   L2Transaction 对象
  收到的逐笔成交行情


   示例：


```
def on_l2transaction(context, transaction):
    print(transaction)
```

  输出：


```
{'symbol': 'SZSE.300003', 'volume': 300, 'created_at': datetime.datetime(2020, 11, 24, 9, 38, 16, 50, tzinfo=tzfile('PRC')), 'exec_type': '4', 'side': '', 'price': 0.0}
```

## #   on_l2order  - 逐笔委托事件

  接收逐笔委托数据（L2 行情时有效）
仅特定券商付费提供
   函数原型：


```
on_l2order(context, l2order)
```

  参数：
     参数名
  类型
  说明

     context
   context 对象
  上下文对象

   l2order
   L2Order 对象
  收到的逐笔委托行情


   示例：


```
def on_l2order(context, l2order):
    print(l2order)
```

  输出：


```
{'symbol': 'SZSE.300003', 'side': '1', 'price': 29.350000381469727, 'volume': 2400, 'created_at': datetime.datetime(2020, 11, 24, 9, 38, 16, 80, tzinfo=tzfile('PRC')), 'order_type': '2'}
```



      ←

        数据订阅

        行情数据查询函数（免费）

      →

---

## 数据订阅

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E6%95%B0%E6%8D%AE%E8%AE%A2%E9%98%85.html

<!DOCTYPE html>




     数据订阅 - 掘金量化












# #  数据订阅



## #  subscribe - 行情订阅

  订阅行情, 可以指定 symbol, 数据滑窗大小, 以及是否需要等待全部代码的数据到齐再触发事件。
   函数原型：


```
subscribe(symbols, frequency='1d', count=1, unsubscribe_previous=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str or list
  订阅 标的代码 , 注意大小写，支持字串格式，如有多个代码, 中间用  ,  (英文逗号) 隔开, 也支持  ['symbol1', 'symbol2']  这种列表格式

   frequency
  str
  频率, 支持 'tick', '60s', '300s', '900s' 等, 默认'1d', 详情见 股票行情数据 和 期货行情数据 ,  实时行情支持的频率

   count
  int
  context.data返回的订阅数据滑窗大小, 默认 1  ,详情见 数据滑窗

   wait_group
  bool
  是否等待同一频率的bar同时到齐（只支持bar频率），默认 False 不取消, 输入 True 则同时等待同频率所有bar到齐再一次性返回

   wait_group_timeout
  str
  等待超时时间，只有wait_group=True时生效，默认'10s'

   unsubscribe_previous
  bool
  是否取消过去订阅的 symbols, 默认 False 不取消, 输入 True 则取消所有原来的订阅。

   fields
  str
  context.data返回的对象字段, 如有多个字段, 中间用, 隔开, 默认所有, 具体字段见: tick 对象  和  bar 对象  ，在 subscribe 函数中指定的字段越少，context.data查询速度越快

   format
  str
  context.data返回的数据格式，默认"df", "df": 数据框格式，返回dataframe（默认）,"row": 原始行式组织格式，返回list[dict]（当用户对性能有要求时, 推荐使用此格式）, "col": 列式组织格式，返回dict 。


   返回值：
   None
   示例：


```
def init(context):
    # 同时订阅600519的tick数据和分钟数据
    subscribe(symbols='SHSE.600519', frequency='tick', count=2)
    subscribe(symbols='SHSE.600519', frequency='60s', count=2)

def on_tick(context,tick):
    print('收到tick行情---', tick)

def on_bar(context,bars):
    print('收到bar行情---', bars)
    data = context.data(symbol='SHSE.600519', frequency='60s', count=2)
    print('bar数据滑窗---', data)
```

  注意：
   1.  subscribe 支持多次调用，支持同一标的不同频率订阅。订阅后的数据储存在本地，需要通过 context.data 接口调用或是直接在 on_tick 或 on_bar 中获取。
   2.  在实时模式下，最新返回的数据是 不复权 的。
   3.  订阅函数subscribe里面指定字段越少，查询速度越快，目前效率是row > col > df。
   4.  当subscribe的format指定col时，tick的quotes字段会被拆分，只返回买卖一档的量和价，即只有bid_p，bid_v, ask_p和ask_v。
   5.  在回测模式下，subscribe使用wait_group=True时，等待的标的需要下个时间到期。例如订阅60s的频率A和B标的，当天第一条bar数据是在09:32:00推送eob为09:31:00的A和B的bar，因为需要走到09:32:00才能确认09:31:00的全部bar是否到齐。在实时模式下，会根据实时到齐时间推送。


## #  unsubscribe - 取消订阅

  取消行情订阅, 默认取消所有已订阅行情
   函数原型：


```
unsubscribe(symbols='*', frequency='60s')
```

  参数：
     参数名
  类型
  说明

     symbols
  str or list
  订阅 标的代码 , 支持字串格式，如有多个代码, 中间用  ,  (英文逗号) 隔开, 也支持  ['symbol1', 'symbol2']  这种列表格式

   frequency
  str
  频率, 支持 'tick', '60s', '300s', '900s' 等, 默认'1d', 详情见 股票行情数据 和 期货行情数据 ,  实时行情支持的频率


   返回值：
   None
   示例：


```
unsubscribe(symbols='SHSE.600000,SHSE.600004', frequency='60s')
```

  注意：
如示例所示代码，取消 SHSE.600000,SHSE.600004 两只代码 60s 行情的订阅，若 SHSE.600000 同时还订阅了 "300s" 频度的行情，该代码不会取消该标的此频度的订阅


      ←

        基本函数

        数据事件

      →

---

## 新股新债交易函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E6%96%B0%E8%82%A1%E6%96%B0%E5%80%BA%E4%BA%A4%E6%98%93%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     新股新债交易函数 - 掘金量化












# #  新股新债交易函数



## #   ipo_buy  - 新股新债申购

  仅在 实盘 中可以使用
   函数原型：


```
ipo_buy(symbol, volume, price, account_id='')
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  申购数量

   price
  float
  新股新债发行价

   account_id
  str
  账户 ID，不指定则使用默认账户


  返回值  List[Dict]


## #   ipo_get_quota  - 查询新股新债申购额度

  仅在 实盘 中可以使用
   函数原型：


```
ipo_get_quota(account_id='')
```

  参数：
     参数名
  类型
  说明

     account_id
  str
  账户 ID，不指定则使用默认账户


   返回值：
   List[Dict[str, Any]]
     key
  value 类型
  说明

     quota
  float
  可申购数量




## #   ipo_get_instruments  - 查询当日新股新债清单

  仅在 实盘 中可以使用
   函数原型：


```
ipo_get_instruments(sec_type, account_id='', df=False)
```

  参数：
     参数名
  类型
  说明

     sec_type
  int
  标的类型，用以区别获取新股还是新债

   account_id
  str
  账户 ID，不指定则使用默认账户

   df
  bool
  是否返回 DataFrame


   返回值：
   List[Dict]
     key
  value 类型
  说明

     symbol
  str
  标的代码

   price
  float
  申购价格

   min_vol
  int
  申购最小数量

   max_vol
  int
  申购最大数量




## #   ipo_get_match_number  - 查询配号

  仅在 实盘 中可以使用
   函数原型：


```
ipo_get_match_number(start_time, end_time, account_id='', df=False)
```

  参数：
     参数名
  类型
  说明

     start_time
  str
  开始时间， (%Y-%m-%d %H:%M:%S 格式)

   end_time
  str
  结束时间， (%Y-%m-%d %H:%M:%S 格式)

   account_id
  str
  账户 ID，不指定则使用默认账户

   df
  bool
  是否返回 DataFrame


   返回值：
   List[Dict]
     key
  value 类型
  说明

     symbol
  str
  标的代码

   order_id
  str
  委托号

   volume
  int
  成交数量

   match_number
  str
  申购配号

   order_at
  datetime.datetime
  委托日期

   match_at
  datetime.datetime
  配号日期




## #   ipo_get_lot_info  - 中签查询

  仅在 实盘 中可以使用
   函数原型：


```
ipo_get_lot_info(start_time,end_time,account_id='', df=False)
```

  参数：
     参数名
  类型
  说明

     start_time
  str
  开始时间， (%Y-%m-%d  格式)

   end_time
  str
  结束时间， (%Y-%m-%d  格式)

   account_id
  str
  账户 ID，不指定则使用默认账户

   df
  bool
  是否返回 DataFrame


   返回值：
   List[Dict]
     key
  value 类型
  说明

     symbol
  str
  标的代码

   order_at
  datetime.datetime
  委托日期

   lot_at
  datetime.datetime
  中签日期

   lot_volume
  int
  中签数量

   give_up_volume
  int
  放弃数量

   price
  float
  中签价格

   amount
  float
  中签金额

   pay_volume
  float
  已缴款数量

   pay_amount
  float
  已缴款金额




      ←

        算法交易函数

        基金交易函数

      →

---

## 期货基础数据函数（免费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E6%9C%9F%E8%B4%A7%E5%9F%BA%E7%A1%80%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0%EF%BC%88%E5%85%8D%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     期货基础数据函数(免费) - 掘金量化












# #  期货基础数据函数(免费)

  python 股票与指数数据 API 包含在 gm3.0.148 版本及以上版本


## #   fut_get_continuous_contracts  - 查询连续合约对应的真实合约

  查询指定时间段连续合约在每个交易日上对应的真实合约
   函数原型：


```
fut_get_continuous_contracts(csymbol, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     csymbol
  str
  连续合约代码
  Y
  无
  必填，只能输入一个 支持主力合约、次主力、前 5 个月份连续和加权指数合约代码，如： 1000 股指期货主力连续合约：CFFEX.IM， 1000 股指期货次主力连续合约：CFFEX.IM22， 1000 股指期货当月连续合约：CFFEX.IM00， 1000 股指期货下月连续合约：CFFEX.IM01， 1000 股指期货下季连续合约：CFFEX.IM02， 1000 股指期货隔季连续合约：CFFEX.IM03， 1000 股指期货加权指数合约：CFFEX.IM99

   start_date
  str
  开始时间
  N
  ""
  开始日期，时间类型为交易日期，%Y-%m-%d 格式，默认 "" 表示最新交易日

   end_date
  str
  结束时间
  N
  ""
  结束日期，时间类型为交易日期，%Y-%m-%d 格式，默认 "" 表示最新交易日


   返回值：  list[dict]
     字段名
  类型
  中文名称
  说明

     symbol
  str
  标的代码
  exchange.sec_id

   trade_date
  str
  交易日期
  具体合约对应的交易日期


   示例：


```
fut_get_continuous_contracts(csymbol='SHFE.NI', start_date="2022-09-01", end_date="2022-09-15")
```

  输出：


```
[{'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-01'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-02'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-05'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-06'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-07'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-08'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-09'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-13'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-14'}, {'symbol': 'SHFE.ni2210', 'trade_date': '2022-09-15'}]
```

  注意：
   1.  具体合约（真实合约）： 交易所.品种名到期月份 对应期货具体合约 symbol，如 CFFEX.IF2206
   2.  主力连续合约（期货连续合约，由真实合约拼接）： 交易所.品种名 对应主力连续合约 symbol，如 CFFEX.IF，CFFEX.IC
    主力连续合约切换规则
 1.  每个品种只选出唯一一个主力合约。
   2.  日成交量和持仓量都为最大的合约，确定为新的主力合约，每日收盘结算后判断，于下一交易日进行指向切换，日内不会进行主力合约的切换。
   3.  按照第二条规定产生新的主力合约之前，维持原来的主力合约不变。
   4.  若出现当前主力合约的成交量和持仓量都不是最大的情况，当前指向合约在下一个交易日必须让出主力合约身份，金融期货新主力指向成交量最大的合约（中金所），商品期货新主力指向持仓量最大的合约（上期所、大商所、郑商所、上期能源）。

   3.  次主力连续合约（期货连续合约，由真实合约拼接）： 交易所.品种名 22 对应次主力连续合约 symbol，如 CFFEX.IF22，CFFEX.IC22
    次主力连续合约切换规则
 1.  每个品种只选出唯一一个次主力合约。
   2.  金融期货日成交量第二大、或商品期货日持仓量第二大的合约，确定为新的次主力合约，每日收盘结算后判断，于下一交易日进行指向切换，日内不会进行次主力合约的切换。
   3.  按照第二条规定产生新的次主力合约之前，维持原来的次主力合约不变。
   4.  若金融期货出现当前次主力合约的成交量、或商品期货出现当前次主力合约持仓量不是第二大的情况，当前指向合约在下一个交易日必须让出次主力合约身份，金融期货新主力指向成交量第二大的合约（中金所），商品期货新主力指向持仓量第二大的合约（上期所、大商所、郑商所、上期能源）。

   4.  月份连续合约（期货连续合约，由真实合约拼接）： 交易所.品种名 月份排序 对应月份连续合约 symbol，如 SHFE.RB00，SHFE.RB01，...，SHFE.RB04（同一品种最多有最近 5 个月的月份连续合约）
    月份连续合约的切换规则
 1.  该品种上市合约按交割月份排序
   2.  00 对应最近月份合约，01 对应其后一个合约，02 对应再后一个合约，依次类推
   3.  合约最后交易日盘后切换。

   5.  当 start_date 小于或等于 end_date 时取指定时间段的数据,当 start_date > end_date 时返回报错。
   6.  交易日每天19:45:00更新下一交易日数据，19:45:00后最新交易日为下一交易日。


      ←

        股票财务数据及基础数据函数（免费）

        股票增值数据函数（付费）

      →

---

## 期货增值数据函数（付费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E6%9C%9F%E8%B4%A7%E5%A2%9E%E5%80%BC%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0%EF%BC%88%E4%BB%98%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     期货增值数据函数(付费) - 掘金量化












# #  期货增值数据函数(付费)

  python 期货数据 API 包含在 gm3.0.145 版本及以上版本，不需要引入新库


## #   fut_get_contract_info  - 查询期货标准品种信息

  查询交易所披露的期货标准品种的合约规格/合约文本
   函数原型：


```
fut_get_contract_info(product_codes, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     product_codes
  str or list
  品种代码
  Y
  无
  必填，交易品种代码，如：IF，AL 多个代码可用 ， 采用 str 格式时，多个标的代码必须用英文逗号分割，如： 'IF, AL'  采用 list 格式时，多个标的代码示例： ['IF', 'AL']

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式，默认 False 返回字典格式，返回 list[dict]，列表每项的 dict 的 key 值见返回字段名


   返回值：  dataframe 或 list[dict]
     字段名
  类型
  中文名称
  说明

     product_name
  str
  交易品种
  交易品种名称，如：沪深 300 指数，铝

   product_code
  str
  交易代码
  交易品种代码，如：IF，AL

   underlying_symbol
  str
  合约标的
  如：SHSE.000300， AL

   multiplier
  int
  合约乘数
  如：200，5

   trade_unit
  str
  交易单位
  如：每点人民币 200 元，5 吨/手

   price_unit
  str
  报价单位
  如：指数点，元（人民币）/吨

   price_tick
  str
  价格最小变动单位
  如：0.2 点，5 元/吨

   delivery_month
  str
  合约月份
  如："当月、下月及随后两个季月"，"1 ～ 12 月"

   trade_time
  str
  交易时间
  如："9:30-11:30，13:00-15:00"， "上午 9:00－11:30 ，下午 1:30－3:00 和交易所规定的其他交易时间"

   price_range
  str
  涨跌停板幅度
  每日价格最大波动限制，如："上一个交易日结算价的 ±10%"， "上一交易日结算价 ±3%"

   minimum_margin
  str
  最低交易保证金
  交易所公布的最低保证金比例，如："合约价值的 8%"，"合约价值的 5%"

   last_trade_date
  str
  最后交易日
  如："合约到期月份的第三个星期五，遇国家法定假日顺延"， "合约月份的 15 日（遇国家法定节假日顺延，春节月份等最后交易日交易所可另行调整并通知）"

   delivery_date
  str
  交割日
  如："同最后交易日"，"最后交易日后连续三个工作日"

   delivery_method
  str
  交割方式
  如："现金交割"，"实物交割"

   exchange_name
  str
  交易所名称
  上市交易所名称，如："中国金融期货交易所"，"上海期货交易所"

   exchange
  str
  交易所代码
  交易品种名称，如："沪深 300 指数"，"铝"


   示例：


```
fut_get_contract_info(product_codes='IF')
```

  输出：


```
[{'product_name': '沪深300股指期货', 'product_code': 'IF', 'underlying_symbol': 'SHSE.000300', 'multiplier': 300, 'trade_unit': '每点300元', 'price_unit': '指数点', 'price_tick': '0.2点', 'delivery_month': '当月、下月及随后两个季月', 'trade_time': '上午9:30-11:30,下午13:00-15:00', 'price_range': '上一个交易日结算价的±10%', 'minimum_margin': '合约价值的8%', 'last_trade_date': '合约到期月份的第三个周五,遇国家法定假日顺延', 'delivery_date': '同最后交易日', 'delivery_method': '现金交割', 'exchange_name': '中国金融期货交易所', 'exchange': 'CFFEX'}]
```

## #   fut_get_transaction_rankings  - 查询期货每日成交持仓排名

  查询期货合约每日成交量/持买单量/持卖单量排名
   函数原型：


```
fut_get_transaction_rankings(symbols, trade_date="", indicators="volume")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  期货合约代码
  Y
  无
  必填，期货真实合约代码，使用时参考symbol, 采用 str 格式时，多个标的代码必须用英文逗号分割，如：'CFFEX.IF2409, CFFEX.IC2409', 采用 list 格式时，多个标的代码示例：['CFFEX.IF2409', 'CFFEX.IC2409']

   trade_date
  str
  交易日期
  N
  ""
  交易日期，%Y-%m-%d 格式，默认 "" 表示最新交易日

   indicators
  str
  排名指标
  N
  ""
  排名指标，即用于排名的依据，可选：'volume'-成交量排名（默认）, 'long'-持买单量排名, 'short'-持卖单量排名, 支持一次查询多个排名指标，如有多个指标，中间用英文逗号分隔, 默认None表示成交量排名


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  期货合约代码
  查询排名的期货合约代码

   trade_date
  str
  交易日期
  查询的交易日期

   member_name
  str
  期货公司会员简称


   indicator
  str
  排名指标
  'volume'-成交量排名, 'long'-持买单量排名, 'short'-持卖单量排名

   indicator_number
  int
  排名指标数值
  单位：手。数值视乎指定的排名指标 indicator，分别为： 成交量（ indicator='volume' 时） 持买单量（ indicator='long' 时） 持卖单量（ indicator='short' 时）

   indicator_change
  int
  排名指标比上交易日增减
  单位：手

   ranking
  int
  排名名次
  指标具体排名

   ranking_change
  float
  排名名次比上交易日增减
  单位：名次


   示例：


```
fut_get_transaction_rankings(symbols='SHFE.ag2212', trade_date="2022-10-10", indicators='volume')
```

  输出：


```
symbol  trade_date member_name  indicator_number  indicator_change  \
0   SHFE.ag2212  2022-10-10        海通期货             90561            -19632
1   SHFE.ag2212  2022-10-10        东证期货             89284            -74685
2   SHFE.ag2212  2022-10-10        中信期货             64196            -77571
3   SHFE.ag2212  2022-10-10        国泰君安             36535            -40570
4   SHFE.ag2212  2022-10-10        新湖期货             22090            -16824
5   SHFE.ag2212  2022-10-10        华闻期货             16531               826
6   SHFE.ag2212  2022-10-10        方正中期             14787            -17407
7   SHFE.ag2212  2022-10-10        华泰期货             14315            -71181
8   SHFE.ag2212  2022-10-10        银河期货             13333             -9714
9   SHFE.ag2212  2022-10-10        中泰期货             11832             -6380
10  SHFE.ag2212  2022-10-10        国投安信             11041            -10375
11  SHFE.ag2212  2022-10-10        光大期货              9917            -14549
12  SHFE.ag2212  2022-10-10        中信建投              9653            -12342
13  SHFE.ag2212  2022-10-10        广发期货              8440             -9462
14  SHFE.ag2212  2022-10-10        东方财富              8166            -21117
15  SHFE.ag2212  2022-10-10        南华期货              7096             -3422
16  SHFE.ag2212  2022-10-10        平安期货              6835             -8312
17  SHFE.ag2212  2022-10-10        浙商期货              6610             -2008
18  SHFE.ag2212  2022-10-10        中辉期货              6569             -3830
19  SHFE.ag2212  2022-10-10        永安期货              6351              -741
    ranking  ranking_change indicator
0         1             2.0    volume
1         2            -1.0    volume
2         3            -1.0    volume
3         4             1.0    volume
4         5             1.0    volume
5         6            10.0    volume
6         7             0.0    volume
7         8            -4.0    volume
8         9             1.0    volume
9        10             4.0    volume
10       11             2.0    volume
11       12            -3.0    volume
12       13            -2.0    volume
13       14             1.0    volume
14       15            -7.0    volume
15       16             3.0    volume
16       17             0.0    volume
17       18             NaN    volume
18       19             1.0    volume
19       20             NaN    volume
```

  注意：
   1.  当上一交易日没有进入前 20 名， ranking_change 返回 NaN.
   2.  数据日频更新，当日更新前返回前一交易日的排名数据，约在交易日 20 点左右更新当日数据。


## #   fut_get_warehouse_receipt  - 查询期货仓单数据

  查询交易所在交易日期货品种的注册仓单数量、有效预报
   期货仓单是指由期货交易所指定交割仓库，按照期货交易所指定的程序，签发的符合合约规定质量的实物提货凭证。记录了交易所所有期货实物的库存情况以及变更情况。

   函数原型：


```
fut_get_warehouse_receipt(product_code, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     product_code
  str
  品种代码
  Y
  无
  必填，只能填写一个交易品种代码，如：AL

   start_date
  str
  开始时间
  N
  ""
  开始时间日期，%Y-%m-%d 格式，默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期，%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     trade_date
  str
  交易日期


   exchange
  str
  期货交易所代码
  期货品种对应交易所代码，如：CFFEX，SHFE

   exchange_name
  str
  期货交易所名称
  上市交易所名称，如：中国金融期货交易所，上海期货交易所

   product_code
  str
  交易代码
  交易品种代码，如：IF，AL

   product_name
  str
  交易品种
  交易品种名称，如：沪深 300 指数，铝

   on_warrant
  int
  注册仓单数量


   warrant_unit
  str
  仓单单位


   warehouse
  str
  仓库名称


   future_inventory
  int
  期货库存


   future_inventory_change
  int
  期货库存增减


   warehouse_capacity
  int
  可用库容量


   warehouse_capacity_change
  int
  可用库容量增减


   inventory_subtotal
  int
  库存小计


   inventory_subtotal_change
  int
  库存小计增减


   effective_forecast
  int
  有效预报
  仅支持郑商所品种

   premium
  int
  升贴水



   示例：


```
fut_get_warehouse_receipt(product_code='AL')
```

  输出：


```
trade_date exchange exchange_name product_code product_name  on_warrant warrant_unit    warehouse  future_inventory  future_inventory_change  warehouse_capacity  warehouse_capacity_change  inventory_subtotal  inventory_subtotal_change  effective_forecast  premium
0   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      上海:上海裕强                 0                        0                   0                          0                   0                          0                   0        0
1   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      上海:上港物流              3965                      -76                   0                          0                   0                          0                   0        0
2   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨  上海:中储临港(保税)                 0                        0                   0                          0                   0                          0                   0        0
3   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      上海:中储吴淞                 0                        0                   0                          0                   0                          0                   0        0
4   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      上海:中储大场                 0                        0                   0                          0                   0                          0                   0        0
5   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      上海:全胜物流                 0                        0                   0                          0                   0                          0                   0        0
6   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨        上海:合计              3965                      -76                   0                          0                   0                          0                   0        0
7   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨     上海:国储外高桥                 0                        0                   0                          0                   0                          0                   0        0
8   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      上海:国储天威                 0                        0                   0                          0                   0                          0                   0        0
9   2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨   上海:外运华东张华浜                 0                        0                   0                          0                   0                          0                   0        0
10  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨     上海:添马行松江                 0                        0                   0                          0                   0                          0                   0        0
11  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      上海:裕强闵行                 0                        0                   0                          0                   0                          0                   0        0
12  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨       保税商品总计                 0                        0                   0                          0                   0                          0                   0        0
13  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      天津:中储陆通                 0                        0                   0                          0                   0                          0                   0        0
14  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      天津:全程物流                 0                        0                   0                          0                   0                          0                   0        0
15  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨        天津:合计                 0                        0                   0                          0                   0                          0                   0        0
16  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨       完税商品总计            109147                    -2851                   0                          0                   0                          0                   0        0
17  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨        山东:合计             12379                        0                   0                          0                   0                          0                   0        0
18  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      山东:山东恒欣              7936                        0                   0                          0                   0                          0                   0        0
19  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨    山东:山东高通临沂              3028                        0                   0                          0                   0                          0                   0        0
20  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨    山东:山东高通泰安              1415                        0                   0                          0                   0                          0                   0        0
21  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      广东:中储晟世                 0                     -551                   0                          0                   0                          0                   0        0
22  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      广东:南储仓储                 0                        0                   0                          0                   0                          0                   0        0
23  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨        广东:合计                 0                     -873                   0                          0                   0                          0                   0        0
24  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      广东:广东炬申                 0                     -322                   0                          0                   0                          0                   0        0
25  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨     广东:广储830                 0                        0                   0                          0                   0                          0                   0        0
26  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨           总计            109147                    -2851                   0                          0                   0                          0                   0        0
27  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨    江苏:上港物流苏州                 0                        0                   0                          0                   0                          0                   0        0
28  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      江苏:中储无锡             49760                        0                   0                          0                   0                          0                   0        0
29  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      江苏:五矿无锡             18343                     -799                   0                          0                   0                          0                   0        0
30  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨        江苏:合计             69030                     -799                   0                          0                   0                          0                   0        0
31  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨    江苏:国能物流常州                 0                        0                   0                          0                   0                          0                   0        0
32  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      江苏:常州融达               198                        0                   0                          0                   0                          0                   0        0
33  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      江苏:无锡国联               704                        0                   0                          0                   0                          0                   0        0
34  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨     江苏:添马行物流                 0                        0                   0                          0                   0                          0                   0        0
35  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨     江苏:百金汇物流                25                        0                   0                          0                   0                          0                   0        0
36  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      河南:中储洛阳                 0                        0                   0                          0                   0                          0                   0        0
37  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      河南:中部陆港              4199                        0                   0                          0                   0                          0                   0        0
38  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨        河南:合计              7585                    -1103                   0                          0                   0                          0                   0        0
39  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨   河南:河南国储431              2885                    -1103                   0                          0                   0                          0                   0        0
40  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨    河南:河南国储巩义               501                        0                   0                          0                   0                          0                   0        0
41  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨    河南:河南国储洛阳                 0                        0                   0                          0                   0                          0                   0        0
42  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨        浙江:合计             15263                        0                   0                          0                   0                          0                   0        0
43  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨    浙江:国储837处                 0                        0                   0                          0                   0                          0                   0        0
44  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨     浙江:宁波九龙仓             15112                        0                   0                          0                   0                          0                   0        0
45  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      浙江:浙江南湖                 0                        0                   0                          0                   0                          0                   0        0
46  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      浙江:浙江田川               151                        0                   0                          0                   0                          0                   0        0
47  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      甘肃:甘肃国通               825                        0                   0                          0                   0                          0                   0        0
48  2022-10-20     SHFE       上海期货交易所           AL            铝           0            吨      重庆:重庆中集               100                        0                   0                          0                   0                          0                   0        0
```

  注意：
   1.  支持郑商所、大商所、上期所和上海国际能源交易中心的期货品种。
   2.  注册仓单数量每日更新，其余数据上期所一周一披露，郑商所一天一披露。
   3.  当 start_date  小于或等于  end_date  时, 取指定时间段的数据,当  start_date  >  end_date
  时, 返回报错。


      ←

        股票增值数据函数（付费）

        基金增值数据函数（付费）

      →

---

## 标的池

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E6%A0%87%E7%9A%84%E6%B1%A0.html

<!DOCTYPE html>




     标的池 - 掘金量化












# #  标的池

  标的池功能，通过调用标的池API接口，实现策略标的池和掘金终端界面【交易工具】-【标的池】联动。在不停止策略运行的情况下，在界面导入标的池，策略可调用标的池API获取标的池成分代码；或者策略通过API创建/修改标的池，在终端界面可查看标的池成分的可视化行情。

   实时模式（仿真交易和实盘交易）标的池应用：在终端【交易工具】-【标的池】进行增删查改操作，策略实时查询指定标的池成分代码进行交易。
  例1：在多个策略之间传递选股标的池（策略A选股 -> 标的池 -> 策略B择时交易）
第一步（策略A）：使用概念板块数据/选股条件产生选股symbol，通过标的池API创建标的池
第二步（终端界面）：人工盯盘，实时手动调整标的池成分股（可选）
第三步（策略B）：通过标的池API获取标的池最新成分股，根据择时逻辑自动交易
  例2：手动选股+策略择时（手动选股 -> 标的池 -> 策略择时交易）
第一步（终端界面）：创建标的池（手动自选/文件导入/持仓导入/板块导入）
第二步（终端界面）：人工盯盘，实时手动调整标的池成分股（可选）
第三步（策略）：通过标的池API获取标的池最新成分股，根据择时逻辑自动交易
  例3：策略选股+手动交易（策略选股 -> 标的池 -> 手动交易）
第一步（策略）：使用概念板块数据/选股条件产生选股symbol，通过标的池API创建标的池、定时任务更新标的池成分股
第二步（终端界面）：人工盯盘，实时手动调整标的池成分股（可选）
第三步（终端界面）：人工盯盘，手动择时交易

  回测模式标的池应用：先手动选股，通过终端界面【交易工具】-【标的池】导入标的池，策略调用标的池API获取成分代码进行回测。
  例4：手动选股+策略回测（手动选股 -> 标的池 -> 策略历史回测）
第一步（终端界面）：创建标的池（手动自选/文件导入/持仓导入/板块导入）
第二步（终端界面）：手动调整修改标的池成分股（可选）
第三步（策略）：调用标的池API获取标的池成分股，根据策略实现逻辑进行历史回测




## #   universe_set  - 设置标的池

  创建一个新标的池，或者重置已有标的池成分标的
   函数原型：


```
universe_set(universe_name, universe_symbols=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     universe_name
  str
  标的池名称
  Y
  无
  指定标的池名称

   universe_symbols
  list[str]
  成分标的代码
  N
  None
  单个标的示例：['SZSE.000002'],多个标的示例：['SHSE.600008', 'SZSE.000002']


   返回值：None
   示例：


```
universe_set(universe_name='妖股', universe_symbols=['SZSE.002137', 'SHSE.603421'])
```

  注意：
   1.  创建/重置标的池失败会报错。
   2.  传入的标的池名称universe_name已存在，会根据universe_symbols重置当前标的池成分。
   3.  传入的标的池名称universe_name不存在，会创建一个新标的池。
   4.  当universe_symbols为空列表或None时，会创建/重置为成分数量为0的一个空标的池。
   5.  若已存在重名标的池，会随机选取其中一个标的池进行重置。


## #   universe_get_symbols  - 获取标的池成分

  获取单个标的池的成分标的代码
   函数原型：


```
universe_get_symbols(universe_name)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     universe_name
  str
  标的池名称
  Y
  无
  指定标的池名称


   返回值：list[str]
     类型
  说明

     list[str]
   成分标的代码  列表


   示例：


```
universe_get_symbols(universe_name='持仓标的')
```

  输出：


```
['SZSE.300403', 'SZSE.002167', 'SHSE.605098', 'SZSE.002478', 'SZSE.000026', 'SZSE.000065', 'SHSE.601611', 'SZSE.000766', 'SHSE.601988', 'SZSE.300660', 'SZSE.300696', 'SHSE.603319']
```

  注意：
   1.  不存在的标的池，返回None。
   2.  成分标的数量为0，返回空列表。
   3.  若存在重名标的池，随机返回其中一个标的池的成分代码。


## #   universe_get_names  - 获取全部标的池名称

  获取全部已创建标的池名称
   函数原型：


```
universe_get_names()
```

  返回值：list[str]
     类型
  说明

     list[str]
   标的池名称  列表


   示例：


```
universe_get_names()
```

  输出：


```
['持仓标的', '龙头', '龙头1']
```

  注意：
   1.  只返回已创建的标的池名称列表。
   2.  没有已创建标的池，返回空列表。


## #   universe_delete  - 删除标的池

  删除一个已创建标的池
   函数原型：


```
universe_delete(universe_name)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     universe_name
  str
  标的池名称
  Y
  无
  指定要删除的标的池


   返回值：None
   示例：


```
universe_delete(universe_name='龙头1')
```

  注意：
   1.  删除标的池失败会报错


      ←

        动态参数

        其他函数

      →

---

## 算法交易函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E7%AE%97%E6%B3%95%E4%BA%A4%E6%98%93%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     算法交易函数 - 掘金量化












# #  算法交易函数

  python 算法 SDK 包含在 gm3.0.126 版本及以上版本，不需要引入新库
仅支持实时模式，部分券商版本可用


## #   algo_order  算法交易委托

  委托算法母单
   函数原型：


```
algo_order(symbol, volume, side, order_type,position_effect, price, algo_name, algo_param)
```

  参数：
     参数
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  数量

   side
  int
  OrderSide_Buy = 1 买入 OrderSide_Sell = 2 卖出

   order_type
  int
  OrderType_Limit = 1 限价委托，OrderType_Market = 2 市价委托

   position_effect
  int
  PositionEffect_Open = 1 开仓 PositionEffect_Close = 2 平仓,

   price
  int
  基准价格（ATS-SMART 算法不生效）

   algo_name
  str
  算法名称，ATS-SMART、ZC-POV

   algo_param
  dict
  算法参数


   返回值：
     类型
  说明

     list[algoOrder]
  算法母单委托对象列表，参见 algoOrder 对象


   当 algo_name = 'ATS-SMART'时
algo_param 的参数为
     参数
  类型
  说明

     start_time
  str
  开始时间

   end_time_referred
  str
  结束参考时间(不能超过 14:55:00)

   end_time
  str
  结束时间(不能超过 14:55:00)

   end_time_valid
  int
  结束时间是否有效,如设为无效，则以收盘时间为结束时间, 1 为有效， 0 为无效

   stop_sell_when_dl
  int
  涨停时是否停止卖出， 1 为是，0 为否

   cancel_when_pl
  int
  跌停时是否撤单, 1 为是， 0 为否

   min_trade_amount
  int
  最小交易金额


   示例：


```
# 下算法母单，设定母单的执行参数
algo_param = {'start_time': '09:00:00', 'end_time_referred':'14:55:00', 'end_time': '14:55:00', 'end_time_valid': 1, 'stop_sell_when_dl': 1,
              'cancel_when_pl': 0, 'min_trade_amount': 100000}
aorders = algo_order(symbol='SHSE.600000', volume=20000, side=OrderSide_Buy, order_type=OrderType_Limit,
                   position_effect=PositionEffect_Open, price=5, algo_name='ATS-SMART', algo_param=algo_param)
print(aorders)
```

  输出：


```
[{'strategy_id': '6f534238-2883-11eb-a8fe-fa163ef85f63', 'account_id': '927f9095-27e5-11eb-bb81-fa163ef85f63', 'account_name': '1001000002', 'cl_ord_id': '03f13690-2d64-11eb-9e36-fa163ef85f63', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'order_type': 1, 'status': 10, 'price': 5.0, 'order_style': 1, 'volume': 20000, 'created_at': datetime.datetime(2020, 11, 23, 16, 15, 15, 105141, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 11, 23, 16, 15, 15, 105141,tzinfo=tzfile('PRC')), 'algo_name': 'ATS-SMART', 'algo_param': 'start_time&&1606093200||end_time_referred&&1606114500||end_time&&1606114500||end_time_valid&&1||stop_sell_when_dl&&1||cancel_when_pl&&0||min_trade_amount&&100000', 'order_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_status': 0, 'algo_comment': ''}]
```

  当 algo_name = 'ZC-POV'时
algo_param 的参数为
     参数
  类型
  说明

     part_rate
  float
  市场参与率（0~45），单位%，默认 30，即 30%

   price
  float
  基准价格


   示例：


```
# 下算法母单，设定母单的执行参数
algo_param = {"participation_rate" : 15, "price" : 15.47}
aorder = algo_order(symbol=symbol, volume=1000, side=OrderSide_Buy, order_type=OrderSide_Buy,
               position_effect=PositionEffect_Open, price=price, algo_name=algo_name, algo_param=algo_param)
print(aorder)
```

  输出：


```
[{'strategy_id': '6f534238-2883-11eb-a8fe-fa163ef85f63', 'account_id': '15b7afb1-e91d-11eb-953b-025041000001', 'account_name': 'b6b2819b-e864-11eb-b146-00163e0a4100', 'cl_ord_id': 'e0f4ca3f-f97a-11eb-acee-165afc004509', 'symbol': 'SHSE.600007', 'side': 1, 'position_effect': 1, 'order_type': 1, 'status': 10, 'price': 15.470000267028809, 'order_style': 1, 'volume': 1000, 'created_at': datetime.datetime(2021, 8, 10, 9, 32, 52, 39737, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2021, 8, 10, 9, 32, 52, 42738, tzinfo=tzfile('PRC')), 'algo_name': 'ZC-POV', 'algo_param': 'TimeStart&&1628559000||TimeEnd&&1628578800||PartRate&&0.150000||MinAmount&&1000', 'order_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_status': 0, 'algo_comment': '', 'properties': {}]
```

  注意：  回测模式不支持算法单


## #   algo_order_cancel  撤销算法委托

  撤销母单委托
   函数原型：


```
algo_order_cancel(wait_cancel_orders)
```

  参数：
     参数
  类型
  说明

     wait_cancel_orders
  str
  撤单算法委托. 传入单个字典. 或者 list 字典. 每个字典包含 key:cl_ord_id key:account_id


  cl_ord_id 为委托 id， account_id 为账户 id
   返回值：
     类型
  说明

     list[algoOrder]
  算法母单委托对象列表，参见 algoOrder 对象


   示例：


```
aorders = get_algo_orders(account='')
wait_cancel_orders = [{'cl_ord_id': aorders[0]['cl_ord_id'], 'account_id': aorders[0]['account_id']}]
algo_order_cancel(wait_cancel_orders)
```

## #   get_algo_orders  查询算法委托

  查询母单委托
   函数原型：


```
algo_order_cancel(account)
```

  参数：
     参数
  类型
  说明

     account
  str
  account_id 默认帐号时为 ''


   返回值：
     类型
  说明

     list[algoOrder]
  算法母单委托对象列表，参见 algoOrder 对象


   示例：


```
get_algo_orders(account='')
```

  输出：


```
[{'strategy_id': '6f534238-2883-11eb-a8fe-fa163ef85f63', 'account_id': '927f9095-27e5-11eb-bb81-fa163ef85f63', 'account_name': '1001000002', 'cl_ord_id': 'fe0ec2d3-2d50-11eb-9e36-fa163ef85f63', 'symbol': 'SHSE.510300', 'side': 1, 'position_effect': 1, 'order_type': 1, 'status': 10, 'price': 5.0, 'order_style': 1, 'volume': 20000, 'created_at': datetime.datetime(2020, 11, 23, 13, 59, 4,794594, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 11, 23, 13, 59, 4, 795571, tzinfo=tzfile('PRC')), 'algo_name': 'ATS-SMART', 'algo_param': 'start_time&&1606093200||end_time_referred&&1606114500||end_time&&1606114500||end_time_valid&&1||stop_sell_when_dl&&1||cancel_when_pl&&0||min_trade_amount&&100000', 'order_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_status': 0, 'algo_comment': ''}]
```

## #   algo_order_pause  暂停或重启或者撤销算法委托

   函数原型：


```
algo_order_pause(alorders)
```

  参数：
     参数
  类型
  说明

     alorders
  str
  传入单个字典. 或者 list 字典. 每个字典包含 key:cl_ord_id, key:account_id key:algo_status


  cl_ord_id 为委托 id， account_id 为账户 id，algo_status 为算法单状态（1 - 重启 2 - 暂停 3 -暂停并撤子单）
   返回值：
     类型
  说明

     list[algoOrder]
  算法母单委托对象列表，参见 algoOrder 对象




```
aorders = get_algo_orders(account='')
# 暂停订单，修改订单结构的母单状态字段
alorders01 = [{'cl_ord_id': aorders[0]['cl_ord_id'], 'account_id': aorders[0]['account_id'], 'algo_status': 3}]
algo_order_pause(alorders01)
```

  注意：  ATS-SMART 和 ZC-POV 算法暂不支持此接口


## #   get_algo_child_orders  查询算法委托的所有子单

   函数原型：


```
get_algo_child_orders(cl_ord_id, account='')
```

  参数：
     参数
  类型
  说明

     cl_ord_id
  str
  传入单个字典. 或者 list 字典. 每个字典包含 key:cl_ord_id

   account
  str
  account_id 默认帐号时为 ''


   返回值：
     类型
  说明

     list[order]
  委托对象列表，参见 order 对象


   示例：


```
aorders = get_algo_orders(account='')
child_order= get_algo_child_orders(aorders[0]['cl_ord_id'], account='')
print(child_order[0])
```

  输出：


```
[{'account_id': '17ceec74-2efb-11eb-b437-00ff5a669ee2', 'account_name': '0000001', 'cl_ord_id': '1606294231_9', 'order_id': '1606294231_9', 'symbol': 'SZSE.000001', 'side': 1, 'position_effect': 1, 'order_type': 1, 'status': 3, 'price': 19.06, 'volume': 100, 'filled_volume': 100, 'filled_vwap': 19.06, 'filled_amount': 1905.9999999999998, 'algo_order_id': '453b3064-2efb-11eb-b437-00ff5a669ee2', 'strategy_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'order_style': 0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_commission': 0.0, 'created_at': None, 'updated_at': None}]
```

## #   on_algo_order_status  算法单状态事件

  响应算法单状态更新事情，下算法单后状态更新时被触发
   函数原型：


```
on_algo_order_status(context, algo_order)
```

  参数：
     参数名
  类型
  说明

     context
   context
  上下文

   algo_order
   order 对象
  委托


   示例：


```
def on_algo_order_status(context, algo_order):
	print(algo_order)
```

  输出：


```
{'strategy_id': '6f534238-2883-11eb-a8fe-fa163ef85f63', 'account_id': '927f9095-27e5-11eb-bb81-fa163ef85f63', 'account_name': '1001000002', 'cl_ord_id': '09baa735-2e01-11eb-ab6f-fa163ef85f63','symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1,'order_type': 1, 'status':1, 'price': 5.0, 'order_style': 1, 'volume': 20000, 'created_at':datetime.datetime(2020,11, 24, 10, 59, 15, 800453, tzinfo=tzfile('PRC')), 'updated_at': datetime.datetime(2020, 11, 24, 10, 59, 17, 922523, tzinfo=tzfile('PRC')), 'algo_name': 'ATS-SMART', 'algo_param': 'start_time&&1606179600||end_time_referred&&1606200900||end_time&&1606200900||end_time_valid&&1|stop_sell_when_dl&&1||cancel_when_pl&&0||min_trade_amount&&100000', 'order_id': '', 'ex_ord_id':'', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier':0, 'order_src': 0, 'position_src': 0, 'ord_rej_reason': 0, 'ord_rej_reason_detail': '', 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_status':0, 'algo_comment': ''}
```

## #   algo_order_batch  批量算法交易委托

  批量委托算法母单（N个标的代码，一次性批量下同一算法的N个母单）
   函数原型：


```
algo_order_batch(algo_orders, algo_name, algo_param, account='')
```

  参数：
     参数
  类型
  说明

     algo_orders
  list[algoOrder]
  算法委托对象列表，其中algoOrder为字典，字段参见 algoOrder 对象

   algo_name
  str
  算法名称，批量算法交易接口仅支持'ATS-SMART'算法，'ZC-POV'算法

   algo_param
  dict
  算法参数

   account
  account id or account name or None
  帐户


  algoOrder字典
     参数
  类型
  说明

     symbol
  str
  标的代码

   volume
  int
  委托数量

   price
  int
  委托价格，ZC-POV算法的基准价格（ATS-SMART 算法不生效）

   side
  int
  参见 订单委托方向 ，OrderSide_Buy = 1 买入OrderSide_Sell = 2 卖出

   order_type
  int
  参见 订单委托类型 ，OrderType_Limit = 1 限价委托，OrderType_Market = 2 市价委托

   position_effect
  int
  参见 开平仓类型 ，PositionEffect_Open = 1 开仓 PositionEffect_Close = 2 平仓


   返回值：
     类型
  说明

     list[algoOrder]
  算法母单委托对象列表，参见 algoOrder 对象


   当 algo_name = 'ATS-SMART'时
algo_param 的参数为
     参数
  类型
  说明

     start_time
  str
  开始时间

   end_time_referred
  str
  结束参考时间(不能超过 14:55:00)

   end_time
  str
  结束时间(不能超过 14:55:00)

   end_time_valid
  int
  结束时间是否有效,如设为无效，则以收盘时间为结束时间, 1 为有效， 0 为无效

   stop_sell_when_dl
  int
  涨停时是否停止卖出， 1 为是，0 为否

   cancel_when_pl
  int
  跌停时是否撤单, 1 为是， 0 为否

   min_trade_amount
  int
  最小交易金额


   示例：


```
order_1 = {'symbol': 'SHSE.600000', 'volume': 20000, 'price': 11, 'side': 1,'order_type': 2, 'position_effect':1}
order_2 = {'symbol': 'SHSE.600004', 'volume': 20000, 'price': 11, 'side': 1,'order_type': 2, 'position_effect':1}
my_orders = [order_1, order_2]

my_algo_param = {'start_time':'10:00:00', 'end_time':'14:55:00', 'end_time_referred':'14:55:00', 'end_time_valid': 1, 'stop_sell_when_dl':1, 'cancel_when_pl': 0, 'min_trade_amount': 100000}

batch_algo_orders = algo_order_batch(algo_orders=my_orders, algo_name='ATS-SMART', algo_param=my_algo_param, account='64b20e68-45b2-11ec-b534-00163e0a4100')

for algo_order in batch_algo_orders:
    print(algo_order)
```

  输出：


```
{'strategy_id': 'f467dbdd-c746-11ef-8b37-803f5d090d40', 'account_id': '64b20e68-45b2-11ec-b534-00163e0a4100', 'account_name': '64b20e68-45b2-11ec-b534-00163e0a4100', 'cl_ord_id': 'b2778a14-c8cf-11ef-b39e-803f5d090d40', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 8, 'ord_rej_reason': 17, 'ord_rej_reason_detail': '[GMTERM] 账号无该算法权限', 'price': 11.0, 'order_style': 1, 'volume': 20000, 'created_at': datetime.datetime(2025, 1, 2, 14, 6, 24, 973877, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'updated_at': datetime.datetime(2025, 1, 2, 14, 6, 24, 973877, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'algo_name': 'ATS-SMART', 'properties': {'origin_product': 'ZILCHTECH'}, 'algo_provider': 'ZILCHTECH', 'algo_params': {'stop_sell_when_dl': '1', 'end_time_valid': '1', 'cancel_when_pl': '0', 'price': '11.000000', 'end_time_referred': '1735800900', 'end_time': '1735800900', 'min_trade_amount': '100000', 'start_time': '1735783200'}, 'channel_id': '', 'order_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_param': '', 'algo_status': 0, 'algo_comment': ''}
{'strategy_id': 'f467dbdd-c746-11ef-8b37-803f5d090d40', 'account_id': '64b20e68-45b2-11ec-b534-00163e0a4100', 'account_name': '64b20e68-45b2-11ec-b534-00163e0a4100', 'cl_ord_id': 'b2778a14-c8cf-11ef-b39f-803f5d090d40', 'symbol': 'SHSE.600004', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 8, 'ord_rej_reason': 17, 'ord_rej_reason_detail': '[GMTERM] 账号无该算法权限', 'price': 11.0, 'order_style': 1, 'volume': 20000, 'created_at': datetime.datetime(2025, 1, 2, 14, 6, 24, 973877, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'updated_at': datetime.datetime(2025, 1, 2, 14, 6, 24, 973877, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'algo_name': 'ATS-SMART', 'properties': {'origin_product': 'ZILCHTECH'}, 'algo_provider': 'ZILCHTECH', 'algo_params': {'stop_sell_when_dl': '1', 'end_time_valid': '1', 'cancel_when_pl': '0', 'end_time_referred': '1735800900', 'price': '11.000000', 'end_time': '1735800900', 'min_trade_amount': '100000', 'start_time': '1735783200'}, 'channel_id': '', 'order_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_param': '', 'algo_status': 0, 'algo_comment': ''}
```

  当 algo_name = 'ZC-POV'时
algo_param 的参数为
     参数
  类型
  说明

     part_rate
  float
  市场参与率（0~45），单位%，默认 30，即 30%


   示例：


```
order_1 = {'symbol': 'SHSE.600000', 'volume': 20000, 'price': 11, 'side': 1,'order_type': 2, 'position_effect':1}
order_2 = {'symbol': 'SHSE.600004', 'volume': 20000, 'price': 11, 'side': 1,'order_type': 2, 'position_effect':1}
my_orders = [order_1, order_2]

my_algo_param = {'participation_rate':40}

batch_algo_orders = algo_order_batch(algo_orders=my_orders, algo_name='ZC-POV', algo_param=my_algo_param, account='64b20e68-45b2-11ec-b534-00163e0a4100')

for algo_order in batch_algo_orders:
    print(algo_order)
```

  输出：


```
{'strategy_id': 'f467dbdd-c746-11ef-8b37-803f5d090d40', 'account_id': '64b20e68-45b2-11ec-b534-00163e0a4100', 'account_name': '64b20e68-45b2-11ec-b534-00163e0a4100', 'cl_ord_id': '11a199f1-c8d2-11ef-b3a0-803f5d090d40', 'symbol': 'SHSE.600000', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 8, 'ord_rej_reason': 17, 'ord_rej_reason_detail': '[GMTERM] 账号无该算法权限', 'price': 11.0, 'order_style': 1, 'volume': 20000, 'created_at': datetime.datetime(2025, 1, 2, 14, 23, 23, 626546, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'updated_at': datetime.datetime(2025, 1, 2, 14, 23, 23, 626546, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'algo_name': 'ZC-POV', 'properties': {'origin_product': 'ZILCHTECH'}, 'algo_provider': 'ZILCHTECH', 'algo_params': {'participation_rate': '40', 'price': '11.000000'}, 'channel_id': '', 'order_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_param': '', 'algo_status': 0, 'algo_comment': ''}
{'strategy_id': 'f467dbdd-c746-11ef-8b37-803f5d090d40', 'account_id': '64b20e68-45b2-11ec-b534-00163e0a4100', 'account_name': '64b20e68-45b2-11ec-b534-00163e0a4100', 'cl_ord_id': '11a199f1-c8d2-11ef-b3a1-803f5d090d40', 'symbol': 'SHSE.600004', 'side': 1, 'position_effect': 1, 'order_type': 2, 'status': 8, 'ord_rej_reason': 17, 'ord_rej_reason_detail': '[GMTERM] 账号无该算法权限', 'price': 11.0, 'order_style': 1, 'volume': 20000, 'created_at': datetime.datetime(2025, 1, 2, 14, 23, 23, 626546, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'updated_at': datetime.datetime(2025, 1, 2, 14, 23, 23, 626546, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), 'algo_name': 'ZC-POV', 'properties': {'origin_product': 'ZILCHTECH'}, 'algo_provider': 'ZILCHTECH', 'algo_params': {'participation_rate': '40', 'price': '11.000000'}, 'channel_id': '', 'order_id': '', 'ex_ord_id': '', 'position_side': 0, 'order_business': 0, 'order_duration': 0, 'order_qualifier': 0, 'order_src': 0, 'position_src': 0, 'stop_price': 0.0, 'value': 0.0, 'percent': 0.0, 'target_volume': 0, 'target_value': 0.0, 'target_percent': 0.0, 'filled_volume': 0, 'filled_vwap': 0.0, 'filled_amount': 0.0, 'filled_commission': 0.0, 'algo_param': '', 'algo_status': 0, 'algo_comment': ''}
```

  注意：
   1.  回测模式不支持批量算法单。
   2.  每个母单 algoOrder 的 symbol 仅支持一个标的代码，若交易代码输入有误，终端会拒绝此单，并显示委托代码不正确。
   3.  每个母单 algoOrder 的 symbol 不能重复，如果 list[algoOrder] 有重复标的代码symbol，批量委托会报错
   4.  算法参数 algo_param 对每个母单 algoOrder 均生效。
   5.  ZC-POV算法支持的批量母单数量上限100，超出会被拒绝。


      ←

        两融交易函数

        新股新债交易函数

      →

---

## 老版本数据函数

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E8%80%81%E7%89%88%E6%9C%AC%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0.html

<!DOCTYPE html>




     老版本数据函数 - 掘金量化












# #  老版本数据函数

   以下接口在终端版本号大于 3.17.0.0 的版本不再维护，请切换到新的通用接口


## #   get_fundamentals  - 查询基本面数据

  获取基本面数据
   此函数掘金公版(体验版/专业版/机构版)不支持，请切换到 stk_get_fundamentals_balance - 查询资产负债表数据 等新接口
   函数原型：


```
get_fundamentals(table, symbols, start_date, end_date, fields=None, filter=None, order_by=None, limit=1000, df=False)
```

  参数：
     参数名
  类型
  说明

     table
  str
  表名，只支持单表查询. 具体表名及 fields 字段名及 filter 可过滤的字段参考  财务数据文档

   symbols
  str or list
  标的代码, 多个代码可用  , (英文逗号)分割, 也支持  ['symbol1', 'symbol2']  这种列表格式，使用时参考 symbol  ，免费版本只支持单个标的，多标的只返回第一个

   start_date
  str
  开始时间, (%Y-%m-%d 格式)

   end_date
  str
  结束时间, (%Y-%m-%d 格式)

   fields
  str
  查询字段 (必填)

   limit
  int
  数量. 默认是 1000 , 为保护服务器, 单次查询最多返回  40000  条记录

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回 list[dict]


   返回值：
     key
  value 类型
  说明

     symbol
  str
  标的代码

   pub_date
  datetime.datetime
  公司发布财报的日期.

   end_date
  datetime.datetime
  财报统计的季度的最后一天.

   fields
  dict
  相应指定查询  fields  字段的值. 字典 key 值请参考  财务数据文档


   示例：
  例 1: 取股票代码  SHSE.600000, SZSE.000001 , 离  2017-01-01  最近一个交易日的 股票交易财务衍生表 的  TCLOSE,NEGOTIABLEMV,TOTMKTCAP,TURNRATE,PELFY,PETTM,PEMRQ,PELFYNPAAEI,PETTMNPAAEI  字段的值


```
get_fundamentals(table='trading_derivative_indicator', symbols='SHSE.600000, SZSE.000001', start_date='2017-01-01', end_date='2017-01-01',             fields='TCLOSE,NEGOTIABLEMV,TOTMKTCAP,TURNRATE,PELFY,PETTM,PEMRQ,PELFYNPAAEI,PETTMNPAAEI', df=True)
```

  输出：


```
symbol       pub_date             end_date             NEGOTIABLEMV  PEMRQ    PELFYNPAAEI    PETTMNPAAEI  PELFY    TURNRATE    PETTM    TOTMKTCAP    TCLOSE
SHSE.600000  2016-12-30 00:00:00  2016-12-30 00:00:00     3.3261e+11    6.4605         7.0707         6.6184   6.925       0.0598   6.4746  3.50432e+11     16.21
SZSE.000001  2016-12-30 00:00:00  2016-12-30 00:00:00     1.33144e+11   6.2604         7.1341         6.2644   7.1462      0.2068   6.8399  1.56251e+11      9.1
```

 例 2: 取股票代码  SHSE.600000, SZSE.000001 , 指定时间段  2016-01-01 -- 2017-01-01  股票交易财务衍生表 的  TCLOSE,NEGOTIABLEMV,TOTMKTCAP,TURNRATE,PELFY,PETTM,PEMRQ,PELFYNPAAEI,PETTMNPAAEI  字段的值


```
get_fundamentals(table='trading_derivative_indicator', symbols='SHSE.600000, SZSE.000001', start_date='2016-01-01', end_date='2017-01-01',
fields='TCLOSE,NEGOTIABLEMV,TOTMKTCAP,TURNRATE,PELFY,PETTM,PEMRQ,PELFYNPAAEI,PETTMNPAAEI', df=True)
```

  注意：
   1.  当  start_date  ==  end_date  时, 取所举每个股票离  end_date  最近业务日期(交易日期或报告日期) 一条数据,当  start_date  <  end_date  时, 取指定时间段的数据,当  start_date  >  end_date  时, 返回 空list/空DataFrame
   2.  当不指定排序方式时,返回的 list/DataFrame 以参数 pub_date/end_date 来排序
   3.  start_date 和 end_date 中月,日均可以只输入个位数,例: '2010-7-8' 或 '2017-7-30'
   4.  若输入包含无效标的代码，则返回的 list/DataFrame 只包含有效标的代码对应的数据
   5.  在该函数中，table 参数只支持输入一个表名，若表名输入错误或以 'table1,table2' 方式输入多个表名，函数返回 空list/空DataFrame
   6.  若表名输入正确，但查询字段中出现非指定字符串，则 程序直接报错


## #   get_fundamentals_n  - 查询基本面数据最新 n 条

  取指定股票的最近  end_date  的  count  条记录
   此函数掘金公版(体验版/专业版/机构版)不支持，请切换到 stk_get_fundamentals_balance - 查询资产负债表数据 等新接口
   函数原型：


```
get_fundamentals_n(table, symbols, end_date, fields=None, filter=None, order_by=None, count=1, df=False)
```

  参数：
     参数名
  类型
  说明

     table
  str
  表名，只支持单表查询. 具体表名及 fields 字段名及 filter 可过滤的字段参考  财务数据文档

   symbols
  str
  标的代码, 多个代码可用  , (英文逗号)分割, 也支持  ['symbol1', 'symbol2']  这种列表格式，使用时参考 symbol ，免费版本只支持单个标的，多标的只返回第一个

   end_date
  str
  结束时间, (%Y-%m-%d 格式)

   fields
  str
  查询字段 (必填)

   count
  int
  每个股票取最近的数量(正整数)

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回 list[dict]


   返回值：
     key
  value 类型
  说明

     symbol
  str
  标的代码

   pub_date
  datetime.datetime
  公司发布财报的日期.

   end_date
  datetime.datetime
  财报统计的季度的最后一天.

   fields
  dict
  相应指定查询  fields  字段的值. 字典 key 值请参考  财务数据文档


   示例：
  例 1: 取股票代码  SHSE.600000, SZSE.000001 , 离  2017-01-01  最近 3 条(每个股票都有 3 条) 股票交易财务衍生表 的  TCLOSE,NEGOTIABLEMV,TOTMKTCAP,TURNRATE,PELFY,PETTM,PEMRQ,PELFYNPAAEI,PETTMNPAAEI  字段的值


```
get_fundamentals_n(table='trading_derivative_indicator', symbols='SHSE.600000, SZSE.000001', end_date='2017-01-01', count=3,           fields='TCLOSE,NEGOTIABLEMV,TOTMKTCAP,TURNRATE,PELFY,PETTM,PEMRQ,PELFYNPAAEI,PETTMNPAAEI',df=True)
```

  输出：


```
symbol        pub_date             end_date           TCLOSE   TOTMKTCAP    PETTM      TURNRATE     PETTMNPAAEI  PELFY    PELFYNPAAEI    NEGOTIABLEMV    PEMRQ
SZSE.000001  2016-12-30 00:00:00  2016-12-30 00:00:00      9.1   1.56251e+11   6.8399      0.2068         6.2644   7.1462         7.1341     1.33144e+11   6.2604
SZSE.000001  2016-12-29 00:00:00  2016-12-29 00:00:00      9.08  1.55907e+11   6.8249      0.2315         6.2506   7.1305         7.1184     1.32851e+11   6.2466
SZSE.000001  2016-12-28 00:00:00  2016-12-28 00:00:00      9.06  1.55564e+11   6.8098      0.2297         6.2369   7.1147         7.1027     1.32558e+11   6.2329
SHSE.600000  2016-12-30 00:00:00  2016-12-30 00:00:00     16.21  3.50432e+11   6.4746      0.0598         6.6184   6.925          7.0707     3.3261e+11    6.4605
SHSE.600000  2016-12-29 00:00:00  2016-12-29 00:00:00     16.07  3.47406e+11   6.4187      0.0578         6.5613   6.8652         7.0097     3.29737e+11   6.4047
SHSE.600000  2016-12-28 00:00:00  2016-12-28 00:00:00     16.09  3.47838e+11   6.4267      0.0704         6.5694   6.8737         7.0184     3.30148e+11   6.4126
```

  注意：
   1.  对每个标的,返回的 list/DataFrame 以参数 pub_date/end_date 的倒序来排序
   2.  end_date 中月,日均可以只输入个位数,例: '2010-7-8' 或 '2017-7-30'
   3.  若输入包含无效标的代码，则返回的 list/DataFrame 只包含有效标的代码对应的数据
   4.  在该函数中，table 参数只支持输入一个表名，若表名输入错误或以 'table1,table2' 方式输入多个表名，函数返回 空list/空DataFrame
   5.  若表名输入正确，但查询字段中出现非指定字符串，则 程序直接报错


## #   get_instruments  - 查询最新交易标的信息

  查询最新交易标的信息,有基本数据及最新日频数据
   掘金公版(体验版/专业版/机构版)请切换到 get_symbols - 查询指定交易日多标的交易信息
   函数原型：


```
get_instruments(symbols=None, exchanges=None, sec_types=None, names=None, skip_suspended=True, skip_st=True, fields=None, df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str or list or None
  标的代码 多个代码可用  , (英文逗号)分割, 也支持  ['symbol1', 'symbol2']  这种列表格式,默认 None 表示所有，使用时参考 symbol

   exchanges
  str or list or None
  见 交易所代码 ,  多个交易所代码可用  , (英文逗号)分割, 也支持  ['exchange1', 'exchange2']  这种列表格式,默认 None 表示所有

   sec_types
  list
  指定类别, 默认所有, 其他类型见 sec_type 类型

   names
  str or None
  查询代码, 默认 None 表示所有

   skip_suspended
  bool
  是否跳过停牌, 默认 True 跳过停牌

   skip_st
  bool
  是否跳过 ST, 默认 True 跳过 ST

   fields
  str or None
  查询字段 默认 None 表示所有,参考返回值。

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回 list[dict]


   返回值：
     key
  类型
  说明

     symbol
  str
  标的代码

   sec_type
  int
  1: 股票, 2: 基金, 3: 指数, 4: 期货, 5: 期权, 8:可转债，10: 期货连续合约

   exchange
  str
  见 交易所代码

   sec_id
  str
  代码

   sec_name
  str
  名称

   sec_abbr
  str
  拼音简称

   price_tick
  float
  最小变动单位

   listed_date
  datetime.datetime
  上市日期

   delisted_date
  datetime.datetime
  退市日期

   trade_date
  datetime.datetime
  交易日期

   sec_level
  int
  1-正常,2-ST 股票,3-*ST 股票,4-股份转让,5-处于退市整理期的证券,6-上市开放基金 LOF,7-交易型开放式指数基金(ETF),8-非交易型开放式基金(暂不交易,仅揭示基金净值及开放申购赎回业务),9-仅提供净值揭示服务的开放式基金;,10-仅在协议交易平台挂牌交易的证券,11-仅在固定收益平台挂牌交易的证券,12-风险警示产品,13-退市整理产品,99-其它

   is_suspended
  int
  是否停牌. 1: 是, 0: 否

   multiplier
  float
  合约乘数

   margin_ratio
  float
  保证金比率

   settle_price
  float
  结算价

   position
  int
  持仓量

   pre_close
  float
  昨收价

   upper_limit
  float
  涨停价 （首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）

   lower_limit
  float
  跌停价 （首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）

   adj_factor
  float
  复权因子.基金跟股票才有

   conversion_price
  float
  可转债转股价

   conversion_start_date
  datetime.datetime
  可转债开始转股时间

   underlying_symbol
  str
  可转债正股标的


   示例：


```
get_instruments(exchanges='SZSE', df=True)
```

  输出：


```
adj_factor    is_st    upper_limit  sec_name      pre_close  symbol         price_tick  delisted_date        exchange    listed_date            sec_type    settle_price    lower_limit    multiplier  sec_abbr      position  trade_date               sec_id    is_suspended    margin_ratio
   115.338          0          12.38  平安银行             11.25  SZSE.000001          0.01  2038-01-01 00:00:00  SZSE        1991-04-03 00:00:00           1               0          10.13             1  payx               0   2017-09-19 00:00:00    000001               0               1
   127.812          0          30.84  万科A                28.04  SZSE.000002          0.01  2038-01-01 00:00:00  SZSE        1991-01-29 00:00:00           1               0          25.24             1  wkA                0   2017-09-19  00:00:00   000002               0               1
   7.44538          0          27.24  国农科技             24.76  SZSE.000004          0.01  2038-01-01 00:00:00  SZSE        1991-01-14 00:00:00           1               0          22.28             1  gnkj               0   2017-09-19 00:00:00    000004               0               1
   ······
```

  注意：
   1.  停牌时且股票发生除权除息, 涨停价和跌停价可能有误差
   2.  预上市股票以 1900-01-01 为虚拟发布日期，未退市股票以 2038-01-01 为虚拟退市日期。
   3.  对于检索所需标的信息的 4 种手段 symbols,exchanges,sec_types,names ,若输入参数之间出现任何矛盾（换句话说，所有的参数限制出满足要求的交集为空),则返回
 空list/空DataFrame
例如 get_instruments(exchanges='SZSE',sec_types=[4]) 返回的是空值
 4.  获取全 A 股票代码示例 get_instruments(exchanges='SZSE,SHSE', sec_types=1, fields='symbol',df=1)['symbol'].tolist()   5.  若查询字段包含无效字段，返回的 列表/DataFrame 只包含有效字段数据
 6.  关于可转债的到期日(退市日期)为 delisted_date ，转股价值为 转股价值 = 转股数*股价=（100/可转债转股价）*股价


## #   get_history_instruments  - 查询交易标的历史信息数据

  返回指定 symbols 的标的日频历史数据
   掘金公版(体验版/专业版/机构版)请切换到 get_history_symbol - 查询指定标的多日交易信息
   函数原型：


```
get_history_instruments(symbols, fields=None, start_date=None, end_date=None, df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str or list
  标的代码, 多个代码可用  , (英文逗号)分割,也支持  ['symbol1', 'symbol2']  这种列表格式, 是必填参数，使用时参考 symbol

   fields
  str or None
  查询字段. 默认  None  表示所有

   start_date
  str or None
  开始时间. (%Y-%m-%d 格式) 默认  None  表示当前时间

   end_date
  str or None
  结束时间. (%Y-%m-%d 格式) 默认  None  表示当前时间

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回  list[dict] , 列表每项的 dict 的 key 值为参数指定的  fields


   返回值：
     key
  类型
  说明

     symbol
  str
  标的代码

   trade_date
  datetime.datetime
  交易日期

   sec_level
  int
  1-正常,2-ST 股票,3-*ST 股票,4-股份转让,5-处于退市整理期的证券,6-上市开放基金 LOF,7-交易型开放式指数基金(ETF),8-非交易型开放式基金(暂不交易,仅揭示基金净值及开放申购赎回业务),9-仅提供净值揭示服务的开放式基金;,10-仅在协议交易平台挂牌交易的证券,11-仅在固定收益平台挂牌交易的证券,12-风险警示产品,13-退市整理产品,99-其它

   is_suspended
  int
  是否停牌. 1: 是, 0: 否

   multiplier
  float
  合约乘数

   margin_ratio
  float
  保证金比率

   settle_price
  float
  结算价

   pre_settle
  float
  昨结价

   position
  int
  持仓量

   pre_close
  float
  昨收价

   upper_limit
  float
  涨停价（首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）

   lower_limit
  float
  跌停价（首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）

   adj_factor
  float
  复权因子.基金跟股票才有


   示例：


```
get_history_instruments(symbols='SZSE.000001,SZSE.000002', start_date='2017-09-19', end_date='2017-09-19', df=True)
```

  输出：


```
adj_factor    is_st       settle_price   upper_limit  symbol        pre_close    lower_limit       is_suspended    multiplier    position      trade_date             margin_ratio
     115.338        0               0          12.38  SZSE.000001        11.25          10.13               0             1           0    2017-09-19 00:00:00               1
     127.812        0               0          30.84  SZSE.000002        28.04          25.24               0             1           0    2017-09-19 00:00:00               1
```

  注意：
   1.  停牌时且股票发生除权除息, 涨停价和跌停价可能有误差
   2.  为保护服务器, 单次查询最多返回  33000  条记录
   3.  对每个标的，数据根据参数 trade_date 的升序进行排序
   4.  start_date 和 end_date 中月,日均可以只输入个位数,例: '2010-7-8' 或 '2017-7-30'
   5.  若查询字段中出现非指定字符串，则 程序直接报错
   6.  若输入包含无效标的代码，则返回的 list/DataFrame 只包含有效标的代码对应的数据


## #   get_instrumentinfos  - 查询交易标的基本信息

  获取到交易标的基本信息, 与时间无关.
   掘金公版(体验版/专业版/机构版)请切换到 get_symbol_infos - 查询标的基本信息
   函数原型：


```
get_instrumentinfos(symbols=None, exchanges=None, sec_types=None, names=None, fields=None, df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str or list or None
  标的代码 多个代码可用  , (英文逗号)分割, 也支持  ['symbol1', 'symbol2']  这种列表格式,默认 None 表示所有，使用时参考 symbol

   exchanges
  str or list or None
  见 交易所代码 ,  多个交易所代码可用  , (英文逗号)分割, 也支持  ['exchange1', 'exchange2']  这种列表格式,默认 None 表示所有

   sec_types
  list
  指定类别, 默认所有, 其他类型见 sec_type 类型

   names
  str or None
  查询代码, 默认  None  表示所有

   fields
  str or None
  查询字段 默认  None  表示所有

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回字典格式，返回  list[dict] , 列表每项的 dict 的 key 值为参数指定的  fields


   返回值：
     key
  类型
  说明

     symbol
  str
  标的代码

   sec_type
  int
  1: 股票, 2: 基金, 3: 指数, 4: 期货, 5: 期权, 8：可转债， 10: 期货连续合约

   exchange
  str
  见 交易市场代码 .

   sec_id
  str
  代码

   sec_name
  str
  名称

   sec_abbr
  str
  拼音简称

   price_tick
  float
  最小变动单位

   listed_date
  datetime.datetime
  上市日期

   delisted_date
  datetime.datetime
  退市日期

   conversion_price
  float
  可转债转股价

   underlying_symbol
  str
  可转债正股标的


   示例：


```
get_instrumentinfos(symbols=['SHSE.000001','SHSE.000002'],df=True)
```

  输出：


```
sec_name      symbol         price_tick  delisted_date          sec_type  sec_abbr   sec_id       listed_date     exchange
上证指数     SHSE.000001            0  2038-01-01 00:00:00           3    szzs          000001    1991-07-15 00:00:00  SHSE
A股指数      SHSE.000002            0  2038-01-01 00:00:00           3    Agzs          000002    1992-02-21 00:00:00  SHSE
```

  注意：
   1.  对于检索所需标的信息的 4 种手段 symbols,exchanges,sec_types,names ,若输入参数之间出现任何矛盾（换句话说，所有的参数限制出满足要求的交集为空),则返回
 空list/空DataFrame
例如 get_instrumentinfos(exchanges='SZSE',sec_types=[4]) 返回的是空值
   2.  若查询字段包含无效字段，返回的 列表/DataFrame 只包含有效字段数据


## #   get_constituents  - 查询指数最新成份股

  获取指数最新成分股
   掘金公版(体验版/专业版/机构版)请切换到 stk_get_index_constituents - 查询指数成分股
   函数原型：


```
get_constituents(index, fields=None, df=False)
```

  参数：
     参数名
  类型
  说明

     index
  str
   指数代码

   fields
  str or None
  若要有返回权重字段, 可以设置为 'symbol, weight'

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回 list[dict]


   返回值：
    参数 fields 为 None 时, 返回  list[str]  , 成分股列表

   参数 fields 指定为  'symbol, weight' , 返回  list[dict] , dict 包含 key 值:

     参数名
  类型
  说明

     symbol
  str
  股票 symbol

   weight
  float
  权重


  当 df = True 时，返回
     类型
  说明

     dataframe
  dataframe


   示例 1：


```
get_constituents(index='SHSE.000001', fields='symbol, weight', df=True)
```

  输出：


```
symbol        weight
SHSE.603966      0.01
SHSE.603960      0.01
···
```

 当 df = False 时，返回
     类型
  说明

     list[dict()]
  列表镶嵌字典


   示例 2：


```
get_constituents(index='SHSE.000001', fields='symbol, weight', df=False)
```

  输出：


```
[{'symbol': 'SHSE.603681', 'weight': 0.009999999776482582}, {'symbol': 'SHSE.601518', 'weight': 0.009999999776482582}, {'symbol': 'SHSE.600010', 'weight': 0.12999999523162842}···]
```

  示例 3：
只输出  symbol  列表


```
get_constituents(index='SHSE.000001')
```

  输出：


```
['SHSE.603966', 'SHSE.603960', 'SHSE.603218',···]
```

  注意：
   1.  在该函数中，index 参数只支持输入一个指数代码，若代码输入错误或以 'index1,inedx2' 方式输入多个代码，函数返回 空list/空DataFrame


## #   get_history_constituents  - 查询指数成份股的历史数据

  获取指数成份股的历史数据
   掘金公版(体验版/专业版/机构版)请切换到 stk_get_index_constituents - 查询指数成分股
   函数原型：


```
get_history_constituents(index, start_date=None, end_date=None)
```

  参数：
     参数名
  类型
  说明

     index
  str
   指数代码

   start_date
  str or datetime.datetime or None
  开始时间 (%Y-%m-%d 格式) 默认  None  表示当前日期

   end_date
  str or datetime.datetime or None
  结束时间 (%Y-%m-%d 格式) 默认  None  表示当前日期


   返回值：
   list[constituent]   constituent  为 dict,包含 key 值 constituents 和 trade_date :
     参数名
  类型
  说明

     constituents
  dict
  股票代码作为 key, 所占权重作为 value 的键值对

   trade_date
  datetime.datetime
  交易日期


   示例：


```
get_history_constituents(index='SHSE.000001', start_date='2017-07-10')
```

  输出：


```
constituents                                                    trade_date
{'SHSE.600527': 0.009999999776482582, 'SHSE.600461': 0.019999999552965164,···}     2017-07-31 00:00:00
{'SHSE.603966': 0.009999999776482582, 'SHSE.603960': 0.009999999776482582,···}     2017-08-31 00:00:00
···
```

  注意：
   1.  函数返回的数据每月发布一次，故返回的数据是月频数据， trade_date 为各月最后一天
   2.  在该函数中，index 参数只支持输入一个指数代码，若代码输入错误或以 'index1,inedx2' 方式输入多个代码，函数返回 空list
   3.  start_date 和 end_date 中月,日均可以只输入个位数,例: '2010-7-8' 或 '2017-7-30' ,但若对应位置为零，则 0 不可被省略


## #   get_continuous_contracts  - 获取主力合约

  获取主力合约和次主力合约
   掘金公版(体验版/专业版/机构版)请切换到 fut_get_continuous_contracts - 查询连续合约对应的真实合约
   函数原型：


```
get_continuous_contracts(csymbol, start_date=None, end_date=None)
```

  参数：
     参数名
  类型
  说明

     csymbol
  str
   查询代码  比如获取主力合约，输入 SHFE.AG;获取连续合约，输入 SHFE.AG00

   start_date
  str
  开始时间 (%Y-%m-%d 格式)

   end_date
  str
  结束时间 (%Y-%m-%d 格式)


   返回值：
  返回  list[dict] , dict 包含 key 值:
     key
  value 类型
  说明

     symbol
  str
  真实合约 symbol

   trade_date
  datetime.datetime
  交易日期


   示例：


```
get_continuous_contracts(csymbol='SHFE.AG', start_date='2017-07-01', end_date='2017-08-01')
```

  输出：


```
[{'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 1, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 2, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 3, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 4, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 5, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 6, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 7, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 8, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 9, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHFE.ag2012', 'trade_date': datetime.datetime(2020, 7, 10, 0, 0, tzinfo=tzfile('PRC'))}]
```

  注意：
   1.  在该函数中，csymbol 参数只支持输入一个标的代码，若代码输入错误或以 'csymbol1,csymbol2' 方式输入多个代码，函数返回 空list
   2.   start_date 和 end_date 中月,日均可以只输入个位数, 例: '2017-7-1' 或 '2017-8-1'


## #   get_industry  - 查询行业股票列表

  获取行业股票列表
   掘金公版(体验版/专业版/机构版)请切换到 stk_get_industry_category - 查询行业分类
   函数原型：


```
get_industry(code)
```

  参数：
     参数名
  类型
  说明

     code
  str
   行业代码  不区分大小写


   返回值：
   list 返回指定行业的成份股 symbol 列表
   示例：


```
#返回所有以J6开头的行业代码对应的成分股(包括:J66,J67,J68,J69的成分股)
get_industry(code='j6')
```

  输出：


```
['SHSE.600000', 'SHSE.600016', 'SHSE.600030',···]
```

  注意：
   1.  在该函数中，code 参数只支持输入一个行业代码，若代码输入错误或以 'code1,code2' 方式输入多个代码，函数返回 空list


## #   get_dividend  - 查询分红送配

  获取分红配送
   掘金公版(体验版/专业版/机构版)请切换到 stk_get_dividend - 查询股票分红送股信息
   函数原型：


```
get_dividend(symbol, start_date, end_date=None)
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码, (必填)，使用时参考 symbol

   start_date
  str
  开始时间 (%Y-%m-%d 格式)

   end_date
  str
  结束时间 (%Y-%m-%d 格式)

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回返回 list[dividend] ，dividend 为 dict


   返回值：
     key
  value 类型
  说明

     symbol
  str
  标的代码

   cash_div
  float
  每股派现

   allotment_ratio
  float
  每股配股比例

   allotment_price
  float
  配股价

   share_div_ratio
  float
  每股送股比例

   share_trans_ratio
  float
  每股转增比例

   created_at
  datetime.datetime
  创建时间


   示例：


```
get_dividend(symbol='SHSE.600000',start_date='2000-01-01', end_date='2017-12-31', df=True)
```

  输出：


```
share_trans_ratio  symbol         cash_div    allotment_ratio    allotment_price    share_div_ratio
       0            SHSE.600000        0.15                  0                  0                  0
       0.5          SHSE.600000         0.2                  0                  0                  0
                ···
```

  注意：
   1.  在该函数中，symbol 参数只支持输入一个标的代码，若代码输入错误或以 'symbol1,symbol2' 方式输入多个代码，函数返回 空list/空DataFrame
   2.   start_date 和 end_date 中月,日均可以只输入个位数, 例: '2010-7-8' 或 '2017-7-30'


## #   get_trading_dates  - 查询交易日列表

  获取交易日列表
   掘金公版(体验版/专业版/机构版)请切换到 get_trading_dates_by_year - 查询年度交易日历
   函数原型：


```
get_trading_dates(exchange, start_date, end_date)
```

  参数：
     参数名
  类型
  说明

     exchange
  str
  见 交易市场代码

   start_date
  str
  开始时间 (%Y-%m-%d 格式)

   end_date
  str
  结束时间 (%Y-%m-%d 格式)


   返回值：
  交易日期字符串(%Y-%m-%d 格式)列表,
   示例：


```
get_trading_dates(exchange='SZSE', start_date='2017-01-01', end_date='2017-01-30')
```

  输出：


```
['2017-01-03', '2017-01-04', '2017-01-05', '2017-01-06', ...]
```

  注意：
   1.   exchange 参数仅支持输入单个交易所代码,若代码错误，返回 空list
   2.   start_date 和 end_date 中月,日均可以只输入个位数, 例: '2010-7-8' 或 '2017-7-30'


## #   get_previous_trading_date  - 返回指定日期的上一个交易日

   掘金公版(体验版/专业版/机构版)请切换到 get_trading_dates_by_year - 查询年度交易日历
   函数原型：


```
get_previous_trading_date(exchange, date)
```

  参数：
     参数名
  类型
  说明

     exchange
  str
  见 交易市场代码

   date
  str
  时间 (%Y-%m-%d 格式)


   返回值：
   str 返回指定日期的上一个交易日字符串(%Y-%m-%d 格式)
   示例：


```
get_previous_trading_date(exchange='SZSE', date='2017-05-01')
```

  输出：


```
'2017-04-28'
```

  注意：
   1.   exchange 参数仅支持输入单个交易所代码,若代码错误，返回 空list
   2.   date 中月,日均可以只输入个位数, 例: '2010-7-8' 或 '2017-7-30'


## #   get_next_trading_date  - 返回指定日期的下一个交易日

   掘金公版(体验版/专业版/机构版)请切换到 get_trading_dates_by_year - 查询年度交易日历
   函数原型：


```
get_next_trading_date(exchange, date)
```

  参数：
     参数名
  类型
  说明

     exchange
  str
  见 交易市场代码

   date
  str
  时间 (%Y-%m-%d 格式)


   返回值：
   str 返回指定日期的下一个交易日字符串 (%Y-%m-%d 格式)
   示例：


```
get_next_trading_date(exchange='SZSE', date='2017-05-01')
```

  输出：


```
'2017-05-02'
```

  注意：
   1.   exchange 参数仅支持输入单个交易所代码,若代码错误，返回 空list
   2.   date 中月,日均可以只输入个位数, 例: '2010-7-8' 或 '2017-7-30'

---

## 股票增值数据函数（付费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E8%82%A1%E7%A5%A8%E5%A2%9E%E5%80%BC%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0%EF%BC%88%E4%BB%98%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     股票增值数据函数(付费) - 掘金量化












# #  股票增值数据函数(付费)

  python 股票与指数数据 API 包含在 gm3.0.148 版本及以上版本


## #   stk_get_industry_category  - 查询行业分类

  查询指定行业来源的行业列表
   函数原型：


```
stk_get_industry_category(source='zjh2012', level=1)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     source
  str
  行业来源
  N
  'zjh2012'
  'zjh2012'- 证监会行业分类 2012（默认）， 'sw2021'- 申万行业分类 2021, 查看 行业分类

   level
  int
  行业分级
  N
  1
  1 - 一级行业（默认），2 - 二级行业，3 - 三级行业


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     industry_code
  str
  行业代码
  所选行业来源，对应的行业代码

   industry_name
  str
  行业名称
  所选行业来源，对应的行业名称


   示例：


```
industry_category = stk_get_industry_category(source='sw2021', level=2)
```

  输出：


```
industry_code industry_name
0          110100           种植业
1          110200            渔业
2          110300           林业Ⅱ
3          110400            饲料
4          110500         农产品加工
..            ...           ...
129        760100          环境治理
130        760200         环保设备Ⅱ
131        770100          个护用品
132        770200           化妆品
133        770300          医疗美容
[134 rows x 2 columns]
```

  注意：
   1.  证监会行业分类 2012 没有三级行业，若输入 source='zjh2012', level=3 则参数无效，返回空 dataframe


## #   stk_get_industry_constituents  - 查询行业成分股

  查询指定某个行业的成分股
   函数原型：


```
stk_get_industry_constituents(industry_code, date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     industry_code
  str
  行业代码
  Y
  无
  需要查询成分股的行业代码，可通过 stk_get_industry_category 获取, 查看 行业分类

   date
  str
  查询日期
  N
  ""
  查询行业成分股的指定日期，%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     industry_code
  str
  行业代码
  成分股的行业代码

   industry_name
  str
  行业名称
  成分股的行业名称

   symbol
  str
  成分股票代码
  exchange.sec_id

   sec_name
  str
  成分股名称
  symbol 对应的股票名称

   date_in
  str
  纳入日期
  成分股被纳入指定行业的日期，%Y-%m-%d 格式

   date_out
  str
  剔除日期
  成分股被剔除指定行业的日期，%Y-%m-%d 格式


   示例：


```
stk_get_industry_constituents(industry_code='A', date='2022-09-05')
```

  输出：


```
industry_code industry_name       symbol sec_name     date_in date_out
0             04            渔业  SZSE.000798     中水渔业  2012-12-31
1             01            农业  SHSE.600359     新农开发  2012-12-31
2             01            农业  SHSE.600371     万向德农  2012-12-31
3             01            农业  SHSE.600506     香梨股份  2012-12-31
4             02            林业  SZSE.000592     平潭发展  2012-12-31
5             01            农业  SHSE.600598      北大荒  2012-12-31
6             01            农业  SZSE.002041     登海种业  2012-12-31
7             01            农业  SHSE.600540     新赛股份  2012-12-31
8             01            农业  SHSE.600354     敦煌种业  2012-12-31
9             04            渔业  SHSE.600467      好当家  2012-12-31
10            03           畜牧业  SHSE.600975      新五丰  2012-12-31
11            04            渔业  SZSE.200992      中鲁B  2012-12-31
12            01            农业  SHSE.600313     农发种业  2015-07-20
13            04            渔业  SHSE.600097     开创国际  2012-12-31
14            01            农业  SHSE.600108     亚盛集团  2012-12-31
15            03           畜牧业  SHSE.600965     福成股份  2012-12-31
16            05    农、林、牧、渔服务业  SZSE.000711     京蓝科技  2016-12-31
17            05    农、林、牧、渔服务业  SZSE.000713     丰乐种业  2012-12-31
18            03           畜牧业  SZSE.000735      罗牛山  2012-12-31
19            02            林业  SZSE.000663     永安林业  2012-12-31
20            01            农业  SZSE.300189     神农科技  2012-12-31
21            04            渔业  SZSE.002069    ST獐子岛  2012-12-31
22            03           畜牧业  SZSE.002234     民和股份  2012-12-31
23            04            渔业  SZSE.002086     ST东洋  2012-12-31
24            01            农业  SHSE.601118     海南橡胶  2012-12-31
25            03           畜牧业  SZSE.002157     正邦科技  2021-09-30
26            03           畜牧业  SZSE.002299     圣农发展  2012-12-31
27            03           畜牧业  SZSE.002458     益生股份  2012-12-31
28            04            渔业  SZSE.300094     国联水产  2012-12-31
29            03           畜牧业  SZSE.300106     西部牧业  2012-12-31
30            02            林业  SZSE.002679     福建金森  2012-12-31
31            04            渔业  SHSE.600257     大湖股份  2012-12-31
32            01            农业  SZSE.000998     隆平高科  2012-12-31
33            01            农业  SZSE.300087     荃银高科  2012-12-31
34            03           畜牧业  SZSE.300313     ST天山  2019-06-30
35            04            渔业  SZSE.002696     百洋股份  2012-12-31
36            03           畜牧业  SZSE.002505     鹏都农牧  2012-12-31
37            03           畜牧业  SZSE.002714     牧原股份  2014-01-09
38            03           畜牧业  SZSE.002746     仙坛股份  2015-02-02
39            01            农业  SZSE.300511     雪榕生物  2016-04-14
40            01            农业  SZSE.002772     众兴菌业  2015-06-10
41            03           畜牧业  SZSE.300498     温氏股份  2015-10-29
42            03           畜牧业  SZSE.002982     湘佳股份  2020-04-03
43            01            农业  SZSE.300143     盈康生命  2012-12-31
44            03           畜牧业  SZSE.300761     立华股份  2019-01-22
45            03           畜牧业  SHSE.605296     神农集团  2021-04-20
46            03           畜牧业  SHSE.603477     巨星农牧  2020-09-30
47            03           畜牧业  SZSE.140006    牧原优01  2014-01-09
48            03           畜牧业  SZSE.001201     东瑞股份  2020-06-05
49            01            农业  SZSE.300970     华绿生物  2015-07-21
50            01            农业  SZSE.300972     万辰生物  2015-08-18
51            03           畜牧业  SZSE.300967     晓鸣股份  2014-10-30
52            03           畜牧业  SZSE.002124     天邦食品  2021-09-30
53            03           畜牧业  SZSE.002321     ST华英  2012-12-31
54            02            林业  SZSE.002200     ST交投  2012-12-31
55            02            林业  SHSE.600265     ST景谷  2012-12-31
```

  注意：
   1.  只能指定一个行业代码查询成分股。


## #   stk_get_symbol_industry  - 查询股票的所属行业

  查询指定股票所属的行业
   函数原型：


```
stk_get_symbol_industry(symbols, source="zjh2012", level=1, date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  多个代码可用 ，使用时参考 symbol  采用 str 格式时，多个标的代码必须用英文逗号分割如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例： ['SHSE.600008', 'SZSE.000002']

   source
  str
  行业来源
  N
  'zjh2012'
  'zjh2012'- 证监会行业分类 2012（默认）， 'sw2021'- 申万行业分类 2021, 查看 行业分类

   level
  int
  行业分级
  N
  1
  1 - 一级行业（默认），2 - 二级行业，3 - 三级行业

   date
  str
  查询日期
  N
  ""
  查询行业分类的指定日期，%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   sec_name
  str
  股票名称
  symbol 对应的股票名称

   industry_code
  str
  行业代码
  指定行业来源下，symbol 所属的行业代码

   industry_name
  str
  行业名称
  指定行业来源下，symbol 所属的行业名称


   示例：


```
stk_get_symbol_industry(symbols='SHSE.600000, SZSE.000002', source="zjh2012", level=1, date="")
```

  输出：


```
symbol sec_name industry_code industry_name
0  SHSE.600000     浦发银行             J           金融业
1  SZSE.000002      万科A             K          房地产业
```

  注意：
   1.  证监会行业分类 2012 没有三级行业，若输入 source='zjh2012', level=3 则参数无效，返回空 dataframe


## #   stk_get_sector_category  - 查询板块分类

  查询指定类型的板块列表
   函数原型：


```
stk_get_sector_category(sector_type)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     sector_type
  str
  板块类型
  Y
  无
  只能选择一种类型，可选择 1001:市场类 1002:地域类 1003:概念类, 查看 板块分类


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     sector_code
  str
  板块代码
  所选板块类型的板块代码

   sector_name
  str
  板块名称
  所选板块类型的板块名称


   示例：


```
stk_get_sector_category(sector_type='1003')
```

  输出：


```
sector_code      sector_name
0        007001          军工
1        007003         煤化工
2        007004         新能源
3        007005        节能环保
4        007007         AB股
..          ...         ...
420      007499        存储芯片
421      007500        液冷概念
422      007501         中特估
423      007502        央企改革
424      007503        混合现实
[425 rows x 2 columns]
```

## #   stk_get_sector_constituents  - 查询板块成分股

  查询指定某个板块的成分股
   函数原型：


```
stk_get_sector_constituents(sector_code)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     sector_code
  str
  板块代码
  Y
  无
  需要查询成分股的板块代码，可通过 stk_get_sector_category 获取, 查看 板块分类


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     sector_code
  str
  板块代码
  查询的板块代码

   sector_name
  str
  板块名称
  查询的板块代码对应的板块名称

   symbol
  str
  成分股票代码
  exchange.sec_id

   sec_name
  str
  成分股票名称
  symbol 对应的股票名称


   示例：


```
stk_get_sector_constituents(sector_code='007089')
```

  输出：


```
sector_code sector_name       symbol sec_name
0       007089        央视50  SHSE.600196     复星医药
1       007089        央视50  SZSE.000848     承德露露
2       007089        央视50  SZSE.000049     德赛电池
3       007089        央视50  SHSE.600887     伊利股份
4       007089        央视50  SZSE.300003     乐普医疗
5       007089        央视50  SZSE.300024      机器人
6       007089        央视50  SZSE.002008     大族激光
7       007089        央视50  SZSE.000895     双汇发展
8       007089        央视50  SZSE.002410      广联达
9       007089        央视50  SZSE.300183     东软载波
10      007089        央视50  SHSE.601166     兴业银行
11      007089        央视50  SHSE.600563     法拉电子
12      007089        央视50  SZSE.000423     东阿阿胶
13      007089        央视50  SZSE.300244     迪安诊断
14      007089        央视50  SHSE.600522     中天科技
15      007089        央视50  SZSE.300124     汇川技术
16      007089        央视50  SHSE.600398     海澜之家
17      007089        央视50  SHSE.601607     上海医药
18      007089        央视50  SZSE.002294      信立泰
19      007089        央视50  SZSE.300136     信维通信
20      007089        央视50  SHSE.600585     海螺水泥
21      007089        央视50  SHSE.600276     恒瑞医药
22      007089        央视50  SHSE.600036     招商银行
23      007089        央视50  SZSE.002120     韵达股份
24      007089        央视50  SHSE.603986     兆易创新
25      007089        央视50  SHSE.603160     汇顶科技
26      007089        央视50  SZSE.000651     格力电器
27      007089        央视50  SHSE.601088     中国神华
28      007089        央视50  SHSE.601939     建设银行
29      007089        央视50  SHSE.600016     民生银行
30      007089        央视50  SZSE.000538     云南白药
31      007089        央视50  SZSE.000002      万科A
32      007089        央视50  SHSE.601601     中国太保
33      007089        央视50  SHSE.601318     中国平安
34      007089        央视50  SHSE.600535      天士力
35      007089        央视50  SHSE.601398     工商银行
36      007089        央视50  SHSE.601988     中国银行
37      007089        央视50  SHSE.600085      同仁堂
38      007089        央视50  SHSE.600660     福耀玻璃
39      007089        央视50  SHSE.600519     贵州茅台
40      007089        央视50  SHSE.600690     海尔智家
41      007089        央视50  SZSE.002415     海康威视
42      007089        央视50  SZSE.002230     科大讯飞
43      007089        央视50  SZSE.000596     古井贡酒
44      007089        央视50  SZSE.300070      碧水源
45      007089        央视50  SZSE.002038     双鹭药业
46      007089        央视50  SHSE.600104     上汽集团
47      007089        央视50  SHSE.600600     青岛啤酒
48      007089        央视50  SZSE.000333     美的集团
49      007089        央视50  SZSE.000726      鲁泰A
```

  注意：
   1.  只能指定一个板块代码查询成分股。


## #   stk_get_symbol_sector  - 查询股票的所属板块

  查询指定股票所属的板块
   函数原型：


```
stk_get_symbol_sector(symbols, sector_type)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  多个代码可用 ，使用时参考 symbol  采用 str 格式时，多个标的代码必须用英文逗号分割如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例： ['SHSE.600008', 'SZSE.000002']

   sector_type
  str
  板块类型
  Y
  无
  只能选择一种类型，可选择 1001:市场类 1002:地域类 1003:概念类


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   sec_name
  str
  股票名称
  symbol 对应的股票名称

   sector_code
  str
  板块代码
  指定板块类型下，symbol 所属的板块代码

   sector_name
  str
  板块名称
  指定板块类型下，symbol 所属的板块名称


   示例：


```
stk_get_symbol_sector(symbols='SHSE.600008,SZSE.000002', sector_type='1002')
```

  输出：


```
symbol sec_name   sector_code sector_name
0  SHSE.600008     首创环保  006002001001         北京市
1  SZSE.000002      万科A  006006001015         深圳市
```

## #   stk_get_dividend  - 查询股票分红送股信息

  查询指定股票在一段时间内的分红送股信息
   函数原型：


```
stk_get_dividend(symbol, start_date, end_date)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  标的代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   start_date
  str
  开始时间
  Y
  无
  必填，开始时间日期（除权除息日），%Y-%m-%d 格式

   end_date
  str
  结束时间
  Y
  无
  必填，结束时间日期（除权除息日），%Y-%m-%d 格式


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   scheme_type
  str
  分配方案
  现金分红，送股，转增

   pub_date
  str
  公告日
  %Y-%m-%d 格式

   equity_reg_date
  str
  股权登记日
  %Y-%m-%d 格式

   ex_date
  str
  除权除息日
  %Y-%m-%d 格式

   cash_pay_date
  str
  现金红利发放日
  %Y-%m-%d 格式

   share_acct_date
  str
  送转股到账日
  %Y-%m-%d 格式

   share_lst_date
  str
  新增股份上市流通日
  红股上市日或送（转增）股份上市交易日, %Y-%m-%d 格式

   cash_af_tax
  float
  税后红利
  单位：元/10 股

   cash_bf_tax
  float
  税前红利
  单位：元/10 股

   bonus_ratio
  float
  送股比例
  10:X

   convert_ratio
  float
  转增比例
  10:X

   base_date
  str
  股本基准日
  %Y-%m-%d 格式

   base_share
  float
  股本基数
  基准股本

   dvd_target
  str
  分派对象
  如：全体股东，流通股股东，非流通股股东，A股股东，A股流通股股东，A股限售股股东


   示例：


```
stk_get_dividend(symbol='SHSE.600000', start_date='2022-07-01', end_date='2022-07-31')
```

  输出：


```
symbol scheme_type    pub_date equity_reg_date     ex_date cash_pay_date share_acct_date share_lst_date  cash_af_tax  cash_bf_tax  bonus_ratio  convert_ratio   base_date  base_share
0  SHSE.600000        现金分红  2022-07-13      2022-07-20  2022-07-21    2022-07-21            None           None         3.69          4.1          0.0            0.0  2022-07-20  2.9352e+10
```

  注意：
   1.  当 start_date 小于或等于 end_date  时取指定时间段的数据,当 start_date > end_date 时返回报错.


## #   stk_get_ration  - 查询股票配股信息

  查询指定股票在一段时间内的配股信息
   函数原型：


```
stk_get_ration(symbol, start_date, end_date)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  标的代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   start_date
  str
  开始时间
  Y
  无
  必填, 开始时间日期（除权除息日），%Y-%m-%d 格式

   end_date
  str
  结束时间
  Y
  无
  必填, 结束时间日期（除权除息日），%Y-%m-%d 格式


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   pub_date
  str
  公告日
  %Y-%m-%d 格式

   equity_reg_date
  str
  股权登记日
  %Y-%m-%d 格式

   ex_date
  str
  除权除息日
  %Y-%m-%d 格式

   ration_ratio
  float
  配股比例
  10:X

   ration_price
  float
  配股价格
  单位：元


   示例：


```
stk_get_ration(symbol='SZSE.000728', start_date="2005-01-01", end_date="2022-09-30")
```

  输出：


```
symbol    pub_date equity_reg_date     ex_date  ration_ratio  ration_price
0  SZSE.000728  2020-10-09      2020-10-13  2020-10-22           3.0          5.44
```

  注意：
   1.  当 start_date  小于或等于  end_date  时取指定时间段的数据,当 start_date  >  end_date 时返回报错.


## #   stk_get_adj_factor  - 查询股票的复权因子

  查询某只股票在一段时间内的复权因子
   函数原型：


```
stk_get_adj_factor(symbol, start_date="", end_date="", base_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  标的代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间交易日期，%Y-%m-%d 格式，默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间交易日期，%Y-%m-%d 格式，默认 "" 表示最新时间

   base_date
  str
  复权基准日
  N
  ""
  前复权的基准日，%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     trade_date
  str
  交易日期
  开始时间至结束时间的交易日期

   adj_factor_bwd
  float
  当日后复权因子
  T 日后复权因子=T-1 日的收盘价/T 日昨收价

   adj_factor_bwd_acc
  float
  当日累计后复权因子
  T 日累计后复权因子=T 日后复权因子 ×T-1 日累计后复权因子, ... 第一个累计后复权因子=第一个后复权因子

   adj_factor_fwd
  float
  当日前复权因子
  T 日前复权因子=T 日累计后复权因子/复权基准日累计后复权因子

   adj_factor_fwd_acc
  float
  当日累计前复权因子
  T 日累计前复权因子=1/T 日后复权因子, T-1 日累计前复权因子=1/(T 日后复权因子 ×T-1 日后复权因子), ... 第一个累计前复权因子=1/最新累计后复权因子


   示例：


```
stk_get_adj_factor(symbol='SZSE.000651', start_date="2015-01-01", end_date="2022-09-01", base_date="")
```

  输出：


```
trade_date  adj_factor_bwd  adj_factor_bwd_acc  adj_factor_fwd  adj_factor_fwd_acc
0     2015-01-05             1.0             49.1697          0.3315              3.0169
1     2015-01-06             1.0             49.1697          0.3315              3.0169
2     2015-01-07             1.0             49.1697          0.3315              3.0169
3     2015-01-08             1.0             49.1697          0.3315              3.0169
4     2015-01-09             1.0             49.1697          0.3315              3.0169
...          ...             ...                 ...             ...                 ...
1862  2022-08-26             1.0            148.3407          1.0000              1.0000
1863  2022-08-29             1.0            148.3407          1.0000              1.0000
1864  2022-08-30             1.0            148.3407          1.0000              1.0000
1865  2022-08-31             1.0            148.3407          1.0000              1.0000
1866  2022-09-01             1.0            148.3407          1.0000              1.0000
[1867 rows x 5 columns]
```

  注意：
   1.  T+1 日复权因子会二次更新，分别约在 T 日 19:00 和 T+1 日 19:00 更新
   2.  复权价格计算：
 T日后复权价格 = T日不复权价格 * T日累计后复权因子   T日前复权价格 = T日不复权价格 * T日前复权因子
   3.  上市首日后复权因子和累计后复权因子为 1，最近一次除权除息日后的前复权因子为 1
   4.  前复权基准日 base_date  应不早于设定的结束日期 end_date ，不晚于最新交易日。若设定的基准日早于 end_date 则等同于 end_date ，若设定的基准日晚于最新交易日则等同于最新交易日。
   5.  当 start_date 小于或等于  end_date  时取指定时间段的数据,当 start_date  >  end_date 时返回报错.


## #   stk_get_shareholder_num  - 查询股东户数

  查询上市公司股东总数，A 股股东、B 股股东、H 股股东总数
   函数原型：


```
stk_get_shareholder_num(symbol, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（公告日期），%Y-%m-%d 格式，默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（公告日期），%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   sec_name
  str
  股票名称
  symbol 对应的股票名称

   pub_date
  str
  公告日期


   expiry_date
  str
  截止日期


   total_share
  int
  股东总数


   total_share_a
  int
  A 股股东总数


   total_share_b
  int
  流通 B 股股东总数


   total_share_h
  int
  流通 H 股股东总数


   other_share
  int
  其他股东户数


   total_share_pfd
  int
  优先股股东总数（表决权恢复）


   total_share_mgn
  int
  股东户数（含融资融券）
  合并普通账户和融资融券信用账户后的股东总户数

   total_share_no_mgn
  int
  股东户数（不含融资融券）
  普通账户的股东总户数


   示例：


```
stk_get_shareholder_num(symbol='SZSE.002594', start_date="2022-01-01", end_date="2022-08-01")
```

  输出：


```
symbol sec_name    pub_date expiry_date  total_share  total_share_a  total_share_b  total_share_h  other_share  total_share_pfd  total_share_mgn  total_share_no_mgn
0  SZSE.002594      比亚迪  2022-03-30  2021-12-31       357227         357109              0            118            0                0                0                   0
1  SZSE.002594      比亚迪  2022-03-30  2022-02-28       392631         392511              0            120            0                0                0                   0
2  SZSE.002594      比亚迪  2022-04-28  2022-03-31       405607         405486              0            121            0                0                0                   0
```

  注意：
  当 start_date == end_date 时，取离 end_date 最近公告日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   stk_get_top_shareholder  - 查询十大股东

  查询上市公司前十大股东的持股情况，包括持股数量，所持股份性质等
   函数原型：


```
stk_get_top_shareholder(symbol, start_date="", end_date="", tradable_holder=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（公告日期），%Y-%m-%d 格式，默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（公告日期），%Y-%m-%d 格式，默认 "" 表示最新时间

   tradable_holder
  bool
  是否流通股东
  N
  False
  False-十大股东（默认）、True-十大流通股东 默认 False 表示十大股东


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   sec_name
  str
  股票名称
  symbol 对应的股票名称

   pub_date
  str
  公告日期


   expiry_date
  str
  截止日期


   holder_name
  str
  股东名称


   holder_rank
  int
  股东序号
  名次

   holder_type
  str
  股东类型


   holder_attr
  str
  股东性质
  十大流通股东不返回

   share_type
  str
  股份类型
  股份性质

   share_num
  float
  持股数量
  持有数量（股）

   share_ratio1
  float
  持股比例 1
  持股占总股本比例（%）

   share_ratio2
  float
  持股比例 2
  持股占已上市流通股比例（%），仅十大流通股东才返回

   share_pledge
  float
  质押股份数量
  股权质押涉及股数（股）

   share_freeze
  float
  冻结股份数量
  股权冻结涉及股数（股）


   示例：


```
stk_get_top_shareholder(symbol='SHSE.603906', start_date="2022-06-01", end_date="2022-08-01", tradable_holder=False)
```

  输出：


```
symbol sec_name    pub_date expiry_date                                       holder_name  holder_rank holder_type holder_attr share_type   share_num  share_ratio1  share_ratio2  share_pledge  share_freeze
0   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                       上海歆享资产管理有限公司-歆享盈新1号私募证券投资基金           10        投资公司       境内法人股       流通A股  3.1941e+06          0.66           0.0           0.0           0.0
1   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                       上海迎水投资管理有限公司-迎水日新9号私募证券投资基金            9        投资公司       境内法人股       流通A股  3.2252e+06          0.67           0.0           0.0           0.0
2   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                中国工商银行股份有限公司-南方卓越优选3个月持有期混合型证券投资基金            5      证券投资基金       境内法人股       流通A股  4.9513e+06          1.03           0.0           0.0           0.0
3   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                     中国工商银行股份有限公司-申万菱信新经济混合型证券投资基金            7      证券投资基金       境内法人股       流通A股  3.7343e+06          0.77           0.0           0.0           0.0
4   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                    中国工商银行股份有限公司-财通资管价值成长混合型证券投资基金            3      证券投资基金       境内法人股       流通A股  8.1342e+06          1.69           0.0           0.0           0.0
5   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10               中国工商银行股份有限公司-财通资管均衡价值一年持有期混合型证券投资基金            8      证券投资基金       境内法人股       流通A股  3.6870e+06          0.76           0.0           0.0           0.0
6   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10     平安基金-中国平安人寿保险股份有限公司-平安人寿-平安基金权益委托投资1号单一资产管理计划            4    基金资产管理计划       境内法人股       流通A股  5.6035e+06          1.16           0.0           0.0           0.0
7   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                                    建投嘉驰(上海)投资有限公司            6        投资公司         国有股       流通A股  4.4512e+06          0.92           0.0           0.0           0.0
8   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                                               朱香兰            2          个人        自然人股       流通A股  2.3619e+07          4.90           0.0           0.0           0.0
9   SHSE.603906     龙蟠科技  2022-06-18  2022-06-10                                               石俊峰            1          个人        自然人股       流通A股  2.1266e+08         44.11           0.0           0.0           0.0
10  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16          JPMORGAN CHASE BANK,NATIONAL ASSOCIATION            8        QFII       境外法人股       流通A股  5.5692e+06          0.99           0.0           0.0           0.0
11  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16                中国工商银行股份有限公司-南方卓越优选3个月持有期混合型证券投资基金           10      证券投资基金       境内法人股       流通A股  4.9513e+06          0.88           0.0           0.0           0.0
12  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16                    中国工商银行股份有限公司-财通资管价值成长混合型证券投资基金            4      证券投资基金       境内法人股       流通A股  1.1999e+07          2.12           0.0           0.0           0.0
13  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16               中国工商银行股份有限公司-财通资管均衡价值一年持有期混合型证券投资基金            9      证券投资基金       境内法人股       流通A股  5.5354e+06          0.98           0.0           0.0           0.0
14  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16     平安基金-中国平安人寿保险股份有限公司-平安人寿-平安基金权益委托投资1号单一资产管理计划            7    基金资产管理计划       境内法人股       流通A股  5.6035e+06          0.99           0.0           0.0           0.0
15  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16           成都丝路重组股权投资基金管理有限公司-成都振兴嘉业贰号股权投资中心(有限合伙)            5        投资公司       境内法人股       流通A股  5.6582e+06          1.00           0.0           0.0           0.0
16  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16                                               朱香兰            2          个人        自然人股       流通A股  2.3619e+07          4.18           0.0           0.0           0.0
17  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16  汇添富基金-中信银行理财之乐赢成长周期一年B款理财产品-汇添富中信添富牛170号单一资产管理计划            3    基金资产管理计划       境内法人股       流通A股  1.3203e+07          2.34           0.0           0.0           0.0
18  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16                                  济南江山投资合伙企业(有限合伙)            5        投资公司       境内法人股       流通A股  5.6582e+06          1.00           0.0           0.0           0.0
19  SHSE.603906     龙蟠科技  2022-06-18  2022-06-16                                               石俊峰            1          个人        自然人股       流通A股  2.1266e+08         37.63           0.0           0.0           0.0
```

  注意：
  当 start_date == end_date 时，取离 end_date 最近公告日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   stk_get_share_change  - 查询股本变动

  查询上市公司的一段时间内公告的股本变动情况
   函数原型：


```
stk_get_share_change(symbol, start_date="", end_date="")
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   start_date
  str
  开始时间
  N
  ""
  开始时间日期（发布日期），%Y-%m-%d 格式，默认 "" 表示最新时间

   end_date
  str
  结束时间
  N
  ""
  结束时间日期（发布日期），%Y-%m-%d 格式，默认 "" 表示最新时间


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   company_name
  str
  公司名称
  symbol 对应的公司名称

   pub_date
  str
  发布日期


   chg_date
  str
  股本变动日期


   chg_reason
  str
  股本变动原因


   chg_event
  str
  股本变动事件


   share_total
  float
  总股本
  未流通股份+已流通股份，单位：股

   share_total_nlf
  float
  未流通股份
  单位：股

   share_prom
  float
  一、发起人股份
  国有发起人股 + 发起社会法人股 + 其他发起人股份，单位：股

   share_prom_state
  float
  1.国有发起人股
  国家持股+国有法人股，单位：股

   share_state
  float
  （1）国家股
  单位：股

   share_state_lp
  float
  （2）国有法人股
  单位：股

   share_prom_soc
  float
  2.发起社会法人股
  境内社会法人股+境外法人股，单位：股

   share_dc_lp
  float
  （1）境内社会法人股
  单位：股

   share_os_lp
  float
  （2）境外法人股
  单位：股

   share_prom_other
  float
  3.其他发起人股份
  单位：股

   share_rs
  float
  二、募集人股份
  募集国家股+募集境内法人股+募集境外法人股，单位：股

   share_rs_state
  float
  1.募集国家股
  单位：股

   share_rs_dc_lp
  float
  2.募集境内法人股
  募集境内国有法人股+募集境内社会法人股，单位：股

   share_rs_state_lp
  float
  （1）募集境内国有法人股
  单位：股

   share_rs_soc_lp
  float
  （2）募集境内社会法人股
  单位：股

   share_rs_os_lp
  float
  3.募集境外法人股
  单位：股

   share_emp_nlf
  float
  三、内部职工股
  单位：股

   share_pfd_nlf
  float
  四、优先股
  单位：股

   share_oth_nlf
  float
  五、其他未流通股份
  单位：股

   share_circ
  float
  流通股份
  单位：股，无限售条件股份+有限售条件股份，实际流通股份可用share_ttl_unl（无限售条件股份）

   share_ttl_unl
  float
  无限售条件股份
  人民币普通股（A 股）+ 境内上市外资股（B 股）+ 境外上市外资股（H 股）+ 其他已流通股份，单位：股

   share_a_unl
  float
  1.人民币普通股（A 股）
  单位：股

   share_b_unl
  float
  2.境内上市外资股（B 股）
  单位：股

   share_h_unl
  float
  3.境外上市外资股（H 股）
  单位：股

   share_oth_unl
  float
  4.其他已流通股份
  单位：股

   share_ttl_ltd
  float
  有限售条件股份
  单位：股

   share_gen_ltd
  float
  一、一般有限售条件股份
  限售国家持股+ 限售国有法人持股+ 限售其他内资持股+ 限售外资持股+ 锁定股份+ 高管持股，单位：股

   share_state_ltd
  float
  1.限售国家持股
  单位：股

   share_state_lp_ltd
  float
  2.限售国有法人持股
  单位：股

   share_oth_dc_ltd
  float
  3.限售其他内资持股
  限售境内非国有法人持股+限售境内自然人持股，单位：股

   share_nst_dc_lp_ltd
  float
  （1）限售境内非国有法人持股
  单位：股

   share_dc_np_ltd
  float
  （2）限售境内自然人持股
  单位：股

   share_forn_ltd
  float
  4.限售外资持股
  限售境外法人持股+限售境外自然人持股，单位：股

   share_os_lp_ltd
  float
  （1）限售境外法人持股
  单位：股

   share_os_np_ltd
  float
  （2）限售境外自然人持股
  单位：股

   share_lk_ltd
  float
  5.锁定股份
  单位：股

   share_gm_ltd
  float
  6.高管持股(原始披露)
  单位：股

   share_plc_lp_ltd
  float
  二、配售法人持股
  战略投资者配售股份+一般法人投资者配售+ 证券投资基金配售股份，单位：股

   share_plc_si_ltd
  float
  1.战略投资者配售股份
  单位：股

   share_plc_lp_gen_ltd
  float
  2.一般法人投资者配售股份
  单位：股

   share_plc_fnd_ltd
  float
  3.证券投资基金配售股份
  单位：股

   share_a_ltd
  float
  限售流通 A 股
  单位：股

   share_b_ltd
  float
  限售流通 B 股
  单位：股

   share_h_ltd
  float
  限售流通 H 股
  单位：股

   share_oth_ltd
  float
  其他限售股份
  单位：股

   share_list_date
  str
  变动股份上市日
  %Y-%m-%d 格式


   示例：


```
stk_get_share_change(symbol='SHSE.605090', start_date="2020-01-01", end_date="2022-10-01")
```

  输出：


```
symbol  company_name    pub_date    chg_date chg_reason chg_event  share_total  share_total_nlf  share_prom  share_prom_state  share_state  share_state_lp  share_prom_soc  share_dc_lp  share_os_lp  share_prom_other  share_rs  share_rs_state  share_rs_dc_lp  share_rs_state_lp  share_rs_soc_lp  share_rs_os_lp  share_emp_nlf  share_pfd_nlf  share_oth_nlf  share_circ  share_ttl_unl  share_a_unl  share_b_unl  share_h_unl  share_oth_unl  share_ttl_ltd  share_gen_ltd  share_state_ltd  share_state_lp_ltd  share_oth_dc_ltd  share_nst_dc_lp_ltd  share_dc_np_ltd  share_forn_ltd  share_os_lp_ltd  share_os_np_ltd  share_lk_ltd  share_gm_ltd  share_plc_lp_ltd  share_plc_si_ltd  share_plc_lp_gen_ltd  share_plc_fnd_ltd  share_a_ltd  share_b_ltd  share_h_ltd  share_oth_ltd share_list_date
0  SHSE.605090  江西九丰能源股份有限公司  2021-05-24  2021-05-13     首发A股上市      发行融资   4.4297e+08              0.0         0.0               0.0          0.0             0.0             0.0          0.0          0.0               0.0       0.0             0.0             0.0                0.0              0.0             0.0            0.0            0.0            0.0  4.4297e+08     8.2970e+07   8.2970e+07          0.0          0.0            0.0     3.6000e+08     3.6000e+08              0.0                 0.0        3.1967e+08           2.1591e+08       1.0376e+08      4.0330e+07       4.0330e+07              0.0           0.0    1.0376e+08               0.0               0.0                   0.0                0.0   3.6000e+08          0.0          0.0            0.0      2021-05-25
1  SHSE.605090  江西九丰能源股份有限公司  2022-05-12  2022-05-18      转增股上市      分红派息   6.2016e+08              0.0         0.0               0.0          0.0             0.0             0.0          0.0          0.0               0.0       0.0             0.0             0.0                0.0              0.0             0.0            0.0            0.0            0.0  6.2016e+08     1.1616e+08   1.1616e+08          0.0          0.0            0.0     5.0400e+08     5.0400e+08              0.0                 0.0        4.4754e+08           3.0228e+08       1.4526e+08      5.6462e+07       5.6462e+07              0.0           0.0    0.0000e+00               0.0               0.0                   0.0                0.0   5.0400e+08          0.0          0.0            0.0      2022-05-19
2  SHSE.605090  江西九丰能源股份有限公司  2022-05-25  2022-05-30   首发限售股份上市     限售股解禁   6.2016e+08              0.0         0.0               0.0          0.0             0.0             0.0          0.0          0.0               0.0       0.0             0.0             0.0                0.0              0.0             0.0            0.0            0.0            0.0  6.2016e+08     2.5281e+08   2.5281e+08          0.0          0.0            0.0     3.6735e+08     3.6735e+08              0.0                 0.0        3.6735e+08           2.2209e+08       1.4526e+08      0.0000e+00       0.0000e+00              0.0           0.0    0.0000e+00               0.0               0.0                   0.0                0.0   3.6735e+08          0.0          0.0            0.0      2022-05-30
```

  注意：
  当 start_date == end_date 时，取离 end_date 最近发布日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。


## #   stk_abnor_change_stocks  - 查询龙虎榜股票数据

  查询指定时间段龙虎榜股票数据
   gm SDK  3.0.163 版本新增
   函数原型：


```
stk_abnor_change_stocks(symbols=None, change_types=None, trade_date=None, fields=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  N
  None
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如：'SHSE.600008,SZSE.000002'; 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002'], 默认None表示所有标的。

   change_types
  str or list
  异动类型
  N
  None
  输入异动类型，可输入多个. 采用 str 格式时，多个异动类型必须用英文逗号分割，如：'106,107'; 采用 list 格式时，多个异动类型示例：['106','107']； 默认None表示所有异动类型。 龙虎榜异动类型列表

   trade_date
  str or datetime.date
  交易日期
  N
  None
  交易日期，支持str格式（%Y-%m-%d 格式）和 datetime.date 格式，默认None表示最新交易日期。

   fields
  str
  返回字段
  N
  None
  指定需要返回的字段，如有多个字段，中间用英文逗号分隔，默认 None 返回所有字段。

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict],列表每项的dict的key值为参数指定的 fields 。


   返回值：
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   trade_date
  str
  交易日期


   change_type
  str
  异动类型
  交易所披露的公开信息及异常波动信息的原因类型, 龙虎榜异动类型列表

   change_type_name
  str
  异动类型说明
  交易所披露的公开信息及异常波动信息的原因的中文说明

   abnor_start_date
  str
  异动开始日期
  股票异动开始的日期，仅部分异动类型才有

   abnor_end_date
  str
  异动结束日期
  股票异动结束的日期，仅部分异动类型才有

   close
  float
  收盘价
  股票的日频收盘价

   cum_volume
  int
  累计成交量
  股票的累计成交量，当存在具体异动开始/结束日期时，累计成交量为区间成交量；当不存在具体异动开始/结束日期时，累计成交量为当日成交量

   cum_amount
  float
  累计成交额
  股票的累计成交额，当存在具体异动开始/结束日期时，累计成交额为区间成交额；当不存在具体异动开始/结束日期时，累计成交额为当日成交额

   prc_change_rate
  float
  涨跌幅%
  当日涨跌幅

   avg_turn_rate
  float
  日均换手率比值
  异动类型中，触发相应异动事件的日均换手率比值

   stat_value
  float
  统计值
  异动类型中，触发相应异动事件的统计值


   示例：


```
stk_abnor_change_stocks(symbols=None, change_types='106', trade_date=None, fields=None, df=False)
```

  输出：


```
[{'symbol': 'SZSE.000017', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '日涨幅偏离值达到7%的前5只证券', 'close': 12.77, 'cum_volume': 110996688, 'cum_amount': 1375429201.0, 'prc_change_rate': 9.9914, 'stat_value': 9.05},
 {'symbol': 'SZSE.001217', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '日涨幅偏离值达到7%的前5只证券', 'close': 16.68, 'cum_volume': 54707801, 'cum_amount': 798100880.0, 'prc_change_rate': 10.0264, 'stat_value': 9.05},
 {'symbol': 'SZSE.002230', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '日涨幅偏离值达到7%的前5只证券', 'close': 42.11, 'cum_volume': 105142255, 'cum_amount': 4299831646.0, 'prc_change_rate': 10.0052, 'stat_value': 9.05},
 {'symbol': 'SZSE.002517', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '日涨幅偏离值达到7%的前5只证券', 'close': 11.2, 'cum_volume': 134710030, 'cum_amount': 1488908194.0, 'prc_change_rate': 10.0196, 'stat_value': 9.05},
 {'symbol': 'SZSE.003027', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '日涨幅偏离值达到7%的前5只证券', 'close': 28.84, 'cum_volume': 26272266, 'cum_amount': 727342648.0, 'prc_change_rate': 9.9924, 'stat_value': 9.05},
 {'symbol': 'SHSE.600200', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券', 'close': 8.97, 'cum_volume': 5877996, 'cum_amount': 52725624.0, 'prc_change_rate': 10.0613, 'stat_value': 9.53},
 {'symbol': 'SHSE.600629', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券', 'close': 4.93, 'cum_volume': 25619361, 'cum_amount': 121095785.0, 'prc_change_rate': 10.0446, 'stat_value': 9.52},
 {'symbol': 'SHSE.600675', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券', 'close': 3.16, 'cum_volume': 37060390, 'cum_amount': 111530727.0, 'prc_change_rate': 10.1045, 'stat_value': 9.58},
 {'symbol': 'SHSE.600816', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券', 'close': 2.83, 'cum_volume': 21759618, 'cum_amount': 59379245.0, 'prc_change_rate': 10.1167, 'stat_value': 9.59},
 {'symbol': 'SHSE.600836', 'trade_date': '2024-01-23', 'change_type': '106', 'change_type_name': '有价格涨跌幅限制的日收盘价格涨幅偏离值达到7%的前五只证券', 'close': 3.81, 'cum_volume': 21817595, 'cum_amount': 78789358.0, 'prc_change_rate': 10.1156, 'stat_value': 9.59}]
```

  注意：
   1.  数据日频更新，在交易日约20点更新当日数据。如果当前交易日数据尚未更新，调用时不指定trade_date会返回前一交易日的数据，调用时指定trade_date为当前交易日会返回空。
   2.  trade_date输入非交易日，会返回空。


## #   stk_abnor_change_detail  - 查询龙虎榜营业部数据

  查询指定时间段龙虎榜营业数据
   gm SDK  3.0.163 版本新增
   函数原型：


```
stk_abnor_change_detail(symbols=None, change_types=None, trade_date=None, fields=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  N
  None
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如：'SHSE.600008,SZSE.000002'; 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002'], 默认None表示所有标的。

   change_types
  str or list
  异动类型
  N
  None
  输入异动类型，可输入多个. 采用 str 格式时，多个异动类型必须用英文逗号分割，如：'106,107'; 采用 list 格式时，多个异动类型示例：['106','107']； 默认None表示所有异动类型。 龙虎榜异动类型列表

   trade_date
  str or datetime.date
  交易日期
  N
  None
  交易日期，支持str格式（%Y-%m-%d 格式）和 datetime.date 格式，默认None表示最新交易日期。

   fields
  str
  返回字段
  N
  None
  指定需要返回的字段，如有多个字段，中间用英文逗号分隔，默认 None 返回所有字段。

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict],列表每项的dict的key值为参数指定的 fields 。


   返回值：
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  exchange.sec_id

   trade_date
  str
  交易日期


   change_type
  str
  异动类型
  交易所披露的公开信息及异常波动信息的原因类型, 龙虎榜异动类型列表

   side
  int
  交易方向
  0-买入 1-卖出

   sales_dept
  str
  营业部名称


   buy_amount
  float
  买入金额


   sell_amount
  float
  卖出金额


   rank
  int
  排名


   stat_days
  str
  统计天数



   示例：


```
stk_abnor_change_detail(symbols=['SZSE.300799'], change_types=None, trade_date='2024-01-23', fields=None, df=False)
```

  输出：


```
[{'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨东环路第一证券营业部', 'buy_amount': 14564894.0, 'sell_amount': 7558746.0, 'rank': 1, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨团结路第二证券营业部', 'buy_amount': 9851257.0, 'sell_amount': 7961995.0, 'rank': 2, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨东环路第二证券营业部', 'buy_amount': 9168211.0, 'sell_amount': 10625788.4, 'rank': 3, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨金融城南环路证券营业部', 'buy_amount': 8130605.0, 'sell_amount': 4825320.0, 'rank': 4, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨团结路第一证券营业部', 'buy_amount': 7874940.0, 'sell_amount': 7103053.0, 'rank': 5, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨东环路第二证券营业部', 'buy_amount': 9168211.0, 'sell_amount': 10625788.4, 'rank': 1, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '华泰证券股份有限公司杭州求是路证券营业部', 'buy_amount': 86904.0, 'sell_amount': 8832233.0, 'rank': 2, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨团结路第二证券营业部', 'buy_amount': 9851257.0, 'sell_amount': 7961995.0, 'rank': 3, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨东环路第一证券营业部', 'buy_amount': 14564894.0, 'sell_amount': 7558746.0, 'rank': 4, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨团结路第一证券营业部', 'buy_amount': 7874940.0, 'sell_amount': 7103053.0, 'rank': 5, 'change_type': '149'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨东环路第一证券营业部', 'buy_amount': 20244889.0, 'sell_amount': 13720238.0, 'rank': 1, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨东环路第二证券营业部', 'buy_amount': 16872156.0, 'sell_amount': 16700434.4, 'rank': 2, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨团结路第二证券营业部', 'buy_amount': 16274111.0, 'sell_amount': 13804247.0, 'rank': 3, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨团结路第一证券营业部', 'buy_amount': 13191129.0, 'sell_amount': 13434925.0, 'rank': 4, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'sales_dept': '东方财富证券股份有限公司拉萨金融城南环路证券营业部', 'buy_amount': 12009881.0, 'sell_amount': 7226749.0, 'rank': 5, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨东环路第二证券营业部', 'buy_amount': 16872156.0, 'sell_amount': 16700434.4, 'rank': 1, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨团结路第二证券营业部', 'buy_amount': 16274111.0, 'sell_amount': 13804247.0, 'rank': 2, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨东环路第一证券营业部', 'buy_amount': 20244889.0, 'sell_amount': 13720238.0, 'rank': 3, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨团结路第一证券营业部', 'buy_amount': 13191129.0, 'sell_amount': 13434925.0, 'rank': 4, 'stat_days': '2         ', 'change_type': '153'},
 {'symbol': 'SZSE.300799', 'trade_date': '2024-01-23', 'side': 1, 'sales_dept': '东方财富证券股份有限公司拉萨东城区江苏大道证券营业部', 'buy_amount': 8374957.0, 'sell_amount': 11359868.5, 'rank': 5, 'stat_days': '2         ', 'change_type': '153'}]
```

  注意：
   1.  数据日频更新，在交易日约20点更新当日数据。如果当前交易日数据尚未更新，调用时不指定trade_date会返回前一交易日的数据，调用时指定trade_date为当前交易日会返回空。
   2.  trade_date输入非交易日，会返回空。


## #   stk_quota_shszhk_infos  - 查询沪深港通额度数据

  查询指定时间段沪深港通额度数据
   gm SDK  3.0.163 版本新增
   交易所信息披露调整，2024.8.19起，NF-北向资金/SH-沪股通/SZ-深股通只返回结算汇率数据，历史数据不受影响，SHHK-沪港股通/SZHK-深港股通不受影响
   函数原型：


```
stk_quota_shszhk_infos(types=None, start_date=None, end_date=None, count=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     types
  str or list
  类型
  N
  None
  类型，可输入多个，采用 str 格式时，多个类型必须用英文逗号分割，如：'SZ,SHHK' 采用 list 格式时，多个标的代码示例：['SZ', 'SHHK']，类型包括：SH - 沪股通 ，SHHK - 沪港股通 ，SZ - 深股通 ，SZHK - 深港股通，NF - 北向资金（沪股通+深股通），默认 None 为全部北向资金。

   start_date
  str or datetime.date
  开始日期
  N
  None
  开始日期，支持str格式（%Y-%m-%d 格式）和 datetime.date 格式，默认None表示最新交易日期。

   end_date
  str or datetime.date
  结束日期
  N
  None
  结束日期，支持str格式（%Y-%m-%d 格式）和 datetime.date 格式，默认None表示最新交易日期。

   count
  int
  交易日数量
  N
  None
  数量(正整数)，不能与start_date同时使用，否则返回报错；与 end_date 同时使用时，表示获取 end_date 前 count 个交易日的数据(包含 end_date 当日)；默认为 None ，不使用该字段。

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict],列表每项的dict的key值为参数指定的 fields 。


   返回值：
     字段名
  类型
  中文名称
  说明

     type
  str
  类型
  SH - 沪股通 ，SHHK - 沪港股通 ，SZ - 深股通 ，SZHK - 深港股通，NF - 北向资金（沪股通+深股通）

   trade_date
  str
  最新交易日期


   daily_quota
  float
  每日额度上限(亿元)


   day_balance
  float
  当日余额(亿元)


   day_used
  float
  当日使用额度(亿元)


   day_used_rate
  float
  当日额度使用率(%)


   day_buy_amount
  float
  当日买入成交金额(亿元)


   day_buy_volume
  float
  当日买入成交笔数(笔)


   day_sell_amount
  float
  当日卖出成交金额(亿元)


   day_sell_volume
  float
  当日卖出成交笔数(笔)


   day_net_amount
  float
  当日买卖成交净额(亿元)


   settle_exrate_buy
  float
  沪深港通结算汇率(买入)


   settle_exrate_sell
  float
  沪深港通结算汇率(卖出)



   示例：


```
stk_quota_shszhk_infos(types='SHHK', start_date=None, end_date='2024-01-23', count=1, df=False)
```

  输出：


```
[{'type': 'SHHK', 'trade_date': '2024-01-23', 'daily_quota': 420.0, 'day_balance': 433.3, 'day_used': -13.3, 'day_used_rate': -3.167, 'day_buy_amount': 63.4454, 'day_buy_volume': 179494.0, 'day_sell_amount': 86.4077, 'day_sell_volume': 216835.0, 'settle_exrate_buy': 0.9209, 'settle_exrate_sell': 0.9225, 'day_net_amount': -22.9623}]
```

  注意：
   1.  当 start_date == end_date 时，取离 end_date 最近公告日期的一条数据，
当 start_date < end_date 时，取指定时间段的数据，
当 start_date > end_date 时，返回报错。
   2.  count不能与start_date同时使用，否则返回报错；与 end_date 同时使用时，表示获取 end_date 前 count 个交易日的数据(包含 end_date 当日)；默认为 None ，不使用该字段。


## #   stk_hk_inst_holding_detail_info  - 查询沪深港通标的港股机构持股明细数据

  查询沪深港通标的港股机构持股明细数据
   gm SDK  3.0.163 版本新增
   交易所信息披露调整，数据最晚更新到2024.8.16，历史数据不受影响
   函数原型：


```
stk_hk_inst_holding_detail_info(symbols=None, trade_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str
  股票代码
  N
  None
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如：'SHSE.600008,SZSE.000002' 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002'] 默认None表示所有标的。

   trade_date
  str or datetime.date
  交易日期
  N
  None
  交易日期，支持str格式（%Y-%m-%d 格式）和 datetime.date 格式，默认None表示最新交易日期。

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict],列表每项的dict的key值为参数指定的 fields 。


   返回值：
     字段名
  类型
  中文名称
  说明

     trade_date
  str
  最新交易日期
  最新交易日期

   symbol
  str
  证券代码
  证券代码

   sec_name
  str
  证券简称
  证券简称

   participant_name
  str
  参与者名称
  参与者名称

   share_holding
  int
  持股量(股)
  持股量(股)

   shares_rate
  float
  占已发行股份(%)
  占已发行股份(%)


   示例：


```
stk_hk_inst_holding_detail_info(symbols='SHSE.600008', trade_date=None, df=False)
```

  输出：


```
[{'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': 'CREDIT SUISSE SECURITIES (HONG KONG) LTD', 'share_holding': 374905, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': 'J.P. MORGAN BROKING (HONG KONG) LTD', 'share_holding': 6445488, 'shares_rate': 0.08},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': 'JPMORGAN CHASE BANK, NATIONAL ASSOCIATION', 'share_holding': 19630045, 'shares_rate': 0.26},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': 'MLFE LTD', 'share_holding': 2134425, 'shares_rate': 0.02},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': 'MORGAN STANLEY HONG KONG SECURITIES LTD', 'share_holding': 2962125, 'shares_rate': 0.04},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': 'Societe Generale', 'share_holding': 176637, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': 'UBS SECURITIES HONG KONG LTD', 'share_holding': 2238651, 'shares_rate': 0.03},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '上银证券有限公司', 'share_holding': 132000, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '东亚证券有限公司', 'share_holding': 7000, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '中信证券经纪(香港)有限公司', 'share_holding': 22900, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '中信里昂证券有限公司', 'share_holding': 158790, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '中国国际金融香港证券有限公司', 'share_holding': 821082, 'shares_rate': 0.01},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '中国建设银行(亚洲)股份有限公司', 'share_holding': 10600, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '中国银行(香港)有限公司', 'share_holding': 219800, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '中银国际证券有限公司', 'share_holding': 49824935, 'shares_rate': 0.67},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '元大证券(香港)有限公司', 'share_holding': 60000, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '创兴证券有限公司', 'share_holding': 13000, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '华盛资本证券有限公司', 'share_holding': 27800, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '国信证券(香港)经纪有限公司', 'share_holding': 400, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '国泰君安证券(香港)有限公司', 'share_holding': 280600, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '大华继显(香港)有限公司', 'share_holding': 141800, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '宝生证券有限公司', 'share_holding': 655900, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '富途证券国际(香港)有限公司', 'share_holding': 77300, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '广发证券(香港)经纪有限公司', 'share_holding': 14000, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '恒生证券有限公司', 'share_holding': 179700, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '永丰金证券(亚洲)有限公司', 'share_holding': 52000, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '法国巴黎银行', 'share_holding': 4579831, 'shares_rate': 0.06},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '渣打银行(香港)有限公司', 'share_holding': 13222494, 'shares_rate': 0.18},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '盈透证券香港有限公司', 'share_holding': 47930, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '耀才证券国际(香港)有限公司', 'share_holding': 3000, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '花旗银行', 'share_holding': 11468541, 'shares_rate': 0.15},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '辉立证券(香港)有限公司', 'share_holding': 337500, 'shares_rate': 0.0},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '香港上海汇丰银行有限公司', 'share_holding': 10059735, 'shares_rate': 0.13},
 {'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'participant_name': '高盛(亚洲)证券有限公司', 'share_holding': 5938226, 'shares_rate': 0.08}]
```

  注意：
   1.  数据日频更新，在交易日约20点更新当日数据。如果当前交易日数据尚未更新，调用时不指定trade_date会返回前一交易日的数据，调用时指定trade_date为当前交易日会返回空。
   2.  trade_date输入非交易日，会返回空。


## #   stk_hk_inst_holding_info  - 查询沪深港通标的港股机构持股数据

  查询沪深港通标的港股机构持股数据
   gm SDK  3.0.163 版本新增
   交易所信息披露调整，数据最晚更新到2024.8.16，历史数据不受影响
   函数原型：


```
stk_hk_inst_holding_info(symbols=None, trade_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str
  股票代码
  N
  None
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如：'SHSE.600008,SZSE.000002' 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002'] 默认None表示所有标的。

   trade_date
  str or datetime.date
  交易日期
  N
  None
  交易日期，支持str格式（%Y-%m-%d 格式）和 datetime.date 格式，默认None表示最新交易日期。

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict],列表每项的dict的key值为参数指定的 fields 。


   返回值：
     字段名
  类型
  中文名称
  说明

     trade_date
  str
  最新交易日期
  最新交易日期

   symbol
  str
  证券代码
  证券代码

   sec_name
  str
  证券简称
  证券简称

   participant_name
  str
  参与者名称
  参与者名称

   cum_share_holding
  int
  累计持股量(股)
  累计持股量(股)

   cum_shares_rate
  float
  累计占已发行股份(%)
  累计占已发行股份(%)


   示例：


```
stk_hk_inst_holding_info(symbols='SHSE.600008,SZSE.000002', trade_date=None, df=False)
```

  输出：


```
[{'symbol': 'SHSE.600008', 'trade_date': '2024-01-25', 'sec_name': '首创环保', 'cum_share_holding': 132319140, 'cum_shares_rate': 1.71},
 {'symbol': 'SZSE.000002', 'trade_date': '2024-01-25', 'sec_name': '万科A', 'cum_share_holding': 228964226, 'cum_shares_rate': 2.23}]
```

  注意：
   1.  数据日频更新，在交易日约20点更新当日数据。如果当前交易日数据尚未更新，调用时不指定trade_date会返回前一交易日的数据，调用时指定trade_date为当前交易日会返回空。
   2.  trade_date输入非交易日，会返回空。


## #   stk_active_stock_top10_shszhk_info  - 查询沪深港通十大活跃成交股数据

  查询沪深港通十大活跃成交股数据
   gm SDK  3.0.163 版本新增
   函数原型：


```
stk_active_stock_top10_shszhk_info(types=None, trade_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     types
  str or list
  类型
  N
  None
  类型，可输入多个，采用 str 格式时，多个类型必须用英文逗号分割，如：'SZ,SHHK' 采用 list 格式时，多个标的代码示例：['SZ', 'SHHK']，类型包括：SH - 沪股通 ，SHHK - 沪港股通 ，SZ - 深股通 ，SZHK - 深港股通，NF - 北向资金（沪股通+深股通），默认 None 为全部北向资金。

   trade_date
  str or datetime.date
  交易日期
  N
  None
  交易日期，支持str格式（%Y-%m-%d 格式）和 datetime.date 格式，默认None表示最新交易日期。

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict],列表每项的dict的key值为参数指定的 fields 。


   返回值：
     字段名
  类型
  中文名称
  说明

     trade_type
  str
  类型
  SH - 沪股通 ，SHHK - 沪港股通 ，SZ - 深股通 ，SZHK - 深港股通，NF - 北向资金（沪股通+深股通）

   trade_date
  str
  最新交易日期


   rank
  int
  排名


   symbol
  str
  代码


   sec_name
  str
  名称


   close
  float
  收盘价格(元)


   price_range
  float
  涨跌幅(%)


   buy_amount
  float
  买入金额(万元)
  （沪深港通）买入金额(万元)

   buy_volume
  float
  卖出金额(万元)
  （沪深港通）卖出金额(万元)

   total_amount
  float
  成交金额(万元)
  （沪深港通）成交金额(万元)

   stock_total_amount
  float
  股票成交金额(万元)
  股票成交金额(万元)

   transaction_rate
  float
  成交占比(%)
  （沪深港通）成交金额(万元)占股票成交金额(万元)的比例(%)

   market_value_total
  float
  总市值(亿元)


   cum_number_of_times
  int
  累计上榜次数
  股票进入每日十大活跃成交股的次数

   currency
  str
  币种
  CNY(人民币) , HKD(港元)


   示例：


```
stk_active_stock_top10_shszhk_info(types='SZHK', trade_date=None, df=False)
```

  输出：


```
[{'symbol': 'HK.03690', 'trade_date': '2024-01-25', 'rank': 4, 'type': 'SZHK', 'sec_name': '美团-W', 'close': 69.4, 'price_range': -1.2802, 'buy_amount': 30656.8865, 'sell_amount': 28844.0799, 'total_amount': 59500.9664, 'stock_total_amount': 310032.2982, 'transaction_rate': 19.1919, 'market_value_total': 4333.9628, 'cum_number_of_times': 1996, 'currency': 'HKD'},
 {'symbol': 'HK.02318', 'trade_date': '2024-01-25', 'rank': 8, 'type': 'SZHK', 'sec_name': '中国平安', 'close': 34.6, 'price_range': 4.8485, 'buy_amount': 11403.6125, 'sell_amount': 10698.3075, 'total_amount': 22101.92, 'stock_total_amount': 296208.1587, 'transaction_rate': 7.4616, 'market_value_total': 6300.7412, 'cum_number_of_times': 790, 'currency': 'HKD'},
 {'symbol': 'HK.01810', 'trade_date': '2024-01-25', 'rank': 10, 'type': 'SZHK', 'sec_name': '小米集团-W', 'close': 13.74, 'price_range': 0.292, 'buy_amount': 6782.6328, 'sell_amount': 13975.542, 'total_amount': 20758.1748, 'stock_total_amount': 115367.6607, 'transaction_rate': 17.9931, 'market_value_total': 3445.2863, 'cum_number_of_times': 1246, 'currency': 'HKD'},
 {'symbol': 'HK.01797', 'trade_date': '2024-01-25', 'rank': 6, 'type': 'SZHK', 'sec_name': '东方甄选', 'close': 24.2, 'price_range': -8.3333, 'buy_amount': 21350.9475, 'sell_amount': 12630.7475, 'total_amount': 33981.695, 'stock_total_amount': 67946.4211, 'transaction_rate': 50.0125, 'market_value_total': 246.0016, 'cum_number_of_times': 348, 'currency': 'HKD'},
 {'symbol': 'HK.01024', 'trade_date': '2024-01-25', 'rank': 9, 'type': 'SZHK', 'sec_name': '快手-W', 'close': 44.6, 'price_range': -0.112, 'buy_amount': 14876.216, 'sell_amount': 6185.893, 'total_amount': 21062.109, 'stock_total_amount': 97141.6742, 'transaction_rate': 21.6818, 'market_value_total': 1948.6613, 'cum_number_of_times': 637, 'currency': 'HKD'},
 {'symbol': 'HK.00981', 'trade_date': '2024-01-25', 'rank': 7, 'type': 'SZHK', 'sec_name': '中芯国际', 'close': 16.04, 'price_range': 3.4839, 'buy_amount': 15796.551, 'sell_amount': 7910.155, 'total_amount': 23706.706, 'stock_total_amount': 74554.1682, 'transaction_rate': 31.798, 'market_value_total': 1274.6363, 'cum_number_of_times': 1533, 'currency': 'HKD'},
 {'symbol': 'HK.00941', 'trade_date': '2024-01-25', 'rank': 2, 'type': 'SZHK', 'sec_name': '中国移动', 'close': 67.65, 'price_range': 2.3449, 'buy_amount': 61646.64, 'sell_amount': 26017.6775, 'total_amount': 87664.3175, 'stock_total_amount': 248358.7732, 'transaction_rate': 35.2975, 'market_value_total': 14472.2173, 'cum_number_of_times': 1118, 'currency': 'HKD'},
 {'symbol': 'HK.00883', 'trade_date': '2024-01-25', 'rank': 3, 'type': 'SZHK', 'sec_name': '中国海洋石油', 'close': 14.44, 'price_range': 4.7896, 'buy_amount': 57442.304, 'sell_amount': 23673.3544, 'total_amount': 81115.6584, 'stock_total_amount': 269234.0355, 'transaction_rate': 30.1283, 'market_value_total': 6868.6407, 'cum_number_of_times': 1044, 'currency': 'HKD'},
 {'symbol': 'HK.00762', 'trade_date': '2024-01-25', 'rank': 5, 'type': 'SZHK', 'sec_name': '中国联通', 'close': 5.45, 'price_range': 4.6065, 'buy_amount': 21708.258, 'sell_amount': 12586.296, 'total_amount': 34294.554, 'stock_total_amount': 59194.3214, 'transaction_rate': 57.9355, 'market_value_total': 1667.5978, 'cum_number_of_times': 112, 'currency': 'HKD'},
 {'symbol': 'HK.00700', 'trade_date': '2024-01-25', 'rank': 1, 'type': 'SZHK', 'sec_name': '腾讯控股', 'close': 290.8, 'price_range': 3.1938, 'buy_amount': 31622.082, 'sell_amount': 76991.966, 'total_amount': 108614.048, 'stock_total_amount': 984146.2621, 'transaction_rate': 11.0364, 'market_value_total': 27487.5599, 'cum_number_of_times': 3613, 'currency': 'HKD'}]
```

  注意：
   1.  数据日频更新，在交易日约20点更新当日数据。如果当前交易日数据尚未更新，调用时不指定trade_date会返回前一交易日的数据，调用时指定trade_date为当前交易日会返回空。
   2.  trade_date输入非交易日，会返回空。


## #   stk_get_money_flow  - 查询股票交易资金流向

  查询股票每日交易的资金流向
   gm SDK  3.0.172 版本新增
   函数原型：


```
stk_get_money_flow(symbols, trade_date=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考symbol. 采用 str 格式时，多个标的代码必须用英文逗号分割（逗号中间不能有空格），如：'SHSE.600008,SZSE.000002'; 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   trade_date
  str
  交易日期
  N
  None
  交易日期，支持str格式（%Y-%m-%d 格式），默认None表示最新交易日期。


   返回值：
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  格式exchange.sec_id（SHSE.600000, SZSE.000001）

   trade_date
  str
  交易日期


   main_in
  float
  主力流入资金
  超大单加大单买入成交额之和

   main_out
  float
  主力流出资金
  超大单加大单卖出成交额之和

   main_net_in
  float
  主力净流入资金
  主力流入资金-主力流出资金

   main_net_in_rate
  float
  主力资金净流入率
  主力净流入资金/主力总成交额

   super_in
  float
  超大单流入资金
  大于等于50万股或者100万元的成交单买入成交额

   super_out
  float
  超大单流出资金
  大于等于50万股或者100万元的成交单卖出成交额

   super_net_in
  float
  超大单净流入资金
  超大单流入资金-超大单流出资金

   super_net_in_rate
  float
  超大单净流入率
  超大单净流入资金/超大单总成交额

   large_in
  float
  大单流入资金
  大于等于10万股或者20万元且小于50万股和100万元的成交单买入成交额

   large_out
  float
  大单流出资金
  大于等于10万股或者20万元且小于50万股和100万元的成交单卖出成交额

   large_net_in
  float
  大单净流入资金
  大单流入资金-大单流出资金

   large_net_in_rate
  float
  大单净流入率
  大单净流入资金/大单总成交额

   mid_in
  float
  中单流入资金
  大于等于2万股或者4万元且小于10万股和20万元的成交单买入成交额

   mid_out
  float
  中单流出资金
  大于等于2万股或者4万元且小于10万股和20万元的成交单卖出成交额

   mid_net_in
  float
  中单净流入资金
  中单流入资金-中单流出资金

   mid_net_in_rate
  float
  中单净流入率
  中单净流入资金/中单总成交额

   small_in
  float
  小单流入资金
  小于2万股和4万元的成交单买入成交额

   small_out
  float
  小单流出资金
  小于2万股和4万元的成交单卖出成交额

   small_net_in
  float
  小单净流入资金
  小单流入资金-小单流出资金

   small_net_in_rate
  float
  小单净流入率
  小单净流入资金/小单总成交额


   示例：


```
stk_get_money_flow(symbols='SZSE.002583,SHSE.603955',trade_date='2024-11-20')
```

  输出：


```
symbol                 trade_date       main_in      main_out  \
0  SHSE.603955  2024-11-20T00:00:00+08:00   275694357.0   242070831.0
1  SZSE.002583  2024-11-20T00:00:00+08:00  5505519712.0  6385983392.0
   main_net_in  main_net_in_rate      super_in     super_out  super_net_in  \
0   33623526.0          5.248040   128754495.0   101308759.0    27445736.0
1 -880463680.0         -7.440565  3101942544.0  3378101408.0  -276158864.0
   super_net_in_rate      large_in     large_out  large_net_in  \
0           4.283796   146939862.0   140762072.0     6177790.0
1          -2.333745  2403577168.0  3007881984.0  -604304816.0
   large_net_in_rate        mid_in       mid_out   mid_net_in  \
0           0.964244   160360769.0   176158944.0  -15798175.0
1          -5.106820  3212696272.0  3014466672.0  198229600.0
   mid_net_in_rate      small_in     small_out  small_net_in  \
0        -2.465817   111742406.0   129567758.0   -17825352.0
1         1.675186  2781545824.0  2099311744.0   682234080.0
   small_net_in_rate
0          -2.782223
1           5.765379
```

  注意：
   1.  日频资金流向有效数据从2010-01-04开始
   2.  订单大小具体定义：https://finance.eastmoney.com/a/20110101117172217.html


## #   stk_get_finance_audit  - 查询财务审计意见

  获取股票所属上市公司的定期财务审计意见数据
   gm SDK  3.0.172 版本新增
   函数原型：


```
stk_get_finance_audit(symbols, date=None, rpt_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考symbol. 采用 str 格式时，多个标的代码必须用英文逗号分割（逗号中间不能有空格），如：'SHSE.600008,SZSE.000002'; 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   date
  str
  查询日期
  N
  None
  查询时间，时间类型为最新公告日期，%Y-%m-%d 格式，默认None表示最新时间

   rpt_date
  str
  报告日期
  N
  None
  报告截止日期，%Y-%m-%d 格式，可从三大财报接口返回的rpt_date获取。例如：'2023-12-31'表示年报，'2024-03-31'表示一季报，'2024-06-30'表示半年报，'2024-09-30'表示前三季报, 默认None表示不限

   df
  bool
  返回格式
  N
  False
  是否返回dataframe格式， 默认False返回字典格式，返回 list[dict]， 列表每项的dict的key值为参数指定的 fields


   返回值：df=True, 返回dataframe; df=False, 返回list[dict]
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  格式exchange.sec_id（SHSE.600000, SZSE.000001）

   pub_date
  str
  最新公告日期


   first_pub_date
  str
  首次公告日期


   rpt_date
  str
  报告日期
  报告截止日期（报告期）

   audit_date
  str
  审计日期


   acct_standard
  str
  会计准则


   acct_agency
  str
  会计师事务所名称


   cpa
  str
  注册会计师
  审计人员

   audit_opinion
  str
  审计意见


   audit_opinion_code
  str
  审计意见类型代码
  001:经审计, 001001:标准审计报告, 001001001:标准无保留意见, 001002:非标准审计报告, 001002001:带解释性说明的无保留意见, 001002002:保留意见, 001002003:否定意见, 001002004:无法表示意见, 001002005:带强调事项段的无保留意见, 002:未经审计

   audit_opinion_text
  str
  审计意见正文


   audit_no
  str
  审计文号



   示例：


```
stk_get_finance_audit(symbols='SHSE.600000', date=None, rpt_date='2023-12-31', df=False)
```

  输出：


```
[{'symbol': 'SHSE.600000', 'pub_date': '2024-04-30T00:00:00+08:00', 'first_pub_date': '2024-04-30T00:00:00+08:00', 'rpt_date': '2023-12-31T00:00:00+08:00', 'audit_date': '2024-04-26T00:00:00+08:00', 'acct_standard': '大陆会计准则', 'acct_agency': '毕马威华振会计师事务所(特殊普通合伙)', 'cpa': '石海云、窦友明', 'audit_opinion': '标准无保留意见', 'audit_opinion_code': '001001001', 'audit_opinion_text': '一、审计意见我们审计了后附的第1页至第149页的上海浦东发展银行股份有限公司(以下简称“贵行”)及其子公司(统称“贵集团”)财务报表，包括2023年12月31日的合并资产负债表和资产负债表，2023年度的合并利润表和利润表、合并现金流量表和现金流量表、合并股东权益变动表和股东权益变动表以及相关财务报表附注。我们认为，后附的财务报表在所有重大方面按照中华人民共和国财政部颁布的企业会计准则(以下简称“企业会计准则”)的规定编制，公允反映了贵行2023年12月31日的合并财务状况和财务状况以及2023年度的合并经营成果和经营成果及合并现金流量和现金流量。二、形成审计意见的基础我们按照中国注册会计师审计准则(以下简称“审计准则”)的规定执行了审计工作。审计报告的“注册会计师对财务报表审计的责任”部分进一步阐述了我们在这些准则下的责任。按照中国注册会计师职业道德守则，我们独立于贵集团，并履行了职业道德方面的其他责任。我们相信，我们获取的审计证据是充分、适当的，为发表审计意见提供了基础。三、关键审计事项关键审计事项是我们根据职业判断，认为对本年财务报表审计最为重要的事项。这些事项的应对以对财务报表整体进行审计并形成审计意见为背景，我们不对这些事项单独发表意见。发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的预期信用损失计量请参阅财务报表附注三第8.(6)项、附注五第6项、附注五第7.(b)项、附注五第15项、附注五第24项、附注十二第1.(1)项、附注十二第1.(3)项、附注十二第1.(4)项、附注十二第1.(5)项。关键审计事项发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的预期信用损失计量涉及管理层主观判断。贵集团就预期信用损失计量建立了相关的内部控制。在审计中如何应对该事项与评价发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的预期信用损失计量相关的审计程序中包括以下程序：了解和评价与发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的预期信用损失计量相关的关键财务报告内部控制的设计和运行有效性：-了解和评价信用审批、记录、监控、定期信用等级重评、预期信用损失模型数据输入、预期信用损失计算等相关的关键财务报告内部控制的设计和运行有效性；特别地，我们评价与基于各级次发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的信用质量而进行各金融工具阶段划分相关的关键财务报告内部控制的设计和运行有效性；-利用我们信息技术专家和金融风险管理专家的工作，了解和评价相关信息系统控制的设计和运行有效性，包括：系统的信息技术一般控制、关键内部历史数据的完整性、系统间数据传输、预期信用损失模型参数的映射，以及发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺预期信用损失的计算逻辑设置等；请参阅财务报表附注三第8.(6)项、附注五第6项、附注五第7.(b)项、附注五第15项、附注五第24项、附注十二第1.(1)项、附注十二第1.(3)项、附注十二第1.(4)项、附注十二第1.(5)项。关键审计事项贵集团通过评估发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的信用风险自初始确认后是否显著增加，运用三阶段减值模型计量预期信用损失。对于发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺，管理层运用包含违约概率、违约损失率、违约风险敞口和折现率等关键参数的风险参数模型法评估损失准备。在审计中如何应对该事项利用我们金融风险管理专家的工作，评价贵集团评估预期信用损失时所用的预期信用损失模型和参数的可靠性，审慎评价违约概率、违约损失率、违约风险暴露、折现率、前瞻性调整及其他调整等，以及其中所涉及的关键管理层判断的合理性；评价预期信用损失模型使用的关键数据的完整性和准确性。针对与业务原始档案相关的关键内部数据，我们将管理层用以评估减值准备的发放贷款和垫款、金融资产中债权投资、财务担保合同和贷款承诺清单总额分别与总账进行比较，以评价清单的完整性。我们选取样本，将单项贷款、金融投资中债权投资或财务担保合同和贷款承诺的信息与相关协议以及其他有关文件进行比较，以评价清单的准确性；针对关键外部数据，我们将其与公开信息来源进行核对，以评价其准确性；评价涉及主观判断的输入参数，包括从外部寻求支持证据，比对历史损失经验及担保方式等内部记录。作为上述程序的一部分，我们还询问了管理层对关键假设和输入参数所做调整的理由，并考虑管理层所运用的判断是否一致；请参阅财务报表附注三第8.(6)项、附注五第6项、附注五第7.(b)项、附注五第15项、附注五第24项、附注十二第1.(1)项、附注十二第1.(3)项、附注十二第1.(4)项、附注十二第1.(5)项。关键审计事项预期信用损失计量模型所包含的重大管理层判断和假设主要包括：(1)将具有类似信用风险特征的业务划入同一个组合，选择恰当的计量模型，并确定计量相关的关键参数；(2)信用风险显著增加、违约和已发生信用减值的判断标准；(3)用于前瞻性计量的经济指标、经济情景及其权重的采用。在审计中如何应对该事项将管理层在上年计量预期信用损失时采用的经济指标估计与本年实际情况进行比较，以评价是否存在管理层偏向的迹象；针对需由系统运算生成的关键内部数据，我们选取样本将系统运算使用的输入数据核对至业务原始档案以评价系统输入数据的准确性。此外，利用我们信息技术专家的工作，选取样本，测试了发放贷款和垫款逾期信息的编制逻辑；选取样本，评价管理层对信用风险自初始确认后是否显著增加的判断以及是否已发生信用减值的判断的合理性。我们按照行业分类对公司类发放贷款和垫款以及金融投资中债权投资进行分析，选取样本时考虑选取受目前行业周期及调控政策影响较大的行业，关注高风险领域的贷款以及债权投资，并选取已发生信用减值的贷款以及债权投资、逾期未发生信用减值的贷款以及债权投资、信用风险显著上升的贷款以及债权投资、存在负面预警信号、负面媒体消息等其他风险因素的借款人为信贷审阅的样本。我们在选取样本的基础上查看业务文档、检查逾期信息、向客户经理询问借款人的经营状况、检查借款人的财务信息以及搜寻有关借款人业务和经营的市场信息等；请参阅财务报表附注三第8.(6)项、附注五第6项、附注五第7.(b)项、附注五第15项、附注五第24项、附注十二第1.(1)项、附注十二第1.(3)项、附注十二第1.(4)项、附注十二第1.(5)项。关键审计事项由于发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的预期信用损失计量存在固有不确定性以及涉及管理层判断，同时对贵集团的经营状况和资本状况会产生重要影响，我们将发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的预期信用损失计量识别为关键审计事项。在审计中如何应对该事项对选取的已发生信用减值的公司类发放贷款和垫款以及金融投资中债权投资执行信贷审阅时，根据所属分组评估损失率计算模型，或通过询问、运用职业判断和独立查询等方法，评价其预计可收回的现金流。我们还评价担保物的变现时间和方式并考虑管理层提供的其他还款来源。评价管理层对关键假设使用的一致性，并将其与我们的数据来源进行比较；选取样本，复核对预期信用损失的计算，以评价贵集团对预期信用损失模型的应用；根据相关会计准则，评价发放贷款和垫款、金融投资中债权投资、财务担保合同和贷款承诺的财务报表信息披露的合理性。结构化主体的合并请参阅财务报表附注三第4项以及附注七。关键审计事项结构化主体通常是为实现具体而明确的目的而设计并成立的，并在确定的范围内开展业务活动。贵集团可能通过发起设立、持有投资或保留权益份额等方式在结构化主体中享有权益。这些结构化主体主要包括理财产品、资产支持证券、信托计划、资产管理计划或证券投资基金。当判断贵集团是否应该将结构化主体纳入贵集团合并范围时，管理层应考虑贵集团所承担的风险和享有的报酬，贵集团对结构化主体相关活动拥有的权力，以及通过运用该权力而影响其可变回报的能力。这些因素并非完全可量化的，需要综合考虑整体交易的实质内容。由于涉及部分结构化主体的交易较为复杂，并且贵集团在对每个结构化主体的条款及交易实质进行定性评估时需要作出判断，我们将结构化主体的合并识别为关键审计事项。在审计中如何应对该事项与评价结构化主体的合并相关的审计程序中包括以下程序：通过询问管理层和检查与管理层对结构化主体是否合并作出的判断过程相关的文件，以评价贵集团就此设立的流程是否完备；选取样本，对结构化主体执行了下列审计程序：-检查相关合同、内部设立文件以及向投资者披露的信息，以理解结构化主体的设立目的以及贵集团对结构化主体的参与程度，并评价管理层关于贵集团对结构化主体是否拥有权力的判断；-检查结构化主体对风险与报酬的结构设计，包括在结构化主体中拥有的任何资本或对其收益作出的担保、提供流动性支持的安排、佣金的支付和收益的分配等，以评价管理层就贵集团因参与结构化主体的相关活动而拥有的对结构化主体的风险敞口、权力及对可变回报的影响所作的判断；选取样本，对结构化主体执行了下列审计程序(续)：-检查管理层对结构化主体的分析，包括定性分析，以及贵集团对享有结构化主体的经济利益的比重和可变动性的计算，以评价管理层关于贵集团影响其来自结构化主体可变回报的能力判断；-评价管理层就是否合并结构化主体所作的判断；评价财务报表中对结构化主体的相关披露是否符合企业会计准则的披露要求。金融工具公允价值的评估请参阅财务报表附注三第8项、附注三第23项、附注三第34项所述的会计政策以及附注十二第4项。关键审计事项以公允价值计量的金融工具是贵集团持有/承担的重要资产/负债。公允价值调整可能影响损益或其他综合收益。贵集团以公允价值计量的金融工具的估值以市场数据和估值模型为基础，其中估值模型通常需要大量的参数输入。大部分参数来源于能够可靠获取的数据，尤其是第一层次和第二层次公允价值计量的金融工具，其估值模型采用的参数分别是市场报价和可观察参数。当可观察的参数无法可靠获取时，即第三层次公允价值计量的金融工具的情形下，不可观察输入值的确定会使用到管理层估计，这当中会涉及管理层的重大判断。此外，贵集团已对特定的第二层次及第三层次公允价值计量的金融工具开发了自有估值模型，这也会涉及管理层的重大判断。由于金融工具公允价值的评估涉及复杂的流程，以及在确定估值模型使用的参数时涉及管理层判断的程度，我们将金融工具公允价值的评估识别为关键审计事项。在审计中如何应对该事项与评价金融工具的公允价值相关的审计程序中包括以下程序：了解和评价贵集团与估值、独立价格验证、前后台对账及金融工具估值模型审批相关的关键财务报告内部控制的设计和运行有效性；选取样本，通过比较贵集团采用的公允价值与公开可获取的市场数据，评价第一层次公允价值计量的金融工具的估值；利用我们的金融风险管理专家的工作，在选取样本的基础上对第二层次和第三层次公允价值计量的金融工具进行独立估值，并将我们的估值结果与贵集团的估值结果进行比较。上述程序具体包括将贵行的估值模型与我们了解的行业通行估值方法进行比较，测试公允价值计算的输入值，以及建立平行估值模型进行重估；在评价对构成公允价值组成部分的公允价值调整的运用是否适当时，询问管理层计算公允价值调整的方法是否发生变化，并评价参数运用的恰当性；评价财务报表的相关披露，是否符合企业会计准则的披露要求，恰当反映了金融工具估值风险。四、其他信息贵行管理层对其他信息负责。其他信息包括贵行2023年年度报告中涵盖的信息，但不包括财务报表和我们的审计报告。我们对财务报表发表的审计意见不涵盖其他信息，我们也不对其他信息发表任何形式的鉴证结论。结合我们对财务报表的审计，我们的责任是阅读其他信息，在此过程中，考虑其他信息是否与财务报表或我们在审计过程中了解到的情况存在重大不一致或者似乎存在重大错报。基于我们已经执行的工作，如果我们确定其他信息存在重大错报，我们应当报告该事实。在这方面，我们无任何事项需要报告。五、管理层和治理层对财务报表的责任管理层负责按照企业会计准则的规定编制财务报表，使其实现公允反映，并设计、执行和维护必要的内部控制，以使财务报表不存在由于舞弊或错误导致的重大错报。在编制财务报表时，管理层负责评估贵集团及贵行的持续经营能力，披露与持续经营相关的事项(如适用)，并运用持续经营假设，除非贵集团及贵行计划进行清算、终止运营或别无其他现实的选择。治理层负责监督贵集团的财务报告过程。六、注册会计师对财务报表审计的责任我们的目标是对财务报表整体是否不存在由于舞弊或错误导致的重大错报获取合理保证，并出具包含审计意见的审计报告。合理保证是高水平的保证，但并不能保证按照审计准则执行的审计在某一重大错报存在时总能发现。错报可能由于舞弊或错误导致，如果合理预期错报单独或汇总起来可能影响财务报表使用者依据财务报表作出的经济决策，则通常认为错报是重大的。在按照审计准则执行审计工作的过程中，我们运用职业判断，并保持职业怀疑。同时，我们也执行以下工作：(1)识别和评估由于舞弊或错误导致的财务报表重大错报风险，设计和实施审计程序以应对这些风险，并获取充分、适当的审计证据，作为发表审计意见的基础。由于舞弊可能涉及串通、伪造、故意遗漏、虚假陈述或凌驾于内部控制之上，未能发现由于舞弊导致的重大错报的风险高于未能发现由于错误导致的重大错报的风险。(2)了解与审计相关的内部控制，以设计恰当的审计程序。(3)评价管理层选用会计政策的恰当性和作出会计估计及相关披露的合理性。(4)对管理层使用持续经营假设的恰当性得出结论。同时，根据获取的审计证据，就可能导致对贵集团及贵行持续经营能力产生重大疑虑的事项或情况是否存在重大不确定性得出结论。如果我们得出结论认为存在重大不确定性，审计准则要求我们在审计报告中提请报表使用者注意财务报表中的相关披露；如果披露不充分，我们应当发表非无保留意见。我们的结论基于截至审计报告日可获得的信息。然而，未来的事项或情况可能导致贵集团及贵行不能持续经营。(5)评价财务报表的总体列报(包括披露)、结构和内容，并评价财务报表是否公允反映相关交易和事项。(6)就贵集团中实体或业务活动的财务信息获取充分、适当的审计证据，以对财务报表发表审计意见。我们负责指导、监督和执行集团审计，并对审计意见承担全部责任。我们与治理层就计划的审计范围、时间安排和重大审计发现等事项进行沟通，包括沟通我们在审计中识别出的值得关注的内部控制缺陷。我们还就已遵守与独立性相关的职业道德要求向治理层提供声明，并与治理层沟通可能被合理认为影响我们独立性的所有关系和其他事项，以及相关的防范措施(如适用)。从与治理层沟通过的事项中，我们确定哪些事项对本年财务报表审计最为重要，因而构成关键审计事项。我们在审计报告中描述这些事项，除非法律法规禁止公开披露这些事项，或在极少数情形下，如果合理预期在审计报告中沟通某事项造成的负面后果超过在公众利益方面产生的益处，我们确定不应在审计报告中沟通该事项。', 'audit_no': '毕马威华振审字第2407993号'}]
```

  注意：
   1.  为避免未来数据，指定查询日期date后，返回最新公告日期小于等于查询日期下的指定报告日期数据。如果指定报告日期的财务审计意见尚未公告，返回空数据。


## #   stk_get_finance_forecast  - 查询公司业绩预告

  获取股票所属上市公司的业绩预告数据
   gm SDK  3.0.172 版本新增
   函数原型：


```
stk_get_finance_forecast(symbols, rpt_type=None, date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考symbol. 采用 str 格式时，多个标的代码必须用英文逗号分割（逗号中间不能有空格），如：'SHSE.600008,SZSE.000002'; 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   date
  str
  查询日期
  N
  None
  查询时间，时间类型为最新公告日期，%Y-%m-%d 格式，默认None表示最新时间

   rpt_type
  str
  预测报表类型
  N
  None
  按报告期查询可指定以下报表类型：1-一季度报，6-中报，9-前三季报，12-年报，默认None为不限

   df
  bool
  返回格式
  N
  False
  是否返回dataframe格式， 默认False返回字典格式，返回 list[dict]， 列表每项的dict的key值为参数指定的 fields


   返回值：df=True, 返回dataframe; df=False, 返回list[dict]
     字段名
  类型
  中文名称
  说明

     symbol
  str
  股票代码
  格式exchange.sec_id（SHSE.600000, SZSE.000001）

   pub_date
  str
  最新公告日期


   begin_date
  str
  预测起始日


   end_date
  str
  预测截止日


   rpt_type
  str
  预测报表类型


   fcst_type
  str
  业绩预告类型
  001001 预增，001002 略增，001003 略减，001004 预减，001005 续盈，001006 首亏，002 不确定，003001 扭亏，003002 续亏，003003 减亏，003004 增亏

   fcst_field
  str
  预测财务指标
  001 主营业务收入，002 净利润  net_prof，003 每股收益  eps_basic，004 归属于上市公司股东的净利润  net_prof_pcom，005 扣除非经常性损益后的净利润  net_prof_pcom_cut，006 营业收入  inc_oper，007 非经常性损益  nr_prof_loss，008 扣除后营业收入

   fcst_amount_max
  float
  预测金额元(上限)
  单位：元

   fcst_amount_min
  float
  预测金额元(下限)
  单位：元

   amount_ly
  float
  上年同期元
  单位：元

   increase_pct_max
  float
  增长幅度(上限)
  单位：%

   increase_pct_min
  float
  增长幅度(下限)
  单位：%

   fcst_content
  str
  财务指标预告内容


   ann_fcst_amount_unit
  str
  公告预测金融单位


   ann_fcst_amount_max
  float
  公告原始预测金额(上限)
  单位：公告预测金融单位

   ann_fcst_amount_min
  float
  公告原始预测金额(下限)
  单位：公告预测金融单位

   ann_amount_ly
  float
  上年原始同期
  单位：公告预测金融单位

   ann_increase_max
  float
  公告增长金额(上限)
  单位：公告预测金融单位

   ann_increase_min
  float
  公告增长金额(下限)
  单位：公告预测金融单位

   is_change
  bool
  是否变脸
  0-否 1-是

   change_reason
  str
  业绩变动原因说明



   示例：


```
stk_get_finance_forecast(symbols='SHSE.600000,SZSE.000001', rpt_type=None, date=None, df=False)
```

  输出：


```
[{'symbol': 'SHSE.600000', 'pub_date': '2008-10-30T00:00:00+08:00', 'begin_date': '2008-01-01T00:00:00+08:00', 'end_date': '2008-12-31T00:00:00+08:00', 'rpt_type': '12', 'fcst_type': '预增', 'fcst_field': '归属于上市公司股东的净利润', 'fcst_content': '预计与上年同期相比发生大幅度变动。', 'fcst_amount_max': 0.0, 'fcst_amount_min': 0.0, 'amount_ly': 0.0, 'increase_pct_max': 0.0, 'increase_pct_min': 0.0, 'ann_fcst_amount_unit': '', 'ann_fcst_amount_max': 0.0, 'ann_fcst_amount_min': 0.0, 'ann_amount_ly': 0.0, 'ann_increase_max': 0.0, 'ann_increase_min': 0.0, 'is_change': False, 'change_reason': ''},
 {'symbol': 'SZSE.000001', 'pub_date': '2016-01-21T00:00:00+08:00', 'begin_date': '2015-01-01T00:00:00+08:00', 'end_date': '2015-12-31T00:00:00+08:00', 'rpt_type': '12', 'fcst_type': '略增', 'fcst_field': '归属于上市公司股东的净利润', 'fcst_amount_max': 22772250000.0, 'fcst_amount_min': 20792060000.0, 'increase_pct_max': 15.0, 'increase_pct_min': 5.0, 'fcst_content': '预计2015年1-12月归属于上市公司股东的净利润:2,079,206-2,277,225万元,同比上年上升:5%-15%', 'change_reason': '业绩增长的主要原因是资产规模的稳定增长、 息差改善以及成本有效控制。', 'amount_ly': 0.0, 'ann_fcst_amount_unit': '', 'ann_fcst_amount_max': 0.0, 'ann_fcst_amount_min': 0.0, 'ann_amount_ly': 0.0, 'ann_increase_max': 0.0, 'ann_increase_min': 0.0, 'is_change': False},
 {'symbol': 'SZSE.000001', 'pub_date': '2016-01-21T00:00:00+08:00', 'begin_date': '2015-01-01T00:00:00+08:00', 'end_date': '2015-12-31T00:00:00+08:00', 'rpt_type': '12', 'fcst_type': '略增', 'fcst_field': '每股收益', 'fcst_amount_max': 1.62, 'fcst_amount_min': 1.48, 'fcst_content': '预计2015年1-12月每股收益:1.48-1.62元', 'change_reason': '业绩增长的主要原因是资产规模的稳定增长、 息差改善以及成本有效控制。', 'amount_ly': 0.0, 'increase_pct_max': 0.0, 'increase_pct_min': 0.0, 'ann_fcst_amount_unit': '', 'ann_fcst_amount_max': 0.0, 'ann_fcst_amount_min': 0.0, 'ann_amount_ly': 0.0, 'ann_increase_max': 0.0, 'ann_increase_min': 0.0, 'is_change': False}]
```

  注意：
   1.  为避免未来数据，指定查询日期date后，返回公告日期小于等于查询日期下的最新报告期数据。


## #   get_open_call_auction  - 查询集合竞价开盘成交

  查询股票开盘成交数据
   gm SDK  3.0.176 版本新增
   函数原型：


```
get_open_call_auction (symbols, trade_date=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考symbol. 采用 str 格式时，多个标的代码必须用英文逗号分割（逗号中间不能有空格），如：'SHSE.600008,SZSE.000002'; 采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   trade_date
  str
  交易日期
  N
  None
  交易日期，YYYY-MM-DD 格式，默认None返回最新交易日


   返回值：返回dataframe
     字段名
  类型
  中文名称
  说明

     symbol
  str
  标的代码
  格式exchange.sec_id（SHSE.600000, SZSE.000001）

   time
  str
  开盘集合竞价撮合时间
  交易日09:25，%Y-%m-%d %H:%M:%S 格式

   current_price
  float
  当前最新价（不复权）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的最新成交价Tick.price，即开盘价

   open_volume
  int
  开盘成交量（股）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的累计成交量Tick.cum_volume

   open_amount
  float
  开盘成交额（元）
  09:15~09:25开盘前竞价，在09:25一次性集中撮合产生的累计成交额Tick.cum_amount

   ask_v1~ask_v5
  float
  五档卖量
  09:25五档卖量Tick.quotes[0].ask_v~Tick.quotes[4].ask_v。

   ask_p1~ask_p5
  float
  五档卖价
  09:25五档卖价Tick.quotes[0].ask_p~Tick.quotes[4].ask_p。

   bid_v1~bid_v5
  float
  五档买量
  09:25五档买量Tick.quotes[0].bid_v~Tick.quotes[4].bid_v。

   bid_p1~bid_p5
  float
  五档买价
  09:25五档买价Tick.quotes[0].bid_p~Tick.quotes[4].bid_p。


   示例：


```
get_open_call_auction(symbols='SHSE.600000, SZSE.000001', trade_date='2025-03-27')
```

  输出：


```
symbol                 time  current_price  open_volume  open_amount  \
0  SHSE.600000  2025-03-27 09:25:00    10.50000000       122600    1287300.0
1  SZSE.000001  2025-03-27 09:25:00    11.36999989       296000    3365520.0
   ask_v1  ask_v2  ask_v3  ask_v4  ask_v5       ask_p1       ask_p2  \
0     980   15800   21500   16000    6000  10.50000000  10.51000023
1   91100  580821  951900  462900  764400  11.38000011  11.39000034
        ask_p3       ask_p4       ask_p5  bid_v1  bid_v2  bid_v3  bid_v4  \
0  10.52000046  10.52999973  10.53999996    1400     900   15400     700
1  11.39999962  11.40999985  11.42000008  198300  320700  645500  451000
   bid_v5       bid_p1       bid_p2       bid_p3       bid_p4       bid_p5
0   27700  10.48999977  10.47999954  10.47000027  10.46000004  10.44999981
1  391400  11.36999989  11.35999966  11.35000038  11.34000015  11.32999992
```

  注意：
   1.  开盘集合竞价的成交数据于每个交易日09:26更新，09:26后可查询当天开盘集合竞价，在09:26前查询当天开盘集合竞价返回空。
   2.  如果输入symbols包含不存在的标的代码，会报错。
   3.  如果开盘集合竞价没有发生成交，curret_price, open_volume, open_amount返回0.
   4.  数据最早为2025-02-21。


      ←

        期货基础数据函数（免费）

        期货增值数据函数（付费）

      →

---

## 股票财务数据及基础数据函数（免费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E8%82%A1%E7%A5%A8%E8%B4%A2%E5%8A%A1%E6%95%B0%E6%8D%AE%E5%8F%8A%E5%9F%BA%E7%A1%80%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0%EF%BC%88%E5%85%8D%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     股票财务数据及基础数据函数(免费) - 掘金量化












# #  股票财务数据及基础数据函数(免费)

  python 股票与指数数据 API 包含在 gm3.0.148 版本及以上版本


## #   stk_get_index_constituents  - 查询指数成分股

  查询指定指数在最新交易日的成分股和权重(中证系列指数，因版权不提供成分股权重，weight=0)
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_index_constituents(index, trade_date=None)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     index
  str
  指数代码
  Y
  无
  必填，只能输入一个指数，如： 'SHSE.000905'

   trade_date
  str
  交易日期
  N
  None
  交易日期，%Y-%m-%d 格式， 默认 None 为最新交易日


   返回值：  dataframe
     字段名
  类型
  中文名称
  说明

     index
  str
  指数代码
  查询成分股的指数代码

   symbol
  str
  成分股代码
  exchange.sec_id

   weight
  float
  成分股权重
  成分股 symbol 对应的指数权重 (中证系列指数不支持该字段）

   trade_date
  str
  交易日期
  最新交易日，%Y-%m-%d 格式

   market_value_total
  float
  总市值
  单位：亿元

   market_value_circ
  float
  流通市值
  单位：亿元


   示例：


```
stk_get_index_constituents(index='SHSE.000300')
```

  输出：


```
index       symbol  weight  trade_date  market_value_total  market_value_circ
0    SHSE.000300  SHSE.600519    0.05  2023-04-18            22083.96           22083.96
1    SHSE.000300  SZSE.300750    0.03  2023-04-18             9989.35            8822.91
2    SHSE.000300  SHSE.601318    0.03  2023-04-18             8887.85            5266.84
3    SHSE.000300  SHSE.600036    0.02  2023-04-18             8998.44            7360.41
4    SHSE.000300  SZSE.000858    0.02  2023-04-18             6921.68            6921.39
5    SHSE.000300  SZSE.000333    0.01  2023-04-18             3972.72            3891.18
6    SHSE.000300  SHSE.601166    0.01  2023-04-18             3616.80            3616.80
7    SHSE.000300  SHSE.600900    0.01  2023-04-18             5030.92            4834.92
8    SHSE.000300  SHSE.601012    0.01  2023-04-18             3033.36            3031.97
9    SHSE.000300  SZSE.300059    0.01  2023-04-18             2859.02            2399.14
10   SHSE.000300  SZSE.002594    0.01  2023-04-18             7248.75            2900.26...
```

  注意：
   1.  数据日频更新，在交易日约 20 点更新当日数据。如果当日数据尚未更新，调用时不指定 trade_date 会返回前一交易日的成分数据，调用时指定 trade_date 为当日会返回空 dataframe。
   2.   trade_date 输入非交易日，会返回空 dataframe。 trade_date 出入的日期格式错误，会报错。
   3.  指数列表 参考


## #   stk_get_fundamentals_balance_pt  - 查询资产负债表截面数据（多标的）

  查询指定日期截面的股票所属上市公司的资产负债表数据（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_fundamentals_balance_pt(symbols, rpt_type=None, data_type=None, date=None, fields, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型：
1-一季度报
6-中报
9-前三季报
12-年报
默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
100-合并最初（未修正的合并原始）
101-合并原始
102-合并调整
200-母公司最初（未修正的母公司原始）
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始，如果合并原始未修正返回合并最初

   date
  str
  查询日期
  N
  None
  查询时间，时间类型为发布日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  距查询日期最近的发布日期
若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期
若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期
若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：100-合并最初（未修正的合并原始） 101-合并原始 102-合并调整 201-母公司原始 202-母公司调整 200-母公司最初（未修正的母公司原始）

   fields
  list[float]
  财务字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考   资产负债表


   示例：


```
stk_get_fundamentals_balance_pt(symbols='SHSE.600000, SZSE.000001', rpt_type=None, data_type=None, date='2022-10-01', fields='fix_ast', df=True)
```

  输出：


```
symbol    pub_date    rpt_date        fix_ast  data_type  rpt_type
0  SZSE.000001  2022-10-25  2022-09-30 10975000000.00        102         9
1  SHSE.600000  2022-10-29  2022-09-30 42563000000.00        102         9
```

  注意：
   1.  为避免未来数据问题，指定查询日期 date 后，返回发布日期小于查询日期下的最新报告日期数据。
   2.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    资产负债表
     字段名
  类型
  中文名称
  量纲
  说明

       流动资产(资产)





   cash_bal_cb
  float
  现金及存放中央银行款项
  元
  银行

   dpst_ob
  float
  存放同业款项
  元
  银行

   mny_cptl
  float
  货币资金
  元


   cust_cred_dpst
  float
  客户信用资金存款
  元
  证券

   cust_dpst
  float
  客户资金存款
  元
  证券

   pm
  float
  贵金属
  元
  银行

   bal_clr
  float
  结算备付金
  元


   cust_rsv
  float
  客户备付金
  元
  证券

   ln_to_ob
  float
  拆出资金
  元


   fair_val_fin_ast
  float
  以公允价值计量且其变动计入当期损益的金融资产
  元


   ppay
  float
  预付款项
  元


   fin_out
  float
  融出资金
  元


   trd_fin_ast
  float
  交易性金融资产
  元


   deriv_fin_ast
  float
  衍生金融资产
  元


   note_acct_rcv
  float
  应收票据及应收账款
  元


   note_rcv
  float
  应收票据
  元


   acct_rcv
  float
  应收账款
  元


   acct_rcv_fin
  float
  应收款项融资
  元


   int_rcv
  float
  应收利息
  元


   dvd_rcv
  float
  应收股利
  元


   oth_rcv
  float
  其他应收款
  元


   in_prem_rcv
  float
  应收保费
  元


   rin_acct_rcv
  float
  应收分保账款
  元


   rin_rsv_rcv
  float
  应收分保合同准备金
  元
  保险

   rcv_un_prem_rin_rsv
  float
  应收分保未到期责任准备金
  元


   rcv_clm_rin_rsv
  float
  应收分保未决赔偿准备金
  元
  保险

   rcv_li_rin_rsv
  float
  应收分保寿险责任准备金
  元
  保险

   rcv_lt_hi_rin_rsv
  float
  应收分保长期健康险责任准备金
  元
  保险

   ph_plge_ln
  float
  保户质押贷款
  元
  保险

   ttl_oth_rcv
  float
  其他应收款合计
  元


   rfd_dpst
  float
  存出保证金
  元
  证券、保险

   term_dpst
  float
  定期存款
  元
  保险

   pur_resell_fin
  float
  买入返售金融资产
  元


   aval_sale_fin
  float
  可供出售金融资产
  元


   htm_inv
  float
  持有至到期投资
  元


   hold_for_sale
  float
  持有待售资产
  元


   acct_rcv_inv
  float
  应收款项类投资
  元
  保险

   invt
  float
  存货
  元


   contr_ast
  float
  合同资产
  元


   ncur_ast_one_y
  float
  一年内到期的非流动资产
  元


   oth_cur_ast
  float
  其他流动资产
  元


   cur_ast_oth_item
  float
  流动资产其他项目
  元


   ttl_cur_ast
  float
  流动资产合计
  元


     非流动资产(资产)





   loan_adv
  float
  发放委托贷款及垫款
  元


   cred_inv
  float
  债权投资
  元


   oth_cred_inv
  float
  其他债权投资
  元


   lt_rcv
  float
  长期应收款
  元


   lt_eqy_inv
  float
  长期股权投资
  元


   oth_eqy_inv
  float
  其他权益工具投资
  元


   rfd_cap_guar_dpst
  float
  存出资本保证金
  元
  保险

   oth_ncur_fin_ast
  float
  其他非流动金融资产
  元


   amor_cos_fin_ast_ncur
  float
  以摊余成本计量的金融资产（非流动）
  元


   fair_val_oth_inc_ncur
  float
  以公允价值计量且其变动计入其他综合收益的金融资产（非流动）
  元


   inv_prop
  float
  投资性房地产
  元


   fix_ast
  float
  固定资产
  元


   const_prog
  float
  在建工程
  元


   const_matl
  float
  工程物资
  元


   fix_ast_dlpl
  float
  固定资产清理
  元


   cptl_bio_ast
  float
  生产性生物资产
  元


   oil_gas_ast
  float
  油气资产
  元


   rig_ast
  float
  使用权资产
  元


   intg_ast
  float
  无形资产
  元


   trd_seat_fee
  float
  交易席位费
  元
  证券

   dev_exp
  float
  开发支出
  元


   gw
  float
  商誉
  元


   lt_ppay_exp
  float
  长期待摊费用
  元


   dfr_tax_ast
  float
  递延所得税资产
  元


   oth_ncur_ast
  float
  其他非流动资产
  元


   ncur_ast_oth_item
  float
  非流动资产其他项目
  元


   ttl_ncur_ast
  float
  非流动资产合计
  元


   oth_ast
  float
  其他资产
  元
  银行、证券、保险

   ast_oth_item
  float
  资产其他项目
  元


   ind_acct_ast
  float
  独立账户资产
  元
  保险

   ttl_ast
  float
  资产总计
  元


     流动负债(负债)





   brw_cb
  float
  向中央银行借款
  元


   dpst_ob_fin_inst
  float
  同业和其他金融机构存放款项
  元
  银行、保险

   ln_fm_ob
  float
  拆入资金
  元


   fair_val_fin_liab
  float
  以公允价值计量且其变动计入当期损益的金融负债
  元


   sht_ln
  float
  短期借款
  元


   adv_acct
  float
  预收款项
  元


   contr_liab
  float
  合同负债
  元


   trd_fin_liab
  float
  交易性金融负债
  元


   deriv_fin_liab
  float
  衍生金融负债
  元


   sell_repo_ast
  float
  卖出回购金融资产款
  元


   cust_bnk_dpst
  float
  吸收存款
  元
  银行、保险

   dpst_cb_note_pay
  float
  存款证及应付票据
  元
  银行

   dpst_cb
  float
  存款证
  元
  银行

   acct_rcv_adv
  float
  预收账款
  元
  保险

   in_prem_rcv_adv
  float
  预收保费
  元
  保险

   fee_pay
  float
  应付手续费及佣金
  元


   note_acct_pay
  float
  应付票据及应付账款
  元


   stlf_pay
  float
  应付短期融资款
  元


   note_pay
  float
  应付票据
  元


   acct_pay
  float
  应付账款
  元


   rin_acct_pay
  float
  应付分保账款
  元


   emp_comp_pay
  float
  应付职工薪酬
  元


   tax_pay
  float
  应交税费
  元


   int_pay
  float
  应付利息
  元


   dvd_pay
  float
  应付股利
  元


   ph_dvd_pay
  float
  应付保单红利
  元
  保险

   indem_pay
  float
  应付赔付款
  元
  保险

   oth_pay
  float
  其他应付款
  元


   ttl_oth_pay
  float
  其他应付款合计
  元


   ph_dpst_inv
  float
  保户储金及投资款
  元
  保险

   in_contr_rsv
  float
  保险合同准备金
  元
  保险

   un_prem_rsv
  float
  未到期责任准备金
  元
  保险

   clm_rin_rsv
  float
  未决赔款准备金
  元
  保险

   li_liab_rsv
  float
  寿险责任准备金
  元
  保险

   lt_hi_liab_rsv
  float
  长期健康险责任准备金
  元
  保险

   cust_bnk_dpst_fin
  float
  吸收存款及同业存放
  元


   inter_pay
  float
  内部应付款
  元


   agy_secu_trd
  float
  代理买卖证券款
  元


   agy_secu_uw
  float
  代理承销证券款
  元


   sht_bnd_pay
  float
  应付短期债券
  元


   est_cur_liab
  float
  预计流动负债
  元


   liab_hold_for_sale
  float
  持有待售负债
  元


   ncur_liab_one_y
  float
  一年内到期的非流动负债
  元


   oth_cur_liab
  float
  其他流动负债
  元


   cur_liab_oth_item
  float
  流动负债其他项目
  元


   ttl_cur_liab
  float
  流动负债合计
  元


     非流动负债（负债）





   lt_ln
  float
  长期借款
  元


   lt_pay
  float
  长期应付款
  元


   leas_liab
  float
  租赁负债



   dfr_inc
  float
  递延收益
  元


   dfr_tax_liab
  float
  递延所得税负债
  元


   bnd_pay
  float
  应付债券
  元


   bnd_pay_pbd
  float
  其中:永续债
  元


   bnd_pay_pfd
  float
  其中:优先股
  元


   oth_ncur_liab
  float
  其他非流动负债
  元


   spcl_pay
  float
  专项应付款
  元


   ncur_liab_oth_item
  float
  非流动负债其他项目
  元


   lt_emp_comp_pay
  float
  长期应付职工薪酬
  元


   est_liab
  float
  预计负债
  元


   oth_liab
  float
  其他负债
  元
  银行、证券、保险

   liab_oth_item
  float
  负债其他项目
  元
  银行、证券、保险

   ttl_ncur_liab
  float
  非流动负债合计
  元


   ind_acct_liab
  float
  独立账户负债
  元
  保险

   ttl_liab
  float
  负债合计
  元


     所有者权益(或股东权益)





   paid_in_cptl
  float
  实收资本（或股本）
  元


   oth_eqy
  float
  其他权益工具
  元


   oth_eqy_pfd
  float
  其中:优先股
  元


   oth_eqy_pbd
  float
  其中:永续债
  元


   oth_eqy_oth
  float
  其中:其他权益工具
  元


   cptl_rsv
  float
  资本公积
  元


   treas_shr
  float
  库存股
  元


   oth_comp_inc
  float
  其他综合收益
  元


   spcl_rsv
  float
  专项储备
  元


   sur_rsv
  float
  盈余公积
  元


   rsv_ord_rsk
  float
  一般风险准备
  元


   trd_risk_rsv
  float
  交易风险准备
  元
  证券

   ret_prof
  float
  未分配利润
  元


   sugg_dvd
  float
  建议分派股利
  元
  银行

   eqy_pcom_oth_item
  float
  归属于母公司股东权益其他项目
  元


   ttl_eqy_pcom
  float
  归属于母公司股东权益合计
  元


   min_sheqy
  float
  少数股东权益
  元


   sheqy_oth_item
  float
  股东权益其他项目
  元


   ttl_eqy
  float
  股东权益合计
  元


   ttl_liab_eqy
  float
  负债和股东权益合计
  元





## #   stk_get_fundamentals_cashflow_pt  - 查询现金流量表截面数据（多标的）

  查询指定日期截面的股票所属上市公司的现金流量表数据（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_fundamentals_cashflow_pt(symbols, rpt_type=None, data_type=None, date=None, fields, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型：
1-一季度报
6-中报
9-前三季报
12-年报
2-第二季度
3-第三季度
4-第四季度
默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
100-合并最初（未修正的合并原始）
101-合并原始
102-合并调整
200-母公司最初（未修正的母公司原始）
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始，如果合并原始未修正返回合并最初

   date
  str
  查询日期
  N
  None
  查询时间，时间类型为发布日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  距查询日期最近的发布日期
若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期
若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期
若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报, 2-第二季度, 3-第三季度, 4-第四季度

   data_type
  int
  数据类型
  返回数据的数据类型：100-合并最初（未修正的合并原始） 101-合并原始 102-合并调整 201-母公司原始 202-母公司调整 200-母公司最初（未修正的母公司原始）

   fields
  list[float]
  财务字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考   现金流量表


   示例：


```
stk_get_fundamentals_cashflow_pt(symbols='SHSE.600000, SZSE.000001', rpt_type=None, data_type=None, date='2022-10-01', fields='cash_pay_fee', df=True)
```

  输出：


```
symbol    pub_date    rpt_date  rpt_type  data_type  cash_pay_fee
0  SZSE.000001  2022-10-25  2022-09-30         9        102           NaN
1  SHSE.600000  2022-10-29  2022-09-30         9        102 7261000000.00
```

  注意：
   1.  为避免未来数据问题，指定查询日期 date 后，返回发布日期小于查询日期下的最新报告日期数据。
   2.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    现金流量表
     字段名
  类型
  中文名称
  量纲
  说明

       一、经营活动产生的现金流量





   cash_rcv_sale
  float
  销售商品、提供劳务收到的现金
  元


   net_incr_cust_dpst_ob
  float
  客户存款和同业存放款项净增加额
  元


   net_incr_cust_dpst
  float
  客户存款净增加额
  元
  银行

   net_incr_dpst_ob
  float
  同业及其他金融机构存放款项净增加额
  元
  银行

   net_incr_brw_cb
  float
  向中央银行借款净增加额
  元


   net_incr_ln_fm_oth
  float
  向其他金融机构拆入资金净增加额
  元


   cash_rcv_orig_in
  float
  收到原保险合同保费取得的现金
  元


   net_cash_rcv_rin_biz
  float
  收到再保险业务现金净额
  元


   net_incr_ph_dpst_inv
  float
  保户储金及投资款净增加额
  元


   net_decrdpst_cb_ob
  float
  存放中央银行和同业款项及其他金融机构净减少额
  元
  银行、保险

   net_decr_cb
  float
  存放中央银行款项净减少额
  元
  银行

   net_decr_ob_fin_inst
  float
  存放同业及其他金融机构款项净减少额
  元
  银行

   net_cert_dpst
  float
  存款证净额
  元
  银行

   net_decr_trd_fin
  float
  交易性金融资产净减少额
  元
  银行

   net_incr_trd_liab
  float
  交易性金融负债净增加额
  元
  银行

   cash_rcv_int_fee
  float
  收取利息、手续费及佣金的现金
  元


   cash_rcv_int
  float
  其中：收取利息的现金
  元
  银行

   cash_rcv_fee
  float
  收取手续费及佣金的现金
  元
  银行

   net_incr_lnfm_sell_repo
  float
  拆入资金及卖出回购金融资产款净增加额
  元
  银行

   net_incr_ln_fm
  float
  拆入资金净增加额
  元


   net_incr_sell_repo
  float
  卖出回购金融资产款净增加额
  元
  银行 保险

   net_decr_lnto_pur_resell
  float
  拆出资金及买入返售金融资产净减少额
  元
  银行

   net_decr_ln_cptl
  float
  拆出资金净减少额
  元
  银行、保险

   net_dect_pur_resell
  float
  买入返售金融资产净减少额
  元
  银行、保险

   net_incr_repo
  float
  回购业务资金净增加额
  元


   net_decr_repo
  float
  回购业务资金净减少额
  元
  证券

   tax_rbt_rcv
  float
  收到的税费返还
  元


   net_cash_rcv_trd
  float
  收到交易性金融资产现金净额
  元
  保险

   cash_rcv_oth_oper
  float
  收到其他与经营活动有关的现金
  元


   net_cash_agy_secu_trd
  float
  代理买卖证券收到的现金净额
  元
  证券

   cash_rcv_pur_resell
  float
  买入返售金融资产收到的现金
  元
  证券、保险

   net_cash_agy_secu_uw
  float
  代理承销证券收到的现金净额
  元
  证券

   cash_rcv_dspl_debt
  float
  处置抵债资产收到的现金
  元
  银行

   canc_loan_rcv
  float
  收回的已于以前年度核销的贷款
  元
  银行

   cf_in_oper
  float
  经营活动现金流入小计
  元


   cash_pur_gds_svc
  float
  购买商品、接受劳务支付的现金
  元


   net_incr_ln_adv_cust
  float
  客户贷款及垫款净增加额
  元


   net_decr_brw_cb
  float
  向中央银行借款净减少额
  元
  银行

   net_incr_dpst_cb_ob
  float
  存放中央银行和同业款项净增加额
  元


   net_incr_cb
  float
  存放中央银行款项净增加额
  元
  银行

   net_incr_ob_fin_inst
  float
  存放同业及其他金融机构款项净增加额
  元
  银行

   net_decr_dpst_ob
  float
  同业及其他机构存放款减少净额
  元
  银行

   net_decr_issu_cert_dpst
  float
  已发行存款证净减少额
  元
  银行

   net_incr_lnto_pur_resell
  float
  拆出资金及买入返售金融资产净增加额
  元
  银行

   net_incr_ln_to
  float
  拆出资金净增加额
  元
  银行、保险

   net_incr_pur_resell
  float
  买入返售金融资产净增加额
  元
  银行、保险

   net_decr_lnfm_sell_repo
  float
  拆入资金及卖出回购金融资产款净减少额
  元
  银行

   net_decr_ln_fm
  float
  拆入资金净减少额
  元
  银行、证券

   net_decr_sell_repo
  float
  卖出回购金融资产净减少额
  元
  银行、保险

   net_incr_trd_fin
  float
  交易性金融资产净增加额
  元
  银行

   net_decr_trd_liab
  float
  交易性金融负债净减少额
  元
  银行

   cash_pay_indem_orig
  float
  支付原保险合同赔付款项的现金
  元


   net_cash_pay_rin_biz
  float
  支付再保险业务现金净额
  元
  保险

   cash_pay_int_fee
  float
  支付利息、手续费及佣金的现金
  元


   cash_pay_int
  float
  其中：支付利息的现金
  元
  银行

   cash_pay_fee
  float
  支付手续费及佣金的现金
  元
  银行

   ph_dvd_pay
  float
  支付保单红利的现金
  元


   net_decr_ph_dpst_inv
  float
  保户储金及投资款净减少额
  元
  保险

   cash_pay_emp
  float
  支付给职工以及为职工支付的现金



   cash_pay_tax
  float
  支付的各项税费
  元


   net_cash_pay_trd
  float
  支付交易性金融资产现金净额
  元
  保险

   cash_pay_oth_oper
  float
  支付其他与经营活动有关的现金
  元


   net_incr_dspl_trd_fin
  float
  处置交易性金融资产净增加额
  元


   cash_pay_fin_leas
  float
  购买融资租赁资产支付的现金
  元
  银行

   net_decr_agy_secu_pay
  float
  代理买卖证券支付的现金净额（净减少额）
  元
  证券

   net_decr_dspl_trd_fin
  float
  处置交易性金融资产的净减少额
  元
  证券

   cf_out_oper
  float
  经营活动现金流出小计
  元


   net_cf_oper
  float
  经营活动产生的现金流量净额
  元


     二、投资活动产生的现金流量：





   cash_rcv_sale_inv
  float
  收回投资收到的现金
  元


   inv_inc_rcv
  float
  取得投资收益收到的现金
  元


   cash_rcv_dvd_prof
  float
  分得股利或利润所收到的现金
  元
  银行

   cash_rcv_dspl_ast
  float
  处置固定资产、无形资产和其他长期资产收回的现金净额
  元


   cash_rcv_dspl_sub_oth
  float
  处置子公司及其他营业单位收到的现金净额
  元


   cash_rcv_oth_inv
  float
  收到其他与投资活动有关的现金
  元


   cf_in_inv
  float
  投资活动现金流入小计
  元


   pur_fix_intg_ast
  float
  购建固定资产、无形资产和其他长期资产支付的现金
  元


   cash_out_dspl_sub_oth
  float
  处置子公司及其他营业单位流出的现金净额
  元
  保险

   cash_pay_inv
  float
  投资支付的现金
  元


   net_incr_ph_plge_ln
  float
  保户质押贷款净增加额
  元
  保险

   add_cash_pled_dpst
  float
  增加质押和定期存款所支付的现金
  元


   net_incr_plge_ln
  float
  质押贷款净增加额
  元


   net_cash_get_sub
  float
  取得子公司及其他营业单位支付的现金净额
  元


   net_pay_pur_resell
  float
  支付买入返售金融资产现金净额
  元
  证券、保险

   cash_pay_oth_inv
  float
  支付其他与投资活动有关的现金
  元


   cf_out_inv
  float
  投资活动现金流出小计



   net_cf_inv
  float
  投资活动产生的现金流量净额
  元


     三、筹资活动产生的现金流量：





   cash_rcv_cptl
  float
  吸收投资收到的现金
  元


   sub_rcv_ms_inv
  float
  其中：子公司吸收少数股东投资收到的现金
  元


   brw_rcv
  float
  取得借款收到的现金
  元


   cash_rcv_bnd_iss
  float
  发行债券收到的现金
  元


   net_cash_rcv_sell_repo
  float
  收到卖出回购金融资产款现金净额
  元
  保险

   cash_rcv_oth_fin
  float
  收到其他与筹资活动有关的现金
  元


   issu_cert_dpst
  float
  发行存款证
  元
  银行

   cf_in_fin_oth
  float
  筹资活动现金流入其他项目
  元


   cf_in_fin
  float
  筹资活动现金流入小计
  元


   cash_rpay_brw
  float
  偿还债务支付的现金
  元


   cash_pay_bnd_int
  float
  偿付债券利息支付的现金
  元
  银行

   cash_pay_dvd_int
  float
  分配股利、利润或偿付利息支付的现金
  元


   sub_pay_dvd_prof
  float
  其中：子公司支付给少数股东的股利、利润
  元


   cash_pay_oth_fin
  float
  支付其他与筹资活动有关的现金
  元


   net_cash_pay_sell_repo
  float
  支付卖出回购金融资产款现金净额
  元
  保险

   cf_out_fin
  float
  筹资活动现金流出小计
  元


   net_cf_fin
  float
  筹资活动产生的现金流量净额
  元


   efct_er_chg_cash
  float
  四、汇率变动对现金及现金等价物的影响
  元


   net_incr_cash_eq
  float
  五、现金及现金等价物净增加额
  元


   cash_cash_eq_bgn
  float
  加：期初现金及现金等价物余额
  元


   cash_cash_eq_end
  float
  六、期末现金及现金等价物余额
  元


     补充资料 1．将净利润调节为经营活动现金流量：





   net_prof
  float
  净利润
  元


   ast_impr
  float
  资产减值准备
  元


   accr_prvs_ln_impa
  float
  计提贷款减值准备
  元
  银行

   accr_prvs_oth_impa
  float
  计提其他资产减值准备
  元
  银行

   accr_prem_rsv
  float
  提取的保险责任准备金
  元
  保险

   accr_unearn_prem_rsv
  float
  提取的未到期的责任准备金
  元
  保险

   defr_fix_prop
  float
  固定资产和投资性房地产折旧
  元


   depr_oga_cba
  float
  其中:固定资产折旧、油气资产折耗、生产性生物资产折旧
  元


   amor_intg_ast_lt_exp
  float
  无形资产及长期待摊费用等摊销
  元
  银行、证券、保险

   amort_intg_ast
  float
  无形资产摊销
  元


   amort_lt_exp_ppay
  float
  长期待摊费用摊销
  元


   dspl_ast_loss
  float
  处置固定资产、无形资产和其他长期资产的损失
  元


   fair_val_chg_loss
  float
  固定资产报废损失
  元


   fv_chg_loss
  float
  公允价值变动损失
  元


   dfa
  float
  固定资产折旧
  元
  银行

   fin_exp
  float
  财务费用
  元


   inv_loss
  float
  投资损失
  元


   exchg_loss
  float
  汇兑损失
  元
  银行、证券、保险

   dest_incr
  float
  存款的增加
  元
  银行

   loan_decr
  float
  贷款的减少
  元
  银行

   cash_pay_bnd_int_iss
  float
  发行债券利息支出
  元
  银行

   dfr_tax
  float
  递延所得税
  元


   dfr_tax_ast_decr
  float
  其中:递延所得税资产减少
  元


   dfr_tax_liab_incr
  float
  递延所得税负债增加
  元


   invt_decr
  float
  存货的减少
  元


   decr_rcv_oper
  float
  经营性应收项目的减少
  元


   incr_pay_oper
  float
  经营性应付项目的增加
  元


   oth
  float
  其他
  元


   cash_end
  float
  现金的期末余额
  元


   cash_bgn
  float
  减：现金的期初余额
  元


   cash_eq_end
  float
  加:现金等价物的期末余额
  元


   cash_eq_bgn
  float
  减:现金等价物的期初余额
  元


   cred_impr_loss
  float
  信用减值损失
  元


   est_liab_add
  float
  预计负债的增加
  元


   dr_cnv_cptl
  float
  债务转为资本
  元


   cptl_bnd_expr_one_y
  float
  一年内到期的可转换公司债券
  元


   fin_ls_fix_ast
  float
  融资租入固定资产
  元


   amort_dfr_inc
  float
  递延收益摊销
  元


   depr_inv_prop
  float
  投资性房地产折旧
  元


   trd_fin_decr
  float
  交易性金融资产的减少
  元
  证券、保险

   im_net_cf_oper
  float
  间接法-经营活动产生的现金流量净额
  元


   im_net_incr_cash_eq
  float
  间接法-现金及现金等价物净增加额
  元





## #   stk_get_fundamentals_income_pt  - 查询利润表截面数据（多标的）

  查询指定日期截面的股票所属上市公司的利润表数据（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_fundamentals_income_pt(symbols, rpt_type=None, data_type=None, date=None, fields, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型：
1-一季度报
6-中报
9-前三季报
12-年报
2-第二季度
3-第三季度
4-第四季度
默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
100-合并最初（未修正的合并原始）
101-合并原始
102-合并调整
200-母公司最初（未修正的母公司原始）
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始，如果合并原始未修正返回合并最初

   date
  str
  查询日期
  N
  None
  查询时间，时间类型为发布日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  距查询日期最近的发布日期
若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期
若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期
若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报, 2-第二季度, 3-第三季度, 4-第四季度

   data_type
  int
  数据类型
  返回数据的数据类型：100-合并最初（未修正的合并原始） 101-合并原始 102-合并调整 201-母公司原始 202-母公司调整 200-母公司最初（未修正的母公司原始）

   fields
  list[float]
  财务字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考   利润表


   示例：


```
stk_get_fundamentals_income_pt(symbols='SHSE.600000, SZSE.000001', rpt_type=None, data_type=None, date='2022-10-01', fields='inc_oper', df=True)
```

  输出：


```
symbol    pub_date    rpt_date  rpt_type  data_type        inc_oper
0  SZSE.000001  2022-10-25  2022-09-30         9        102 138265000000.00
1  SHSE.600000  2022-10-29  2022-09-30         9        102 143680000000.00
```

  注意：
   1.  为避免未来数据问题，指定查询日期 date 后，返回发布日期小于查询日期下的最新报告日期数据。
   2.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    利润表
     字段名
  类型
  中文名称
  量纲
  说明

     ttl_inc_oper
  float
  营业总收入
  元


   inc_oper
  float
  营业收入
  元


   net_inc_int
  float
  利息净收入
  元
  证券、银行、保险

   exp_int
  float
  利息支出
  元


   net_inc_fee_comm
  float
  手续费及佣金净收入
  元
  证券、银行

   inc_rin_prem
  float
  其中：分保费收入
  元
  保险

   net_inc_secu_agy
  float
  其中:代理买卖证券业务净收入
  元
  证券

   inc_fee_comm
  float
  手续费及佣金收入
  元


   in_prem_earn
  float
  已赚保费
  元
  保险

   inc_in_biz
  float
  其中:保险业务收入
  元
  保险

   rin_prem_cede
  float
  分出保费
  元
  保险

   unear_prem_rsv
  float
  提取未到期责任准备金
  元
  保险

   net_inc_uw
  float
  证券承销业务净收入
  元
  证券

   net_inc_cust_ast_mgmt
  float
  受托客户资产管理业务净收入
  元
  证券

   inc_fx
  float
  汇兑收益
  元


   inc_other_oper
  float
  其他业务收入
  元


   inc_oper_balance
  float
  营业收入平衡项目
  元


   ttl_inc_oper_other
  float
  营业总收入其他项目
  元


   ttl_cost_oper
  float
  营业总成本
  元


   cost_oper
  float
  营业成本
  元


   exp_oper
  float
  营业支出
  元
  证券、银行、保险

   biz_tax_sur
  float
  营业税金及附加
  元


   exp_sell
  float
  销售费用
  元


   exp_adm
  float
  管理费用
  元


   exp_rd
  float
  研发费用
  元


   exp_fin
  float
  财务费用
  元


   int_fee
  float
  其中:利息费用
  元


   inc_int
  float
  利息收入
  元


   exp_oper_adm
  float
  业务及管理费
  元
  证券、银行、保险

   exp_rin
  float
  减:摊回分保费用
  元
  保险

   rfd_prem
  float
  退保金
  元
  保险

   comp_pay
  float
  赔付支出
  元
  保险

   rin_clm_pay
  float
  减:摊回赔付支出
  元
  保险

   draw_insur_liab
  float
  提取保险责任准备金
  元
  保险

   amor_insur_liab
  float
  减:摊回保险责任准备金
  元
  保险

   exp_ph_dvd
  float
  保单红利支出
  元
  保险

   exp_fee_comm
  float
  手续费及佣金支出
  元


   other_oper_cost
  float
  其他业务成本
  元


   oper_exp_balance
  float
  营业支出平衡项目
  元
  证券、银行、保险

   exp_oper_other
  float
  营业支出其他项目
  元
  证券、银行、保险

   ttl_cost_oper_other
  float
  营业总成本其他项目
  元


     其他经营收益


  元


   inc_inv
  float
  投资收益
  元


   inv_inv_jv_p
  float
  对联营企业和合营企业的投资收益
  元


   inc_ast_dspl
  float
  资产处置收益
  元


   ast_impr_loss
  float
  资产减值损失(新)
  元


   cred_impr_loss
  float
  信用减值损失(新)
  元


   inc_fv_chg
  float
  公允价值变动收益
  元


   inc_other
  float
  其他收益
  元


   oper_prof_balance
  float
  营业利润平衡项目
  元


   oper_prof
  float
  营业利润
  元


   inc_noper
  float
  营业外收入
  元


   exp_noper
  float
  营业外支出
  元


   ttl_prof_balance
  float
  利润总额平衡项目
  元


   oper_prof_other
  float
  营业利润其他项目
  元


   ttl_prof
  float
  利润总额
  元


   inc_tax
  float
  所得税费用
  元


   net_prof
  float
  净利润
  元


   oper_net_prof
  float
  持续经营净利润
  元


   net_prof_pcom
  float
  归属于母公司股东的净利润
  元


   min_int_inc
  float
  少数股东损益
  元


   end_net_prof
  float
  终止经营净利润
  元


   net_prof_other
  float
  净利润其他项目
  元


   eps_base
  float
  基本每股收益
  元


   eps_dil
  float
  稀释每股收益
  元


   other_comp_inc
  float
  其他综合收益
  元


   other_comp_inc_pcom
  float
  归属于母公司股东的其他综合收益
  元


   other_comp_inc_min
  float
  归属于少数股东的其他综合收益
  元


   ttl_comp_inc
  float
  综合收益总额
  元


   ttl_comp_inc_pcom
  float
  归属于母公司所有者的综合收益总额
  元


   ttl_comp_inc_min
  float
  归属于少数股东的综合收益总额
  元


   prof_pre_merge
  float
  被合并方在合并前实现利润
  元


   net_rsv_in_contr
  float
  提取保险合同准备金净额
  元


   net_pay_comp
  float
  赔付支出净额
  元


   net_loss_ncur_ast
  float
  非流动资产处置净损失
  元


   amod_fin_asst_end
  float
  以摊余成本计量的金融资产终止确认收益
  元


   cash_flow_hedging_pl
  float
  现金流量套期损益的有效部分
  元


   cur_trans_diff
  float
  外币财务报表折算差额
  元


   gain_ncur_ast
  float
  非流动资产处置利得
  元


   afs_fv_chg_pl
  float
  可供出售金融资产公允价值变动损益
  元


   oth_eqy_inv_fv_chg
  float
  其他权益工具投资公允价值变动
  元


   oth_debt_inv_fv_chg
  float
  其他债权投资公允价值变动
  元


   oth_debt_inv_cred_impr
  float
  其他债权投资信用减值准备
  元





## #   stk_get_finance_prime_pt  - 查询财务主要指标截面数据（多标的）

  查询指定日期截面上，股票所属上市公司的财务主要指标数据（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_finance_prime_pt(symbols, fields, rpt_type=None, data_type=None, date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务主要指标， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型：
1-一季度报
6-中报
9-前三季报
12-年报
默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
100-合并最初（未修正的合并原始）
101-合并原始
102-合并调整
200-母公司最初（未修正的母公司原始）
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始，如果合并原始未修正返回合并最初

   date
  str
  查询日期
  N
  None
  查询时间，时间类型为发布日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  距查询日期最近的发布日期
若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期
若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期
若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：100-合并最初（未修正的合并原始） 101-合并原始 102-合并调整 201-母公司原始 202-母公司调整 200-母公司最初（未修正的母公司原始）

   fields
  list[float]
  财务字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考   财务主要指标


   示例：


```
stk_get_finance_prime_pt(symbols=['SZSE.000001', 'SZSE.300002'], fields='eps_basic,eps_dil', rpt_type=None, data_type=None, date='2023-06-19', df=True)
```

  输出：


```
symbol    pub_date    rpt_date  rpt_type  data_type  eps_dil  eps_basic
0  SZSE.000001  2023-04-25  2023-03-31         1        101   0.6500     0.6500
1  SZSE.300002  2023-04-27  2023-03-31         1        101   0.0914     0.0914
```

  注意：
   1.  为避免未来数据问题，指定查询日期 date 后，返回发布日期小于查询日期下的最新报告日期数据。
   2.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
   3.  财务主要指标由上市公司选择性公布，未公布则对应指标返回NaN. 如需获取标准公开的财务指标，请优先使用三大财务报表数据函数（stk_get_fundamentals_balance_pt - 查询资产负债表截面数据（多标的）、stk_get_fundamentals_cashflow_pt - 查询现金流量表截面数据（多标的）、stk_get_fundamentals_income_pt - 查询利润表截面数据（多标的））查询。
    财务主要指标
     字段名
  类型
  中文名称
  量纲
  说明

     eps_basic
  float
  基本每股收益
  元


   eps_dil
  float
  稀释每股收益
  元


   eps_basic_cut
  float
  扣除非经常性损益后的基本每股收益
  元


   eps_dil_cut
  float
  扣除非经常性损益后的稀释每股收益
  元


   net_cf_oper_ps
  float
  每股经营活动产生的现金流量净额
  元


   bps_pcom_ps
  float
  归属于母公司股东的每股净资产
  元


   ttl_ast
  float
  总资产
  元


   ttl_liab
  float
  总负债
  元


   share_cptl
  float
  股本
  股


   ttl_inc_oper
  float
  营业总收入
  元


   inc_oper
  float
  营业收入
  元


   oper_prof
  float
  营业利润
  元


   ttl_prof
  float
  利润总额
  元


   ttl_eqy_pcom
  float
  归属于母公司股东的所有者权益
  元


   net_prof_pcom
  float
  归属于母公司股东的净利润
  元


   net_prof_pcom_cut
  float
  扣除非经常性损益后归属于母公司股东的净利润
  元


   roe
  float
  全面摊薄净资产收益率
  %


   roe_weight_avg
  float
  加权平均净资产收益率
  %


   roe_cut
  float
  扣除非经常性损益后的全面摊薄净资产收益率
  %


   roe_weight_avg_cut
  float
  扣除非经常性损益后的加权平均净资产收益率
  %


   net_cf_oper
  float
  经营活动产生的现金流量净额
  元


   eps_yoy
  float
  每股收益同比比例
  %


   inc_oper_yoy
  float
  营业收入同比比例
  %


   ttl_inc_oper_yoy
  float
  营业总收入同比比例
  %


   net_prof_pcom_yoy
  float
  归母净利润同比比例
  %


   bps_sh
  float
  归属于普通股东的每股净资产
  元


   net_asset
  float
  归属于普通股东的净资产
  元


   net_prof
  float
  归属于普通股东的净利润
  元


   net_prof_cut
  float
  扣除非经常性损益后归属于普通股股东的净利润
  元





## #   stk_get_finance_deriv_pt  - 查询财务衍生指标截面数据（多标的）

  查询指定日期截面上，股票所属上市公司的财务衍生指标数据（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_finance_deriv_pt(symbols, fields, rpt_type=None, data_type=None, date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务衍生指标， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型：
1-一季度报
6-中报
9-前三季报
12-年报
默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。 101-合并原始
102-合并调整 201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始

   date
  str
  查询日期
  N
  None
  查询时间，时间类型为发布日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  距查询日期最近的发布日期
若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期
若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期
若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：101-合并原始, 102-合并调整, 201-母公司原始, 202-母公司调整

   fields
  list[float]
  财务字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考   财务衍生指标指标


   示例：


```
stk_get_finance_deriv_pt(symbols=['SZSE.000001', 'SZSE.300002'], fields='eps_basic,eps_dil2',
                                   rpt_type=None, data_type=None, date='2023-06-19', df=True)
```

  输出：


```
symbol    pub_date    rpt_date  ...  data_type  eps_basic  eps_dil2
0  SZSE.000001  2023-04-25  2023-03-31  ...        102     0.6500    0.6500
1  SZSE.300002  2023-04-27  2023-03-31  ...        102     0.0914    0.0914
```

  注意：
   1.  为避免未来数据问题，指定查询日期 date 后，返回发布日期小于查询日期下的最新报告日期数据。
   2.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    财务衍生指标指标
     字段名
  类型
  中文名称
  量纲
  说明

     eps_basic
  float
  每股收益EPS(基本)
  元


   eps_dil2
  float
  每股收益EPS(稀释)
  元


   eps_dil
  float
  每股收益EPS(期末股本摊薄)
  元


   eps_basic_cut
  float
  每股收益EPS(扣除/基本)
  元


   eps_dil2_cut
  float
  每股收益EPS(扣除/稀释)
  元


   eps_dil_cut
  float
  每股收益EPS(扣除/期末股本摊薄)
  元


   bps
  float
  每股净资产BPS
  元


   net_cf_oper_ps
  float
  每股经营活动产生的现金流量净额
  元


   ttl_inc_oper_ps
  float
  每股营业总收入
  元


   inc_oper_ps
  float
  每股营业收入
  元


   ebit_ps
  float
  每股息税前利润
  元


   cptl_rsv_ps
  float
  每股资本公积
  元


   sur_rsv_ps
  float
  每股盈余公积
  元


   retain_prof_ps
  float
  每股未分配利润
  元


   retain_inc_ps
  float
  每股留存收益
  元


   net_cf_ps
  float
  每股现金流量净额
  元


   fcff_ps
  float
  每股企业自由现金流量
  元


   fcfe_ps
  float
  每股股东自由现金流量
  元


   ebitda_ps
  float
  每股EBITDA
  元


   roe
  float
  净资产收益率ROE(摊薄)
  %


   roe_weight
  float
  净资产收益率ROE(加权)
  %


   roe_avg
  float
  净资产收益率ROE(平均)
  %


   roe_cut
  float
  净资产收益率ROE(扣除/摊薄)
  %


   roe_weight_cut
  float
  净资产收益率ROE(扣除/加权)
  %


   ocf_toi
  float
  经营性现金净流量/营业总收入



   eps_dil_yoy
  float
  稀释每股收益同比增长率
  %


   net_cf_oper_ps_yoy
  float
  每股经营活动中产生的现金流量净额同比增长率
  %


   ttl_inc_oper_yoy
  float
  营业总收入同比增长率
  %


   inc_oper_yoy
  float
  营业收入同比增长率
  %


   oper_prof_yoy
  float
  营业利润同比增长率
  %


   ttl_prof_yoy
  float
  利润总额同比增长率
  %


   net_prof_pcom_yoy
  float
  归属母公司股东的净利润同比增长率
  %


   net_prof_pcom_cut_yoy
  float
  归属母公司股东的净利润同比增长率(扣除非经常性损益)
  %


   net_cf_oper_yoy
  float
  经营活动产生的现金流量净额同比增长率
  %


   roe_yoy
  float
  净资产收益率同比增长率(摊薄)
  %


   net_asset_yoy
  float
  净资产同比增长率
  %


   ttl_liab_yoy
  float
  总负债同比增长率
  %


   ttl_asset_yoy
  float
  总资产同比增长率
  %


   net_cash_flow_yoy
  float
  现金净流量同比增长率
  %


   bps_gr_begin_year
  float
  每股净资产相对年初增长率
  %


   ttl_asset_gr_begin_year
  float
  资产总计相对年初增长率
  %


   ttl_eqy_pcom_gr_begin_year
  float
  归属母公司的股东权益相对年初增长率
  %


   net_debt_eqy_ev
  float
  净债务/股权价值
  %


   int_debt_eqy_ev
  float
  带息债务/股权价值



   eps_bas_yoy
  float
  基本每股收益同比增长率
  %


   ebit
  float
  EBIT(正推法)
  元


   ebitda
  float
  EBITDA(正推法)
  元


   ebit_inverse
  float
  EBIT(反推法)
  元


   ebitda_inverse
  float
  EBITDA(反推法)
  元


   nr_prof_loss
  float
  非经常性损益
  元


   net_prof_cut
  float
  扣除非经常性损益后的净利润
  元


   gross_prof
  float
  毛利润
  元


   oper_net_inc
  float
  经营活动净收益
  元


   val_chg_net_inc
  float
  价值变动净收益
  元


   exp_rd
  float
  研发费用
  元


   ttl_inv_cptl
  float
  全部投入资本
  元


   work_cptl
  float
  营运资本
  元


   net_work_cptl
  float
  净营运资本
  元


   tg_asset
  float
  有形资产
  元


   retain_inc
  float
  留存收益
  元


   int_debt
  float
  带息债务
  元


   net_debt
  float
  净债务
  元


   curr_liab_non_int
  float
  无息流动负债
  元


   ncur_liab_non_int
  float
  无息非流动负债
  元


   fcff
  float
  企业自由现金流量FCFF
  元


   fcfe
  float
  股权自由现金流量FCFE
  元


   cur_depr_amort
  float
  当期计提折旧与摊销
  元


   eqy_mult_dupont
  float
  权益乘数(杜邦分析)



   net_prof_pcom_np
  float
  归属母公司股东的净利润/净利润
  %


   net_prof_tp
  float
  净利润/利润总额
  %


   ttl_prof_ebit
  float
  利润总额/息税前利润
  %


   roe_cut_avg
  float
  净资产收益率ROE(扣除/平均)
  %


   roe_add
  float
  净资产收益率ROE(增发条件)
  %


   roe_ann
  float
  净资产收益率ROE(年化)
  %


   roa
  float
  总资产报酬率ROA
  %


   roa_ann
  float
  总资产报酬率ROA(年化)
  %


   jroa
  float
  总资产净利率
  %


   jroa_ann
  float
  总资产净利率(年化)
  %


   roic
  float
  投入资本回报率ROIC
  %


   sale_npm
  float
  销售净利率
  %


   sale_gpm
  float
  销售毛利率
  %


   sale_cost_rate
  float
  销售成本率
  %


   sale_exp_rate
  float
  销售期间费用率
  %


   net_prof_toi
  float
  净利润/营业总收入
  %


   oper_prof_toi
  float
  营业利润/营业总收入
  %


   ebit_toi
  float
  息税前利润/营业总收入
  %


   ttl_cost_oper_toi
  float
  营业总成本/营业总收入
  %


   exp_oper_toi
  float
  营业费用/营业总收入
  %


   exp_admin_toi
  float
  管理费用/营业总收入
  %


   exp_fin_toi
  float
  财务费用/营业总收入
  %


   ast_impr_loss_toi
  float
  资产减值损失/营业总收入
  %


   ebitda_toi
  float
  EBITDA/营业总收入
  %


   oper_net_inc_tp
  float
  经营活动净收益/利润总额
  %


   val_chg_net_inc_tp
  float
  价值变动净收益/利润总额
  %


   net_exp_noper_tp
  float
  营业外支出净额/利润总额



   inc_tax_tp
  float
  所得税/利润总额
  %


   net_prof_cut_np
  float
  扣除非经常性损益的净利润/净利润
  %


   eqy_mult
  float
  权益乘数



   curr_ast_ta
  float
  流动资产/总资产
  %


   ncurr_ast_ta
  float
  非流动资产/总资产
  %


   tg_ast_ta
  float
  有形资产/总资产
  %


   ttl_eqy_pcom_tic
  float
  归属母公司股东的权益/全部投入资本
  %


   int_debt_tic
  float
  带息负债/全部投入资本
  %


   curr_liab_tl
  float
  流动负债/负债合计
  %


   ncurr_liab_tl
  float
  非流动负债/负债合计
  %


   ast_liab_rate
  float
  资产负债率
  %


   quick_rate
  float
  速动比率



   curr_rate
  float
  流动比率



   cons_quick_rate
  float
  保守速动比率



   liab_eqy_rate
  float
  产权比率



   ttl_eqy_pcom_tl
  float
  归属母公司股东的权益/负债合计



   ttl_eqy_pcom_debt
  float
  归属母公司股东的权益/带息债务



   tg_ast_tl
  float
  有形资产/负债合计



   tg_ast_int_debt
  float
  有形资产/带息债务



   tg_ast_net_debt
  float
  有形资产/净债务



   ebitda_tl
  float
  息税折旧摊销前利润/负债合计



   net_cf_oper_tl
  float
  经营活动产生的现金流量净额/负债合计



   net_cf_oper_int_debt
  float
  经营活动产生的现金流量净额/带息债务



   net_cf_oper_curr_liab
  float
  经营活动产生的现金流量净额/流动负债



   net_cf_oper_net_liab
  float
  经营活动产生的现金流量净额/净债务



   ebit_int_cover
  float
  已获利息倍数



   long_liab_work_cptl
  float
  长期债务与营运资金比率



   ebitda_int_debt
  float
  EBITDA/带息债务
  %


   oper_cycle
  float
  营业周期
  天


   inv_turnover_days
  float
  存货周转天数
  天


   acct_rcv_turnover_days
  float
  应收账款周转天数(含应收票据)
  天


   inv_turnover_rate
  float
  存货周转率
  次


   acct_rcv_turnover_rate
  float
  应收账款周转率(含应收票据)
  次


   curr_ast_turnover_rate
  float
  流动资产周转率
  次


   fix_ast_turnover_rate
  float
  固定资产周转率
  次


   ttl_ast_turnover_rate
  float
  总资产周转率
  次


   cash_rcv_sale_oi
  float
  销售商品提供劳务收到的现金/营业收入
  %


   net_cf_oper_oi
  float
  经营活动产生的现金流量净额/营业收入
  %


   net_cf_oper_oni
  float
  经营活动产生的现金流量净额/经营活动净收益



   cptl_exp_da
  float
  资本支出/折旧摊销
  %


   cash_rate
  float
  现金比率



   acct_pay_turnover_days
  float
  应付账款周转天数(含应付票据)
  天


   acct_pay_turnover_rate
  float
  应付账款周转率(含应付票据)
  次


   net_oper_cycle
  float
  净营业周期
  天


   ttl_cost_oper_yoy
  float
  营业总成本同比增长率
  %


   net_prof_yoy
  float
  净利润同比增长率
  %


   net_cf_oper_np
  float
  经营活动产生的现金流量净额/净利润
  %





## #   stk_get_daily_valuation_pt  - 查询估值指标单日截面数据（多标的）

  查询指定日期截面上，股票的单日估值指标（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_daily_valuation_pt(symbols, fields, trade_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的交易衍生指标， 如有多个字段，中间用 英文逗号 分隔

   trade_date
  str
  查询日期
  N
  None
  查询时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   trade_date
  str
  交易日期


   fields
  list[float]
  指标字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考   估值指标


   示例：


```
stk_get_daily_valuation_pt(symbols=['SZSE.000001', 'SZSE.300002'], fields='pe_ttm,pe_lyr,pe_mrq',
                               trade_date=None, df=True)
```

  输出：


```
symbol  trade_date   pe_ttm   pe_mrq   pe_lyr
0  SZSE.000001  2023-06-26   4.5900   3.7145   4.7666
1  SZSE.300002  2023-06-26  39.3144  36.2480  47.6621
```

  注意：
   1.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    估值指标
     字段名
  类型
  中文名称
  量纲
  说明

     pe_ttm
  float
  市盈率(TTM)
  倍


   pe_lyr
  float
  市盈率(最新年报LYR)
  倍


   pe_mrq
  float
  市盈率(最新报告期MRQ)
  倍


   pe_1q
  float
  市盈率(当年一季×4)
  倍


   pe_2q
  float
  市盈率(当年中报×2)
  倍


   pe_3q
  float
  市盈率(当年三季×4/3)
  倍


   pe_ttm_cut
  float
  市盈率(TTM) 扣除非经常性损益
  倍


   pe_lyr_cut
  float
  市盈率(最新年报LYR) 扣除非经常性损益
  倍


   pe_mrq_cut
  float
  市盈率(最新报告期MRQ) 扣除非经常性损益
  倍


   pe_1q_cut
  float
  市盈率(当年一季×4) 扣除非经常性损益
  倍


   pe_2q_cut
  float
  市盈率(当年中报×2) 扣除非经常性损益
  倍


   pe_3q_cut
  float
  市盈率(当年三季×4/3) 扣除非经常性损益
  倍


   pb_lyr
  float
  市净率(最新年报LYR)
  倍


   pb_mrq
  float
  市净率(最新报告期MRQ)
  倍


   pb_lyr_1
  float
  市净率(剔除其他权益工具，最新年报LYR)
  倍


   pb_mrq_1
  float
  市净率(剔除其他权益工具，最新报告期MRQ)
  倍


   pcf_ttm_oper
  float
  市现率(经营现金流,TTM)
  倍


   pcf_ttm_ncf
  float
  市现率(现金净流量,TTM)
  倍


   pcf_lyr_oper
  float
  市现率(经营现金流,最新年报LYR)
  倍


   pcf_lyr_ncf
  float
  市现率(现金净流量,最新年报LYR)
  倍


   ps_ttm
  float
  市销率(TTM)
  倍


   ps_lyr
  float
  市销率(最新年报LYR)
  倍


   ps_mrq
  float
  市销率(最新报告期MRQ)
  倍


   ps_1q
  float
  市销率(当年一季×4)
  倍


   ps_2q
  float
  市销率(当年中报×2)
  倍


   ps_3q
  float
  市销率(当年三季×4/3)
  倍


   peg_lyr
  float
  历史PEG值(当年年报增长率)



   peg_mrq
  float
  历史PEG值(最新报告期增长率)



   peg_1q
  float
  历史PEG值(当年1季*4较上年年报增长率)



   peg_2q
  float
  历史PEG值(当年中报*2较上年年报增长率)



   peg_3q
  float
  历史PEG值(当年3季*4/3较上年年报增长率)



   peg_np_cgr
  float
  历史PEG值(PE_TTM较净利润3年复合增长率)



   peg_npp_cgr
  float
  历史PEG值(PE_TTM较净利润3年复合增长率)



   dy_ttm
  float
  股息率(滚动 12 月TTM)
  %


   dy_lfy
  float
  股息率(上一财年LFY)
  %





## #   stk_get_daily_mktvalue_pt  - 查询市值指标单日截面数据（多标的）

  查询指定日期截面上，股票的单日市值截面数据（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_daily_mktvalue_pt(symbols, fields, trade_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的交易衍生指标， 如有多个字段，中间用 英文逗号 分隔

   trade_date
  str
  查询日期
  N
  None
  查询时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   trade_date
  str
  交易日期


   fields
  list[float]
  指标字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考    市值指标


   示例：


```
stk_get_daily_mktvalue_pt(symbols=['SZSE.000001', 'SZSE.300002'], fields='tot_mv,tot_mv_csrc,a_mv',
                               trade_date=None, df=True)
```

  输出：


```
symbol  trade_date        a_mv      tot_mv  tot_mv_csrc
0  SZSE.000001  2023-06-26  2.1696e+11  2.1696e+11   2.1696e+11
1  SZSE.300002  2023-06-26  2.5828e+10  2.5828e+10   2.5828e+10
```

  注意：
   1.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    市值指标
     字段名
  类型
  中文名称
  量纲
  说明

     tot_mv
  float
  总市值
  元


   tot_mv_csrc
  float
  总市值(证监会算法)
  元


   a_mv
  float
  A股流通市值(含限售股)
  元


   a_mv_ex_ltd
  float
  A股流通市值(不含限售股)
  元


   b_mv
  float
  B股流通市值(含限售股，折人民币)
  元


   b_mv_ex_ltd
  float
  B股流通市值(不含限售股，折人民币)
  元


   ev
  float
  企业价值(含货币资金)(EV1)
  元


   ev_ex_curr
  float
  企业价值(剔除货币资金)(EV2)
  元


   ev_ebitda
  float
  企业倍数
  倍


   equity_value
  float
  股权价值
  元





## #   stk_get_daily_basic_pt  - 查询股本等基础指标单日截面数据（多标的）

  查询指定日期截面上，股票的单日基础指标截面数据（point-in-time）
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_daily_basic_pt(symbols, fields, trade_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  股票代码
  Y
  无
  必填，可输入多个，使用时参考 symbol  采用 str 格式时，多个标的代码必须用 英文逗号 分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例：['SHSE.600008', 'SZSE.000002']

   fields
  str
  返回字段
  Y
  无
  指定需要返回的交易衍生指标， 如有多个字段，中间用 英文逗号 分隔

   trade_date
  str
  查询日期
  N
  None
  查询时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   trade_date
  str
  交易日期


   fields
  list[float]
  指标字段数据
  指定查询  fields 字段的数值. 支持的字段名请参考    基础指标


   示例：


```
stk_get_daily_basic_pt(symbols=['SZSE.000001', 'SZSE.300002'], fields='tclose,turnrate,ttl_shr',
                                  trade_date=None, df=True)
```

  输出：


```
symbol  trade_date  turnrate  tclose     ttl_shr
0  SZSE.000001  2023-06-27    0.2379   11.28  1.9406e+10
1  SZSE.300002  2023-06-27    7.3596   13.44  1.9611e+09
```

  注意：
   1.  如果 fields 参数的财务字段填写不正确，或填写空字段 "" ，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    基础指标
     字段名
  类型
  中文名称
  量纲
  说明

     tclose
  float
  收盘价
  元


   turnrate
  float
  当日换手率
  %


   ttl_shr
  float
  总股本
  股


   circ_shr
  float
  流通股本（流通股本=无限售条件流通股本+有限售条件流通股本）
  股


   ttl_shr_unl
  float
  无限售条件流通股本(行情软件定义的流通股)
  股


   ttl_shr_ltd
  float
  有限售条件股本
  股


   a_shr_unl
  float
  无限售条件流通股本(A股)
  股


   h_shr_unl
  float
  无限售条件流通股本(H股)
  股





## #   stk_get_fundamentals_balance  - 查询资产负债表数据

  查询指定时间段某一股票所属上市公司的资产负债表数据
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_fundamentals_balance(symbol, rpt_type=None, data_type=None, start_date=None, end_date=None, fields, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型： 1-一季度报
6-中报
9-前三季报
12-年报 默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
101-合并原始
102-合并调整
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期 若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期 若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：101-合并原始, 102-合并调整, 201-母公司原始, 202-母公司调整

   fields
  list[float]
  财务字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   资产负债表


   示例：


```
stk_get_fundamentals_balance(symbol='SHSE.600000', rpt_type=12, data_type=None, start_date='2022-12-31', end_date='2022-12-31', fields='lt_eqy_inv', df=True)
```

  输出：


```
symbol    pub_date    rpt_date  rpt_type  data_type    lt_eqy_inv
0  SHSE.600000  2022-10-29  2021-12-31        12        102 2819000000.00
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近报告日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  若在指定历史时间段内，有多个同一类型报表（如不同年份的一季度报表），将按照报告日期顺序返回。
   3.  如果 fields 参数的财务字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    资产负债表
     字段名
  类型
  中文名称
  量纲
  说明

       流动资产(资产)





   cash_bal_cb
  float
  现金及存放中央银行款项
  元
  银行

   dpst_ob
  float
  存放同业款项
  元
  银行

   mny_cptl
  float
  货币资金
  元


   cust_cred_dpst
  float
  客户信用资金存款
  元
  证券

   cust_dpst
  float
  客户资金存款
  元
  证券

   pm
  float
  贵金属
  元
  银行

   bal_clr
  float
  结算备付金
  元


   cust_rsv
  float
  客户备付金
  元
  证券

   ln_to_ob
  float
  拆出资金
  元


   fair_val_fin_ast
  float
  以公允价值计量且其变动计入当期损益的金融资产
  元


   ppay
  float
  预付款项
  元


   fin_out
  float
  融出资金
  元


   trd_fin_ast
  float
  交易性金融资产
  元


   deriv_fin_ast
  float
  衍生金融资产
  元


   note_acct_rcv
  float
  应收票据及应收账款
  元


   note_rcv
  float
  应收票据
  元


   acct_rcv
  float
  应收账款
  元


   acct_rcv_fin
  float
  应收款项融资
  元


   int_rcv
  float
  应收利息
  元


   dvd_rcv
  float
  应收股利
  元


   oth_rcv
  float
  其他应收款
  元


   in_prem_rcv
  float
  应收保费
  元


   rin_acct_rcv
  float
  应收分保账款
  元


   rin_rsv_rcv
  float
  应收分保合同准备金
  元
  保险

   rcv_un_prem_rin_rsv
  float
  应收分保未到期责任准备金
  元


   rcv_clm_rin_rsv
  float
  应收分保未决赔偿准备金
  元
  保险

   rcv_li_rin_rsv
  float
  应收分保寿险责任准备金
  元
  保险

   rcv_lt_hi_rin_rsv
  float
  应收分保长期健康险责任准备金
  元
  保险

   ph_plge_ln
  float
  保户质押贷款
  元
  保险

   ttl_oth_rcv
  float
  其他应收款合计
  元


   rfd_dpst
  float
  存出保证金
  元
  证券、保险

   term_dpst
  float
  定期存款
  元
  保险

   pur_resell_fin
  float
  买入返售金融资产
  元


   aval_sale_fin
  float
  可供出售金融资产
  元


   htm_inv
  float
  持有至到期投资
  元


   hold_for_sale
  float
  持有待售资产
  元


   acct_rcv_inv
  float
  应收款项类投资
  元
  保险

   invt
  float
  存货
  元


   contr_ast
  float
  合同资产
  元


   ncur_ast_one_y
  float
  一年内到期的非流动资产
  元


   oth_cur_ast
  float
  其他流动资产
  元


   cur_ast_oth_item
  float
  流动资产其他项目
  元


   ttl_cur_ast
  float
  流动资产合计
  元


     非流动资产(资产)





   loan_adv
  float
  发放委托贷款及垫款
  元


   cred_inv
  float
  债权投资
  元


   oth_cred_inv
  float
  其他债权投资
  元


   lt_rcv
  float
  长期应收款
  元


   lt_eqy_inv
  float
  长期股权投资
  元


   oth_eqy_inv
  float
  其他权益工具投资
  元


   rfd_cap_guar_dpst
  float
  存出资本保证金
  元
  保险

   oth_ncur_fin_ast
  float
  其他非流动金融资产
  元


   amor_cos_fin_ast_ncur
  float
  以摊余成本计量的金融资产（非流动）
  元


   fair_val_oth_inc_ncur
  float
  以公允价值计量且其变动计入其他综合收益的金融资产（非流动）
  元


   inv_prop
  float
  投资性房地产
  元


   fix_ast
  float
  固定资产
  元


   const_prog
  float
  在建工程
  元


   const_matl
  float
  工程物资
  元


   fix_ast_dlpl
  float
  固定资产清理
  元


   cptl_bio_ast
  float
  生产性生物资产
  元


   oil_gas_ast
  float
  油气资产
  元


   rig_ast
  float
  使用权资产
  元


   intg_ast
  float
  无形资产
  元


   trd_seat_fee
  float
  交易席位费
  元
  证券

   dev_exp
  float
  开发支出
  元


   gw
  float
  商誉
  元


   lt_ppay_exp
  float
  长期待摊费用
  元


   dfr_tax_ast
  float
  递延所得税资产
  元


   oth_ncur_ast
  float
  其他非流动资产
  元


   ncur_ast_oth_item
  float
  非流动资产其他项目
  元


   ttl_ncur_ast
  float
  非流动资产合计
  元


   oth_ast
  float
  其他资产
  元
  银行、证券、保险

   ast_oth_item
  float
  资产其他项目
  元


   ind_acct_ast
  float
  独立账户资产
  元
  保险

   ttl_ast
  float
  资产总计
  元


     流动负债(负债)





   brw_cb
  float
  向中央银行借款
  元


   dpst_ob_fin_inst
  float
  同业和其他金融机构存放款项
  元
  银行、保险

   ln_fm_ob
  float
  拆入资金
  元


   fair_val_fin_liab
  float
  以公允价值计量且其变动计入当期损益的金融负债
  元


   sht_ln
  float
  短期借款
  元


   adv_acct
  float
  预收款项
  元


   contr_liab
  float
  合同负债
  元


   trd_fin_liab
  float
  交易性金融负债
  元


   deriv_fin_liab
  float
  衍生金融负债
  元


   sell_repo_ast
  float
  卖出回购金融资产款
  元


   cust_bnk_dpst
  float
  吸收存款
  元
  银行、保险

   dpst_cb_note_pay
  float
  存款证及应付票据
  元
  银行

   dpst_cb
  float
  存款证
  元
  银行

   acct_rcv_adv
  float
  预收账款
  元
  保险

   in_prem_rcv_adv
  float
  预收保费
  元
  保险

   fee_pay
  float
  应付手续费及佣金
  元


   note_acct_pay
  float
  应付票据及应付账款
  元


   stlf_pay
  float
  应付短期融资款
  元


   note_pay
  float
  应付票据
  元


   acct_pay
  float
  应付账款
  元


   rin_acct_pay
  float
  应付分保账款
  元


   emp_comp_pay
  float
  应付职工薪酬
  元


   tax_pay
  float
  应交税费
  元


   int_pay
  float
  应付利息
  元


   dvd_pay
  float
  应付股利
  元


   ph_dvd_pay
  float
  应付保单红利
  元
  保险

   indem_pay
  float
  应付赔付款
  元
  保险

   oth_pay
  float
  其他应付款
  元


   ttl_oth_pay
  float
  其他应付款合计
  元


   ph_dpst_inv
  float
  保户储金及投资款
  元
  保险

   in_contr_rsv
  float
  保险合同准备金
  元
  保险

   un_prem_rsv
  float
  未到期责任准备金
  元
  保险

   clm_rin_rsv
  float
  未决赔款准备金
  元
  保险

   li_liab_rsv
  float
  寿险责任准备金
  元
  保险

   lt_hi_liab_rsv
  float
  长期健康险责任准备金
  元
  保险

   cust_bnk_dpst_fin
  float
  吸收存款及同业存放
  元


   inter_pay
  float
  内部应付款
  元


   agy_secu_trd
  float
  代理买卖证券款
  元


   agy_secu_uw
  float
  代理承销证券款
  元


   sht_bnd_pay
  float
  应付短期债券
  元


   est_cur_liab
  float
  预计流动负债
  元


   liab_hold_for_sale
  float
  持有待售负债
  元


   ncur_liab_one_y
  float
  一年内到期的非流动负债
  元


   oth_cur_liab
  float
  其他流动负债
  元


   cur_liab_oth_item
  float
  流动负债其他项目
  元


   ttl_cur_liab
  float
  流动负债合计
  元


     非流动负债（负债）





   lt_ln
  float
  长期借款
  元


   lt_pay
  float
  长期应付款
  元


   leas_liab
  float
  租赁负债



   dfr_inc
  float
  递延收益
  元


   dfr_tax_liab
  float
  递延所得税负债
  元


   bnd_pay
  float
  应付债券
  元


   bnd_pay_pbd
  float
  其中:永续债
  元


   bnd_pay_pfd
  float
  其中:优先股
  元


   oth_ncur_liab
  float
  其他非流动负债
  元


   spcl_pay
  float
  专项应付款
  元


   ncur_liab_oth_item
  float
  非流动负债其他项目
  元


   lt_emp_comp_pay
  float
  长期应付职工薪酬
  元


   est_liab
  float
  预计负债
  元


   oth_liab
  float
  其他负债
  元
  银行、证券、保险

   liab_oth_item
  float
  负债其他项目
  元
  银行、证券、保险

   ttl_ncur_liab
  float
  非流动负债合计
  元


   ind_acct_liab
  float
  独立账户负债
  元
  保险

   ttl_liab
  float
  负债合计
  元


     所有者权益(或股东权益)





   paid_in_cptl
  float
  实收资本（或股本）
  元


   oth_eqy
  float
  其他权益工具
  元


   oth_eqy_pfd
  float
  其中:优先股
  元


   oth_eqy_pbd
  float
  其中:永续债
  元


   oth_eqy_oth
  float
  其中:其他权益工具
  元


   cptl_rsv
  float
  资本公积
  元


   treas_shr
  float
  库存股
  元


   oth_comp_inc
  float
  其他综合收益
  元


   spcl_rsv
  float
  专项储备
  元


   sur_rsv
  float
  盈余公积
  元


   rsv_ord_rsk
  float
  一般风险准备
  元


   trd_risk_rsv
  float
  交易风险准备
  元
  证券

   ret_prof
  float
  未分配利润
  元


   sugg_dvd
  float
  建议分派股利
  元
  银行

   eqy_pcom_oth_item
  float
  归属于母公司股东权益其他项目
  元


   ttl_eqy_pcom
  float
  归属于母公司股东权益合计
  元


   min_sheqy
  float
  少数股东权益
  元


   sheqy_oth_item
  float
  股东权益其他项目
  元


   ttl_eqy
  float
  股东权益合计
  元


   ttl_liab_eqy
  float
  负债和股东权益合计
  元





## #   stk_get_fundamentals_cashflow  - 查询现金流量表数据

  查询指定时间段某一股票所属上市公司的现金流量表数据
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_fundamentals_cashflow(symbol, rpt_type=None, data_type=None, start_date=None, end_date=None, fields, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型：
1-一季度报
6-中报
9-前三季报
12-年报
默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
101-合并原始
102-合并调整
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期 若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期 若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：101-合并原始, 102-合并调整, 201-母公司原始, 202-母公司调整

   fields
  list[float]
  财务字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   现金流量表


   示例：


```
stk_get_fundamentals_cashflow(symbol='SHSE.600000', rpt_type=None, data_type=101, start_date='2022-12-31', end_date='2022-12-31', fields='cash_pay_fee', df=True)
```

  输出：


```
symbol    pub_date    rpt_date  rpt_type  data_type  cash_pay_fee
0  SHSE.600000  2022-10-29  2022-09-30         9        101 7261000000.00
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近报告日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  若在指定历史时间段内，有多个同一类型报表（如不同年份的一季度报表），将按照报告日期顺序返回。
   3.  如果 fields 参数的财务字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    现金流量表
     字段名
  类型
  中文名称
  量纲
  说明

       一、经营活动产生的现金流量





   cash_rcv_sale
  float
  销售商品、提供劳务收到的现金
  元


   net_incr_cust_dpst_ob
  float
  客户存款和同业存放款项净增加额
  元


   net_incr_cust_dpst
  float
  客户存款净增加额
  元
  银行

   net_incr_dpst_ob
  float
  同业及其他金融机构存放款项净增加额
  元
  银行

   net_incr_brw_cb
  float
  向中央银行借款净增加额
  元


   net_incr_ln_fm_oth
  float
  向其他金融机构拆入资金净增加额
  元


   cash_rcv_orig_in
  float
  收到原保险合同保费取得的现金
  元


   net_cash_rcv_rin_biz
  float
  收到再保险业务现金净额
  元


   net_incr_ph_dpst_inv
  float
  保户储金及投资款净增加额
  元


   net_decrdpst_cb_ob
  float
  存放中央银行和同业款项及其他金融机构净减少额
  元
  银行、保险

   net_decr_cb
  float
  存放中央银行款项净减少额
  元
  银行

   net_decr_ob_fin_inst
  float
  存放同业及其他金融机构款项净减少额
  元
  银行

   net_cert_dpst
  float
  存款证净额
  元
  银行

   net_decr_trd_fin
  float
  交易性金融资产净减少额
  元
  银行

   net_incr_trd_liab
  float
  交易性金融负债净增加额
  元
  银行

   cash_rcv_int_fee
  float
  收取利息、手续费及佣金的现金
  元


   cash_rcv_int
  float
  其中：收取利息的现金
  元
  银行

   cash_rcv_fee
  float
  收取手续费及佣金的现金
  元
  银行

   net_incr_lnfm_sell_repo
  float
  拆入资金及卖出回购金融资产款净增加额
  元
  银行

   net_incr_ln_fm
  float
  拆入资金净增加额
  元


   net_incr_sell_repo
  float
  卖出回购金融资产款净增加额
  元
  银行 保险

   net_decr_lnto_pur_resell
  float
  拆出资金及买入返售金融资产净减少额
  元
  银行

   net_decr_ln_cptl
  float
  拆出资金净减少额
  元
  银行、保险

   net_dect_pur_resell
  float
  买入返售金融资产净减少额
  元
  银行、保险

   net_incr_repo
  float
  回购业务资金净增加额
  元


   net_decr_repo
  float
  回购业务资金净减少额
  元
  证券

   tax_rbt_rcv
  float
  收到的税费返还
  元


   net_cash_rcv_trd
  float
  收到交易性金融资产现金净额
  元
  保险

   cash_rcv_oth_oper
  float
  收到其他与经营活动有关的现金
  元


   net_cash_agy_secu_trd
  float
  代理买卖证券收到的现金净额
  元
  证券

   cash_rcv_pur_resell
  float
  买入返售金融资产收到的现金
  元
  证券、保险

   net_cash_agy_secu_uw
  float
  代理承销证券收到的现金净额
  元
  证券

   cash_rcv_dspl_debt
  float
  处置抵债资产收到的现金
  元
  银行

   canc_loan_rcv
  float
  收回的已于以前年度核销的贷款
  元
  银行

   cf_in_oper
  float
  经营活动现金流入小计
  元


   cash_pur_gds_svc
  float
  购买商品、接受劳务支付的现金
  元


   net_incr_ln_adv_cust
  float
  客户贷款及垫款净增加额
  元


   net_decr_brw_cb
  float
  向中央银行借款净减少额
  元
  银行

   net_incr_dpst_cb_ob
  float
  存放中央银行和同业款项净增加额
  元


   net_incr_cb
  float
  存放中央银行款项净增加额
  元
  银行

   net_incr_ob_fin_inst
  float
  存放同业及其他金融机构款项净增加额
  元
  银行

   net_decr_dpst_ob
  float
  同业及其他机构存放款减少净额
  元
  银行

   net_decr_issu_cert_dpst
  float
  已发行存款证净减少额
  元
  银行

   net_incr_lnto_pur_resell
  float
  拆出资金及买入返售金融资产净增加额
  元
  银行

   net_incr_ln_to
  float
  拆出资金净增加额
  元
  银行、保险

   net_incr_pur_resell
  float
  买入返售金融资产净增加额
  元
  银行、保险

   net_decr_lnfm_sell_repo
  float
  拆入资金及卖出回购金融资产款净减少额
  元
  银行

   net_decr_ln_fm
  float
  拆入资金净减少额
  元
  银行、证券

   net_decr_sell_repo
  float
  卖出回购金融资产净减少额
  元
  银行、保险

   net_incr_trd_fin
  float
  交易性金融资产净增加额
  元
  银行

   net_decr_trd_liab
  float
  交易性金融负债净减少额
  元
  银行

   cash_pay_indem_orig
  float
  支付原保险合同赔付款项的现金
  元


   net_cash_pay_rin_biz
  float
  支付再保险业务现金净额
  元
  保险

   cash_pay_int_fee
  float
  支付利息、手续费及佣金的现金
  元


   cash_pay_int
  float
  其中：支付利息的现金
  元
  银行

   cash_pay_fee
  float
  支付手续费及佣金的现金
  元
  银行

   ph_dvd_pay
  float
  支付保单红利的现金
  元


   net_decr_ph_dpst_inv
  float
  保户储金及投资款净减少额
  元
  保险

   cash_pay_emp
  float
  支付给职工以及为职工支付的现金



   cash_pay_tax
  float
  支付的各项税费
  元


   net_cash_pay_trd
  float
  支付交易性金融资产现金净额
  元
  保险

   cash_pay_oth_oper
  float
  支付其他与经营活动有关的现金
  元


   net_incr_dspl_trd_fin
  float
  处置交易性金融资产净增加额
  元


   cash_pay_fin_leas
  float
  购买融资租赁资产支付的现金
  元
  银行

   net_decr_agy_secu_pay
  float
  代理买卖证券支付的现金净额（净减少额）
  元
  证券

   net_decr_dspl_trd_fin
  float
  处置交易性金融资产的净减少额
  元
  证券

   cf_out_oper
  float
  经营活动现金流出小计
  元


   net_cf_oper
  float
  经营活动产生的现金流量净额
  元


     二、投资活动产生的现金流量：





   cash_rcv_sale_inv
  float
  收回投资收到的现金
  元


   inv_inc_rcv
  float
  取得投资收益收到的现金
  元


   cash_rcv_dvd_prof
  float
  分得股利或利润所收到的现金
  元
  银行

   cash_rcv_dspl_ast
  float
  处置固定资产、无形资产和其他长期资产收回的现金净额
  元


   cash_rcv_dspl_sub_oth
  float
  处置子公司及其他营业单位收到的现金净额
  元


   cash_rcv_oth_inv
  float
  收到其他与投资活动有关的现金
  元


   cf_in_inv
  float
  投资活动现金流入小计
  元


   pur_fix_intg_ast
  float
  购建固定资产、无形资产和其他长期资产支付的现金
  元


   cash_out_dspl_sub_oth
  float
  处置子公司及其他营业单位流出的现金净额
  元
  保险

   cash_pay_inv
  float
  投资支付的现金
  元


   net_incr_ph_plge_ln
  float
  保户质押贷款净增加额
  元
  保险

   add_cash_pled_dpst
  float
  增加质押和定期存款所支付的现金
  元


   net_incr_plge_ln
  float
  质押贷款净增加额
  元


   net_cash_get_sub
  float
  取得子公司及其他营业单位支付的现金净额
  元


   net_pay_pur_resell
  float
  支付买入返售金融资产现金净额
  元
  证券、保险

   cash_pay_oth_inv
  float
  支付其他与投资活动有关的现金
  元


   cf_out_inv
  float
  投资活动现金流出小计



   net_cf_inv
  float
  投资活动产生的现金流量净额
  元


     三、筹资活动产生的现金流量：





   cash_rcv_cptl
  float
  吸收投资收到的现金
  元


   sub_rcv_ms_inv
  float
  其中：子公司吸收少数股东投资收到的现金
  元


   brw_rcv
  float
  取得借款收到的现金
  元


   cash_rcv_bnd_iss
  float
  发行债券收到的现金
  元


   net_cash_rcv_sell_repo
  float
  收到卖出回购金融资产款现金净额
  元
  保险

   cash_rcv_oth_fin
  float
  收到其他与筹资活动有关的现金
  元


   issu_cert_dpst
  float
  发行存款证
  元
  银行

   cf_in_fin_oth
  float
  筹资活动现金流入其他项目
  元


   cf_in_fin
  float
  筹资活动现金流入小计
  元


   cash_rpay_brw
  float
  偿还债务支付的现金
  元


   cash_pay_bnd_int
  float
  偿付债券利息支付的现金
  元
  银行

   cash_pay_dvd_int
  float
  分配股利、利润或偿付利息支付的现金
  元


   sub_pay_dvd_prof
  float
  其中：子公司支付给少数股东的股利、利润
  元


   cash_pay_oth_fin
  float
  支付其他与筹资活动有关的现金
  元


   net_cash_pay_sell_repo
  float
  支付卖出回购金融资产款现金净额
  元
  保险

   cf_out_fin
  float
  筹资活动现金流出小计
  元


   net_cf_fin
  float
  筹资活动产生的现金流量净额
  元


   efct_er_chg_cash
  float
  四、汇率变动对现金及现金等价物的影响
  元


   net_incr_cash_eq
  float
  五、现金及现金等价物净增加额
  元


   cash_cash_eq_bgn
  float
  加：期初现金及现金等价物余额
  元


   cash_cash_eq_end
  float
  六、期末现金及现金等价物余额
  元


     补充资料 1．将净利润调节为经营活动现金流量：





   net_prof
  float
  净利润
  元


   ast_impr
  float
  资产减值准备
  元


   accr_prvs_ln_impa
  float
  计提贷款减值准备
  元
  银行

   accr_prvs_oth_impa
  float
  计提其他资产减值准备
  元
  银行

   accr_prem_rsv
  float
  提取的保险责任准备金
  元
  保险

   accr_unearn_prem_rsv
  float
  提取的未到期的责任准备金
  元
  保险

   defr_fix_prop
  float
  固定资产和投资性房地产折旧
  元


   depr_oga_cba
  float
  其中:固定资产折旧、油气资产折耗、生产性生物资产折旧
  元


   amor_intg_ast_lt_exp
  float
  无形资产及长期待摊费用等摊销
  元
  银行、证券、保险

   amort_intg_ast
  float
  无形资产摊销
  元


   amort_lt_exp_ppay
  float
  长期待摊费用摊销
  元


   dspl_ast_loss
  float
  处置固定资产、无形资产和其他长期资产的损失
  元


   fair_val_chg_loss
  float
  固定资产报废损失
  元


   fv_chg_loss
  float
  公允价值变动损失
  元


   dfa
  float
  固定资产折旧
  元
  银行

   fin_exp
  float
  财务费用
  元


   inv_loss
  float
  投资损失
  元


   exchg_loss
  float
  汇兑损失
  元
  银行、证券、保险

   dest_incr
  float
  存款的增加
  元
  银行

   loan_decr
  float
  贷款的减少
  元
  银行

   cash_pay_bnd_int_iss
  float
  发行债券利息支出
  元
  银行

   dfr_tax
  float
  递延所得税
  元


   dfr_tax_ast_decr
  float
  其中:递延所得税资产减少
  元


   dfr_tax_liab_incr
  float
  递延所得税负债增加
  元


   invt_decr
  float
  存货的减少
  元


   decr_rcv_oper
  float
  经营性应收项目的减少
  元


   incr_pay_oper
  float
  经营性应付项目的增加
  元


   oth
  float
  其他
  元


   cash_end
  float
  现金的期末余额
  元


   cash_bgn
  float
  减：现金的期初余额
  元


   cash_eq_end
  float
  加:现金等价物的期末余额
  元


   cash_eq_bgn
  float
  减:现金等价物的期初余额
  元


   cred_impr_loss
  float
  信用减值损失
  元


   est_liab_add
  float
  预计负债的增加
  元


   dr_cnv_cptl
  float
  债务转为资本
  元


   cptl_bnd_expr_one_y
  float
  一年内到期的可转换公司债券
  元


   fin_ls_fix_ast
  float
  融资租入固定资产
  元


   amort_dfr_inc
  float
  递延收益摊销
  元


   depr_inv_prop
  float
  投资性房地产折旧
  元


   trd_fin_decr
  float
  交易性金融资产的减少
  元
  证券、保险

   im_net_cf_oper
  float
  间接法-经营活动产生的现金流量净额
  元


   im_net_incr_cash_eq
  float
  间接法-现金及现金等价物净增加额
  元





## #   stk_get_fundamentals_income  - 查询利润表数据

  查询指定时间段某一股票所属上市公司的利润表数据
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_fundamentals_income(symbol, rpt_type=None, data_type=None, start_date=None, end_date=None, fields, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型：
1-一季度报
6-中报
9-前三季报
12-年报
默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
101-合并原始
102-合并调整
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期 若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期 若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：101-合并原始, 102-合并调整, 201-母公司原始, 202-母公司调整

   fields
  list[float]
  财务字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   利润表


   示例：


```
stk_get_fundamentals_income(symbol='SHSE.600000', rpt_type=6, data_type=None, start_date='2022-12-31', end_date='2022-12-31', fields='inc_oper', df=True)
```

  输出：


```
symbol    pub_date    rpt_date  rpt_type  data_type       inc_oper
0  SHSE.600000  2022-08-27  2022-06-30         6        102 98644000000.00
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近报告日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  若在指定历史时间段内，有多个同一类型报表（如不同年份的一季度报表），将按照报告日期顺序返回。
   3.  如果 fields 参数的财务字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    利润表
     字段名
  类型
  中文名称
  量纲
  说明

     ttl_inc_oper
  float
  营业总收入
  元


   inc_oper
  float
  营业收入
  元


   net_inc_int
  float
  利息净收入
  元
  证券、银行、保险

   exp_int
  float
  利息支出
  元


   net_inc_fee_comm
  float
  手续费及佣金净收入
  元
  证券、银行

   inc_rin_prem
  float
  其中：分保费收入
  元
  保险

   net_inc_secu_agy
  float
  其中:代理买卖证券业务净收入
  元
  证券

   inc_fee_comm
  float
  手续费及佣金收入
  元


   in_prem_earn
  float
  已赚保费
  元
  保险

   inc_in_biz
  float
  其中:保险业务收入
  元
  保险

   rin_prem_cede
  float
  分出保费
  元
  保险

   unear_prem_rsv
  float
  提取未到期责任准备金
  元
  保险

   net_inc_uw
  float
  证券承销业务净收入
  元
  证券

   net_inc_cust_ast_mgmt
  float
  受托客户资产管理业务净收入
  元
  证券

   inc_fx
  float
  汇兑收益
  元


   inc_other_oper
  float
  其他业务收入
  元


   inc_oper_balance
  float
  营业收入平衡项目
  元


   ttl_inc_oper_other
  float
  营业总收入其他项目
  元


   ttl_cost_oper
  float
  营业总成本
  元


   cost_oper
  float
  营业成本
  元


   exp_oper
  float
  营业支出
  元
  证券、银行、保险

   biz_tax_sur
  float
  营业税金及附加
  元


   exp_sell
  float
  销售费用
  元


   exp_adm
  float
  管理费用
  元


   exp_rd
  float
  研发费用
  元


   exp_fin
  float
  财务费用
  元


   int_fee
  float
  其中:利息费用
  元


   inc_int
  float
  利息收入
  元


   exp_oper_adm
  float
  业务及管理费
  元
  证券、银行、保险

   exp_rin
  float
  减:摊回分保费用
  元
  保险

   rfd_prem
  float
  退保金
  元
  保险

   comp_pay
  float
  赔付支出
  元
  保险

   rin_clm_pay
  float
  减:摊回赔付支出
  元
  保险

   draw_insur_liab
  float
  提取保险责任准备金
  元
  保险

   amor_insur_liab
  float
  减:摊回保险责任准备金
  元
  保险

   exp_ph_dvd
  float
  保单红利支出
  元
  保险

   exp_fee_comm
  float
  手续费及佣金支出
  元


   other_oper_cost
  float
  其他业务成本
  元


   oper_exp_balance
  float
  营业支出平衡项目
  元
  证券、银行、保险

   exp_oper_other
  float
  营业支出其他项目
  元
  证券、银行、保险

   ttl_cost_oper_other
  float
  营业总成本其他项目
  元


     其他经营收益


  元


   inc_inv
  float
  投资收益
  元


   inv_inv_jv_p
  float
  对联营企业和合营企业的投资收益
  元


   inc_ast_dspl
  float
  资产处置收益
  元


   ast_impr_loss
  float
  资产减值损失(新)
  元


   cred_impr_loss
  float
  信用减值损失(新)
  元


   inc_fv_chg
  float
  公允价值变动收益
  元


   inc_other
  float
  其他收益
  元


   oper_prof_balance
  float
  营业利润平衡项目
  元


   oper_prof
  float
  营业利润
  元


   inc_noper
  float
  营业外收入
  元


   exp_noper
  float
  营业外支出
  元


   ttl_prof_balance
  float
  利润总额平衡项目
  元


   oper_prof_other
  float
  营业利润其他项目
  元


   ttl_prof
  float
  利润总额
  元


   inc_tax
  float
  所得税费用
  元


   net_prof
  float
  净利润
  元


   oper_net_prof
  float
  持续经营净利润
  元


   net_prof_pcom
  float
  归属于母公司股东的净利润
  元


   min_int_inc
  float
  少数股东损益
  元


   end_net_prof
  float
  终止经营净利润
  元


   net_prof_other
  float
  净利润其他项目
  元


   eps_base
  float
  基本每股收益
  元


   eps_dil
  float
  稀释每股收益
  元


   other_comp_inc
  float
  其他综合收益
  元


   other_comp_inc_pcom
  float
  归属于母公司股东的其他综合收益
  元


   other_comp_inc_min
  float
  归属于少数股东的其他综合收益
  元


   ttl_comp_inc
  float
  综合收益总额
  元


   ttl_comp_inc_pcom
  float
  归属于母公司所有者的综合收益总额
  元


   ttl_comp_inc_min
  float
  归属于少数股东的综合收益总额
  元


   prof_pre_merge
  float
  被合并方在合并前实现利润
  元


   net_rsv_in_contr
  float
  提取保险合同准备金净额
  元


   net_pay_comp
  float
  赔付支出净额
  元


   net_loss_ncur_ast
  float
  非流动资产处置净损失
  元


   amod_fin_asst_end
  float
  以摊余成本计量的金融资产终止确认收益
  元


   cash_flow_hedging_pl
  float
  现金流量套期损益的有效部分
  元


   cur_trans_diff
  float
  外币财务报表折算差额
  元


   gain_ncur_ast
  float
  非流动资产处置利得
  元


   afs_fv_chg_pl
  float
  可供出售金融资产公允价值变动损益
  元


   oth_eqy_inv_fv_chg
  float
  其他权益工具投资公允价值变动
  元


   oth_debt_inv_fv_chg
  float
  其他债权投资公允价值变动
  元


   oth_debt_inv_cred_impr
  float
  其他债权投资信用减值准备
  元





## #   stk_get_finance_prime  - 查询财务主要指标数据

  查询指定时间段股票所属上市公司的财务主要指标
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_finance_prime(symbol, fields, rpt_type=None, data_type=None, start_date=None, end_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务主要指标， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型： 1-一季度报
6-中报
9-前三季报
12-年报 默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。
101-合并原始
102-合并调整
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期 若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期 若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：101-合并原始, 102-合并调整, 201-母公司原始, 202-母公司调整

   fields
  list[float]
  财务字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   财务主要指标


   示例：


```
stk_get_finance_prime(symbol='SHSE.600000', fields='eps_basic,eps_dil',rpt_type=None, data_type=None,
start_date=None, end_date=None, df=True)
```

  输出：


```
symbol    pub_date    rpt_date  rpt_type  data_type  eps_dil  eps_basic
0  SHSE.600000  2023-04-29  2023-03-31         1        101     0.47       0.51
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近报告日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  若在指定历史时间段内，有多个同一类型报表（如不同年份的一季度报表），将按照报告日期顺序返回。
   3.  如果 fields 参数的财务字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
   4.  财务主要指标由上市公司选择性公布，未公布则对应指标返回NaN. 如需获取标准公开的财务指标，请优先使用三大财务报表数据函数（stk_get_fundamentals_balance - 查询资产负债表数据、stk_get_fundamentals_cashflow - 查询现金流量表数据、stk_get_fundamentals_income - 查询利润表数据）查询。
    财务主要指标
     字段名
  类型
  中文名称
  量纲
  说明

     eps_basic
  float
  基本每股收益
  元


   eps_dil
  float
  稀释每股收益
  元


   eps_basic_cut
  float
  扣除非经常性损益后的基本每股收益
  元


   eps_dil_cut
  float
  扣除非经常性损益后的稀释每股收益
  元


   net_cf_oper_ps
  float
  每股经营活动产生的现金流量净额
  元


   bps_pcom_ps
  float
  归属于母公司股东的每股净资产
  元


   ttl_ast
  float
  总资产
  元


   ttl_liab
  float
  总负债
  元


   share_cptl
  float
  股本
  股


   ttl_inc_oper
  float
  营业总收入
  元


   inc_oper
  float
  营业收入
  元


   oper_prof
  float
  营业利润
  元


   ttl_prof
  float
  利润总额
  元


   ttl_eqy_pcom
  float
  归属于母公司股东的所有者权益
  元


   net_prof_pcom
  float
  归属于母公司股东的净利润
  元


   net_prof_pcom_cut
  float
  扣除非经常性损益后归属于母公司股东的净利润
  元


   roe
  float
  全面摊薄净资产收益率
  %


   roe_weight_avg
  float
  加权平均净资产收益率
  %


   roe_cut
  float
  扣除非经常性损益后的全面摊薄净资产收益率
  %


   roe_weight_avg_cut
  float
  扣除非经常性损益后的加权平均净资产收益率
  %


   net_cf_oper
  float
  经营活动产生的现金流量净额
  元


   eps_yoy
  float
  每股收益同比比例
  %


   inc_oper_yoy
  float
  营业收入同比比例
  %


   ttl_inc_oper_yoy
  float
  营业总收入同比比例
  %


   net_prof_pcom_yoy
  float
  归母净利润同比比例
  %


   bps_sh
  float
  归属于普通股东的每股净资产
  元


   net_asset
  float
  归属于普通股东的净资产
  元


   net_prof
  float
  归属于普通股东的净利润
  元


   net_prof_cut
  float
  扣除非经常性损益后归属于普通股股东的净利润
  元





## #   stk_get_finance_deriv  - 查询财务衍生指标数据

  查询指定时间段股票所属上市公司的财务衍生指标
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_finance_deriv(symbol, fields, rpt_type=None, data_type=None, start_date=None, end_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务衍生指标， 如有多个字段，中间用 英文逗号 分隔

   rpt_type
  int
  报表类型
  N
  None
  按 报告期 查询可指定以下报表类型： 1-一季度报
6-中报
9-前三季报
12-年报 默认 None 为不限

   data_type
  int
  数据类型
  N
  None
  在发布原始财务报告以后，上市公司可能会对数据进行修正。 101-合并原始
102-合并调整
201-母公司原始
202-母公司调整 默认 None 返回当期合并调整，如果没有调整返回合并原始

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为报告日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   pub_date
  str
  发布日期
  若数据类型选择合并原始( data_type=101 )，则返回原始发布的发布日期 若数据类型选择合并调整( data_type=102 )，则返回调整后最新发布日期 若数据类型选择母公司原始( data_type=201 )，则返回母公司原始发布的发布日期
若数据类型选择母公司调整( data_type=202 )，则返回母公司调整后最新发布日期

   rpt_date
  str
  报告日期
  报告截止日期，财报统计的最后一天，在指定时间段[开始时间,结束时间]内的报告截止日期

   rpt_type
  int
  报表类型
  返回数据的报表类型：1-一季度报, 6-中报, 9-前三季报, 12-年报

   data_type
  int
  数据类型
  返回数据的数据类型：101-合并原始, 102-合并调整, 201-母公司原始, 202-母公司调整

   fields
  list[float]
  财务字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   财务衍生指标指标


   示例：


```
stk_get_finance_deriv(symbol='SHSE.600000', fields='eps_basic,eps_dil2,eps_dil,eps_basic_cut',
rpt_type=9, data_type=None, start_date=None, end_date=None, df=True)
```

  输出：


```
symbol    pub_date    rpt_date  ...  eps_dil  eps_basic  eps_dil2
0  SHSE.600000  2022-10-29  2022-09-30  ...   1.3785       1.31       1.2
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近报告日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  若在指定历史时间段内，有多个同一类型报表（如不同年份的一季度报表），将按照报告日期顺序返回。
   3.  如果 fields 参数的财务字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    财务衍生指标指标
     字段名
  类型
  中文名称
  量纲
  说明

     eps_basic
  float
  每股收益EPS(基本)
  元


   eps_dil2
  float
  每股收益EPS(稀释)
  元


   eps_dil
  float
  每股收益EPS(期末股本摊薄)
  元


   eps_basic_cut
  float
  每股收益EPS(扣除/基本)
  元


   eps_dil2_cut
  float
  每股收益EPS(扣除/稀释)
  元


   eps_dil_cut
  float
  每股收益EPS(扣除/期末股本摊薄)
  元


   bps
  float
  每股净资产BPS
  元


   net_cf_oper_ps
  float
  每股经营活动产生的现金流量净额
  元


   ttl_inc_oper_ps
  float
  每股营业总收入
  元


   inc_oper_ps
  float
  每股营业收入
  元


   ebit_ps
  float
  每股息税前利润
  元


   cptl_rsv_ps
  float
  每股资本公积
  元


   sur_rsv_ps
  float
  每股盈余公积
  元


   retain_prof_ps
  float
  每股未分配利润
  元


   retain_inc_ps
  float
  每股留存收益
  元


   net_cf_ps
  float
  每股现金流量净额
  元


   fcff_ps
  float
  每股企业自由现金流量
  元


   fcfe_ps
  float
  每股股东自由现金流量
  元


   ebitda_ps
  float
  每股EBITDA
  元


   roe
  float
  净资产收益率ROE(摊薄)
  %


   roe_weight
  float
  净资产收益率ROE(加权)
  %


   roe_avg
  float
  净资产收益率ROE(平均)
  %


   roe_cut
  float
  净资产收益率ROE(扣除/摊薄)
  %


   roe_weight_cut
  float
  净资产收益率ROE(扣除/加权)
  %


   ocf_toi
  float
  经营性现金净流量/营业总收入



   eps_dil_yoy
  float
  稀释每股收益同比增长率
  %


   net_cf_oper_ps_yoy
  float
  每股经营活动中产生的现金流量净额同比增长率
  %


   ttl_inc_oper_yoy
  float
  营业总收入同比增长率
  %


   inc_oper_yoy
  float
  营业收入同比增长率
  %


   oper_prof_yoy
  float
  营业利润同比增长率
  %


   ttl_prof_yoy
  float
  利润总额同比增长率
  %


   net_prof_pcom_yoy
  float
  归属母公司股东的净利润同比增长率
  %


   net_prof_pcom_cut_yoy
  float
  归属母公司股东的净利润同比增长率(扣除非经常性损益)
  %


   net_cf_oper_yoy
  float
  经营活动产生的现金流量净额同比增长率
  %


   roe_yoy
  float
  净资产收益率同比增长率(摊薄)
  %


   net_asset_yoy
  float
  净资产同比增长率
  %


   ttl_liab_yoy
  float
  总负债同比增长率
  %


   ttl_asset_yoy
  float
  总资产同比增长率
  %


   net_cash_flow_yoy
  float
  现金净流量同比增长率
  %


   bps_gr_begin_year
  float
  每股净资产相对年初增长率
  %


   ttl_asset_gr_begin_year
  float
  资产总计相对年初增长率
  %


   ttl_eqy_pcom_gr_begin_year
  float
  归属母公司的股东权益相对年初增长率
  %


   net_debt_eqy_ev
  float
  净债务/股权价值
  %


   int_debt_eqy_ev
  float
  带息债务/股权价值



   eps_bas_yoy
  float
  基本每股收益同比增长率
  %


   ebit
  float
  EBIT(正推法)
  元


   ebitda
  float
  EBITDA(正推法)
  元


   ebit_inverse
  float
  EBIT(反推法)
  元


   ebitda_inverse
  float
  EBITDA(反推法)
  元


   nr_prof_loss
  float
  非经常性损益
  元


   net_prof_cut
  float
  扣除非经常性损益后的净利润
  元


   gross_prof
  float
  毛利润
  元


   oper_net_inc
  float
  经营活动净收益
  元


   val_chg_net_inc
  float
  价值变动净收益
  元


   exp_rd
  float
  研发费用
  元


   ttl_inv_cptl
  float
  全部投入资本
  元


   work_cptl
  float
  营运资本
  元


   net_work_cptl
  float
  净营运资本
  元


   tg_asset
  float
  有形资产
  元


   retain_inc
  float
  留存收益
  元


   int_debt
  float
  带息债务
  元


   net_debt
  float
  净债务
  元


   curr_liab_non_int
  float
  无息流动负债
  元


   ncur_liab_non_int
  float
  无息非流动负债
  元


   fcff
  float
  企业自由现金流量FCFF
  元


   fcfe
  float
  股权自由现金流量FCFE
  元


   cur_depr_amort
  float
  当期计提折旧与摊销
  元


   eqy_mult_dupont
  float
  权益乘数(杜邦分析)



   net_prof_pcom_np
  float
  归属母公司股东的净利润/净利润
  %


   net_prof_tp
  float
  净利润/利润总额
  %


   ttl_prof_ebit
  float
  利润总额/息税前利润
  %


   roe_cut_avg
  float
  净资产收益率ROE(扣除/平均)
  %


   roe_add
  float
  净资产收益率ROE(增发条件)
  %


   roe_ann
  float
  净资产收益率ROE(年化)
  %


   roa
  float
  总资产报酬率ROA
  %


   roa_ann
  float
  总资产报酬率ROA(年化)
  %


   jroa
  float
  总资产净利率
  %


   jroa_ann
  float
  总资产净利率(年化)
  %


   roic
  float
  投入资本回报率ROIC
  %


   sale_npm
  float
  销售净利率
  %


   sale_gpm
  float
  销售毛利率
  %


   sale_cost_rate
  float
  销售成本率
  %


   sale_exp_rate
  float
  销售期间费用率
  %


   net_prof_toi
  float
  净利润/营业总收入
  %


   oper_prof_toi
  float
  营业利润/营业总收入
  %


   ebit_toi
  float
  息税前利润/营业总收入
  %


   ttl_cost_oper_toi
  float
  营业总成本/营业总收入
  %


   exp_oper_toi
  float
  营业费用/营业总收入
  %


   exp_admin_toi
  float
  管理费用/营业总收入
  %


   exp_fin_toi
  float
  财务费用/营业总收入
  %


   ast_impr_loss_toi
  float
  资产减值损失/营业总收入
  %


   ebitda_toi
  float
  EBITDA/营业总收入
  %


   oper_net_inc_tp
  float
  经营活动净收益/利润总额
  %


   val_chg_net_inc_tp
  float
  价值变动净收益/利润总额
  %


   net_exp_noper_tp
  float
  营业外支出净额/利润总额



   inc_tax_tp
  float
  所得税/利润总额
  %


   net_prof_cut_np
  float
  扣除非经常性损益的净利润/净利润
  %


   eqy_mult
  float
  权益乘数



   curr_ast_ta
  float
  流动资产/总资产
  %


   ncurr_ast_ta
  float
  非流动资产/总资产
  %


   tg_ast_ta
  float
  有形资产/总资产
  %


   ttl_eqy_pcom_tic
  float
  归属母公司股东的权益/全部投入资本
  %


   int_debt_tic
  float
  带息负债/全部投入资本
  %


   curr_liab_tl
  float
  流动负债/负债合计
  %


   ncurr_liab_tl
  float
  非流动负债/负债合计
  %


   ast_liab_rate
  float
  资产负债率
  %


   quick_rate
  float
  速动比率



   curr_rate
  float
  流动比率



   cons_quick_rate
  float
  保守速动比率



   liab_eqy_rate
  float
  产权比率



   ttl_eqy_pcom_tl
  float
  归属母公司股东的权益/负债合计



   ttl_eqy_pcom_debt
  float
  归属母公司股东的权益/带息债务



   tg_ast_tl
  float
  有形资产/负债合计



   tg_ast_int_debt
  float
  有形资产/带息债务



   tg_ast_net_debt
  float
  有形资产/净债务



   ebitda_tl
  float
  息税折旧摊销前利润/负债合计



   net_cf_oper_tl
  float
  经营活动产生的现金流量净额/负债合计



   net_cf_oper_int_debt
  float
  经营活动产生的现金流量净额/带息债务



   net_cf_oper_curr_liab
  float
  经营活动产生的现金流量净额/流动负债



   net_cf_oper_net_liab
  float
  经营活动产生的现金流量净额/净债务



   ebit_int_cover
  float
  已获利息倍数



   long_liab_work_cptl
  float
  长期债务与营运资金比率



   ebitda_int_debt
  float
  EBITDA/带息债务
  %


   oper_cycle
  float
  营业周期
  天


   inv_turnover_days
  float
  存货周转天数
  天


   acct_rcv_turnover_days
  float
  应收账款周转天数(含应收票据)
  天


   inv_turnover_rate
  float
  存货周转率
  次


   acct_rcv_turnover_rate
  float
  应收账款周转率(含应收票据)
  次


   curr_ast_turnover_rate
  float
  流动资产周转率
  次


   fix_ast_turnover_rate
  float
  固定资产周转率
  次


   ttl_ast_turnover_rate
  float
  总资产周转率
  次


   cash_rcv_sale_oi
  float
  销售商品提供劳务收到的现金/营业收入
  %


   net_cf_oper_oi
  float
  经营活动产生的现金流量净额/营业收入
  %


   net_cf_oper_oni
  float
  经营活动产生的现金流量净额/经营活动净收益



   cptl_exp_da
  float
  资本支出/折旧摊销
  %


   cash_rate
  float
  现金比率



   acct_pay_turnover_days
  float
  应付账款周转天数(含应付票据)
  天


   acct_pay_turnover_rate
  float
  应付账款周转率(含应付票据)
  次


   net_oper_cycle
  float
  净营业周期
  天


   ttl_cost_oper_yoy
  float
  营业总成本同比增长率
  %


   net_prof_yoy
  float
  净利润同比增长率
  %


   net_cf_oper_np
  float
  经营活动产生的现金流量净额/净利润
  %





## #   stk_get_daily_valuation  - 查询估值指标每日数据

  查询指定时间段股票的每日估值指标
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_daily_valuation(symbol, fields, start_date=None, end_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   trade_date
  str
  交易日期


   fields
  list[float]
  指标字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   估值指标


   示例：


```
stk_get_daily_valuation(symbol='SHSE.600000', fields='pe_ttm,pe_lyr,pe_mrq', start_date=None, end_date=None, df=True)
```

  输出：


```
symbol  trade_date  pe_ttm  pe_lyr  pe_mrq
0  SHSE.600000  2023-06-26  4.4139   4.107  3.3188
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近交易日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  如果 fields 参数的指标字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    估值指标
     字段名
  类型
  中文名称
  量纲
  说明

     pe_ttm
  float
  市盈率(TTM)
  倍


   pe_lyr
  float
  市盈率(最新年报LYR)
  倍


   pe_mrq
  float
  市盈率(最新报告期MRQ)
  倍


   pe_1q
  float
  市盈率(当年一季×4)
  倍


   pe_2q
  float
  市盈率(当年中报×2)
  倍


   pe_3q
  float
  市盈率(当年三季×4/3)
  倍


   pe_ttm_cut
  float
  市盈率(TTM) 扣除非经常性损益
  倍


   pe_lyr_cut
  float
  市盈率(最新年报LYR) 扣除非经常性损益
  倍


   pe_mrq_cut
  float
  市盈率(最新报告期MRQ) 扣除非经常性损益
  倍


   pe_1q_cut
  float
  市盈率(当年一季×4) 扣除非经常性损益
  倍


   pe_2q_cut
  float
  市盈率(当年中报×2) 扣除非经常性损益
  倍


   pe_3q_cut
  float
  市盈率(当年三季×4/3) 扣除非经常性损益
  倍


   pb_lyr
  float
  市净率(最新年报LYR)
  倍


   pb_mrq
  float
  市净率(最新报告期MRQ)
  倍


   pb_lyr_1
  float
  市净率(剔除其他权益工具，最新年报LYR)
  倍


   pb_mrq_1
  float
  市净率(剔除其他权益工具，最新报告期MRQ)
  倍


   pcf_ttm_oper
  float
  市现率(经营现金流,TTM)
  倍


   pcf_ttm_ncf
  float
  市现率(现金净流量,TTM)
  倍


   pcf_lyr_oper
  float
  市现率(经营现金流,最新年报LYR)
  倍


   pcf_lyr_ncf
  float
  市现率(现金净流量,最新年报LYR)
  倍


   ps_ttm
  float
  市销率(TTM)
  倍


   ps_lyr
  float
  市销率(最新年报LYR)
  倍


   ps_mrq
  float
  市销率(最新报告期MRQ)
  倍


   ps_1q
  float
  市销率(当年一季×4)
  倍


   ps_2q
  float
  市销率(当年中报×2)
  倍


   ps_3q
  float
  市销率(当年三季×4/3)
  倍


   peg_lyr
  float
  历史PEG值(当年年报增长率)



   peg_mrq
  float
  历史PEG值(最新报告期增长率)



   peg_1q
  float
  历史PEG值(当年1季*4较上年年报增长率)



   peg_2q
  float
  历史PEG值(当年中报*2较上年年报增长率)



   peg_3q
  float
  历史PEG值(当年3季*4/3较上年年报增长率)



   peg_np_cgr
  float
  历史PEG值(PE_TTM较净利润3年复合增长率)



   peg_npp_cgr
  float
  历史PEG值(PE_TTM较净利润3年复合增长率)



   dy_ttm
  float
  股息率(滚动 12 月TTM)
  %


   dy_lfy
  float
  股息率(上一财年LFY)
  %





## #   stk_get_daily_mktvalue  - 查询市值指标每日数据

  查询指定时间段股票的每日市值指标
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_daily_mktvalue(symbol, fields, start_date=None, end_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   trade_date
  str
  交易日期


   fields
  list[float]
  指标字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   市值指标


   示例：


```
stk_get_daily_mktvalue(symbol='SHSE.600000', fields='tot_mv,tot_mv_csrc,a_mv',
                                  start_date=None, end_date=None, df=True)
```

  输出：


```
symbol  trade_date      tot_mv  tot_mv_csrc        a_mv
0  SHSE.600000  2023-06-26  2.1016e+11   2.1016e+11  2.1016e+11
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近交易日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  如果 fields 参数的指标字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    市值指标
     字段名
  类型
  中文名称
  量纲
  说明

     tot_mv
  float
  总市值
  元


   tot_mv_csrc
  float
  总市值(证监会算法)
  元


   a_mv
  float
  A股流通市值(含限售股)
  元


   a_mv_ex_ltd
  float
  A股流通市值(不含限售股)
  元


   b_mv
  float
  B股流通市值(含限售股，折人民币)
  元


   b_mv_ex_ltd
  float
  B股流通市值(不含限售股，折人民币)
  元


   ev
  float
  企业价值(含货币资金)(EV1)
  元


   ev_ex_curr
  float
  企业价值(剔除货币资金)(EV2)
  元


   ev_ebitda
  float
  企业倍数
  倍


   equity_value
  float
  股权价值
  元





## #   stk_get_daily_basic  - 查询股本等基础指标每日数据

  查询指定时间段股票的每日基础指标
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
stk_get_daily_basic(symbol, fields, start_date=None, end_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  股票代码
  Y
  无
  必填，只能填一个股票标的，使用时参考 symbol

   fields
  str
  返回字段
  Y
  无
  指定需要返回的财务字段， 如有多个字段，中间用 英文逗号 分隔

   start_date
  str
  开始时间
  N
  None
  开始时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   end_date
  str
  结束时间
  N
  None
  结束时间，时间类型为交易日期，%Y-%m-%d 格式， 默认 None 表示最新时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式 ， 默认 False 返回 list[dict]


   返回值：
      字段名
   类型
   中文名称
   说明

     symbol
  str
  股票代码


   trade_date
  str
  交易日期


   fields
  list[float]
  指标字段数据
  指定返回  fields 字段的数值. 支持的字段名请参考   基础指标


   示例：


```
stk_get_daily_basic(symbol='SHSE.600000', fields='tclose,turnrate,ttl_shr,circ_shr',
                                  start_date=None, end_date=None, df=True)
```

  输出：


```
symbol  trade_date  turnrate    circ_shr     ttl_shr  tclose
0  SHSE.600000  2023-06-26    0.1159  2.9352e+10  2.9352e+10    7.16
```

  注意：
   1.  当 start_date  ==  end_date 时，取离  end_date  最近交易日期的一条数据，
  当 start_dat <  end_date 时，取指定时间段的数据，
  当  start_date  >  end_date 时，返回报错。
   2.  如果 fields 参数的财务字段填写不正确，或填写空字段，会报错提示“填写的 fields 不正确”。fields不能超过20个字段
    基础指标
     字段名
  类型
  中文名称
  量纲
  说明

     tclose
  float
  收盘价
  元


   turnrate
  float
  当日换手率
  %


   ttl_shr
  float
  总股本
  股


   circ_shr
  float
  流通股本（流通股本=无限售条件流通股本+有限售条件流通股本）
  股


   ttl_shr_unl
  float
  无限售条件流通股本(A股+H股)
  股


   ttl_shr_ltd
  float
  有限售条件股本
  股


   a_shr_unl
  float
  无限售条件流通A股股本(行情软件定义的流通股)
  股


   h_shr_unl
  float
  无限售条件流通H股股本
  股





      ←

        通用数据函数（免费）

        期货基础数据函数（免费）

      →

---

## 行情数据查询函数（免费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E8%A1%8C%E6%83%85%E6%95%B0%E6%8D%AE%E6%9F%A5%E8%AF%A2%E5%87%BD%E6%95%B0%EF%BC%88%E5%85%8D%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     行情数据查询函数（免费） - 掘金量化












# #  行情数据查询函数（免费）



## #   last_tick  - 查询已订阅的最新 Tick （多标的）

  查询已订阅的最新 Tick
   函数原型：


```
last_tick(symbols, fields="", include_call_auction = False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str or list
  查询代码，如有多个代码, 中间用  ,  (英文逗号) 隔开,  也支持  ['symbol1', 'symbol2']  这种列表格式 ，使用参考 symbol

   fields
  str
  查询字段, 默认所有字段 具体字段见: tick 对象

   include_call_auction
  bool
  是否支持集合竞价(9:15-9:25)取数，True为支持，False为不支持，默认为False


   返回值：
   list[dict]
   示例：


```
def init(context):
    context.symbol_list = ['SZSE.000002', 'SHSE.600000']
    context.index_symbol = 'SHSE.000001'
    subscribe(symbols=context.symbol_list + [context.index_symbol], frequency='tick')
    schedule(schedule_func=algo, date_rule='1d', time_rule='14:50:00')

def on_tick(context, tick):
    symbol = tick['symbol']
    if symbol == context.index_symbol:
        # 每次收到指数行情，获取订阅股票的最新tick，避免每个股票的tick都触发，多次查询占用资源
        data = last_tick(symbols=context.symbol_list, fields='symbol,price,open,created_at')
        print(data)

# 或者定时任务里调用
def algo(context):
    data = last_tick(symbols=context.symbol_list, fields='symbol,price,open,created_at')
    print(data)
```

  输出：


```
[{'symbol': 'SZSE.000001', 'price': 16.559999465942383, 'created_at': datetime.datetime(2020, 10, 15, 15, 0, 3, tzinfo=tzfile('PRC'))}]
```

  注意：
   1.  输入的 symbols 必须先订阅 tick，如果 last_tick 查询的标的代码不在 tick 行情订阅范围内，则返该代码的 tick 字典，除 symbol 外其他字段均为 空字符串/0
   2.  若输入代码有效，在 tick 行情订阅范围内，但查询字段 fields 中包括错误字段，返回的列表仍包含对应数量的dict，但每个dict中除有效字段外，其他字段的值均为空字符串/0
   3.  实时模式获取集合竞价的tick数据，需要指定include_call_auction=True，注意集合竞价阶段没有成交，有效字段只有报价quotes。
   4.  回测模式，先订阅标的行情 frequency='tick' 再调用 last_tick ，会返回回测当前时刻最新的 tick.price，如果超出历史行情权限会报错中止回测。


## #   current_price  - 查询当前最新价

  查询指定标的当前时点最新价
   函数原型：


```
current_price(symbols)
```

  参数：
     参数名
  类型
  说明

     symbols
  str or list
  查询代码，如有多个代码, 中间用  ,  (英文逗号) 隔开,  也支持  ['symbol1', 'symbol2']  这种列表格式 ，使用参考 symbol


   返回值：
   list[dict]
     字段名
  类型
  中文名称
  说明

     symbol
  str
  标的代码
  格式exchange.sec_id（SHSE.600000, SZSE.000001）

   price
  float
  最新价
  实时模式：当前时点最新tick.price。回测模式：若在subscribe的订阅频度frequency='tick', 返回回测当前时点最新tick.price;若在subscribe的订阅频度frequency='60s', 返回回测当前时点最近1分钟bar.close;若在subscribe的订阅频度frequency='1d', 返回回测当前时点最近日线bar.close.

   created_at
  datetime.datetime
  创建时间
  实时模式：当前时点最新tick.created_at。回测模式：若在subscribe的订阅频度frequency='tick', 返回回测当前时点最新tick.created_at;若在subscribe的订阅频度frequency='60s', 返回回测当前时点最近1分钟bar.eob; 若在subscribe的订阅频度frequency='1d', 返回回测当前时点最近日线bar.eob.


   示例：


```
current_data = current_price(symbols='SZSE.000001')
```

  输出：


```
[{'symbol': 'SZSE.000001', 'price': 16.559999465942383, 'created_at': datetime.datetime(2020, 10, 15, 15, 0, 3, tzinfo=tzfile('PRC'))}]
```

  注意：
   1.  若输入包含无效标的代码，则返回的列表只包含有效标的代码对应的 dict
   2.  回测模式，如果订阅标的行情 frequency='tick' 或 frequency='60s' 再调用 current_price ，会返回回测当前时刻最新的 tick.price（订阅 tick）或 bar.close（订阅分钟bar），超出历史行情权限会报错中止回测。
   3.  回测模式，如果订阅标的行情日线 frequency='1d'  或 不订阅行情，直接调用 current_price ，会根据 run() 函数指定的 backtest_intraday 参数返回：（python 版本 >= 3.0.178起）
   backtest_intraday=0，返回回测当前时刻的的历史最新日线收盘价（T日盘中为T-1日收盘价，T日盘后为T日收盘价）；
  backtest_intraday=1，返回回测当前交易日的日线收盘价（T日盘中和盘后均为T日收盘价）



## #  history - 查询历史行情

  查询标的在指定时间段的历史行情数据
   函数原型：


```
history(symbol, frequency, start_time, end_time, fields=None, skip_suspended=True,
        fill_missing=None, adjust=ADJUST_NONE, adjust_end_time='', df=False)
```

  参数：
     参数名
  类型
  说明

     symbol
  str or list
  标的代码, 如有多个代码, 中间用  ,  (英文逗号) 隔开,  也支持  ['symbol1', 'symbol2']  这种列表格式 ，使用参考 symbol

   frequency
  str
  频率, 支持 'tick', '1d', '60s' 等, 默认 '1d', 详情见 股票行情数据 和 期货行情数据 ,  实时行情支持的频率

   start_time
  str or datetime.datetime
  开始时间 (%Y-%m-%d %H:%M:%S 格式), 也支持 datetime.datetime 格式

   end_time
  str or datetime.datetime
  结束时间 (%Y-%m-%d %H:%M:%S 格式), 也支持 datetime.datetime 格式

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有, 具体字段见: tick 对象  和  bar 对象

   adjust
  int
   ADJUST_NONE or 0: 不复权 ,  ADJUST_PREV or 1: 前复权 ,  ADJUST_POST or 2: 后复权  默认不复权

   adjust_end_time
  str
  复权基点时间, 默认当前时间

   df
  bool
  是否返回 dataframe 格式, 默认  False , 返回 list[dict]


   返回值:参考 tick 对象  和  bar 对象 。
  当 df = True 时， 返回
     类型
  说明

     dataframe
  tick 的 dataframe 或者 bar 的 dataframe


   示例：


```
history_data = history(symbol='SHSE.000300', frequency='1d', start_time='2010-07-28',  end_time='2017-07-30', fields='open, close, low, high, eob', adjust=ADJUST_PREV, df= True)
```

  输出：


```
open      close        low       high                       eob
0     2796.4829  2863.7241  2784.1550  2866.4041 2010-07-28 00:00:00+08:00
1     2866.7720  2877.9761  2851.9961  2888.5991 2010-07-29 00:00:00+08:00
2     2871.4810  2868.8459  2844.6819  2876.1360 2010-07-30 00:00:00+08:00
3     2868.2791  2917.2749  2867.4500  2922.6121 2010-08-02 00:00:00+08:00
4     2925.2539  2865.9709  2865.7610  2929.6140 2010-08-03 00:00:00+08:00
```

 当 df = False 时， 返回
     类型
  说明

     list
  tick 列表 或者 bar 列表


   注意：


```
history_data = history(symbol='SHSE.000300', frequency='1d', start_time='2017-07-30',  end_time='2017-07-31', fields='open, close, low, high, eob', adjust=ADJUST_PREV, df=False)
```

  输出：


```
[{'open': 3722.42822265625, 'close': 3737.873291015625, 'low': 3713.655029296875, 'high': 3746.520751953125, 'eob': datetime.datetime(2017, 7, 31, 0, 0, tzinfo=tzfile('PRC'))}]
```

  1.  返回的 list/DataFrame 是以参数 eob/bob 的升序来排序的，若要获取多标的的数据，通常需进一步的数据处理来分别提取出每只标的的历史数据。
   2.  获取数据目前采用前开后闭区间的方式，根据eob升序排序。
   3.  若输入无效标的代码，返回 空列表/空DataFrame 。
   4.  若输入代码正确，但查询字段包含无效字段，返回的列表、DataFrame 只包含  eob、symbol 和输入的其他有效字段。
   5.  skip_suspended 和 fill_missing 参数暂不支持。
   6.  日内数据单次返回数据量最大返回 33000, 超出部分不返回。
   7.  start_time 和 end_time 输入不存在日期时，会报错 details = "failed to parse datetime"。
   8.  盘后18点清洗入库更新当天数据，需要盘后取数据的，请在18点后取。


## #   history_n  - 查询历史行情最新 n 条

  查询标的最新n条的历史行情数据
   函数原型：


```
history_n(symbol, frequency, count, end_time=None, fields=None, skip_suspended=True,
          fill_missing=None, adjust=ADJUST_NONE, adjust_end_time='', df=False)
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码(只允许单个标的的代码字符串)，使用时参考 symbol

   frequency
  str
  频率, 支持 'tick', '1d', '60s' 等, 默认 '1d', 详情见 股票行情数据 和 期货行情数据 ,  实时行情支持的频率

   count
  int
  数量(正整数)

   end_time
  str or datetime.datetime
  结束时间 (%Y-%m-%d %H:%M:%S 格式), 也支持 datetime.datetime 格式，默认 None 时，用了实际当前时间，非回测当前时间

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有, 具体字段见: tick 对象  和  bar 对象

   adjust
  int
   ADJUST_NONE or 0: 不复权 ,  ADJUST_PREV or 1: 前复权 ,  ADJUST_POST or 2: 后复权  默认不复权

   adjust_end_time
  str
  复权基点时间, 默认当前时间

   df
  bool
  是否返回 dataframe 格式, 默认 False, 返回 list[dict]


   返回值:参考 tick 对象  和  bar 对象 。
  当 df = True 时，返回
     类型
  说明

     dataframe
  tick 的 dataframe 或者 bar 的 dataframe


   示例：


```
history_n_data = history_n(symbol='SHSE.600519', frequency='1d', count=100, end_time='2020-10-20 15:30:00', fields='symbol, open, close, low, high, eob', adjust=ADJUST_PREV, df=True)
```

  输出：


```
symbol       open  ...       high                       eob
0   SHSE.600519  1350.2278  ...  1350.3265 2020-05-22 00:00:00+08:00
1   SHSE.600519  1314.6434  ...  1350.8010 2020-05-25 00:00:00+08:00
2   SHSE.600519  1354.0629  ...  1354.1321 2020-05-26 00:00:00+08:00
3   SHSE.600519  1343.3086  ...  1344.2970 2020-05-27 00:00:00+08:00
4   SHSE.600519  1322.5214  ...  1331.3878 2020-05-28 00:00:00+08:00
```

 当 df = False 时， 返回
     类型
  说明

     list
  tick 列表 或者 bar 列表


   示例：


```
history_n_data = history_n(symbol='SHSE.600519', frequency='1d', count=2, end_time='2020-10-20 15:30:00', fields='symbol, open, close, low, high, eob', adjust=ADJUST_PREV, df=False)
```

  输出：


```
[{'symbol': 'SHSE.600519', 'open': 1725.0, 'close': 1699.0, 'low': 1691.9000244140625, 'high': 1733.97998046875, 'eob': datetime.datetime(2020, 10, 19, 0, 0, tzinfo=tzfile('PRC'))}, {'symbol': 'SHSE.600519', 'open': 1699.989990234375, 'close': 1734.0, 'low': 1695.0, 'high': 1734.969970703125, 'eob': datetime.datetime(2020, 10, 20, 0, 0, tzinfo=tzfile('PRC'))}]
```

  注意：
   1.  返回的 list/DataFrame 是以参数 eob/bob 的升序来排序的
   2.  若输入无效标的代码，返回 空列表/空DataFrame
   3.  若输入代码正确，但查询字段包含无效字段，返回的列表、DataFrame 只包含  eob、symbol 和输入的其他有效字段
   4.  end_time 中月,日,时,分,秒均可以只输入个位数,例: '2017-7-30 20:0:20' ,但若对应位置为零，则 0 不可被省略,如不可输入 '2017-7-30 20: :20'
   5.  skip_suspended 和 fill_missing 参数暂不支持
   6.  单次返回数据量最大返回 33000, 超出部分不返回
   7.  end_time 输入不存在日期时，会报错 details = "Can't parse string as time: 2020-10-40 15:30:00"
   8.  盘后18点清洗入库更新当天数据，需要盘后取数据的，请在18点后取。


## #  context.data - 查询订阅数据

   函数原型：


```
context.data(symbol, frequency, count, fields)
```

  参数：
     参数名
  类型
  说明

     symbol
  str
  标的代码(只允许单个标的的代码字符串)，使用时参考 symbol

   frequency
  str
  频率, 支持 'tick', '1d', '60s' 等, 默认 '1d', 详情见 股票行情数据 和 期货行情数据 ,  实时行情支持的频率

   count
  int
  滑窗大小(正整数)，需小于等于 subscribe 函数中 count 值

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有, 具体字段见: tick 对象  和  bar 对象  ，需在 subscribe 函数中指定的fields范围内，指定字段越少，查询速度越快


   返回值：
   当subscribe的format="df"（默认）时，返回dataframe
     类型
  说明

     dataframe
  tick 的 dataframe 或者 bar 的 dataframe


   示例：


```
def init(context):
    subscribe(symbols='SHSE.600519', frequency='60s', count=50, fields='symbol, close, eob', format='df')

def on_bar(context,bars):
    data = context.data(symbol=bars[0]['symbol'], frequency='60s', count=10)
    print(data.tail())
```

  输出：


```
symbol    close                       eob
5  SHSE.600519  1629.96 2024-01-22 14:56:00+08:00
6  SHSE.600519  1627.25 2024-01-22 14:57:00+08:00
7  SHSE.600519  1627.98 2024-01-22 14:58:00+08:00
8  SHSE.600519  1642.00 2024-01-22 15:00:00+08:00
9  SHSE.600519  1632.96 2024-01-23 09:31:00+08:00
```

  subscribe的format ="row"时，返回list[dict]
     类型
  说明

     list[dict]
  当frequency='tick'时，返回tick列表：[{tick_1}, {tick_2},  ..., {tick_n}]，列表长度等于滑窗大小，即n=count， 当frequency='60s', '300s', '900s', '1800s', '3600s'时，返回bar列表：[{bar_1}, {bar_2}, {bar_n}, ..., ] ，列表长度等于滑窗大小，即n=count


   示例：


```
def init(context):
    subscribe(symbols='SHSE.600519', frequency='tick', count=50, fields='symbol, price, quotes,created_at', format='row')

def on_tick(context, tick):
    data = context.data(symbol=tick['symbol'], frequency='tick', count=3)
    print(data)
```

  输出：


```
[{'symbol': 'SHSE.600519', 'price': 1642.0, 'quotes': [{'bid_p': 1640.0, 'bid_v': 100, 'ask_p': 1642.0, 'ask_v': 4168}, {'bid_p': 1634.52, 'bid_v': 300, 'ask_p': 1642.01, 'ask_v': 100}, {'bid_p': 1633.0, 'bid_v': 100, 'ask_p': 1642.06, 'ask_v': 100}, {'bid_p': 1632.96, 'bid_v': 100, 'ask_p': 1642.08, 'ask_v': 200}, {'bid_p': 1632.89, 'bid_v': 100, 'ask_p': 1642.2, 'ask_v': 200}], 'created_at': datetime.datetime(2024, 1, 22, 15, 1, 51, 286000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))}, {'symbol': 'SHSE.600519', 'price': 1642.0, 'quotes': [{'bid_p': 1640.0, 'bid_v': 100, 'ask_p': 1642.0, 'ask_v': 4168}, {'bid_p': 1634.52, 'bid_v': 300, 'ask_p': 1642.01, 'ask_v': 100}, {'bid_p': 1633.0, 'bid_v': 100, 'ask_p': 1642.06, 'ask_v': 100}, {'bid_p': 1632.96, 'bid_v': 100, 'ask_p': 1642.08, 'ask_v': 200}, {'bid_p': 1632.89, 'bid_v': 100, 'ask_p': 1642.2, 'ask_v': 200}], 'created_at': datetime.datetime(2024, 1, 22, 15, 1, 54, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))}, {'symbol': 'SHSE.600519', 'price': 0.0, 'quotes': [{'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}, {'bid_p': 0.0, 'bid_v': 0, 'ask_p': 0.0, 'ask_v': 0}], 'created_at': datetime.datetime(2024, 1, 23, 9, 14, 1, 91000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))}]
```

  subscribe的format ="col"时，返回dict
     类型
  说明

     dict
  当frequency='tick'时，返回tick数据（symbol为str格式，其余字段为列表，列表长度等于滑窗大小count），当frequency='60s', '300s', '900s', '1800s', '3600s'时，返回bar数据（symbol和frequency为str格式，其余字段为列表，列表长度等于滑窗大小count）


   示例：


```
def init(context):
    subscribe(symbols='SHSE.600519', frequency='tick', count=10, fields='symbol, price, bid_p, created_at', format='col')

def on_tick(context, tick):
    data = context.data(symbol=tick['symbol'], frequency='tick', count=10)
    print(data)
```

  输出：


```
{'symbol': 'SHSE.600519', 'price': [1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 1642.0, 0.0], 'bid_p': [1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 1640.0, 0.0], 'created_at': [datetime.datetime(2024, 1, 22, 15, 1, 12, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 21, 277000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 24, 278000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 33, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 36, 282000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 39, 279000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 48, 283000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 51, 286000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 22, 15, 1, 54, 280000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai')), datetime.datetime(2024, 1, 23, 9, 14, 1, 91000, tzinfo=datetime.timezone(datetime.timedelta(seconds=28800), 'Asia/Shanghai'))]}
```

  注意：
   1.  只有在 订阅 后，此接口才能取到数据，如未订阅数据，则返回报错。
   2.  symbol 参数只支持输入 一个 标的。
   3.  count 参数必须 小于或等于 订阅函数里面的 count 值。
   4.  fields 参数必须在订阅函数subscribe里面指定的 fields 范围内。指定字段越少，查询速度越快，目前效率是row > col > df。
   5.  当subscribe的format指定col时，tick的quotes字段会被拆分，只返回买卖一档的量和价，即只有bid_p，bid_v, ask_p和ask_v。


## #   get_history_l2ticks  - 查询历史 L2 Tick 行情

   仅特定券商付费提供
   函数原型：


```
get_history_l2ticks(symbols, start_time, end_time, fields=None,skip_suspended=True, fill_missing=None,adjust=ADJUST_NONE, adjust_end_time='', df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str
  标的代码，使用时参考 symbol

   start_time
  str
  开始时间 (%Y-%m-%d %H:%M:%S 格式)

   end_time
  str
  结束时间 (%Y-%m-%d %H:%M:%S 格式)

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有

   skip_suspended
  bool
  是否跳过停牌, 默认跳过

   fill_missing
  str or None
  填充方式,  None  - 不填充,  'NaN'  - 用空值填充,  'Last'  - 用上一个值填充, 默认 None

   adjust
  int
   ADJUST_NONE or 0: 不复权 ,  ADJUST_PREV or 1: 前复权 ,  ADJUST_POST or 2: 后复权  默认不复权

   adjust_end_time
  str
  复权基点时间, 默认当前时间

   df
  bool
  是否返回 dataframe 格式, 默认  False


   返回值:参考 tick 对象
  当 df = True 时， 返回 dataframe
  当 df = Falst， 返回 list   示例：


```
history_l2tick=get_history_l2ticks('SHSE.600519', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None,
                        skip_suspended=True, fill_missing=None,
                        adjust=ADJUST_NONE, adjust_end_time='', df=False)
print(history_l2tick[0])
```

  输出：


```
{'symbol': 'SHSE.600519', 'open': 1771.010009765625, 'high': 1809.9000244140625, 'low': 1771.010009765625, 'price': 1791.0999755859375, 'quotes': [{'bid_p': 1790.8800048828125, 'bid_v': 100, 'ask_p': 1794.760009765625, 'ask_v': 200}, {'bid_p': 1790.80004882812
5, 'bid_v': 123, 'ask_p': 1794.800048828125, 'ask_v': 100}, {'bid_p': 1790.699951171875, 'bid_v': 100, 'ask_p': 1794.8800048828125, 'ask_v': 416}, {'bid_p': 1790.68994140625, 'bid_v': 200, 'ask_p': 1794.8900146484375, 'ask_v': 300}, {'bid_p': 1790.630004882812
5, 'bid_v': 300, 'ask_p': 1794.9000244140625, 'ask_v': 1000}, {'bid_p': 1790.6199951171875, 'bid_v': 500, 'ask_p': 1794.949951171875, 'ask_v': 300}, {'bid_p': 1790.6099853515625, 'bid_v': 300, 'ask_p': 1794.9599609375, 'ask_v': 300}, {'bid_p': 1790.59997558593
75, 'bid_v': 200, 'ask_p': 1794.97998046875, 'ask_v': 100}, {'bid_p': 1790.510009765625, 'bid_v': 314, 'ask_p': 1794.989990234375, 'ask_v': 200}, {'bid_p': 1790.5, 'bid_v': 4200, 'ask_p': 1795.0, 'ask_v': 9700}], 'cum_volume': 5866796, 'cum_amount': 1049949547
1.0, 'last_amount': 1973854.0, 'last_volume': 1100, 'created_at': datetime.datetime(2020, 11, 23, 14, 0, 2, tzinfo=tzfile('PRC')), 'cum_position': 0, 'trade_type': 0}
```

  注意：
   1.   get_history_l2ticks 接口每次只能提取一天的数据, 如果取数时间超过一天，则返回按照结束时间的最近有一个交易日数据， 如果取数时间段超过 1 个自然月（31）天，则获取不到数据


## #   get_history_l2bars  - 查询历史 L2 Bar 行情

   仅特定券商付费提供
   函数原型：


```
get_history_l2bars(symbols, frequency, start_time, end_time, fields=None,skip_suspended=True, fill_missing=None,adjust=ADJUST_NONE, adjust_end_time='', df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str
  标的代码，使用时参考 symbol

   frequency
  str
  频率, 支持 '1d', '60s'等

   start_time
  str
  开始时间 (%Y-%m-%d %H:%M:%S 格式)

   end_time
  str
  结束时间 (%Y-%m-%d %H:%M:%S 格式)

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有

   skip_suspended
  bool
  是否跳过停牌, 默认跳过

   fill_missing
  str or None
  填充方式,  None  - 不填充,  'NaN'  - 用空值填充,  'Last'  - 用上一个值填充, 默认 None

   adjust
  int
   ADJUST_NONE or 0: 不复权 ,  ADJUST_PREV or 1: 前复权 ,  ADJUST_POST or 2: 后复权  默认不复权

   adjust_end_time
  str
  复权基点时间, 默认当前时间

   df
  bool
  是否返回 dataframe 格式, 默认  False


   返回值:参考 bar 对象 。
  当 df = True 时， 返回 dataframe
  当 df = Falst， 返回 list
   示例：


```
history_l2bar=get_history_l2bars('SHSE.600000', '60s', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None,
								skip_suspended=True, fill_missing=None,
								adjust=ADJUST_NONE, adjust_end_time='', df=False)
print(history_l2bar[0])
```

  输出：


```
{'symbol': 'SHSE.600000', 'frequency': '60s', 'open': 9.90999984741211, 'high': 9.90999984741211, 'low': 9.890000343322754, 'close': 9.899999618530273, 'volume': 1270526, 'amount': 12574276.0, 'bob': datetime.datetime(2020, 11, 23, 14, 0, tzinfo=tzfile('PRC'))
, 'eob': datetime.datetime(2020, 11, 23, 14, 1, tzinfo=tzfile('PRC')), 'position': 0, 'pre_close': 0.0}
```

  注意：
   1.   get_history_l2bars 接口每次最多可提取 1 个自然月（31）天的数据如：2015.1.1-2015.1.31
错误设置：（2015.1.1-2015.2.1）超出 31 天则获取不到任何数据


## #   get_history_l2transactions  - 查询历史 L2 逐笔成交

  仅特定券商付费提供
   函数原型：


```
get_history_l2transactions(symbols, start_time, end_time, fields=None, df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str
  标的代码，使用时参考 symbol

   start_time
  str
  开始时间 (%Y-%m-%d %H:%M:%S 格式)

   end_time
  str
  结束时间 (%Y-%m-%d %H:%M:%S 格式)

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有

   df
  bool
  是否返回 dataframe 格式, 默认  False


   返回值:参考 level2 逐笔成交数据
  当 df = True 时， 返回 dataframe
  当 df = Falst， 返回 list
   示例：


```
history_transactions=get_history_l2transactions('SHSE.600000', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None, df=False)
print(history_transactions[0])
```

  输出：


```
{'symbol': 'SHSE.600000', 'side': 'B', 'price': 9.90999984741211, 'volume': 100, 'created_at': datetime.datetime(2020, 11, 23, 14, 0, 0, 820000, tzinfo=tzfile('PRC')), 'exec_type': ''}
```

  注意：
   1.   get_history_l2transactions 接口每次只能提取一天的数据, 如果取数时间超过一天，则返回按照开始时间的最近有一个交易日数据


## #   get_history_l2orders  - 查询历史 L2 逐笔委托

  仅特定券商付费提供
 注意：  仅深市标的可用
   函数原型：


```
get_history_l2orders(symbols, start_time, end_time, fields=None, df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str
  标的代码，使用时参考 symbol

   start_time
  str
  开始时间 (%Y-%m-%d %H:%M:%S 格式)

   end_time
  str
  结束时间 (%Y-%m-%d %H:%M:%S 格式)

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有

   df
  bool
  是否返回 dataframe 格式, 默认  False


   返回值:参考 level2 逐笔委托数据
  当 df = True 时， 返回 dataframe
  当 df = Falst， 返回 list
   示例：


```
history_order=get_history_l2orders('SZSE.000001', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None, df=False)
print(history_order[0])
```

  输出：


```
{'symbol': 'SZSE.000001', 'side': '1', 'price': 19.520000457763672, 'volume': 200, 'created_at': datetime.datetime(2020, 11, 23, 14, 0, 0, 110000, tzinfo=tzfile('PRC')), 'order_type': '2'}
```

  注意：
   1.   get_history_l2orders 接口每次只能提取一天的数据, 如果取数时间超过一天，则返回按照开始时间的最近有一个交易日数据


## #   get_history_l2orders_queue  - 查询历史 L2 委托队列

  仅特定券商付费提供
   函数原型：


```
get_history_l2orders_queue(symbols, start_time, end_time, fields=None, df=False)
```

  参数：
     参数名
  类型
  说明

     symbols
  str
  标的代码，使用时参考 symbol

   start_time
  str
  开始时间 (%Y-%m-%d %H:%M:%S 格式)

   end_time
  str
  结束时间 (%Y-%m-%d %H:%M:%S 格式)

   fields
  str
  指定返回对象字段, 如有多个字段, 中间用, 隔开, 默认所有

   df
  bool
  是否返回 dataframe 格式, 默认  False


   返回值:参考 level2 委托队列据
  当 df = True 时， 返回 dataframe
  当 df = Falst， 返回 list
   示例：


```
history_order_queue=get_history_l2orders_queue('SHSE.600000', '2020-11-23 14:00:00', '2020-11-23 15:00:00', fields=None, df=False)
print(history_order_queue[0])
```

  输出：


```
{'symbol': 'SHSE.600000', 'price': 9.90999984741211, 'total_orders': 155, 'queue_orders': 50, 'queue_volumes': [52452, 600, 1200, 3200, 10000, 1800, 1000, 300, 10000, 2000, 500, 500, 2000, 1000, 2000, 300, 1200, 1400, 1000, 200, 1000, 100, 500, 1000, 500, 2380
0, 25400, 1000, 2000, 200, 500, 1200, 5000, 2000, 17600, 5000, 1000, 1300, 1000, 1200, 1000, 3000, 1000, 1000, 15000, 400, 15000, 5000, 2000, 10000], 'created_at': datetime.datetime(2020, 11, 23, 14, 0, 1, tzinfo=tzfile('PRC')), 'side': '', 'volume': 0}
```

  注意：
   1.   get_history_l2orders_queue 接口每次只能提取一天的数据, 如果取数时间超过一天，则返回按照开始时间的最近有一个交易日数据


      ←

        数据事件

        通用数据函数（免费）

      →

---

## 通用数据函数（免费）

> https://www.myquant.cn/docs2/sdk/python/API%E4%BB%8B%E7%BB%8D/%E9%80%9A%E7%94%A8%E6%95%B0%E6%8D%AE%E5%87%BD%E6%95%B0%EF%BC%88%E5%85%8D%E8%B4%B9%EF%BC%89.html

<!DOCTYPE html>




     通用数据函数（免费） - 掘金量化












# #  通用数据函数（免费）

  python 通用数据 API 包含在 gm3.0.148 版本及以上版本，不需要引入新库


## #   get_symbol_infos  - 查询标的基本信息

  获取指定(范围)交易标的基本信息，与时间无关.
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
get_symbol_infos(sec_type1, sec_type2=None, exchanges=None, symbols=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     sec_type1
  int
  证券品种大类
  Y
  无
  指定一种证券大类，只能输入一个. 证券大类 sec_type1 清单 1010: 股票， 1020: 基金， 1030: 债券 ， 1040: 期货， 1050: 期权， 1060: 指数，1070：板块.

   sec_type2
  int
  证券品种细类
  N
  None
  指定一种证券细类，只能输入一个. 默认 None 表示不区分细类，即证券大类下所有细类. 证券细类见 sec_type2 清单 - 股票 101001:A 股，101002:B 股，101003:存托凭证 - 基金 102001:ETF，102002:LOF，102005:FOF，102009:基础设施REITs - 债券 103001:可转债，103008:回购 - 期货 104001:股指期货，104003:商品期货，104006:国债期货 - 期权 105001:股票期权，105002:指数期权，105003:商品期权 - 指数 106001:股票指数，106002:基金指数，106003:债券指数，106004:期货指数 - 板块：107001:概念板块

   exchanges
  str or list
  交易所代码
  N
  None
  输入交易所代码，可输入多个. 采用 str 格式时，多个交易所代码必须用英文逗号分割，如： 'SHSE,SZSE'  采用 list 格式时，多个交易所代码示例： ['SHSE', 'SZSE']  默认 None 表示所有交易所. 交易所代码清单 SHSE:上海证券交易所，SZSE:深圳证券交易所 ， CFFEX:中金所，SHFE:上期所，DCE:大商所， CZCE:郑商所， INE:上海国际能源交易中心 ，GFEX:广期所

   symbols
  str or list
  标的代码
  N
  None
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例： ['SHSE.600008', 'SZSE.000002']  默认 None 表示所有标的.

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式，默认 False 返回字典格式，返回  list[dict] ， 列表每项的 dict 的 key 值为 fields 字段.


   返回值：
     字段名
  类型
  中文名称
  说明
  股票字段
  基金字段
  债券字段
  期货字段
  期权字段
  指数字段

     symbol
  str
  标的代码
  exchange.sec_id
  √
  √
  √
  √
  √
  √

   sec_type1
  int
  证券品种大类
  1010: 股票，1020: 基金， 1030: 债券，1040: 期货， 1050: 期权，1060: 指数，1070：板块
  √
  √
  √
  √
  √
  √

   sec_type2
  int
  证券品种细类
  - 股票 101001:A 股，101002:B 股，101003:存托凭证 - 基金 102001:ETF，102002:LOF，102005:FOF，102009:基础设施REITs - 债券 103001:可转债，103003:国债，103006:企业债，103008:回购 - 期货 104001:股指期货，104003:商品期货，104006:国债期货 - 期权 105001:股票期权，105002:指数期权，105003:商品期权 - 指数 106001:股票指数，106002:基金指数，106003:债券指数，106004:期货指数 - 板块：107001:概念板块
  √
  √
  √
  √
  √
  √

   board
  int
  板块
  A 股 10100101:主板 A 股 10100102:创业板 10100103:科创版 10100104:北交所股票 ETF 10200101:股票 ETF 10200102:债券 ETF 10200103:商品 ETF 10200104:跨境 ETF 10200105:货币 ETF 可转债 10300101:普通可转债 10300102:可交换债券 10300103:可分离式债券
  √
  √
  √
  无
  无
  无

   exchange
  str
  交易所代码
  SHSE:上海证券交易所， SZSE:深圳证券交易所， CFFEX:中金所， SHFE:上期所， DCE:大商所， CZCE:郑商所， INE:上海国际能源交易中心 ，GFEX:广期所
  √
  √
  √
  √
  √
  √

   sec_id
  str
  交易所标的代码
  股票,基金,债券,指数的证券代码; 期货,期权的合约代码
  √
  √
  √
  √
  √
  √

   sec_name
  str
  交易所标的名称
  股票,基金,债券,指数的证券名称; 期货,期权的合约名称
  √
  √
  √
  √
  √
  √

   sec_abbr
  str
  交易所标的简称
  拼音或英文简称
  √
  √
  √
  √
  √
  √

   price_tick
  float
  最小变动单位
  交易标的价格最小变动单位
  √
  √
  √
  √
  √
  √

   trade_n
  int
  交易制度
  0 表示 T+0，1 表示 T+1，2 表示 T+2
  √
  √
  √
  √
  √
  √

   listed_date
  datetime.datetime
  上市日期
  证券/指数的上市日、衍生品合约的挂牌日
  √
  √
  √
  √
  √
  √

   delisted_date
  datetime.datetime
  退市日期
  股票/基金的退市日， 期货/期权的到期日(最后交易日)， 可转债的赎回登记日
  √
  √
  √
  √
  √
  √

   underlying_symbol
  str
  标的资产
  期货/期权的合约标的物 symbol，可转债的正股标的 symbol
  无
  无
  √
  √
  √
  无

   option_type
  str
  行权方式
  期权行权方式，仅期权适用，E:欧式，A:美式
  无
  无
  无
  无
  √
  无

   option_margin_ratio1
  float
  期权保证金计算系数 1
  计算期权单位保证金的第 1 个系数，仅期权适用
  无
  无
  无
  无
  √
  无

   option_margin_ratio2
  float
  期权保证金计算系数 2
  计算期权单位保证金的第 2 个系数，仅期权适用
  无
  无
  无
  无
  √
  无

   call_or_put
  str
  合约类型
  期权合约类型，仅期权适用，C:Call(认购或看涨)， P:Put(认沽或看跌)
  无
  无
  无
  无
  √
  无

   conversion_start_date
  datetime.datetime
  可转债开始转股日期
  可转债初始转股价的执行日期，仅可转债适用
  无
  无
  √
  无
  无
  无

   delisting_begin_date
  datetime.datetime
  退市整理开始日
  股票退市整理期的开始日，退市公告前为空，退市整理期：[退市整理开始日, 退市日前一个交易日]
  √
  无
  无
  无
  无
  无


   示例：


```
get_symbol_infos(sec_type1=1010, symbols='SHSE.600008,SZSE.000002')
```

  输出：


```
[{'symbol': 'SHSE.600008', 'sec_type1': 1010, 'sec_type2': 101001, 'board': 10100101, 'exchange': 'SHSE', 'sec_id': '600008', 'sec_name': '首创环保', 'sec_abbr': 'SCHB', 'price_tick': 0.01, 'trade_n': 1, 'listed_date': datetime.datetime(2000, 4, 27, 0, 0, tzinfo=tzfile('PRC')), 'delisted_date': datetime.datetime(2038, 1, 1, 0, 0, tzinfo=tzfile('PRC')), 'underlying_symbol': '', 'option_type': '', 'option_margin_ratio1': 0.0, 'option_margin_ratio2': 0.0, 'call_or_put': '', 'conversion_start_date': None},
 {'symbol': 'SZSE.000002', 'sec_type1': 1010, 'sec_type2': 101001, 'board': 10100101, 'exchange': 'SZSE', 'sec_id': '000002', 'sec_name': '万科A', 'sec_abbr': 'WKA', 'price_tick': 0.01, 'trade_n': 1, 'listed_date': datetime.datetime(1991, 1, 29, 0, 0, tzinfo=tzfile('PRC')), 'delisted_date': datetime.datetime(2038, 1, 1, 0, 0, tzinfo=tzfile('PRC')), 'underlying_symbol': '', 'option_type': '', 'option_margin_ratio1': 0.0, 'option_margin_ratio2': 0.0, 'call_or_put': '', 'conversion_start_date': None}]
```

  注意：
   1.   sec_type1 为必填参数，即一次只能查询一个品种的标的基本信息。
   2.  查询的标的信息根据参数组合 sec_type1, sec_type2, exchanges, symbols 取交集，若输入参数之间出现任何矛盾（换句话说，所有的参数限制出满足要求的交集为空)，则返回 空list/空DataFrame  ，例如 get_symbol_infos(sec_type1=1040，exchanges='SZSE') 返回的是空值。
   3.  若输入包含无效标的代码 symbols ，则返回的 list/DataFrame 只包含有效标的代码对应的数据。
   4.  参数组合示例：
     查询以下范围 symbol 的基本信息
  sec_type1
  sec_type2
  exchanges
  symbols

     查询指定股票
  1010
  None
  None
  'SHSE.600008,SZSE.000002'

   查询 A 股股票
  1010
  101001
  None
  None

   查询深交所股票
  1010
  None
  'SZSE'
  None

   查询 ETF
  1020
  102001
  None
  None

   查询上交所 LOF
  1020
  102002
  'SHSE'
  None

   查询可转债
  1030
  103001
  None
  None

   查询深交所可转债
  1030
  103001
  'SZSE'
  None

   查询股指期货
  1040
  104001
  None
  None

   查询商品期货
  1040
  104003
  None
  None

   查询郑商所和大商所期货
  1040
  None
  'CZCE,DCE'
  None

   查询股票期权
  1050
  105001
  None
  None

   查询上交所股票期权
  1050
  105001
  'SHSE'
  None

   查询指数期权
  1050
  105002
  None
  None

   查询商品期权
  1050
  105003
  None
  None

   查询上期所商品期权
  105003
  None
  'SHFE'
  None

   查询股票指数
  1060
  106001
  None
  None




## #   get_symbols  - 查询指定交易日多标的交易信息

  获取指定交易日多个标的交易信息，包括基本信息及日度数据.
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
get_symbols(sec_type1, sec_type2=None, exchanges=None, symbols=None, skip_suspended=True, skip_st=True, trade_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     sec_type1
  int
  证券品种大类
  Y
  无
  指定一种证券大类，只能输入一个. 证券大类 sec_type1 清单 1010: 股票， 1020: 基金， 1030: 债券 ， 1040: 期货， 1050: 期权， 1060: 指数，1070：板块.

   sec_type2
  int
  证券品种细类
  N
  None
  指定一种证券细类，只能输入一个. 默认 None 表示不区分细类，即证券大类下所有细类. 证券细类见 sec_type2 清单 - 股票 101001:A 股，101002:B 股，101003:存托凭证 - 基金 102001:ETF，102002:LOF，102005:FOF，102009:基础设施REITs - 债券 103001:可转债，103008:回购 - 期货 104001:股指期货，104003:商品期货，104006:国债期货 - 期权 105001:股票期权，105002:指数期权，105003:商品期权 - 指数 106001:股票指数，106002:基金指数，106003:债券指数，106004:期货指数 - 板块：107001:概念板块

   exchanges
  str or list
  交易所代码
  N
  None
  输入交易所代码，可输入多个. 采用 str 格式时，多个交易所代码必须用英文逗号分割，如： 'SHSE,SZSE'  采用 list 格式时，多个交易所代码示例： ['SHSE', 'SZSE']  默认 None 表示所有交易所. 交易所代码清单 SHSE:上海证券交易所，SZSE:深圳证券交易所 ， CFFEX:中金所，SHFE:上期所，DCE:大商所， CZCE:郑商所， INE:上海国际能源交易中心 ，GFEX:广期所

   symbols
  str or list
  标的代码
  N
  None
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例： ['SHSE.600008', 'SZSE.000002']  默认 None 表示所有标的.

   skip_suspended
  bool
  跳过停牌
  N
  True
  是否跳过全天停牌，默认 True 跳过

   skip_st
  bool
  跳过 ST
  N
  True
  是否跳过包含 ST 的股票： ST, *ST, SST, S*ST , 默认 True 跳过

   trade_date
  str
  交易日期
  N
  None
  交易日期，%Y-%m-%d 格式，默认 None 取最新截面(包含退市标的)

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式，默认 False 返回字典格式，返回  list[dict] ， 列表每项的 dict 的 key 值为 fields 字段.


   返回值：
     字段名
  类型
  中文名称
  说明
  股票字段
  基金字段
  债券字段
  期货字段
  期权字段
  指数字段

     trade_date
  datetime.datetime
  交易日期
  最新交易日的日期
  √
  √
  √
  √
  √
  √

   symbol
  str
  标的代码
  exchange.sec_id
  √
  √
  √
  √
  √
  √

   sec_type1
  int
  证券品种大类
  1010: 股票，1020: 基金， 1030: 债券，1040: 期货， 1050: 期权，1060: 指数，1070：板块
  √
  √
  √
  √
  √
  √

   sec_type2
  int
  证券品种细类
  - 股票 101001:A 股，101002:B 股，101003:存托凭证 - 基金 102001:ETF，102002:LOF，102005:FOF，102009:基础设施REITs - 债券 103001:可转债，103008:回购 - 期货 104001:股指期货，104003:商品期货，104006:国债期货 - 期权 105001:股票期权，105002:指数期权，105003:商品期权 - 指数 106001:股票指数，106002:基金指数，106003:债券指数，106004:期货指数 - 板块：107001:概念板块
  √
  √
  √
  √
  √
  √

   board
  int
  板块
  A 股 10100101:主板 A 股 10100102:创业板 10100103:科创版 10100104:北交所股票 ETF 10200101:股票 ETF 10200102:债券 ETF 10200103:商品 ETF 10200104:跨境 ETF 10200105:货币 ETF 可转债 10300101:普通可转债 10300102:可交换债券 10300103:可分离式债券
  √
  √
  √
  无
  无
  无

   exchange
  str
  交易所代码
  SHSE:上海证券交易所， SZSE:深圳证券交易所， CFFEX:中金所， SHFE:上期所， DCE:大商所， CZCE:郑商所， INE:上海国际能源交易中心 ，GFEX:广期所
  √
  √
  √
  √
  √
  √

   sec_id
  str
  交易所标的代码
  股票,基金,债券,指数的证券代码; 期货,期权的合约代码
  √
  √
  √
  √
  √
  √

   sec_name
  str
  交易所标的名称
  股票,基金,债券,指数的证券名称; 期货,期权的合约名称
  √
  √
  √
  √
  √
  √

   sec_abbr
  str
  交易所标的简称
  拼音或英文简称
  √
  √
  √
  √
  √
  √

   price_tick
  float
  最小变动单位
  交易标的价格最小变动单位
  √
  √
  √
  √
  √
  √

   trade_n
  int
  交易制度
  0 表示 T+0，1 表示 T+1，2 表示 T+2
  √
  √
  √
  √
  √
  √

   listed_date
  datetime.datetime
  上市日期
  证券/指数的上市日、衍生品合约的挂牌日
  √
  √
  √
  √
  √
  √

   delisted_date
  datetime.datetime
  退市日期
  股票/基金的退市日， 期货/期权的到期日(最后交易日)， 可转债的赎回登记日
  √
  √
  √
  √
  √
  √

   underlying_symbol
  str
  标的资产
  期货/期权的合约标的物 symbol，可转债的正股标的 symbol
  无
  无
  √
  √
  √
  无

   option_type
  str
  行权方式
  期权行权方式，仅期权适用，E:欧式，A:美式
  无
  无
  无
  无
  √
  无

   option_margin_ratio1
  float
  期权保证金计算系数 1
  计算期权单位保证金的第 1 个系数，仅期权适用
  无
  无
  无
  无
  √
  无

   option_margin_ratio2
  float
  期权保证金计算系数 2
  计算期权单位保证金的第 2 个系数，仅期权适用
  无
  无
  无
  无
  √
  无

   call_or_put
  str
  合约类型
  期权合约类型，仅期权适用，C:Call(认购或看涨)， P:Put(认沽或看跌)
  无
  无
  无
  无
  √
  无

   conversion_start_date
  datetime.datetime
  可转债开始转股日期
  可转债初始转股价的执行日期，仅可转债适用
  无
  无
  √
  无
  无
  无

   is_adjusted
  bool
  合约调整
  是否调整合约，True:是，False:否（调整后会产生新的新的合约名称、新的行权价格、新的合约乘数）
  无
  无
  无
  无
  √
  无

   is_suspended
  bool
  是否停牌
  是否停牌，True:是，False:否
  √
  √
  √
  无
  无
  无

   is_st
  bool
  是否 ST
  是否 ST，True: 是 ST 类（含 ST, *ST, SST, S*ST ）, False: 否
  √
  无
  无
  无
  无
  无

   position
  int
  持仓量
  当日累计持仓量(当日盘后更新)
  无
  无
  无
  √
  √
  无

   settle_price
  float
  结算价
  当日结算价(当日盘后更新)
  无
  无
  无
  √
  √
  无

   pre_settle
  float
  昨结价
  昨日结算价
  无
  无
  无
  √
  √
  无

   pre_close
  float
  昨收价
  昨日收盘价
  √
  √
  √
  √
  √
  √

   upper_limit
  float
  涨停价
  当日涨停价（首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）
  √
  √
  √
  √
  √
  无

   lower_limit
  float
  跌停价
  当日跌停价（首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）
  √
  √
  √
  √
  √
  无

   turn_rate
  float
  换手率
  当日换手率(%)(当日盘后更新)
  √
  √
  无
  无
  无
  √

   adj_factor
  float
  复权因子
  当日累计后复权因子
  √
  √
  无
  无
  无
  无

   margin_ratio
  float
  保证金比例
  期货最新保证金比例（交易所标准的最新期货保证金）
  无
  无
  无
  √
  无
  无

   conversion_price
  float
  转股价
  可转债最新转股价（转股价变动后的最新转股价）
  无
  无
  √
  无
  无
  无

   exercise_price
  float
  行权价
  期权最新行权价（期权合约调整后的最新行权价）
  无
  无
  无
  无
  √
  无

   multiplier
  int
  合约乘数
  期货和期权合约最新合约乘数（期权合约调整后的最新合约乘数）
  无
  无
  无
  √
  √
  无

   delisting_begin_date
  datetime.datetime
  退市整理开始日
  股票退市整理期的开始日，退市公告前为空，退市整理期：[退市整理开始日, 退市日前一个交易日]
  √
  无
  无
  无
  无
  无


   示例：


```
get_symbols(sec_type1=1010, symbols='SHSE.600008,SZSE.000002', trade_date='2022-01-13')
```

  输出：


```
[{'trade_date': datetime.datetime(2022, 1, 13, 0, 0, tzinfo=tzfile('PRC')), 'pre_close': 3.47, 'upper_limit': 3.82, 'lower_limit': 3.12, 'turn_rate': 1.1215, 'adj_factor': 6.5564, 'margin_ratio': 1.0, 'multiplier': 1, 'is_adjusted': False, 'is_suspended': False, 'position': 0, 'settle_price': 0.0, 'pre_settle': 0.0, 'conversion_price': 0.0, 'exercise_price': 0.0, 'is_st': False, 'symbol': 'SHSE.600008', 'sec_type1': 1010, 'sec_type2': 101001, 'board': 10100101, 'exchange': 'SHSE', 'sec_id': '600008', 'sec_name': '首创环保', 'sec_abbr': 'SCHB', 'price_tick': 0.01, 'trade_n': 1, 'listed_date': datetime.datetime(2000, 4, 27, 0, 0, tzinfo=tzfile('PRC')), 'delisted_date': datetime.datetime(2038, 1, 1, 0, 0, tzinfo=tzfile('PRC')), 'underlying_symbol': '', 'option_type': '', 'option_margin_ratio1': 0.0, 'option_margin_ratio2': 0.0, 'call_or_put': '', 'conversion_start_date': None},
 {'trade_date': datetime.datetime(2022, 1, 13, 0, 0, tzinfo=tzfile('PRC')), 'pre_close': 22.05, 'upper_limit': 24.26, 'lower_limit': 19.85, 'turn_rate': 0.9394, 'adj_factor': 173.0897, 'margin_ratio': 1.0, 'multiplier': 1, 'is_adjusted': False, 'is_suspended': False, 'position': 0, 'settle_price': 0.0, 'pre_settle': 0.0, 'conversion_price': 0.0, 'exercise_price': 0.0, 'is_st': False, 'symbol': 'SZSE.000002', 'sec_type1': 1010, 'sec_type2': 101001, 'board': 10100101, 'exchange': 'SZSE', 'sec_id': '000002', 'sec_name': '万科A', 'sec_abbr': 'WKA', 'price_tick': 0.01, 'trade_n': 1, 'listed_date': datetime.datetime(1991, 1, 29, 0, 0, tzinfo=tzfile('PRC')), 'delisted_date': datetime.datetime(2038, 1, 1, 0, 0, tzinfo=tzfile('PRC')), 'underlying_symbol': '', 'option_type': '', 'option_margin_ratio1': 0.0, 'option_margin_ratio2': 0.0, 'call_or_put': '', 'conversion_start_date': None}]
```

  注意：
   1.   sec_type1 为必填参数，即一次只能查询一个品种的标的最新交易日信息。
   2.  查询的标的信息根据参数组合 sec_type1, sec_type2, exchanges, symbols 取交集，若输入参数之间出现任何矛盾（换句话说，所有的参数限制出满足要求的交集为空)，则返回 空list/空DataFrame  ，例如 get_symbols(sec_type1=1040, exchanges='SZSE') 返回的是空值。
   3.  若输入包含无效标的代码 symbols ，则返回的 list/DataFrame 只包含有效标的代码对应的数据。
   4.  获取全 A 股票代码示例 get_symbols(sec_type1=1010, sec_type2=101001, df=True)['symbol'].tolist()
   5.  可转债的到期日(退市日期)为 delisted_date ，转股价值为 转股价值 = 转股数*股价 = (100/可转债转股价) * 股价


## #   get_history_symbol  - 查询指定标的多日交易信息

  获取指定标的多个历史交易日的交易信息，包括基本信息及日度数据.
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
get_history_symbol(symbol=None, start_date=None, end_date=None, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbol
  str
  标的代码
  Y
  无
  输入标的代码，只能输入一个.

   start_date
  str
  开始时间
  N
  None
  开始时间日期，%Y-%m-%d 格式，默认 None 表示当前时间

   end_date
  str
  结束时间
  N
  None
  结束时间日期，%Y-%m-%d 格式，默认 None 表示当前时间

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式，默认 False 返回字典格式，返回  list[dict] ， 列表每项的 dict 的 key 值为 fields 字段.


   返回值：
     字段名
  类型
  中文名称
  说明
  股票字段
  基金字段
  债券字段
  期货字段
  期权字段
  指数字段

     trade_date
  datetime.datetime
  交易日期
  最新交易日的日期
  √
  √
  √
  √
  √
  √

   symbol
  str
  标的代码
  exchange.sec_id
  √
  √
  √
  √
  √
  √

   sec_type1
  int
  证券品种大类
  1010: 股票，1020: 基金， 1030: 债券，1040: 期货， 1050: 期权，1060: 指数，1070：板块
  √
  √
  √
  √
  √
  √

   sec_type2
  int
  证券品种细类
  - 股票 101001:A 股，101002:B 股，101003:存托凭证 - 基金 102001:ETF，102002:LOF，102005:FOF，102009:基础设施REITs - 债券 103001:可转债，103008:回购 - 期货 104001:股指期货，104003:商品期货，104006:国债期货 - 期权 105001:股票期权，105002:指数期权，105003:商品期权 - 指数 106001:股票指数，106002:基金指数，106003:债券指数，106004:期货指数 - 板块：107001:概念板块
  √
  √
  √
  √
  √
  √

   board
  int
  板块
  A 股 10100101:主板 A 股 10100102:创业板 10100103:科创版 10100104:北交所股票 ETF 10200101:股票 ETF 10200102:债券 ETF 10200103:商品 ETF 10200104:跨境 ETF 10200105:货币 ETF 可转债 10300101:普通可转债 10300102:可交换债券 10300103:可分离式债券
  √
  √
  √
  无
  无
  无

   exchange
  str
  交易所代码
  SHSE:上海证券交易所， SZSE:深圳证券交易所， CFFEX:中金所， SHFE:上期所， DCE:大商所， CZCE:郑商所， INE:上海国际能源交易中心 ，GFEX:广期所
  √
  √
  √
  √
  √
  √

   sec_id
  str
  交易所标的代码
  股票,基金,债券,指数的证券代码; 期货,期权的合约代码
  √
  √
  √
  √
  √
  √

   sec_name
  str
  交易所标的名称
  股票,基金,债券,指数的证券名称; 期货,期权的合约名称
  √
  √
  √
  √
  √
  √

   sec_abbr
  str
  交易所标的简称
  拼音或英文简称
  √
  √
  √
  √
  √
  √

   price_tick
  float
  最小变动单位
  交易标的价格最小变动单位
  √
  √
  √
  √
  √
  √

   trade_n
  int
  交易制度
  0 表示 T+0，1 表示 T+1，2 表示 T+2
  √
  √
  √
  √
  √
  √

   listed_date
  datetime.datetime
  上市日期
  证券/指数的上市日、衍生品合约的挂牌日
  √
  √
  √
  √
  √
  √

   delisted_date
  datetime.datetime
  退市日期
  股票/基金的退市日， 期货/期权的到期日(最后交易日)， 可转债的赎回登记日
  √
  √
  √
  √
  √
  √

   underlying_symbol
  str
  标的资产
  期货/期权的合约标的物 symbol，可转债的正股标的 symbol
  无
  无
  √
  √
  √
  无

   option_type
  str
  行权方式
  期权行权方式，仅期权适用，E:欧式，A:美式
  无
  无
  无
  无
  √
  无

   option_margin_ratio1
  float
  期权保证金计算系数 1
  计算期权单位保证金的第 1 个系数，仅期权适用
  无
  无
  无
  无
  √
  无

   option_margin_ratio2
  float
  期权保证金计算系数 2
  计算期权单位保证金的第 2 个系数，仅期权适用
  无
  无
  无
  无
  √
  无

   call_or_put
  str
  合约类型
  期权合约类型，仅期权适用，C:Call(认购或看涨)， P:Put(认沽或看跌)
  无
  无
  无
  无
  √
  无

   conversion_start_date
  datetime.datetime
  可转债开始转股日期
  可转债初始转股价的执行日期，仅可转债适用
  无
  无
  √
  无
  无
  无

   is_adjusted
  bool
  合约调整
  是否调整合约，True:是，False:否（调整后会产生新的新的合约名称、新的行权价格、新的合约乘数）
  无
  无
  无
  无
  √
  无

   is_suspended
  bool
  是否停牌
  是否停牌，True:是，False:否
  √
  √
  √
  无
  无
  无

   is_st
  bool
  是否 ST
  是否 ST，True: 是 ST 类（含 ST, *ST, SST, S*ST ）, False: 否
  √
  无
  无
  无
  无
  无

   position
  int
  持仓量
  当日累计持仓量(当日盘后更新)
  无
  无
  无
  √
  √
  无

   settle_price
  float
  结算价
  当日结算价(当日盘后更新)
  无
  无
  无
  √
  √
  无

   pre_settle
  float
  昨结价
  昨日结算价
  无
  无
  无
  √
  √
  无

   pre_close
  float
  昨收价
  昨日收盘价
  √
  √
  √
  √
  √
  √

   upper_limit
  float
  涨停价
  当日涨停价（首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）
  √
  √
  √
  √
  √
  无

   lower_limit
  float
  跌停价
  当日跌停价（首次公开发行上市的股票上市前 5 日无涨跌停价，返回0）
  √
  √
  √
  √
  √
  无

   turn_rate
  float
  换手率
  当日换手率(%)(当日盘后更新)
  √
  √
  无
  无
  无
  √

   adj_factor
  float
  复权因子
  当日累计后复权因子
  √
  √
  无
  无
  无
  无

   margin_ratio
  float
  保证金比例
  期货在指定交易日的交易所保证金比例
  无
  无
  无
  √
  无
  无

   conversion_price
  float
  转股价
  可转债在指定交易日的转股价
  无
  无
  √
  无
  无
  无

   exercise_price
  float
  行权价
  期权在指定交易日的行权价
  无
  无
  无
  无
  √
  无

   multiplier
  int
  合约乘数
  期货/期权合约在指定交易日的合约乘数
  无
  无
  无
  √
  √
  无

   delisting_begin_date
  datetime.datetime
  退市整理开始日
  股票退市整理期的开始日，退市公告前为空，退市整理期：[退市整理开始日, 退市日前一个交易日]
  √
  无
  无
  无
  无
  无


   示例：


```
get_history_symbol(symbol='SZSE.000002', start_date='2022-09-01', end_date='2022-09-30', df=True)
```

  输出：


```
trade_date  pre_close  ...  conversion_start_date
0  2022-09-01 00:00:00+08:00      16.63  ...                   None
1  2022-09-02 00:00:00+08:00      16.84  ...                   None
2  2022-09-05 00:00:00+08:00      16.80  ...                   None
3  2022-09-06 00:00:00+08:00      17.17  ...                   None
4  2022-09-07 00:00:00+08:00      17.85  ...                   None
5  2022-09-08 00:00:00+08:00      17.52  ...                   None
6  2022-09-09 00:00:00+08:00      17.58  ...                   None
7  2022-09-13 00:00:00+08:00      18.15  ...                   None
8  2022-09-14 00:00:00+08:00      18.18  ...                   None
9  2022-09-15 00:00:00+08:00      17.91  ...                   None
10 2022-09-16 00:00:00+08:00      18.50  ...                   None
11 2022-09-19 00:00:00+08:00      18.00  ...                   None
12 2022-09-20 00:00:00+08:00      18.18  ...                   None
13 2022-09-21 00:00:00+08:00      17.56  ...                   None
14 2022-09-22 00:00:00+08:00      17.56  ...                   None
15 2022-09-23 00:00:00+08:00      17.49  ...                   None
16 2022-09-26 00:00:00+08:00      17.51  ...                   None
17 2022-09-27 00:00:00+08:00      17.44  ...                   None
18 2022-09-28 00:00:00+08:00      17.60  ...                   None
19 2022-09-29 00:00:00+08:00      17.46  ...                   None
20 2022-09-30 00:00:00+08:00      17.15  ...                   None

[21 rows x 34 columns]
```

  注意：
   1.  若输入包含无效标的代码 symbol ，则返回的 list/DataFrame 只包含有效标的代码对应的数据。
   2.  停牌时且股票发生除权除息，涨停价和跌停价可能有误差。
   3.  对每个标的，数据根据 trade_date 的升序进行排序。
   4.   start_date 和 end_date 中月份和日期都可以只输入个位数，例: '2010-7-8'或'2017-7-30'
   5.  当 start_date 小于或者等于  end_date  时, 取指定时间段的数据,当  start_date  >  end_date 时, 返回报错
   6.  可转债的到期日(退市日期) delisted_date ，转股价值为 转股价值 = 转股数*股价 = (100/可转债转股价) * 股价


## #   get_trading_dates_by_year  - 查询年度交易日历

  查询一个交易所的指定年份的交易日历.
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
get_trading_dates_by_year(exchange, start_year, end_year)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     exchange
  str
  交易所代码
  Y
  无
  只能填写一个交易所代码 交易所代码清单: SHSE:上海证券交易所，SZSE:深圳证券交易所，CFFEX:中金所，SHFE:上期所，DCE:大商所，CZCE:郑商所，INE:上海国际能源交易中心，GFEX:广期所

   start_year
  int
  开始年份
  Y
  无
  查询交易日历开始年份（含），yyyy 格式

   end_year
  int
  结束年份
  Y
  无
  查询交易日历结束年份（含），yyyy 格式


   返回值:dataframe
      字段名
   类型
   中文名称
   说明

     date
  str
  自然日期
  查询年份的自然日日期

   trade_date
  str
  交易日期
  查询年份的交易日日期，如果所在自然日不是交易日，交易日期为空字符串 ''

   next_trade_date
  str
  下一交易日
  交易日对应的下一交易日

   pre_trade_date
  str
  上一交易日
  交易日对应的上一交易日


   示例：


```
# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

def init(context):

    # 实时模式
    if context.mode == MODE_LIVE:
        context.trade_date = get_trading_dates_by_year(exchange='SHSE', start_year=int(context.now.strftime('%Y')) - 1,
                                                       end_year=int(context.now.strftime('%Y')) + 1)
        context.trade_date.index = context.trade_date['date']
    # 回测模式
    else:
        context.trade_date = get_trading_dates_by_year(exchange='SHSE', start_year=int(context.backtest_start_time[:4]) - 1,
                                                       end_year=int(context.backtest_end_time[:4]) + 1)
        context.trade_date.index = context.trade_date['date']
    today = context.now.strftime('%Y-%m-%d')
    next_trade_date = context.trade_date.loc[today, 'next_trade_date']
    pre_trade_date = context.trade_date.loc[today, 'pre_trade_date']
    print('今天：{}, 上个交易日：{}， 下个交易日：{}'.format(today, pre_trade_date, next_trade_date))

    # 判断当天是否为交易日
    trade_date = context.trade_date['trade_date'].tolist()
    if context.now.strftime('%Y-%m-%d') not in  trade_date:
        print(context.now,"当前为非交易日")
    else:
        print(context.now, "当前为交易日")
```

  输出：


```
今天：2023-08-21, 上个交易日：2023-08-18， 下个交易日：2023-08-22
```

  示例：


```
get_trading_dates_by_year(exchange='SHSE', start_year=2020, end_year=2023)
```

  输出：


```
date next_trade_date pre_trade_date  trade_date
0     2020-01-01      2020-01-02     2019-12-31
1     2020-01-02      2020-01-03     2019-12-31  2020-01-02
2     2020-01-03      2020-01-06     2020-01-02  2020-01-03
3     2020-01-04      2020-01-06     2020-01-03
4     2020-01-05      2020-01-06     2020-01-03
         ...             ...            ...         ...
1456  2023-12-27      2023-12-28     2023-12-26  2023-12-27
1457  2023-12-28      2023-12-29     2023-12-27  2023-12-28
1458  2023-12-29      2024-01-02     2023-12-28  2023-12-29
1459  2023-12-30      2024-01-02     2023-12-29
1460  2023-12-31      2024-01-02     2023-12-29

[1461 rows x 4 columns]
```

  注意：
   1.   exchange 参数仅支持输入单个交易所代码，若代码错误，会报错
   2.  开始年份必须不晚于结束年份，否则返回 空dataframe


## #   get_previous_n_trading_dates  - 查询指定日期的前n个交易日

  查询一个交易所指定日期的前n个交易日
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准, gm SDK 3.0.163 版本新增
   函数原型：


```
get_previous_n_trading_dates(exchange, date, n=1)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     exchange
  str
  交易所代码
  Y
  无
  只能填写一个交易所代码，交易所代码清单： SHSE:上海证券交易所，SZSE:深圳证券交易所，CFFEX:中金所，SHFE:上期所，DCE:大商所，CZCE:郑商所，INE:能源中心，GFEX:广期所

   date
  str
  指定日期
  Y
  无
  指定的基准日期T，%Y-%m-%d 格式

   n
  int
  交易日个数
  N
  无
  前n个交易日，默认为1，即前一天，取值范围[1，支持的最早交易日至当前交易日个数-1]


   返回值：
  交易日期字符串(%Y-%m-%d 格式)列表


```
get_previous_n_trading_dates(exchange='SHSE', date='2023-10-10', n=10)
```

  输出：


```
['2023-09-18', '2023-09-19', '2023-09-20', '2023-09-21', '2023-09-22', '2023-09-25', '2023-09-26', '2023-09-27', '2023-09-28', '2023-10-09']
```

  注意：
   1.  exchange参数仅支持输入单个交易所代码。
   2.  n必须为非零正整数，n=0时会报错，n超出最早支持的交易日时只会返回至最早交易日。
   3.  获取date前N个交易日，不包括date日期。


## #   get_next_n_trading_dates  - 查询指定日期的后n个交易日

  查询一个交易所指定日期的后n个交易日
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准, gm SDK 3.0.163 版本新增
   函数原型：


```
get_next_n_trading_dates(exchange, date, n=1)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     exchange
  str
  交易所代码
  Y
  无
  只能填写一个交易所代码，交易所代码清单： SHSE:上海证券交易所，SZSE:深圳证券交易所，CFFEX:中金所，SHFE:上期所，DCE:大商所，CZCE:郑商所，INE:能源中心，GFEX:广期所

   date
  str
  指定日期
  Y
  无
  指定的基准日期T，%Y-%m-%d 格式

   n
  int
  交易日个数
  N
  无
  前n个交易日，默认为1，即前一天，取值范围[1，支持的最早交易日至当前交易日个数-1]


   返回值：
  交易日期字符串(%Y-%m-%d 格式)列表


```
get_next_n_trading_dates(exchange='SHSE', date='2023-09-27', n=10)
```

  输出：


```
['2023-09-28', '2023-10-09', '2023-10-10', '2023-10-11', '2023-10-12', '2023-10-13', '2023-10-16', '2023-10-17', '2023-10-18', '2023-10-19']
```

  注意：
   1.  exchange参数仅支持输入单个交易所代码。
   2.  n必须为非零正整数，n=0时会报错，n超出最早支持的交易日时只会返回至最早交易日。
   3.  获取date前N个交易日，不包括date日期。


## #   get_trading_session  - 查询交易时段

  查询一个标的所属品种交易时间段.
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
get_trading_session(symbols, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  标的代码
  Y
  无
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如： 'SHSE.600008,SZSE.000002'  采用 list 格式时，多个标的代码示例： ['SHSE.600008', 'SZSE.000002'] .

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式， 默认 False 返回字典格式，返回 list[dict] ，列表每项的 dict 的 key 值见返回字段名


   返回值：
     字段名
  类型
  中文名称
  说明

     symbol
  str
  标的代码
  exchange.sec_id

   exchange
  str
  交易所代码
  SHSE:上海证券交易所，SZSE:深圳证券交易所，CFFEX:中金所， SHFE:上期所，DCE:大商所，CZCE:郑商所，INE:上海国际能源交易中心，GFEX:广期所

   time_trading
  list[dict]
  连续竞价时段
  HH:MM 格式，按时间顺序排列，如品种存在夜盘，夜盘时段排最前。 如 [{'start': '09:30'，'end': '11:30'}， {'start': '13:00'， 'end': '14:57'}] ，

   time_auction
  list[dict]
  集合竞价时段
  HH:MM 格式，按时间顺序排列，如品种存在夜盘，夜盘时段排最前。 如 [{’start': '09:15'， 'end': '09:25'}，{'start': '14:57'， 'end': '15:00'}] ，


   示例：


```
get_trading_session(symbols='SHFE.au2306', df=False)
```

  输出：


```
[{'symbol': 'SHFE.AU2306', 'exchange': 'SHFE', 'time_trading': [{'start': '21:00', 'end': '2:30'}, {'start': '9:00', 'end': '10:15'}, {'start': '10:30', 'end': '11:30'}, {'start': '13:30', 'end': '15:00'}], 'time_auction': [{'start': '20:55', 'end': '20:59'}]}]
```

  注意：
   1.  如果输入不存在的合约代码 symbol，会报错提示"该合约[symbol]不存在"。


## #   get_contract_expire_rest_days  - 查询合约到期剩余天数

  查询期货合约、期权合约、可转债的到期剩余天数。
   此函数为掘金公版(体验版/专业版/机构版)函数，券商版以升级提示为准
   函数原型：


```
get_contract_expire_rest_days(symbols, start_date=None, end_date=None, trade_flag = False, df=False)
```

  参数：
     参数名
  类型
  中文名称
  必填
  默认值
  参数用法说明

     symbols
  str or list
  标的代码
  Y
  无
  输入标的代码，可输入多个. 采用 str 格式时，多个标的代码必须用英文逗号分割，如： 'CFFEX.IF2212,CFFEX.IC2212'  采用 list 格式时，多个标的代码示例： ['CFFEX.IF2212', CFFEX.IC2212'] .

   start_date
  str or datetime
  开始日期
  N
  None
  %Y-%m-%d 格式，不早于合约上市日 默认 None 表示最新时间.

   end_date
  str or datetime
  结束日期
  N
  None
  %Y-%m-%d 格式，不早于指定的开始日期，否则返回报错 默认 None 表示最新时间.

   trade_flag
  bool
  交易日
  N
  False
  是否需要按交易日计算，默认 False 按自然日计算，则返回到期剩余自然日天数; 设置为 True 按交易日计算，则返回到期剩余交易日天数

   df
  bool
  返回格式
  N
  False
  是否返回 dataframe 格式， 默认 False 返回字典格式，返回 list[dict] ，列表每项的 dict 的 key 值见返回字段名


   返回值：
     字段名
  类型
  中文名称
  说明

     date
  str
  日期
  [开始日期,结束日期]内的自然日期

   symbol
  str
  合约代码
  exchange.sec_id

   days_to_expire
  int
  到期剩余天数
  合约在指定交易时间至合约到期日的剩余天数. trade_flag=False，计算方法按自然日 trade_flag=True，计算方法按交易日


   示例：


```
get_contract_expire_rest_days(symbols='CFFEX.IM2212', start_date='2022-12-12', end_date='2022-12-16', trade_flag = True, df=True)
```

  输出：


```
date        symbol  days_to_expire
0  2022-12-12  CFFEX.IM2212               4
1  2022-12-13  CFFEX.IM2212               3
2  2022-12-14  CFFEX.IM2212               2
3  2022-12-15  CFFEX.IM2212               1
4  2022-12-16  CFFEX.IM2212               0
```

  注意：
   1.  参数 start_date 和 end_date 必须是 pd.to_dateime()可识别的字符串 str 格式，例'yyyy-mm-dd'， 'yyyy-mm-dd %H:%M:%S'，或者是 datetime 对象
   2.  在到期日当天，到期剩余天数为 0。正数表示距离到期日的剩余天数，0 表示到期日当天，负数表示距离到期日已经过去的天数。
   3.  如果输入不存在的合约代码 symbol ，会报错提示"该合约[symbol]不存在"。
   4.  如果输入的合约代码 symbol 在时间段内的某个日期未上市，在该日期的到期剩余天数返回 NaN。
   5.  用于剩余天数计算的到期日是最后交易日。


      ←

        行情数据查询函数（免费）

        股票财务数据及基础数据函数（免费）

      →