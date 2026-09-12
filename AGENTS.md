# AGENTS.md — Local AI Writer（仓库根目录速览）

> 面向 AI 助手的项目速览。命令均在仓库根目录执行（Windows 用 `python`，Linux/macOS 用 `python3`）。
> 只记录已核实的事实；易过时的文档见文末「文档时效」。

## 1. 项目概述

- **Local AI Writer**（内核名 Local AI Studio）：Tkinter 桌面「本地优先」AI 写作工作室，主攻**短剧剧本 + 网文创作**；后端可接任意 OpenAI 兼容或 Anthropic 端点（双协议）；Python **3.12+**（Windows 推荐 3.14，Tk 9 才会有彩色 emoji 图标）；核心模块仅用标准库，可选依赖优雅降级。
- **单内核多产品**：仓库根目录的扁平模块 = 共享内核；`products/<name>/profile.json` 定义品牌与功能开关（`products.feature(key)`，缺省为 true），`DEFAULT_PRODUCT = 'novelwriter'`。
  - 产品：`novelwriter`（默认，本仓库主产品）、`quant`（量化策略互转）、`devtool` / `devtool_local`（编码助手）、`devrag`（企业多根 RAG）。
- **数据目录**：Windows `%APPDATA%\local-ai-studio`，其他平台 `~/.config/local-ai-studio`（单一来源 `config.CONFIG_DIR`，在 import 时解析一次）；仓库根的 `models.json` 只是首次运行的种子文件。

## 2. 常用命令

| 目的 | 命令 |
|---|---|
| 运行默认产品 | `python main.py` |
| 运行其他产品 | `LOCAL_AI_PRODUCT=quant python main.py`（Windows：`set LOCAL_AI_PRODUCT=quant`）或 `python products/quant/run.py` |
| 单元测试 | `python -m pytest tests/ -q`（约 560 passed；全 mock，隔离 HOME/APPDATA） |
| 语法门（同 CI） | `python -m py_compile *.py`（CI 还编译 `examples/`、`products/`、`packaging/`） |
| 打包 | `python packaging/build.py [product] [--clean]` → `dist/<exe_name>-<platform>/` |
| 量化一致性矩阵 | `python -m products.quant.benchmark`（6 策略 × 12 方向，确定性路径须 100%，验收线 ≥90%） |
| 量化互转 demo | `python -m products.quant.demo` |
| 安装依赖 | `pip install -r requirements.txt`（语音等可选）/ `requirements-dev.txt`（仅 pytest） |

> 若沙箱禁止执行命令（如 Windows 下 shell 返回 0xC0000142），改用 `read_file` / `grep_search` / `lsp_diagnostics` 核实代码。

## 3. 架构概览

```
main.py（Python 3.12 版本守卫，必须在 import ui 之前）
  └ ui.launch() → App（Tkinter 单线程 mainloop；每条消息起一个 daemon worker 线程）
       └ agent.Agent.run()  同步 function-calling 循环（≤ MAX_TOOL_ROUNDS=24，撞顶后强制一次无工具收尾）
            ├ llm.py      SSE 流式客户端，双协议（ModelConfig.api_type = openai_compatible | anthropic）
            ├ tools.py    内置工具 schema + _EXECUTORS + 权限分层 + 沙箱
            ├ context.py  token 预算 + 渐进压缩（中段折成摘要，保留 system + 首问 + 末 2 轮）
            ├ cache.py    LLM / 工具结果缓存（SQLite WAL，或内存后端）
            ├ codeindex.py / codera.py   工作区 TF-IDF（index_search）/ 多根 KB RAG（kb_search）
            ├ vecstore.py Qdrant REST + 内存降级（小说 RAG）；mcp.py MCP stdio/HTTP 客户端
            └ pipeline.py → novel_chain.py 整本小说生产线；publisher.py 导出与发布
```

