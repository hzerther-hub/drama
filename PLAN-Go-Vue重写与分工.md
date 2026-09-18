# PLAN：Go + Vue 重写与四人分工

> 版本：v1.0 ｜ 日期：2026-09-16
> 团队：1 名资深（下称 **S**）+ 3 名偏后端、Go/Vue 双新手（下称 **A / B / C**）
> 交付目标：novelwriter 主产品的 Go 内核 + Wails/Vue 桌面端 + CLI，行为与 Python 版一致
>
> 本文取代 `PLAN-Reasonix-Desktop-Go重写.md` 的**前端选型**（Wails+React → Wails+Vue）与**里程碑**章节；
> 该文档的架构判断（三模块 go.work、kernel 不 import Wails、SetSink 一套循环两种壳）继续有效，不再重复。

---

## 1. 决策基线

| 项 | 决策 |
|---|---|
| 范围 | **仅 novelwriter**。quant / devtool / devrag / gpulocal 保留 Python 版不动 |
| v1 砍掉 | 截图覆盖层（`screenshot.py` 880 行）、图片标注面板（`ui_panel_annotate.py` 366 行）、语音输入（`voice.py` 187 行） |
| v1 替换 | 内置编辑器（手写高亮+补全+LSP 胶水，`ui.py:1955-3110`）→ 直接换 Monaco |
| 后端 | Go 内核（纯 Go，`CGO_ENABLED=0`），SQLite 用 `modernc.org/sqlite` |
| 桌面 | Wails v2 + Vue 3 + Vite + TypeScript + Pinia |
| 周期 | 约 **11 周**（P0 1 周 + P1 3 周 + P2 3 周 + P3 3 周 + P4 缓冲 1 周） |
| Python 仓库 | 冻结保留，作为行为对照与 golden files 来源，不删除 |

---

## 2. 分工的四个依据（为什么这么分）

这些是实际探查仓库得出的结论，分工直接建立在其上。

**依据一：内核已经零 UI 依赖，所以 Go 内核可以独立开工。**
27 个内核模块里没有任何一个 `import ui` 或 `import tkinter`（逐文件计数为 0）。UI 与内核只靠 `on_event(dict)` 回调通信，唯一的双向耦合是 `ui.py ↔ ui_panel_*`（面板函数内惰性 `import ui`），这个环不经过内核。结论：**不需要先做 UI 才能做内核**，这是四线能并行的前提。

**依据二：`config.py` 是唯一枢纽，必须先冻结，否则四线互相阻塞。**
`config.py` 被 24 个非测试文件导入（`cache`/`llm`/`tools`/`agent`/`novel_chain`/`ui` 及全部面板）。因此 W1 只有一件事最重要：把 `config` 包和全部 Go 接口冻结下来。

**依据三：扇出最大的两个文件必须归 S。**
`tools.py`（1048 行 / 43KB）在函数内惰性拼装 7 个后端（`checkpoints:338`、`codeindex:410`、`codera:642`、`products:674/796`、`codegraph:723`、`lsp:923`），是全项目耦合最重的文件；`agent.py` 一次性导入 8 个模块并承载审批跨线程与缓存不变量。这两块交给新手，返工成本最高。

**依据四：模块的"可外派度"差异极大，按客观验收门槛分配。**

| 模块 | 客观验收门槛 | 适合新手？ |
|---|---|---|
| `pipeline.py` | `tests/test_pipeline.py` 10 个测试函数 / 31 条断言 | ✅ 最好 |
| `products/quant` | benchmark 一条命令 + exit code | ✅（本期不做） |
| `codeindex` / `codera` / `codegraph` | 均有等价测试 | ✅ |
| `sessions` / `cache` / `checkpoints` / `context` | 纯逻辑、协议清晰 | ✅ |
| `vecstore.py` | **无独立测试** | ⚠️ 需先补单测 |
| `mcp.py`（536 行） | **无测试** | ⚠️ 需 S 先写协议契约 |
| `novel_chain` 的 `_arc_compress` / `rag_recall` / `.events.jsonl` | **无测试** | ⚠️ 需 Go 侧补等价测试 |
| `llm` / `agent` / `tools` / `config` | 有测试但逻辑最难 | ❌ 归 S |

---

## 3. 分工总表（核心）

### 3.1 一人一句话

