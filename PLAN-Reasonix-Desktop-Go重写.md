# Reasonix Desktop · Go 内核重写计划

> 版本：v1.0 ｜ 日期：2026-08-27
> 目标一句话：**把现有 Python/Tkinter 内核（agent/llm/tools/sessions/…）重写为 Go 内核**，
> 桌面端用 **Wails + React/TypeScript** 重建 UI；内核与 CLI 版共享，行为一致。
>
> 现有 Python 仓库（本仓库）**冻结保留**作为行为参照，不删除；新实现落在新目录/新仓库。

---

## 〇、总体架构

```
┌─────────────────────────────────────────────────────────┐
│  Reasonix Desktop (Wails)                               │
│                                                         │
│  React/TS 前端  ←→  window.go.main.App 方法绑定          │
│  (Vite + pnpm)  ←→  window.runtime.EventsOn 事件推送     │
│         │                                               │
│  ┌──────▼───────────────────────────────────┐           │
│  │  desktop/  (独立 Go 模块, 允许 CGO)        │           │
│  │  绑定层: App struct + 事件桥 + 生命周期     │           │
│  └──────┬───────────────────────────────────┘           │
│  ┌──────▼───────────────────────────────────┐           │
│  │  kernel/  (Go 模块, 零 UI 依赖)            │           │
│  │  agent · llm · tools · session · config   │           │
│  │  context · cache · kb · attach · i18n     │           │
│  └──────┬───────────────────────────────────┘           │
│  ┌──────▼───────────────────────────────────┐           │
│  │  cli/  (Go 模块, CGO_ENABLED=0 纯静态)     │           │
│  └──────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
```

三个 Go 模块用 `go.work` 组成工作区：

| 模块 | 职责 | CGO | SQLite 驱动 |
|---|---|---|---|
| `kernel/` | 内核：代理逻辑、工具、会话、配置、RAG | 禁用（纯 Go） | `modernc.org/sqlite`（纯 Go） |
| `cli/` | 命令行版，复用 kernel | 禁用 → 单文件交叉编译 | 同 kernel |
| `desktop/` | Wails 桌面壳 + 绑定层 | 允许（WebView/GTK 依赖） | 可选 `mattn/go-sqlite3`（性能更好，非必需） |

> 铁律：**kernel 不 import Wails**。desktop 只做「绑定的手」，所有业务在 kernel。
> 保证 CLI 与 Desktop 行为一致、内核可独立单测。

---

## 一、目录结构（新仓库 `reasonix/`）

```
reasonix/
├── go.work                    # use kernel, cli, desktop
├── kernel/
│   ├── go.mod                 # module reasonix/kernel
│   ├── agent/                 # Agent.run() 循环、权限模式(readonly/ask/always)、工具轮次上限
│   ├── llm/                   # OpenAI 兼容 SSE 流式客户端；tool_calls 分片累积；usage 统计
│   ├── tools/                 # 内置工具注册表 + 执行器 + 沙箱护栏 + MCP 路由
│   ├── mcp/                   # MCP 客户端（stdio JSON-RPC + streamable HTTP）
│   ├── session/               # SQLite 会话库（保存/切换/搜索/目录绑定）
│   ├── config/                # models.json / state.json 读写；配置目录解析（跨平台）
│   ├── context/               # token 预算 + 三段式压缩
│   ├── cache/                 # LLM/工具缓存（SQLite/内存，TTL）
│   ├── kb/                    # 多根知识库 RAG（TF-IDF + 可选 embedding）
│   ├── attach/                # docx/pdf/zip 附件分析
│   ├── dispatch/              # call_model 子任务委派
│   ├── i18n/                  # en/zh 词典（JSON）
│   └── kerneltest/            # 内核级测试夹具（mock LLM transport）
├── cli/
│   ├── go.mod                 # module reasonix/cli
│   └── main.go                # 交互式 TUI（bubbletea 或裸终端）
└── desktop/
    ├── go.mod                 # module reasonix/desktop
    ├── main.go                # wails.Run 入口、窗口/生命周期
    ├── app/                   # 绑定层（见 §三）
    │   ├── app.go             # App struct：前端可调用的全部方法
    │   ├── events.go          # 事件名常量 + emit 封装
    │   └── fs.go              # 文件对话框/路径桥（Wails runtime）
    ├── wails.json
    └── frontend/
        ├── package.json       # pnpm
        ├── vite.config.ts
        ├── src/
        │   ├── App.tsx
        │   ├── api/           # window.go.main.App 封装 + 类型
        │   ├── events/        # EventsOn 订阅封装
        │   ├── components/    # 见 §五
        │   ├── stores/        # zustand（会话/设置/流式状态）
        │   └── i18n/          # 与 kernel/i18n 同源 JSON
        └── index.html
```

---

## 二、Python → Go 迁移对照

