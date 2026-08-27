# 量化开发工具

产品 4（见根目录 `PLAN-五产品矩阵.md`）。本地模型 + 微调，策略不出机。

## v0.1 ✅ 互转骨架

- `ir.py` —— 策略中间表示（Strategy IR）+ 双均线 demo
- `emitters.py` —— IR → 聚宽/PTrade 确定性模板发射（含 open→09:30 等已知差异映射）
- `parsers.py` —— AST 确定性解析（平台代码 → IR），超范围抛 ParseError 留待 LLM 兜底
- `validate.py` —— 语法 + API 白名单沙箱校验（禁 os/sys/subprocess/网络/文件）
- `translate.py` —— 互转主流程 translate / roundtrip
- `demo.py` —— `python -m products.quant.demo`：双均线 聚宽↔PTrade 双向互转全流程
- `api_maps/` —— 平台 API 对照表（互转映射 / 校验白名单 / 微调语料三用）
- 测试：`tests/test_quant_translate.py`

## v0.5 ✅ 数据接入 + 语义校验基准

- 5 种基准信号：ma_cross / threshold / rsi / bollinger / grid（emitters 与 parsers 双向支持）
- `sim.py` —— 桩运行时：mocked 平台 API 真实 exec 生成代码，同行情逐日比对目标仓位信号
- `data/` —— akshare 日线接入（懒加载可选依赖 + CSV 缓存）+ 自带样本行情 200 根日线
- `benchmark.py` —— `python -m products.quant.benchmark`：5 策略 × 双向互转一致率报告
  （当前全部 100%，验收线 ≥90%）
- 测试：`tests/test_quant_sim.py`
- RAG 知识库 ✅：`kb.py`（API 对照表 + 从基准策略动态生成的 10 条 few-shot 代码↔IR 对
  + `kb/*.md` 手写知识，关键词检索）；`llm_parse.py`（手写策略 → LLM → IR，严格校验 +
  带反馈重试）；`translate(..., chat_fn=...)` 在 AST 解析抛 ParseError 时自动兜底，
  测试全走 mock chat_fn，无需网络
- 后续：`adapters/`（QMT/掘金）、v2.0 微调（语料 = 对照表 + 策略对，已在 kb.py 汇集）

## v1.0 ✅ 互转面板 + QMT 探活

- `ui_panel_quant.py` —— 顶栏「📈 策略互转」入口（仅本产品，功能开关 `quant`）：
  粘贴策略 → 选源/目标平台 → 互转 → 校验报告；「LLM 兜底」勾选后手写策略
  后台线程走 RAG 解析；一键载入双均线示例、复制结果
- `qmt.py` —— QMT/miniQMT 终端探活：psutil → tasklist/ps 三级进程探测 +
  xtquant SDK 检测；面板内实时刷新
- 测试：`tests/test_quant_qmt.py`（探活注入式测试，不碰真机）

## v1.5 ✅ 四平台互转矩阵（掘金/QMT）

- 平台扩到 4 个：joinquant / ptrade / **gm（掘金）** / **qmt（miniQMT xtquant）**
- 平台差异收敛为四项：入口/上下文变量名（initialize+context / init+C）、
  调度（run_daily / schedule / handlebar bar 驱动）、K 线获取、时间映射
- `symbols.py` —— 标的代码自动转换（`000001.XSHE` ↔ `SZSE.000001` ↔ `000001.SZ`），
  IR 内部统一聚宽规范形
- QMT 下单为占位调用 + 人工确认注释（passorder 股数换算在对照表标 TBD，不臆造）
- `api_maps/` 新增 gm_myquant.md / qmt_xtquant.md；RAG few-shot 自动扩到 20 条
- benchmark 全矩阵：5 策略 × 12 方向，实测全部 100%
- 测试：`tests/test_quant_platforms.py`

## v2.0 ✅ 多标的动量轮动（产品可转换）

- 新增信号 kind **`momentum_rotation`**：多标的动量轮动，四平台（聚宽/PTrade/掘金/QMT）
  **确定性互转**。语义：对 universe 每只 ETF 取近 `lookback+1` 根日线收盘，纯 Python
  加权(1→2)对数回归算年化动量 slope 与 R²，分数 = 年化收益 × R²；近 `drop_days` 日任一日
  收盘比 < `drop_threshold`（如 0.95）→ 分数归零；取 `min_score < score < max_score` 者
  按分数降序（同分按代码升序）选前 `top_n` 等权，其余清仓。
- `demo_etf_rotation()`：全球宽基 ETF 轮动示例（19 只 ETF，`lookback=25 / top_n=1`），
  unicode 标的聚宽规范形，发射到掘金/QMT 自动转换代码格式。
- `sim.py` 支持**逐标的**历史获取与逐日**持有证券集合**一致率口径；`consistency` 按
  策略类型自动选口径（单标的比目标仓位、轮动比持有集合），持有集合用规范形跨平台可比。
- `data/synthetic_bars()`：确定性多标的合成行情（独立漂移 + 跌幅事件制造轮动），供
  benchmark / sim 使用（只用于互转一致性校验，不用于收益回测）。
- benchmark 扩到 **6 策略 × 12 方向**，实测全部 100%。
- **示例（产品可载入转换）**：`examples/` 存放用户聚宽策略：
  - `全球宽基ETF轮动策略.py` —— 聚宽原版（可被产品确定性四平台互转）
  - `早小市值.py` —— 干净版小市值（**无八星打分**；仅产品 LLM 兜底转换，不保证一致率）
  - 面板示例下拉：双均线 / 全球宽基ETF轮动 / 早小市值（干净版）
- 测试：`tests/test_quant_rotation.py`

## 说明：八星打分

「早小市值加ETF.py」中的**八星打分（代码数字吉凶对）仅作演示、不构成有效信号、不保证
收益**——已从示例中剔除，改用干净版 `早小市值.py`（纯市值排序 + 连续3天-2%清仓冷静期）
作为有效参考。小市值类依赖聚宽 `get_index_stocks` / `get_fundamentals`（指数成分与基本面），
四平台 API 差异大，产品只能走 LLM 兜底转换（不保证一致率）。

## 互转铁律

走 IR，不做平台 N×N 直译。校验三件套：语法 + API 白名单 + 桩运行时信号一致率。

## 合规红线

开发/研究工具定位，不承诺收益；下单动作强制人工确认；平台 SDK 只引用不内嵌。