| 人 | 角色 | 一句话职责 |
|---|---|---|
| **S** | 内核关键路径 + 架构负责人 | 冻结接口、写 `config`/`llm`/`agent`/`tools` 四个最难模块、搭前端骨架前三组件、code review 兜底 |
| **A** | 纯逻辑线 | `pipeline`/`context`/`cache`/`checkpoints`/`sessions` → 之后接手 `novel_chain` 8 阶段 → 最后转前端支援面板 |
| **B** | 检索与协议线 | `codeindex`/`codera`/`vecstore`/`embed`/`codegraph`/`lsp` → 之后 `mcp`/`attach`/CI → 外围模块 |
| **C** | Vue 前端线 | i18n 导出与工程搭建 → 聊天渲染与输入区（对 mock）→ 八个管理面板 + Monaco + 文件树 |

### 3.2 按模块的负责人与验收（可直接当任务单用）

#### S —— 内核关键路径（约 3067 行 Python，最难的部分）

| Python 源 | 行数 | Go 包 | 周次 | 验收方式 |
|---|---|---|---|---|
| `config.py` | 1058 | `kernel/config` | W1 冻结 | 配置目录跨平台解析（`%APPDATA%` / `~/.config`）+ 旧目录迁移 + `models.json` 读写往返 |
| 全部接口与事件契约 | — | `kernel/*` | W1 冻结 | 事件类型表 + `Sink` 接口文档，之后变更需 S 签字 |
| `llm.py` | 534 | `kernel/llm` | W2–3 | 移植 `tests/test_llm.py`；双协议 `openai_compatible` / `anthropic`；SSE 按行解析、`tool_calls` 按 index 聚合、`_ThinkFilter` 跨 chunk 缓冲 |
| `agent.py` | 427 | `kernel/agent` | W3–4 | 移植 `tests/test_agent.py`：权限三态、缓存不变量（请求时消息列表做键 / 中断不入缓存 / MCP 不缓存）、空轮终止、轮次耗尽强制总结、云回退仅 `gpulocal-*` |
| 最小 CLI | — | `cli/` | W2 | 复用 kernel，只实现 `Sink`；能流式对话并调用一个工具 |
| `tools.py` | 1048 | `kernel/tools` | W5–7 | 沙箱越权用例（工作区逃逸、`run_shell` 高危命令黑名单）+ 13 个内置工具 schema |
| 前端模板组件 | — | `desktop/frontend` | W5–6 | App 外壳 + ChatStream + Composer 三个组件写成模板供 C 照抄 |

#### A —— 纯逻辑线

| Python 源 | 行数 | Go 包 | 周次 | 验收方式 |
|---|---|---|---|---|
| `pipeline.py` | 283 | `kernel/pipeline` | W2–3 | 移植 `tests/test_pipeline.py`（10 个测试函数 / 31 条断言）：`StageStopError` 停链 / `StageDebtError` 记债续跑 / `StagePaused` 重跑阶段 / `until` 部分执行 / 原子检查点 / 恢复时 running→paused / 落盘失败不静默 |
| `context.py` | 233 | `kernel/context` | W3 | 预算公式 `min(budget, context_window − output_max − 1024)`；三段压缩保留 system + 首条 user + 末 2 轮 |
| `cache.py` | 307 | `kernel/cache` | W3–4 | SQLite 与内存双后端 + TTL + 命中统计 |
| `checkpoints.py` | 132 | `kernel/checkpoints` | W4 | 每文件 10 份快照 + 覆盖前快照 + 回滚是消费式（每次退一步）+ 新文件不快照 |
| `sessions.py` | 278 | `kernel/session` | W4 | SQLite WAL + 工作区绑定 + 搜索 + UI-only `notes` 不外发模型 |
| `novel_chain.py` | 1548 | `kernel/novel` | W5–8 | 8 阶段整链（对齐 `tests/test_novel_chain.py` 637 行）：setup→outline→world→contract→characters→volume→chapter_plan→chapters；外加台账（上限 60）、伏笔（上限 8）、每 4 章弧线压缩、章号重排 `_reindex_refs`、检查点格式与 `.events.jsonl` |

> `novel_chain` 的 prompt 装配接缝、台账写入、伏笔生命周期由 **S 与 A 共同定**（A 实现，S 审），
> 这是 A 整条线上唯一需要 S 深度介入的地方。

#### B —— 检索与协议线

