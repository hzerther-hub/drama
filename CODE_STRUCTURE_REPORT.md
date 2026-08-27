# 代码结构分析报告

**生成时间**: 2026-08-27  
**项目路径**: D:\drama  
**语言**: Python 3.12+  
**规模**: 81 文件, 22,632 行, 1,303 函数, 90 类

---

## 1. 项目概览

本地 AI 编程助手，采用 **Tkinter 桌面 GUI + OpenAI 兼容 LLM 后端** 架构。支持流式函数调用、MCP 集成和双重 RAG 系统。一个内核，五种产品变体。

---

## 2. 核心架构

```
┌─────────────┐
│   main.py   │ 入口点 (22行)
└──────┬──────┘
       ▼
┌─────────────┐
│   ui.py     │ Tkinter 主界面 (~5,100行)
│  launch()   │ 驱动 App 类
└──────┬──────┘
       ▼
┌─────────────────┐
│   agent.py      │ Agent 循环
│   Agent.run()   │ 同步函数调用循环
└──────┬──────────┘
       │
       ├──► llm.py     # SSE 流式 LLM 客户端
       ├──► tools.py   # 8 个内置工具 + 执行器
       ├──► mcp.py     # MCP 客户端 (stdio/HTTP)
       └──► context.py # 令牌预算 + 压缩
```

**线程模型**: Tkinter 主循环单线程。Worker 线程必须通过 `root.after(0, fn)` 更新 UI，禁止直接操作组件。

---

## 3. 关键模块

### 3.1 核心运行时

| 模块 | 行数 | 函数/类 | 职责 |
|------|------|---------|------|
| `ui.py` | 5,107 | 279F / 1C | Tkinter 主界面，面板组织 |
| `agent.py` | 377 | 11F / 1C | Agent 循环、权限模式、事件发射 |
| `llm.py` | 144 | 3F / 1C | OpenAI 兼容 SSE 流式客户端 |
| `tools.py` | 882 | 34F | 内置 8 工具执行器，写操作守卫 |
| `mcp.py` | 536 | 39F / 5C | MCP 管理器，stdio + HTTP 传输 |
| `config.py` | 844 | 56F | ModelConfig 数据类，配置加载 |
| `context.py` | 227 | 9F | 令牌预算估算，两阶段压缩 |
| `sessions.py` | 278 | 12F | SQLite WAL 会话数据库 |
| `cache.py` | 307 | 22F | LLM/工具缓存 (SQLite WAL) |
| `i18n.py` | 788 | 9F | 中英双语 UI 国际化 |

### 3.2 RAG 系统

| 模块 | 行数 | 职责 |
|------|------|------|
| `codeindex.py` | 292 | 工作区 TF-IDF 索引 (`index_search` 工具) |
| `codera.py` | 431 | 企业多根知识库 RAG (`kb_search` 工具) |
| `embed.py` | 54 | 可选嵌入支持 |

### 3.3 UI 面板

| 面板文件 | 行数 | 职责 |
|----------|------|------|
| `ui_panel_dispatch.py` | 298 | 模型分发面板 |
| `ui_panel_models.py` | 352 | 模型管理面板 |
| `ui_panel_mcp.py` | 190 | MCP 配置面板 |
| `ui_panel_kb.py` | 231 | 知识库面板 |
| `ui_panel_quant.py` | 390 | 量化策略面板 |
| `ui_panel_sessions.py` | 136 | 会话管理面板 |
| `ui_panel_annotate.py` | 366 | 截图标注面板 |
| `ui_panel_approval.py` | 106 | 审批面板 |
| `ui_panel_cache.py` | 96 | 缓存面板 |
| `ui_panel_help.py` | 79 | 帮助面板 |

### 3.4 辅助功能

| 模块 | 行数 | 职责 |
|------|------|------|
| `lsp.py` | 360 | stdlib JSON-RPC LSP 客户端 (pyright/tsserver 等) |
| `screenshot.py` | 880 | 多显示器截图 + 标注 |
| `voice.py` | 187 | faster-whisper 转录 + PortAudio VAD |
| `attach.py` | 268 | 文档分析 (docx/pdf/zip) |
| `media.py` | 313 | 图像/音频/视频加载播放 |
| `localmodels.py` | 266 | GPU 本地模型桥接 (systemd/进程管理) |
| `weblinks.py` | 381 | 网页链接处理 |
| `theme.py` | 83 | UI 主题 |

### 3.5 量化产品 (quant)

| 模块 | 行数 | 职责 |
|------|------|------|
| `ir.py` | 135 | 策略翻译中间表示 (4类) |
| `parsers.py` | 244 | JoinQuant/PTrade/gm/QMT 解析器 (3类) |
| `emitters.py` | 401 | 代码生成发射器 (8类) |
| `translate.py` | 135 | 跨平台翻译逻辑 |
| `llm_parse.py` | 122 | LLM 解析策略文本 |
| `sim.py` | 178 | 回测模拟引擎 |
| `qmt.py` | 86 | QMT 平台适配 |
| `validate.py` | 67 | 策略验证 |
| `benchmark.py` | 136 | 性能基准测试 |