- **事件契约**：agent 抛出 `{"type": ...}` 字典 —— `text / reasoning / tool_start / tool_result / tool_denied / round / usage / cache_hit / context_compact / model_switch / plan / media`，由 `ui.App._on_event` 单点消费；小说流水线经 `_novel_event` 转成同类事件。
- **权限**：`readonly` / `ask`（默认，写工具需审批）/ `always`；写工具 = `write_file`、`run_shell`（及非只读的 MCP 服务器）。审批跨线程用共享 dict + `threading.Event`，超时自动拒绝。
- **沙箱**：默认开启，`LAS_SANDBOX=off` 关闭；`write_file` 只能写工作区内（`tools.path_in_workspace`），`run_shell` 拦截明显破坏性命令（`tools._BLOCKED_SHELL_PATTERNS`）。这是护栏，不是 OS 级隔离。
- **内置工具（`tools.py`）**：`read_file`、`write_file`、`list_dir`、`glob_search`、`grep_search`、`index_search`、`lsp_diagnostics`、`run_shell`、`web_search`、`task_plan`、`call_model`、`kb_search`。
- **小说线**：`pipeline.py` 通用阶段状态机（`StageStopError` 断链 / `StageDebtError` 记债续跑 / `StagePaused` 恢复时跳过已完成阶段，原子 JSON 检查点 + `.events.jsonl` 事件日志）→ `novel_chain.py` 8 阶段（setup→outline→world→contract→characters→volume→chapter_plan→chapters，`STAGES` 定义于 `novel_chain.py:460`），逐章 草稿→五维审校→修复一次→事实/伏笔台账→RAG 索引。交互全部是 `ui.py` 内联的 `/novel` 子命令（**不存在 `ui_panel_novel.py`**，也没有弹出式工作台）。书稿落在 `工作区/novels/<书名>/{大纲,设定集,正文,审查报告}`。
- **量化线**：铁律 **禁 N×N 平台直译**。`parsers.py`（AST 确定性解析，超范围抛 `ParseError`）→ `ir.py`（`StrategyIR`）→ `emitters.py`（确定性模板发射，不用 LLM）→ `validate.py`（白名单沙箱）→ `sim.py`（桩运行时信号一致率）→ `benchmark.py`；`llm_parse.py` 仅在 ParseError 时兜底。映射真相在 `products/quant/api_maps/*.md`（改映射先改对照表），IR 内部统一聚宽规范形，只在 parse/emit 边界转换（`symbols.py`）；QMT 模板故意保留 `TODO: 填资金账号`（合规红线），xtquant 只引用不内嵌。

## 4. 关键模块（职责速查）

| 模块 | 职责 |
|---|---|
| `main.py` | 入口：Python 3.12 守卫（先于 `import ui`）→ `ui.launch()` |
| `ui.py`（约 6.5k 行） | `App`：三栏布局、发送链路（`_send_with` 起 worker 线程）、`_on_event`、状态栏、斜杠命令（含内联 `/novel` 全流程）、`launch()` |
| `ui_input.py` | `InputController`：按键统一分发（Enter 发送 / Shift+Enter 换行 / Ctrl+Enter 排队）、`@` 文件与 `/` 命令弹窗；纯函数 `decide()` 可脱离 Tk 测试 |
| `ui_panel_*.py` | 对话框面板：models / mcp / kb / cache / sessions / dispatch / approval / help / annotate / quant；`show(app)` 风格入口，函数内惰性 `import ui` |
| `agent.py` / `llm.py` / `tools.py` / `config.py` | 主循环与权限 / SSE 双协议（`_post_stream` 是测试 monkeypatch 缝，`_ThinkFilter` 跨 chunk 剥离 `<think>`）/ 工具 schema + 执行器 + 沙箱 / `CONFIG_DIR`、`ModelConfig` 与各类常量 |
| `context.py` / `cache.py` / `sessions.py` | 预算与渐进压缩 / LLM 与工具结果缓存 / SQLite 会话（`messages` 含 UI-only `notes`，不会送给模型） |
| `pipeline.py` / `novel_chain.py` / `publisher.py` / `vecstore.py` | 阶段机 / 小说主链与提示词模板 / txt·md·html·epub 导出 + Wattpad·Webhook 发布 + 封面（纯 stdlib）/ Qdrant 或内存检索 |
| `attach.py` / `voice.py` / `weblinks.py` / `media.py` | docx·pdf·zip 附件分析 / faster-whisper 语音录入 / 消息内链接自动取材 / 图片音频视频渲染 |
| `checkpoints.py` / `dircache.py` / `errlog.py` / `lsp.py` / `embed.py` / `imggen.py` / `theme.py` | 写前快照与 `/undo` / `@` 目录快照 / 异常统一上报 / LSP 客户端 / embedding / 出图 / 主题令牌 |
| `products/quant/*` | 量化 IR 互转子系统：parsers、emitters、ir、sim、validate、benchmark、qmt、kb、api_maps、examples |