| Python（现仓库） | Go（kernel/） | 要点 / 风险 |
|---|---|---|
| `agent.py` | `agent/` | function-calling 循环、≤12 轮上限、审批流。审批在桌面端变为**前端事件+回执**（`events.go`），kernel 提供阻塞回调接口 |
| `llm.py` | `llm/` | SSE 流式解析（`bufio.Scanner` 按行、`data:` 前缀）、tool_calls 增量聚合、usage。**无官方 SDK，手写**（与现在 stdlib urllib 同路数） |
| `tools.py` | `tools/` | 工具 schema（JSON Schema 常量）、执行器、`is_write_tool`、沙箱（`write_file` 限工作区、`run_shell` 高危拦截）、超时（`context.WithTimeout`） |
| `config.py` | `config/` | 配置目录 `%APPDATA%`/`~/.config`、models.json 结构体、旧目录迁移 |
| `sessions.py` | `session/` | SQLite WAL；驱动差异用 `database/sql` 抽象，驱动由各模块注入 |
| `context.py` | `context/` | 预算估算（近似 token 化）+ 三段压缩，纯逻辑好迁 |
| `cache.py` | `cache/` | 接口 + sqlite/memory 两实现 |
| `codera.py` `codeindex.py` | `kb/` | TF-IDF 分词（camelCase/snake_case 拆分、中文 bigram）→ 纯 Go 重写 |
| `attach.py` | `attach/` | docx/pdf 文本抽取：docx=zip+xml 可纯 Go；**pdf 用纯 Go 库（风险点，见 §七）** |
| `weblinks.py` | `llm/` 或独立 `webfetch/` | 图片下载 / 网页正文抽取 |
| `mcp.py` | `mcp/` | 先评估 `mark3labs/mcp-go`，不合适再手写（现在就是手写的，量不大） |
| `dispatch`(call_model) | `dispatch/` | 子任务委派 + 结果截断回填 |
| `i18n.py` | `i18n/` | 词典 JSON 与前端共享 |
| `voice.py` | ❌ v1 不迁 | 见 §七 决策点 D2 |
| `ui*.py` `theme.py` | `desktop/frontend` | React 重写，视觉沿用 slate 浅色设计令牌 |
| `gpulocal/` | ❌ 不迁 | 本产品（novelwriter）未启用 |

---

## 三、Wails 绑定层设计（desktop/app/）

### 3.1 方法绑定（前端 `window.go.main.App.Xxx` 直调，请求-响应型）

```go
type App struct {
    ctx  context.Context
    k    *kernel.Kernel          // 内核句柄
    agent *kernel.AgentSession   // 当前会话的 agent
}

// —— 会话/配置 ——
func (a *App) ListModels() []ModelInfo
func (a *App) SelectModel(key string) error
func (a *App) ListSessions(dir string) []SessionMeta
func (a *App) OpenSession(id string) (Session, error)
func (a *App) DeleteSession(id string) error
func (a *App) GetSettings() Settings
func (a *App) SaveSettings(s Settings) error

// —— 工作区/文件 ——
func (a *App) PickDirectory() (string, error)        // 原生对话框（wails runtime）
func (a *App) ListWorkspace(dir string) []FileNode   // 文件树
func (a *App) ReadFile(path string) (string, error)  // 编辑器面板

// —— 知识库/附件 ——
func (a *App) KBStatus() KBStatus
func (a *App) KBAddRoot(path string) error
func (a *App) KBRebuild() error                      // 进度走事件
func (a *App) PickAttachments() []Attachment         // 原生多选
```

### 3.2 事件推送（`window.runtime.EventsOn`，流式/异步型）

| 事件名 | 载荷 | 说明 |
|---|---|---|
| `chat:delta` | `{session, type:"text"\|"reasoning", text}` | 流式增量 |
| `chat:tool_call` | `{id, name, args}` | 工具调用卡片 |
| `chat:tool_result` | `{id, ok, output, ms}` | 工具结果 |
| `chat:done` | `{session, usage, error?}` | 一轮结束 |
| `chat:approval` | `{id, tool, args}` → 前端回执 `ResolveApproval(id, allow)` | ask 模式审批 |
| `kb:progress` | `{done, total}` | 索引进度 |
| `status` | `{state:"idle"\|"busy", tokens...}` | 状态栏 |

**取消**：前端调 `App.StopGen()` → kernel `context.Cancel`；流循环检测 ctx 后发 `chat:done{cancelled:true}`。

**背压**：delta 在 Go 侧按 ~30ms 聚合批量 emit，避免 Wails 桥每 token 一跳。

---

## 四、内核关键设计

1. **Agent 循环**（对标 `agent.Agent.run`）：
   `for round := 0; round < MaxRounds; round++ { stream → 若 tool_calls → 审批 → 执行 → 追加消息 }`
   事件通过 `func Agent.SetSink(Sink)` 注入（Sink 接口：OnDelta/OnToolCall/OnDone），CLI 打到 stdout，Desktop emit 到前端——**一套循环两种壳**。