### 3.6 产品变体

```
products/
├── devtool_local/   # 默认: 带本地模型的开发者工具
├── devtool/         # 通用开发者工具
├── novelwriter/     # 小说写作助手
├── quant/           # 量化策略翻译 (JoinQuant↔PTrade↔gm↔QMT)
├── devrag/          # 企业多根知识库
└── __init__.py      # 产品注册与 feature() API
```

---

## 4. 设计模式与约定

### 4.1 依赖注入
- 全局模块单例，非构造函数注入
- 通过 `reset()` / `push_workspace()` 上下文管理器重置单例（测试隔离）

### 4.2 错误处理
- 工具错误以**中文字符串**返回（不抛出），LLM 将其视为工具输出
- 传输/解析失败抛出 `LLMError` / `MCPError`

### 4.3 权限控制
- 三种模式: `readonly` / `ask` / `always`
- 双重权限: `tools.is_write_tool` + `MCPManager.is_write_tool`
- Shell 沙箱 (`config.SANDBOX`): 默认启用，限制 `write_file` 到工作区

### 4.4 模型分发
- 配置键在 `config.py`: `model_dispatch`, `dispatch_smart`, `dispatch_model` (本地大脑)
- 视觉路由优先本地模型，否则回退到 `dispatch_vision`

### 4.5 缓存键
- 使用**请求时**消息列表，不要在键入前追加助手回复

---

## 5. 测试体系

- **框架**: pytest (~284 单元测试, 24 文件)
- **隔离**: `conftest.py` fixtures 重定向 HOME/APPDATA/USERPROFILE 到 tmp_path
- **Mock**: `monkeypatch.setattr(module, 'func', fake)` 广泛使用
- **覆盖**: 参数化测试 (`test_products.py` 覆盖所有 5 个产品)

---

## 6. 构建与部署

```bash
# 语法检查
python -m py_compile *.py

# 运行测试
python -m pytest tests/ -q

# 安装依赖
pip install -r requirements.txt        # 运行时 (voice)
pip install -r requirements-dev.txt    # 开发

# 构建可执行文件
python packaging/build.py [product] [--clean]
```

**CI**: GitHub Actions 矩阵: ubuntu/windows/macos × Python 3.12  
**打包**: PyInstaller (`LocalAIStudio.spec`)

---

## 7. 文件树 (精简)

```
drama/
├── main.py                  # 入口 (Python 3.12 守卫)
├── ui.py                    # Tkinter 主界面 (~5100行)
├── agent.py                 # Agent 循环
├── llm.py                   # SSE 流式客户端
├── tools.py                 # 8 工具执行器
├── mcp.py                   # MCP 客户端
├── config.py                # 配置单例
├── context.py               # 令牌预算
├── sessions.py              # SQLite 会话
├── cache.py                 # 缓存
├── i18n.py                  # 国际化
├── codeindex.py             # 工作区索引
├── codera.py                # 企业知识库 RAG
├── lsp.py                   # LSP 客户端
├── screenshot.py            # 截图标注
├── voice.py                 # 语音转录
├── attach.py                # 文档分析
├── media.py                 # 媒体处理
├── localmodels.py           # 本地模型管理
├── weblinks.py              # 网页链接
├── theme.py                 # UI 主题
├── embed.py                 # 嵌入支持
├── products/                # 产品变体
│   ├── __init__.py
│   ├── devtool_local/
│   ├── devtool/
│   ├── novelwriter/
│   ├── quant/               # 量化策略翻译
│   └── devrag/
├── gpulocal/                # 本地模型面板
├── packaging/               # PyInstaller 构建
├── tests/                   # pytest 套件
├── assets/                  # 图标
├── fonts/                   # 字体
├── docs/                    # 文档
└── examples/                # MCP 示例服务器
```

---

## 8. 总结

这是一个**本地优先的 AI 编程助手**，架构清晰：

1. **单内核多产品**: 通过 `LOCAL_AI_PRODUCT` 环境变量或 `products/<name>/run.py` 切换 5 种产品变体
2. **标准库优先**: 核心模块仅用 stdlib，可选依赖优雅降级
3. **双重 RAG**: `codeindex.py` (工作区) + `codera.py` (企业知识库)
4. **量化策略翻译**: `quant/` 子产品支持 JoinQuant↔PTrade↔gm↔QMT 跨平台翻译
5. **完整测试**: ~284 单元测试，CI 矩阵覆盖多平台
6. **PyInstaller 打包**: 支持构建独立可执行文件

**技术栈**: Python 3.12 + Tkinter + stdlib + OpenAI 兼容 API + MCP + SQLite + PyInstaller