| Python 源 | 行数 | Go 包 | 周次 | 验收方式 |
|---|---|---|---|---|
| `codeindex.py` | 292 | `kernel/kb/codeindex` | W2 | 移植 `tests/test_codeindex.py`：camelCase/snake_case 拆分 + 中文 bigram + 停用词 + 50 行重叠分块 + 增量跳过 |
| `embed.py` | 55 | `kernel/kb/embed` | W2 | OpenAI 兼容 `/embeddings`，失败返回空且不打断业务 |
| `codera.py` | 431 | `kernel/kb/codera` | W3 | 多根 KB + TF-IDF/embedding 混合（权重 0.6）+ 结果带 `source=tfidf\|hybrid` 探针 + 维度不一致退回 |
| `vecstore.py` | 169 | `kernel/kb/vecstore` | W3 | Qdrant REST + 内存降级 + 256 维 hash 词袋。**先为 Python 版补单测作为验收基线** |
| `codegraph.py` | 735 | `kernel/codegraph` | W4 | AST 建图 + 「精确→前缀→包含→FTS」逐级升级检索 + 兼容真实 CodeGraph 库 |
| `lsp.py` | 360 | `kernel/lsp` | W4–5 | 子进程 JSON-RPC 客户端 + 诊断拉取（供 Monaco 使用） |
| `mcp.py` | 536 | `kernel/mcp` | W5 | stdio JSON-RPC + HTTP/SSE。**无测试，S 先写协议契约**；验收 = 与 `examples/` 示例 MCP server 真连接成功 |
| `attach.py` | 268 | `kernel/attach` | W6 | docx = zip + XML（纯 Go 可做）；**pdf 降级**为外部 `pdftotext` 或提示复制粘贴 |
| `i18n.py` | 1247 | `kernel/i18n` | W1 接线 | 词条由 C 导出为 JSON，内核与前端**同源**一份 |
| 打包与 CI | — | `packaging/` | W7 | 三平台 `go test` + `wails build` 流水线 |

#### C —— Vue 前端线

| 周次 | 内容 | 验收方式 |
|---|---|---|
| W1 | ① `i18n.py` 524 个词条导出 JSON（机械性，可脚本化）② `theme.py` 15 个色令牌 → CSS 变量 ③ Vue3+Vite+TS+Pinia+组件库工程搭建 ④ 对着 mock 画静态三栏骨架 | 静态骨架在浏览器能打开；设计与 Python 版并排看不出差异 |
| W2–3 | ChatStream：流式 markdown（`markdown-it` + `shiki`）、代码块、思考内联、工具调用卡、超长结果折叠、链接弹窗 | **全程对 mock 数据开发，不等后端** |
| W3–4 | Composer：8 种按键场景（Enter 发送 / Shift+Enter 换行 / Ctrl+Enter 排队 / 弹窗内 Enter 与 Tab 确认 / Esc 关 / ↑↓ 导航 / 输入 rescan）、`@` 文件补全、`/` 命令补全、IME 回车容错、占位符浮层、排队消息编辑删除、拖放附件 | 用 `ui_input.py::decide()` 的场景表逐条对照 |
| W4 | 会话侧栏：工作区分组、运行中标记、重命名、删除 | 与 `ui_panel_sessions.py` + `ui.py:1576-1620` 对齐 |
| W5–6 | 八个管理面板：models（867 行，最重，双树表联动）、dispatch、kb、mcp、cache、sessions、approval、help | 照抄 S 给的面板模板；只做「表单 + 列表」型 |
| W7–8 | 文件树（搜索/右键/拖拽源）+ Monaco 集成（替代手写高亮/补全/LSP） | 拖文件进聊天变附件；Monaco 显示 LSP 诊断 |
| W9–10 | i18n 全量、主题打磨、与 Python 版并排盲测 | 核心路径无功能缺失 |

> **为什么 C 的排期最危险，以及怎么救**：C 是三人里最弱的一环（前端 + 新框架同时上手），
> 而前端是唯一无法靠"移植测试"保证质量的部分。三道防线：
> ① S 在 W5–6 亲手写 App 外壳 + ChatStream + Composer 当模板，C 只做可照抄的面板；
> ② 事件契约 W1 冻结后 C 全程对 mock 开发，不被后端进度阻塞；
> ③ W9 起 A 转前端分担面板积压。

---

## 4. 架构与目录