## 5. 代码约定与注意事项

- **语言**：中文 docstring/注释 + 英文标识符；每个文件 `from __future__ import annotations`。
- **核心仅用标准库**：可选依赖一律 `try: import X except ...: X = None` + 降级路径。已知例外：`ui_panel_annotate.py` 无保护地 import PIL。
- **工具错误以中文字符串返回**（`错误：…`）而不抛异常，让模型当普通工具输出看；只有 `LLMError` / `MCPError` / `ImgError` / `VecError` / `PublishError` 会抛。
- **线程**：worker 线程绝不直接改控件，一律 `root.after(0, fn)`（面板用 `win.after`）；长任务（MCP 重连、KB 建索引、量化 LLM 翻译）都跑 daemon 线程。
- **面板**：`import ui` 必须写在**函数内部**（顶层会循环导入、启动即炸）；`ui.FONT_UI` / `FONT_MONO` 在打开时读、勿在 import 期缓存；复用 `ui._make_modal`、`ui._flat_button`、`theme.*`。
- **输入框**：占位符是浮动 `tk.Label` 覆盖层，不写入输入缓冲区；`<<Modified>>` 标志粘滞，处理完必须 `edit_modified(False)`。改动输入/弹窗逻辑前先读 `docs/harness-notes.md`。
- **i18n**：所有用户可见文案走 `i18n.t(key, **kw)`，词表为稀疏 `key → {en, zh}`；语言持久化在 `CONFIG_DIR/models.json`。
- **存储**：一切路径派生自 `config.CONFIG_DIR`；SQLite 模块统一 WAL + `RLock` + 线程本地连接；流水线落盘原子（tmp + `os.replace`）。
- **模型配置**：provider id 需匹配 `^[a-z0-9_-]+$`，id 与显示名必须唯一；模型级字段 `vision` / `context_window` / `max_tokens` / `reasoning`。
- **静默降级是有意设计**（vecstore / codera / embed / weblinks / attach 都不打断主流程）；健康度看元数据，如 codera 结果 `source='tfidf'` 还是 `'hybrid'`。
- **构建标记**：窗口标题为 `<profile.title> - build <ui._BUILD_TAG>`（`ui.py:49`，当前 `0906-3`）；多实例/多版本混用时先看标题，改核心逻辑请同步 bump（发布清单见 `docs/optimization-design.md`）。
- **检查点**：`write_file` 覆盖前快照（每文件 10 份），`/undo` 每调用一次回退一份；新建文件不快照。
- **量化同步契约**（改一处必须同步改另一处）：`parsers._KIND_SIGNATURES ↔ emitters._INIT_ATTRS`、`parsers._TIME_IN ↔ emitters._TIME_OUT`、`ir.KNOWN_KINDS_HINT ↔ emitters._LOGICS`；改完必跑 benchmark。
- **测试**：`tests/test_<module>.py`，模块级函数或 `TestX` 分组，中文单行 docstring；`conftest.py` 在任何项目模块导入前把 `HOME` / `USERPROFILE` / `APPDATA` 重定向到临时目录并清除 `LOCAL_AI_PRODUCT`；产品测试用 `monkeypatch.setenv` + `products._reset_for_test()`；单例隔离用 `cache.reset()`、`vecstore.reset_memory()`。UI 测试只测抽出的纯函数，或把 App 方法绑到 StubApp 上测（`ui_input.decide` / `_novel_event` / `_load_session`），不开真窗口。
- **LLM mock 范式**：`monkeypatch.setattr(llm, '_post_stream', lambda model, messages, tools: iter(fake_sse_dicts))`；模型对象直接构造 `config.ModelConfig`。
- **缓存不变量**：缓存键用**请求时**的消息列表（不要在键入前追加助手回复）；被中止的运行绝不缓存；MCP 调用不缓存。
- **文档时效**：`CLAUDE.md`（引用了已删除的 `gpulocal/`、`localmodels.py`）、`CODE_STRUCTURE_REPORT.md`（2026-08-27 快照，行数已滞后）、`docs/optimization-design.md`（称仓库无 LICENSE，实际已有 Mulan PSL v2）均可能过时，**以代码为准**。
