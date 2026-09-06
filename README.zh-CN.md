# Local AI Writer · 短剧网文创作

[English](README.md) | **简体中文**

**Local AI Writer** 是一个桌面 AI 写作工作室，面向**短剧剧本和网文创作**——Tkinter 图形界面，接任意 OpenAI 兼容模型，流式对话，Agent 会真实读写你项目目录里的稿件文件。需要 Python 3.12+，支持 Linux / Windows / macOS。

一切都在本机运行：无账号、无内置云服务。只有当你自己配置了云端模型端点时，稿件内容才会发往你指定的服务器。界面中英双语——模型菜单 → 🌐 Language 切换，持久化在 `models.json`。

> 本仓库是写作产品的独立仓库，从 **Local AI Studio** 内核拆出（「一个内核，多个产品」）。默认产品是 `novelwriter`——`python main.py` 直接进入创作界面。兄弟产品（`devtool`、`devtool_local`、`quant`、`devrag`）仍在 `products/` 里作为内核附带产物运行；见 [产品：一个内核，多张面孔](#产品一个内核多张面孔)。

## 截图

![主界面](docs/screenshots/main.png)

## 当前状态

**v0.1 —— 内核平移完成。** 下述创作内核今天全部可用：Agent 对话真实写文件、多根知识库、附件分析、多会话、语音输入、模型管理。路线图中的写作专属面板（章节树、角色卡、节拍模板）尚未开发——见[路线图](#路线图)。

## 为什么把写作工作室建在 Agent 内核上

多数 AI 写作工具只给你一个聊天框和一个复制按钮。这里的 Agent 有手：

- **稿件就是项目目录。** 大纲、剧本、设定都是普通文件；模型用 `read_file` / `write_file` 就地修改第 12 集，而不是把整个剧本重新打印到聊天气泡里。
- **知识库守设定一致性。** 把世界观文档、人物小传、往期卷目建进持久化多根知识库；模型自己检索相关片段（`kb_search`），不用你每条提示都重新粘贴设定。
- **参考资料走附件。** docx/pdf/txt/md/csv 就地分析；压缩包解压并附文件清单；图片发给识图模型。
- **长篇连载不撑爆上下文。** 三段式上下文压缩（默认 100 万 token 预算）让连载前后连贯，统计栏实时显示消耗。

## 功能

- **流式对话**——正文与思考过程实时流式显示；工具调用显示为卡片
- **文件化写作**——Agent 在所选工作目录内读写文件；草稿不随聊天丢失
- **多根知识库（RAG）**——把 设定/素材/往期作品 目录建进 SQLite；TF-IDF 检索 + 可选 embedding 增强；`kb_search` 工具 + 可开关的自动注入
- **附件**——随消息多选文件；txt/md/csv 内联原文，docx/pdf 提取文本，zip/tar.gz 解压附清单；图片缩到 ≤1568px 发识图模型（`"vision": true`）
- **媒体内嵌**——聊天区直接显示图片/GIF 动画、音频播放条、视频缩略图；文字可选中，Ctrl+C / 右键复制
- **链接自动取材**——消息里的图片 URL 自动下载识图；网页 URL 自动抓正文给模型（后台线程）
- **联网搜索**——`web_search` 走 DuckDuckGo，零依赖无需 API Key
- **智能派发**——`call_model` 工具把重活（大改剧情、识图）委派给更强的已配置模型；简单/高性能/识图三类目标在面板里管理
- **语音输入**——单按钮：长按说话松手识别，轻点自动停顿检测（本地 Whisper / faster-whisper）
- **多会话**——发送即落盘（崩溃不丢），按目录分组，跨项目全局搜索
- **上下文压缩**——超预算自动截断工具结果，再把旧轮折叠为摘要（保留 system + 首问 + 最近几轮）
- **缓存层**——重复请求秒回；SQLite（重启保留）/ 内存双后端；token、缓存命中、秒回次数实时统计
- **模型管理**——provider 优先的两栏管理器：按 Provider 分组、可重命名（唯一性校验）、可改端点/密钥/API 类型（OpenAI 兼容 & Anthropic 双协议）；逐模型配置 识图 / 推理等级 / 上下文窗口 / 最大输出 token，改完即生效
- **快捷命令**——`/init` 生成 AGENTS.md、`/brainstorm` 头脑风暴、`/plan` 制定计划、`/work` 按计划执行、`/loop` 循环执行直到验证通过、`/compress` 压缩会话历史；输入 `/` 弹出联想
- **@ 文件引用**——输入 `@` 弹出工作区文件/目录选择器（类 Cursor），选中的文件引用发送时自动转附件
- **任务步骤面板**——多步任务先经 `task_plan` 生成功能级计划清单再执行，逐步勾选；工具审批内嵌聊天底部，不再弹窗
- **回车换行，Shift+回车发送**——长文写作友好；Ctrl+回车 排队消息
- **三档权限模式**——只读 / 每次询问（默认）/ 总是允许，带沙箱护栏
- **工作目录切换**——多部作品间切换，相对路径跟随所选目录
- **内置字体**——JetBrains Mono + Noto Sans CJK，三平台显示一致

## 一次创作会话

```bash
mkdir 我的短剧 && python main.py     # 然后把 我的短剧 选为工作目录
```

1. 附件传 `大纲.docx`，提问：*“把大纲拆成 20 集的分集梗概，保存到 分集梗概.md”*
2. *“读分集梗概，把第 1 集扩写成 1200 字短剧剧本，存到 剧本/EP01.md，开场 30 秒内放钩子”*
3. 第二天打开会话继续（已自动保存），或切到另一部作品的目录——会话按项目分组。
4. 把知识库指向你的 设定集/ 目录，写作时人物设定自动检索。

## 工具集

| 工具 | 说明 | 权限 |
|---|---|---|
| `read_file` | 读取文件（带行号） | 只读 |
| `write_file` | 写入/覆盖文件 | **可写** |
| `list_dir` | 列目录 | 只读 |
| `glob_search` | 通配符找文件 | 只读 |
| `grep_search` | 全文检索作品内容 | 只读 |
| `index_search` | 工作区索引语义检索 | 只读 |
| `web_search` | 联网搜索（DuckDuckGo，无需 Key） | 只读 |
| `run_shell` | 执行 shell 命令（如 ffmpeg、pandoc 导出） | **可写** |
| `call_model` | 把子任务委派给另一个已配置模型 | 只读 |
| `task_plan` | 制定/更新任务计划（界面显示为任务步骤清单） | 只读 |
| `kb_search` | 检索多根知识库 | 只读 |

（`lsp_diagnostics` 也是内核自带工具；只在代码类项目里有用。）

## 架构

```
main.py → ui.launch() → App (Tkinter 主循环；每条消息一个工作线程)
   └─ agent.Agent.run()     同步 function-calling 循环
        ├─ llm.py           SSE 流式客户端：OpenAI 兼容 & Anthropic 双协议（stdlib urllib）
        ├─ tools.py         内置工具 + 执行器 + 权限分级 + 沙箱
        ├─ codera.py        多根知识库（TF-IDF + 可选 embedding）
        ├─ context.py       token 预算 + 三段式压缩
        ├─ cache.py         LLM/工具缓存（SQLite WAL / 内存）
        ├─ sessions.py      会话库（SQLite，按目录分组）
        ├─ attach.py        docx/pdf/zip 附件分析
        ├─ voice.py         PortAudio 录音 + faster-whisper
        └─ weblinks.py      消息内链接自动取材
```

**Agent 循环**：流式请求（带工具 schema）→ 有 tool_calls？→ `ask` 模式在内嵌审批条确认 → 沙箱内执行 → 结果回传 → 循环（≤ 24 轮；用完强制一次「无工具」汇总，保证有最终结论）→ 最终文本流式显示。

## 产品：一个内核，多张面孔

仓库根目录是共享内核；`products/<name>/profile.json` 定义每个产品的品牌与功能开关（`import products; products.feature("rag")`）。本仓库默认产品：

| 开关 | 值 | 含义 |
|---|---|---|
| `dispatch` | ✅ | 智能派发 + `call_model` |
| `rag` | ✅ | 知识库 + `kb_search` |
| `attachments` / `sessions` / `voice` | ✅ | 附件、多会话、语音输入 |
| `gpulocal` | ❌ | 无内嵌本地 GPU 模型面板 |
| `mcp` | ❌ | 无外部 MCP 工具服务器 |
| `editor` | ✅ | 侧边文件树 + 编辑器面板 |

兄弟产品（`devtool`、`devtool_local`、`quant`、`devrag`）仍可用于内核开发：`LOCAL_AI_PRODUCT=devtool python3 main.py`，或 `python3 products/<name>/run.py`。

## 运行

**要求 Python 3.12+；推荐 3.14+。** Python 3.14 自带 Tcl/Tk 9.0，其彩色 emoji 引擎让工具条图标显示为彩色——3.12/3.13（Tk 8.6）在 Windows 上渲染为黑色单色字形。

```bash
pip install -r requirements.txt   # numpy/sounddevice/faster-whisper（语音）、psutil、tkinterdnd2
python3 main.py                   # Windows: python main.py
```

语音依赖可选——不用语音输入可跳过（语音按钮自动降级）。Windows 上到 [python.org](https://www.python.org/downloads/) 装 Python 3.14+，或用 Miniconda 建 3.12：

```bat
D:\miniconda3\Scripts\conda.exe create -n py312 python=3.12 -y
%USERPROFILE%\.conda\envs\py312\python.exe -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

> Windows 提示缺 PortAudio？重装 sounddevice：`pip uninstall sounddevice && pip install sounddevice`。
> macOS 麦克风无权限：系统设置 → 隐私与安全 → 麦克风 → 允许 Python/终端。

**模型**——首次运行自动生成 `models.json`：默认一个本地 Qwen 端点 + DeepSeek 占位。不跑本地后端的话，打开模型管理（模型菜单 → 添加 provider），填任意 OpenAI 兼容端点和你自己的 Key：DeepSeek、Kimi、GLM、OpenAI 或本地 llama.cpp/vLLM 服务。识图模型标 `"vision": true` 即可收图片附件。

**配置与数据目录**——Linux/macOS：`~/.config/local-ai-studio/`；Windows：`%APPDATA%\local-ai-studio\`（共享内核名；旧 `wellfuture-coder` / `qwen-coder` 目录自动迁移）。内含 `models.json`、`cache.json`、`state.json`、`sessions/`、`index/`、`media/`、`extract/`。

## 打包

```bash
pip install pyinstaller
python packaging/build.py novelwriter          # → dist/LocalAIWriter-<platform>/
python packaging/build.py novelwriter --clean  # 清缓存重打
```

打包是产品感知的：`profile.json` 决定 exe 名（`LocalAIWriter`），并排除 AI 重栈（torch/faster-whisper/onnx 不入包，体积几十 MB）。CI（`.github/workflows/test.yml`）在 ubuntu / windows / macos 三平台跑测试并出包。

## 路线图

来自[`PLAN-五产品矩阵.md`](PLAN-五产品矩阵.md)（产品 3；市场分析见[`PLAN-市场前景分析.md`](PLAN-市场前景分析.md)）：

| 版本 | 内容 |
|---|---|
| v0.1 ✅ | 内核平移：对话、模型管理、会话、文件化写作（本仓库现状） |
| v0.5 | 创作骨架：章节树面板、角色卡、世界观设定卡、风格模板、连载管理；txt/docx 导出 |
| v1.0 | 模板库：短剧爆点结构（前 3 集钩子、付费卡点）、网文节奏模板（黄金三章、爽点密度）；模板可配置可分享 |
| v1.1 | 敏感词/合规检查、多模型对比出稿、改写/扩写/续写指令 |

## 安全说明

- `run_shell` / `write_file` 会真实执行命令和写文件；默认**每次询问**模式逐次确认
- 沙箱护栏（默认开启，`LAS_SANDBOX=off` 关闭）：`write_file` 只允许写工作目录内；`run_shell` 拦截明显高危命令（rm -rf /、mkfs、关机、fork bomb）。护栏性质，非操作系统级隔离
- 工具执行有 60 秒超时和 24 轮上限（用完强制汇总收尾），防失控循环
- 让模型处理不可信文本时，避免使用「总是允许」模式

## 开发

```bash
pip install -r requirements-dev.txt
python -m py_compile *.py            # 语法门禁（与 CI 相同）
python -m pytest tests/ -q           # 350+ 单元测试；LLM 传输层 mock，HOME/APPDATA 隔离
```

核心模块只依赖标准库；可选依赖（numpy、faster-whisper、psutil、Pillow、tkinterdnd2）缺失时自动降级。UI 对话框在 `ui_panel_*.py`。代码约定见[`AGENTS.md`](AGENTS.md)。

## 许可证

[木兰宽松许可证，第2版](LICENSE)（Mulan Permissive Software License, v2）。