```
reasonix/
├── go.work                    # use kernel, cli, desktop
├── kernel/                    # 纯 Go，零 UI 依赖，CGO_ENABLED=0
│   ├── config/                # ← S（枢纽，W1 先冻结）
│   ├── llm/                   # ← S  双协议 SSE
│   ├── agent/                 # ← S  循环 + 权限 + 缓存不变量
│   ├── tools/                 # ← S  工具注册表 + 沙箱 + MCP 路由
│   ├── pipeline/              # ← A  状态机
│   ├── context/               # ← A  预算 + 三段压缩
│   ├── cache/                 # ← A
│   ├── checkpoints/           # ← A
│   ├── session/               # ← A  SQLite
│   ├── novel/                 # ← A  8 阶段业务链
│   ├── kb/                    # ← B  codeindex / codera / vecstore / embed
│   ├── codegraph/             # ← B
│   ├── lsp/                   # ← B
│   ├── mcp/                   # ← B
│   ├── attach/                # ← B
│   └── i18n/                  # ← B 接线 / ← C 出词条
├── cli/                       # ← S（W2 最小版，用作内核独立验证）
└── desktop/                   # Wails v2 壳（允许 CGO）
    ├── app/                   # ← S  绑定层 + 事件桥
    └── frontend/              # ← C  主力 / ← S 模板组件
```

**铁律**：`kernel` 不 import Wails，不 import 任何 UI。desktop 只做"绑定的手"。
这条铁律靠 CLI 来强制执行——如果内核里混进了 UI 依赖，CLI 就编译不过。

---

## 5. 契约冻结（W1 的唯一重点）

四线并行的代价是接口漂移，新手团队的接口漂移会直接变成集成期爆炸。所以 W1 不写业务，只冻结三样东西。

### 5.1 事件契约（沿用 Python 的 dict 契约，逐个映射）

| 事件 | 载荷 | 前端用途 |
|---|---|---|
| `text` | `{text}` | 助手流式增量 |
| `reasoning` | `{text}` | 思考增量 |
| `tool_start` | `{name, args}` | 工具卡（开始） |
| `tool_result` | `{name, ok, output}` | 工具卡（结果） |
| `tool_denied` | `{name}` | 审批被拒标记 |
| `round` | `{n}` | 轮次计数 |
| `usage` | `{...}` | 统计栏 |
| `cache_hit` | `{}` | 缓存命中标记 |
| `context_compact` | `{...}` | 上下文压缩提示 |
| `model_switch` | `{from, to}` | 云回退提示 |
| `plan` | `{steps}` | 计划面板 |
| `media` | `{paths}` | 媒体内嵌 |

novel 流水线事件单独走一条通道（对应 Python 的 `_novel_event`），事件名与 `pipeline.py` 的 `emit` 类型一一对应：
`pipeline_started` / `stage_start` / `stage_done` / `stage_debt` / `pipeline_paused` / `pipeline_done` / `pipeline_failed` / `chapter_start` / `chapter_done`。

### 5.2 Go 接口

```go
// 内核只依赖这些接口，不依赖具体壳
type Sink interface {
    Delta(kind string, text string)   // "text" | "reasoning"
    ToolCall(id, name string, args []byte)
    ToolResult(id string, ok bool, output string)
    Done(usage Usage, err error)
}

type ChatFn func(ctx context.Context, messages []Message) (string, error)  // 量化/兜底路径复用
type Approver interface{ Ask(tool string, args []byte) (bool, error) }     // ask 模式；超时默认拒绝
```

### 5.3 前端与内核的 wire 格式

事件名、载荷字段、错误结构一次定死，之后**只允许加字段，不允许改字段**。
C 从 W1 起就能对着 mock 数据把界面全部写完，这是"前端不等后端"的唯一手段。

---

## 6. 里程碑与每周可运行交付物