2. **SSE 客户端**：`net/http` + `bufio`；`[DONE]` 终止；`choices[0].delta.tool_calls[]` 按 index 聚合（arguments 分片拼接）；`usage` 在最后一 chunk（`stream_options.include_usage`）。
3. **SQLite 双驱动**：kernel 定义 `session.DB` 接口 + `session.NewModernc(path)`；desktop 可注入 mattn 实现换取 WAL 并发性能（v1 先统一 modernc，性能不够再分叉）。
4. **沙箱护栏**：原样移植（工作区路径校验 + 高危命令黑名单 + 环境变量开关 `REASONIX_SANDBOX=off`）。
5. **会话兼容**：沿用现 `sessions/` 存储格式（OpenAI 消息数组），提供一次性迁移工具，**老会话直接可读**。

---

## 五、前端设计（React + TS + Vite + pnpm）

| 组件 | 对应现 UI | 说明 |
|---|---|---|
| `ChatStream` | 聊天区 | 流式 markdown（`react-markdown` + 代码高亮 `shiki`）、思考折叠块、工具卡 |
| `Composer` | 输入区 | 多行输入、Enter 发送/Shift+Enter 换行、附件条、排队消息 |
| `ModelMenu` | 模型下拉 | 图标（沿用 assets/icons PNG）、能力标记、✓ 当前项 |
| `ThinkMenu` | 思考等级 | ⚪🚫🐢🧠⚡🔥🚀 七档 |
| `SessionDrawer` | 会话侧栏 | 目录分组、全局搜索 |
| `WorkspaceTree` | 文件树/编辑器 | 拖拽附件、只读预览 + 外部编辑器打开 |
| `KBPanel` | 知识库面板 | 根目录管理、重建进度、测试查询 |
| `StatusBar` | 统计栏 | token/缓存命中/请求计数 |
| `ApprovalDialog` | 审批弹窗 | ask 模式 工具确认 |

状态管理用 zustand（一个 `chatStore` + 一个 `settingsStore`）；i18n 用 `i18next`，词典与 kernel 共用 JSON 源。

---

## 六、里程碑（每步可运行、可验收）

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| **M0 骨架**（3 天） | go.work 三模块 + Wails 跑通空窗口 + React 壳 + CI（go test / pnpm build / wails build 三平台） | 三平台出包可启动 |
| **M1 内核最小闭环**（1 周） | llm/ + agent/ + tools/(read_file,list_dir,write_file,run_shell) + config/；CLI 可对话；mock transport 单测 | CLI 流式对话 + 工具调用闭环；kernel 单测覆盖循环/聚合/沙箱 |
| **M2 桌面对话**（1 周） | 绑定层 + chat:delta 流 + ChatStream/Composer/审批弹窗 + 取消 | Desktop 与 CLI 行为一致；流式不卡 UI |
| **M3 会话与模型**（1 周） | session/ + ModelMenu/SessionDrawer/ThinkMenu + 会话迁移工具 | 老会话可导入；模型切换/等级切换生效 |
| **M4 完整功能**（1–2 周） | cache/ + context 压缩 + kb/ + attach/ + dispatch/ + KBPanel/StatusBar | 对齐现 Python 版功能清单（除 voice） |
| **M5 打磨发布**（1 周） | 图标/主题令牌/i18n 全量、安装包（NSIS/dmg/AppImage）、签名占位 | 与 Python 版并排盲测无功能缺失 |

总计约 **5–7 周**（单人全职估算）。

---

## 七、风险与决策点

| # | 决策 | 建议 |
|---|---|---|
| D1 | **Wails v2 还是 v3** | v2 稳定文档全；v3（alpha）绑定更现代。**选 v2**，API 隔离在 desktop/app/ 内，日后换 v3 只动壳 |
| D2 | **语音输入**：Go 生态无 faster-whisper 等价物 | v1 砍掉；v2 方案：whisper.cpp CGO 绑定（desktop 模块内）或外接 whisper-server。**不阻塞主线** |
| D3 | **PDF 文本抽取**：纯 Go 库质量参差 | 优先 `pdfcpu`/`ledongthuc/pdf`；不行则降级为「调外部 pdftotext」或提示复制粘贴 |
| D4 | **SQLite 驱动** | v1 全线 modernc（纯 Go、免 CGO 纠缠）；desktop 实测慢再换 mattn |
| D5 | **流式背压** | Go 侧聚合 30ms 批发；前端 rAF 合帧渲染 |
| D6 | **审批 UX** | ask 模式若前端未响应（最小化），kernel 侧 30s 超时默认拒绝，防挂死 |
| D7 | **老配置兼容** | models.json/sessions 格式不变 + 迁移工具；配置目录沿用 `%APPDATA%\local-ai-studio`？→ **否**，新目录 `%APPDATA%\reasonix`，提供导入命令 |

---

## 八、与现有仓库的关系

1. 本 Python 仓库打 `v0.x-python` 标签冻结；README 加一行「桌面新版开发中 → reasonix/」。
2. `assets/icons/`（Noto Emoji PNG，Apache-2.0）直接复制进新仓库 frontend 静态资源 —— 图标体系延续。
3. 行为对照测试：用 Python 版的历史会话 JSON 作为 Go 内核解析的黄金样例（golden files）。
4. Python 版独有、新版权衡后砍掉的功能（voice、gpulocal 面板）在本文档 §二 有记录，不做隐性消失。