| 阶段 | 周 | S | A | B | C | 阶段验收 |
|---|---|---|---|---|---|---|
| **P0 契约冻结与骨架** | W1 | go.work 三模块、`config` 包、接口与事件契约冻结 | 跟参考实现学 Go 约定；把 pipeline 的 14 条断言先写成 Go 测试 | 搭测试脚手架；移植 codeindex 分词断言 | i18n 导 JSON、主题令牌、工程搭建、静态骨架 | `go test ./...` 有测试在跑；Vue 静态骨架能打开 |
| **P1 内核并行填充** | W2–4 | `llm` → `agent`；W2 交付最小 CLI | `pipeline` → `context` → `cache` → `checkpoints` → `session` | `codeindex`/`embed` → `codera`/`vecstore` → `codegraph`/`lsp` | ChatStream → Composer → 会话侧栏（全对 mock） | **每条线各有一条端到端可运行路径**；CLI 能跑工具调用；前端能用 mock 完整演示对话 |
| **P2 合流** | W5–7 | `tools` + 沙箱 + MCP 契约 + 前端模板三组件 | `novel_chain` 8 阶段（与 S 定接缝） | `mcp`/`attach` + i18n 接线 + CI | 八个面板 + 文件树 + Monaco | 端到端跑通一本两章的书（对齐 8 阶段断言）；桌面端能建会话、切模型、跑工具 |
| **P3 打磨对齐** | W8–10 | 评审兜底、性能与背压（delta 30ms 聚合） | 收尾 novel 无测试项，W9 起转前端支援 | 外围模块（weblinks/media/imggen/publisher） | i18n 全量、盲测、三平台出包 | 与 Python 版并排盲测核心路径无缺失 |
| **P4 缓冲** | W11 | — | — | — | — | 吸收集成延期 |

**为什么 W4 是硬关卡**：新手团队最大的失败模式是"各写各的，最后集成爆炸"。
所以要求每条线在 W4 前必须端到端跑通一次（哪怕功能很薄），把集成问题暴露在中期而不是末期。

---

## 7. 护栏规则（针对新手团队，写进 CONTRIBUTING）

1. **垂直切片优先**：不许"全部写完再集成"。W4 是硬关卡。
2. **一个 PR 一个模块，必须带等价测试**，断言从对应 Python 测试移植。无测试不合并。
3. **错误约定继承 Python**：工具错误返回**中文错误值**，不 panic、不中断 agent 循环；只有 `LLMError`/`MCPError` 等内部错误才向上返回。
4. **禁止两人同改一个包**；接口变更必须经 S 确认。
5. **事件契约先冻结、前端对 mock 开发**，只许加字段。
6. **新人的"不知道"要早暴露**：S 每周两次跨线同步 + 固定 code review，宁可慢一周也不要暗坑。
7. **先写测试后写实现**对 A/B 是强制要求——他们的模块都有 Python 测试可照搬，这是新手最可靠的抓手。

---

## 8. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 新人 Go 不熟，写出不地道的并发/错误处理 | 中 | 参考实现 + 先写测试 + 只分配叶子模块（低扇出）；S 评审兜底 |
| **前端线是最弱环**（C 同时学前端和新框架） | **高** | S 亲自写前三组件当模板；C 只做可照抄的表单/列表面板；W9 起 A 支援 |
| `mcp.py` 无测试，等于没有规格 | 中 | S 先写协议契约；用 `examples/` 示例 MCP server 做真连接验收 |
| `novel_chain` 的 `_arc_compress` / `rag_recall` / `.events.jsonl` 无测试 | 中 | Go 侧新增等价测试；否则只能靠人工跑整本书（成本高但可行） |
| `vecstore.py` 无独立测试 | 低 | 迁 Go 前先为 Python 版补单测，作为验收基线 |
| `attach` 的 PDF 抽取，纯 Go 库质量参差 | 中 | docx 用 zip+XML 纯 Go 做；pdf 降级为外部 `pdftotext` 或提示复制粘贴 |
| **集成期爆炸** | **高** | CLI 提前到 W2；W4 硬关卡；事件契约 W1 冻结 |
| 量化子系统二期若接手，`parsers ↔ emitters` 四对隐式契约易漂移 | 中（本期不做） | 二期必须先做「金标映射 JSON」单一数据源，再把门槛从 ≥90% 收紧为确定性路径 =100% 硬失败 |
| 流式事件频率过高拖垮前端 | 低 | Go 侧按 ~30ms 聚合批量 emit，前端 rAF 合帧 |

**另记一条结构性改进**（Python 版的实际问题）：`products.feature(key, default=True)` 缺省为开，
导致"某产品启用哪些功能"由散落在 `ui.py` 的 **8 个调用点**（`1119`/`1133`/`1138`/`1163`/`1186`/`3656`/`3661`/`4122`）的 default 参数分别决定。
任何新开关只要漏写 default，就会在所有产品（含 novelwriter、devrag）静默打开。
**Go 侧改为集中显式白名单、缺省关闭**，novelwriter 启用的功能在一处列全。

---

## 9. 明确不做（不做隐性消失）

- 语音输入（Go 生态无 `faster-whisper` 等价物；原 Go 计划 D2 已判定砍掉）
- 截图覆盖层与图片标注面板（canvas 重做多显示器/DPI 坐标变换，成本最高、收益最低）
- quant 前端面板（量化子系统本身保留 Python）
- devtool / devtool_local / devrag / gpulocal 相关面板
- 内置编辑器的自研高亮/补全/LSP 胶水（改由 Monaco 承担）

以上功能在 Python 版继续可用，冷启动冻结版本不受影响。

---

## 10. 附录：模块 → Go 包 → 负责人 全表

| Python | 行数 | Go 包 | 负责人 | 难度 | 验收门槛 |
|---|---|---|---|---|---|
| `config.py` | 1058 | `kernel/config` | S | 高 | 有测试 |
| `llm.py` | 534 | `kernel/llm` | S | 高 | 有测试 |
| `agent.py` | 427 | `kernel/agent` | S | 高 | 有测试 |
| `tools.py` | 1048 | `kernel/tools` | S | 高 | 有测试 + 沙箱越权用例 |
| `pipeline.py` | 283 | `kernel/pipeline` | A | 中 | 10 个测试函数 / 31 条断言 |
| `context.py` | 233 | `kernel/context` | A | 中 | 有测试 |
| `cache.py` | 307 | `kernel/cache` | A | 中 | 有测试 |
| `checkpoints.py` | 132 | `kernel/checkpoints` | A | 低 | 有测试 |
| `sessions.py` | 278 | `kernel/session` | A | 中 | 有测试 |
| `novel_chain.py` | 1548 | `kernel/novel` | A（S 审接缝） | 高 | 部分有测试（弧线压缩/RAG 需补） |
| `codeindex.py` | 292 | `kernel/kb/codeindex` | B | 中 | 有测试 |
| `codera.py` | 431 | `kernel/kb/codera` | B | 中 | 有测试 |
| `vecstore.py` | 169 | `kernel/kb/vecstore` | B | 中 | **无测试，需先补** |
| `embed.py` | 55 | `kernel/kb/embed` | B | 低 | 有测试（间接） |
| `codegraph.py` | 735 | `kernel/codegraph` | B | 中 | 有测试 |
| `lsp.py` | 360 | `kernel/lsp` | B | 中 | 有测试 |
| `mcp.py` | 536 | `kernel/mcp` | B | 中高 | **无测试，靠示例 server 集成验收** |
| `attach.py` | 268 | `kernel/attach` | B | 中 | 有测试（pdf 降级） |
| `i18n.py` | 1247 | `kernel/i18n` | B 接线 / C 出词条 | 低 | 键数对齐（524 键） |
| `errlog.py` | 74 | `kernel/errlog` | B | 低 | 有测试 |
| `dircache.py` | 56 | `kernel/dircache` | B | 低 | 有测试 |
| `weblinks.py` | 381 | `kernel/weblinks` | B | 低 | 无测试 |
| `media.py` | 313 | `kernel/media` | B | 中 | 无测试 |
| `imggen.py` | 77 | `kernel/imggen` | B | 低 | 无测试 |
| `publisher.py` | 229 | `kernel/publisher` | B | 低 | 无测试 |
| `ui.py` | 6911 | `desktop/frontend` | C（S 模板） | 很高 | 与 Python 版并排盲测 |
| `ui_panel_*.py`（8 个可迁移） | 2028 | `desktop/frontend` | C | 中高 | 同上（models 最重，867 行） |
| `ui_input.py` | 494 | `desktop/frontend` | C | 高 | 逐条对照 `decide()` 场景表 |
| `theme.py` | 83 | CSS 变量 | C | 低 | 15 个色令牌一致 |
| `screenshot.py` | 880 | ❌ 不迁 | — | — | — |
| `ui_panel_annotate.py` | 366 | ❌ 不迁 | — | — | — |
| `voice.py` | 187 | ❌ 不迁 | — | — | — |
| `products/*` | 1905+ | ❌ 不迁（保留 Python） | — | — | — |
| `gpulocal/` | 空目录 | ❌ 不迁（清理残留 57 处引用） | — | — | — |
