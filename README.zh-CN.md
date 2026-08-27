# Local AI Studio

[English](README.md) | **简体中文**

本地编码助手：Tkinter 图形界面 + 本地 Qwen（DFlash2 加速）+ 流式 function-calling。
界面**中英文双语（默认英文）**，模型菜单 → 🌐 语言 切换，语言持久化在
`models.json` 顶层 `"language"` 字段（`en`/`zh`）。本地 GPU 模型管理内嵌于
`gpulocal/` 面板（启停/切换本地模型 + 实时 GPU/系统/硬件状态）。

> 📊 **硬件与模型说明**：[变废为宝 · 2080Ti 第二春 —— Qwen3.8-27B（DFlash2）/ Qwen3-VL-32B / Ornith-1.5-35B-A3B](docs/2080ti-second-spring.md) —— 双卡 2080 Ti（44 GiB，NVLink）跑三个本地模型，以及为什么这台机器选 llama.cpp 而不是 vLLM。

## 截图

<table>
  <tr>
    <td align="center"><img src="docs/screenshots/local-model-panel.png" width="420" alt="本地模型面板"><br><em>内嵌本地模型面板</em></td>
    <td align="center"><img src="docs/screenshots/main.png" width="560" alt="主界面"><br><em>主编码界面</em><br><sub>把你的截图保存为 <code>docs/screenshots/main.png</code></sub></td>
  </tr>
</table>

## 功能

- **流式对话**：正文/思考过程实时显示，任务进行中转轮动画
- **工具调用**：模型可自主调用 8 个内置工具完成编码任务
- **联网搜索**：`web_search` 工具（DuckDuckGo，零依赖无需 Key）
- **MCP 外部工具**：接入任意本地 stdio / 远程 HTTP MCP 服务器，工具自动发现
- **📎 附件识图**：发图随消息（需 vision 模型），音视频附路径分析
- **媒体内嵌**：聊天区直接显示图片/GIF 动画/播放音频/视频缩略图
- **聊天区可复制**：文字可选中、Ctrl+C 复制、右键菜单（复制/全选）
- **附件自动分析**：txt/md/csv 内联原文；docx/pdf 就地提取文本；zip/tar.gz 等
  解压到 `~/.config/local-ai-studio/extract/` 并附文件清单；rar/7z 提示用 `run_shell`
- **多会话**：自动保存、历史切换、按目录分组、全局搜索
- **上下文压缩**：对话过长自动截断/折叠（类 DeepSeek Harness）
- **token 统计**：用量、缓存命中率、秒回省 token 实时显示
- **缓存层**：SQLite / 内存双后端，重复请求秒回
- **代码库索引**：语义检索整个项目（类 opencode-codebase-index）
- **模型管理**：多 provider、添加/编辑/删除、自定义端点、端点模型自动拉取、vision 模型
- **🖥 本地 GPU 模型**：内嵌 `gpulocal/` 面板，模型下拉里启停/切换本地模型，状态实时互通
- **🔗 链接自动取材**：消息里的图片 URL 自动下载识图，网页 URL 自动抓正文给模型（后台线程，不卡界面）
- **语音输入**：单按钮两用——长按说话松手识别，轻点自动停顿检测（本地 Whisper）
- **字体内置**：JetBrains Mono + Noto Sans CJK 打包携带，三平台显示一致
- **三档权限模式**：只读 / 每次询问 / 总是允许
- **工作目录切换**：多项目切换，相对路径操作基于所选目录
- **跨平台**：Linux / Windows / macOS

## 架构

```
local-ai-studio/
├── config.py     # 端点、模型、生成参数、系统提示
├── llm.py        # OpenAI 兼容流式客户端（tool_calls 分片累积 + usage 统计）
├── tools.py      # 8 个内置工具定义 + 执行器 + 权限分级
├── mcp.py        # MCP 客户端（stdio 子进程 / 远程 HTTP 双传输 + 工具发现路由）
├── media.py      # 媒体支持（图片加载/GIF 动画/音频播放/视频缩略图）
├── agent.py      # function-calling Agent 循环 + 权限控制 + 用量聚合 + 多模态
├── context.py    # 上下文压缩（预算 + 截断 + 折叠，类 DeepSeek Harness）
├── cache.py      # 缓存层（SQLite/内存，auto 回退）
├── codeindex.py  # 代码库索引（分块 + TF-IDF + SQLite 检索库）
├── localmodels.py# 本地 GPU 模型桥接（内嵌 gpulocal 注册表 + 跨平台启停 + 状态同步）
├── gpulocal/     # 内嵌本地模型面板（local_model_panel.py + services/ + setup.sh/ps1/setup-mac.sh）
├── weblinks.py   # 消息内链接自动取材（图片下载识图 / 网页正文提取）
├── sessions.py   # 多会话管理（保存/切换/搜索/目录绑定）
├── voice.py      # 语音录入（PortAudio 跨平台 + 本地 Whisper）
├── ui.py         # Tkinter 界面（模型/缓存/MCP/会话管理 + 媒体内嵌 + 帮助）
├── fonts/        # 内置字体（JetBrains Mono + Noto Sans CJK）
└── main.py       # 入口
```

数据流：

```
用户提问 → Agent.run()
  → llm.stream_chat() 流式请求（带 tools schema）
  → 模型返回 tool_calls 或 最终文本
  → 若有工具调用：审批（ask 模式）→ tools.execute_tool() → 结果回传
  → 循环直到无工具调用
  → 最终文本返回并流式显示
```

## 工具集

| 工具 | 说明 | 权限 |
|---|---|---|
| `read_file` | 读取文件（带行号） | 只读 |
| `list_dir` | 列目录 | 只读 |
| `glob_search` | 通配符找文件 | 只读 |
| `grep_search` | 内容搜索 | 只读 |
| `index_search` | 语义检索代码库（按相关度返回代码块） | 只读 |
| `web_search` | 联网搜索（DuckDuckGo，无需 API Key） | 只读 |
| `write_file` | 写入/覆盖文件 | **可写** |
| `run_shell` | 执行 shell 命令 | **可写** |

## 联网搜索

`web_search` 走 DuckDuckGo HTML 接口，返回标题/URL/摘要（默认 8 条，最多 10 条），
无第三方依赖、无需 API Key。直接问需要最新信息的问题（版本号、新闻、文档）模型即自动调用。

## 🖥 本地 GPU 模型（内嵌 gpulocal）

本地模型面板已并入本仓库 `gpulocal/` 子目录统一维护，本应用直接成为本地模型启动器。
三平台一键装机：`bash gpulocal/setup.sh`（Ubuntu/NVIDIA：CUDA + llama.cpp-dflash2 + systemd）、
`powershell -File gpulocal/setup.ps1`（Windows）、`bash gpulocal/setup-mac.sh`（macOS：Homebrew 装
llama.cpp，Metal 加速）；三个脚本都支持 `download` 子命令只下载模型。

- **模型自动同步**：启动时读取 gpulocal 的 `MODELS` 注册表（按文件 mtime 动态缓存），
  同步进 `models.json`（`gpulocal-8097/8098/8099` 三个 provider）；那边加/改模型这边自动跟进
- **下拉菜单一键启停**：模型菜单显示每个本地模型的实时状态点（`●` 就绪 / `◐` 加载中 / `○` 停止），
  子菜单提供 ▶ 启动 / ■ 停止 / ↻ 重启；启动就绪后自动切换为当前模型
- **串行管理**：与 gpulocal 相同规则——启动一个模型先停其它（44 GiB 显存一次只够跑一个）
- **双向动态同步**：两边操作的是同一批 `systemctl --user` 服务（Linux）/后台进程（Windows/macOS），
  任一侧启停，另一侧 ~4 秒内看到新状态；菜单里还可直接「🖥 打开本地模型面板」
- 带 `mmproj` 的模型自动标记识图（`vision: true`）
- gpulocal 目录缺失时自动降级，不影响其它功能

## MCP 外部工具

模型菜单 → 🔌 管理 MCP 服务器，接入任意 MCP 服务器，支持两种传输：

- **本地 stdio 服务器**：作为子进程启动（填 `command` + `args`），JSON-RPC 2.0 按行传输
- **远程 streamable HTTP 服务器**：填 `url`（可带 `headers`），POST 收发，响应兼容纯 JSON 与 SSE

- 配置存于 `~/.config/local-ai-studio/mcp.json`，格式：
  `{"servers": {"名称": {"command": "...", "args": [...], "url": "...", "headers": {...}, "enabled": true, "readonly": false}}}`
- 启动时自动连接，工具以 `mcp_<服务器>_<工具>` 命名并入模型工具表
- 「只读」标记的服务器：工具免审批；未标记视为可写（ask 模式需确认）
- 工具返回的图片自动落盘 `media/` 并内嵌显示
- 示例服务器：`python3 examples/mcp_echo_server.py`

## 📎 附件与媒体

- **📎 附件按钮**：多选图片/音频/视频随消息发送（预览条可单个 ✕ 移除）
- **图片**：转 data URL 视觉输入（需 `"vision": true`），大图自动等比缩到 1568px 内
- **音视频**：消息附上文件路径与说明，模型可用 ffmpeg/ffprobe 分析处理
- **聊天区内嵌**：图片直接显示，GIF 自动播放，音频带 ▶/⏸ 播放条，视频显示 ffmpeg 首帧缩略图，双击或「外部打开」调系统播放器；MCP 工具产出图片同样内嵌
- 聊天区文字可选中、Ctrl+C 复制、右键「复制/全选」
- 可选安装 Pillow 提升图片兼容性：`pip install Pillow`

## 缓存（提速 + 省 tokens）

- **LLM 回复缓存**：相同「模型 + 消息 + 工具」的请求直接返回缓存回复
- **工具结果缓存**：只读工具短时间内重复调用走缓存
- **两种后端**（模型下拉菜单 → ⚡ 管理缓存）：SQLite（`cache.db`，重启保留）与内存（进程内）；`auto` 优先 SQLite、不可用退内存
- 设置存于 `~/.config/local-ai-studio/cache.json`，界面里可调 TTL、清空缓存
- 统计栏实时显示：token 用量、后端 KV 缓存命中率、本层缓存「秒回」次数

## 代码库索引（类 opencode-codebase-index）

不是把全部代码塞进提示词，而是解析 → 分块 → 向量化（TF-IDF）→ SQLite 可检索数据库。
模型用 `index_search` 按相关度取回最相关代码块（含文件和行号）再精读，大幅省 tokens。

- **代码感知分词**：拆 camelCase / snake_case，中文注释按 bigram 索引，中英文查询均可
- **增量更新**：按 mtime/size 跳过未变文件；首次调用自动建索引
- **索引库**：`index/<工作目录哈希>.db`，自动跳过 .git / node_modules / build
- 界面：模型下拉菜单 → 🗂 重建代码索引

## 多会话

- **自动保存**：发送瞬间即落盘（崩溃不丢对话）
- **目录绑定**：每个会话记录所属工作目录，菜单只显示当前目录的会话
- **全局搜索**：按标题/内容关键词跨项目搜会话（「＋ 新会话」→ 🔍）
- **载入切目录**：打开其他项目的会话自动切到该会话的目录
- 存储：`~/.config/local-ai-studio/sessions/*.json`

## 上下文压缩（类 DeepSeek Harness）

对话超过预算（约 24000 tokens）时自动压缩：

1. **阶段 0**：超长工具结果就地截断（旧轮 400 / 最近轮 3000）
2. **阶段 1**：仍超预算 → 旧轮工具结果进一步压缩
3. **阶段 2**：仍超预算 → 中间轮折叠为摘要行（保留 system + 首问 + 最近 2 轮原文）

## 模型管理

- 多 provider 配置（本地 Qwen / Qwen2.5-VL 识图 / DeepSeek / 自定义 OpenAI 兼容端点）
- 添加：一个端点 + 密钥可挂多个模型 ID；「🔍 获取模型列表」自动拉取端点 `/models`
- 编辑：改显示名 / 模型 ID / 端点 / 密钥
- 识图模型：`"vision": true` 即可接收图片附件
- 配置：`~/.config/local-ai-studio/models.json`（旧版 wellfuture-coder / qwen-coder 目录自动迁移）

## Token 统计

底部统计栏实时显示：token 用量（输入/输出/思考）与请求数、后端 KV 缓存命中、秒回次数与估算节省。点击统计栏清零。

## 权限模式

| 模式 | 行为 |
|---|---|
| `readonly` 只读 | 只提供只读工具，模型无法发起写操作 |
| `ask` 每次询问（默认） | 可写工具执行前弹窗，点「允许/拒绝」 |
| `always` 总是允许 | 直接执行，不询问 |

## 运行（Linux / Windows / macOS 均支持）

界面用 Tkinter（Python 自带），录音用 PortAudio（sounddevice），本地识别用 faster-whisper。

```bash
pip install -r requirements.txt   # 语音功能依赖；不用语音可不装
python3 main.py                    # Windows: python main.py
```

**要求 Python 3.12+。** Windows 上若系统 Python 版本过旧：优先用 venv 运行；本机没有 3.12 解释器时，用 Miniconda 装一个再建 venv（仅针对 Windows 的方案）：

```bat
D:\miniconda3\Scripts\conda.exe create -n py312 python=3.12 -y
%USERPROFILE%\.conda\envs\py312\python.exe -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

> Windows 若提示缺 PortAudio，重装 sounddevice 即可：`pip uninstall sounddevice && pip install sounddevice`。
> macOS 若麦克风无权限：系统设置 → 隐私与安全 → 麦克风 → 允许 Python/终端。

**配置与数据目录**——Linux/macOS：`~/.config/local-ai-studio/`；Windows：`%APPDATA%\local-ai-studio\`。
内含 `models.json`、`mcp.json`、`cache.json`、`state.json`、`sessions/`、`index/`、`media/`。
旧名的配置目录（`wellfuture-coder`，以及更早的 `qwen-coder`）首次运行自动迁移。

### 各平台打包

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name LocalAIStudio main.py
# macOS: pyinstaller --windowed --name LocalAIStudio main.py
```

> 仓库内已提供 `LocalAIStudio.spec`：排除 torch/faster-whisper/onnx，打包体积 ~69MB。
> 直接 `pyinstaller LocalAIStudio.spec`。

## 依赖的后端

本地 Qwen 推理服务（`qwen38-27b-q8.service`，端口 8097，DFlash2 投机解码加速）。

- 端点：`http://127.0.0.1:8097/v1`
- 模型：`qwen3.8-27b-q8`
- 识图模型：`qwen2.5-vl-7b`（`http://127.0.0.1:8099/v1`，`"vision": true`）

## 安全说明

- `run_shell` / `write_file` 会真实执行系统命令和写文件，默认「每次询问」模式最安全
- 内置沙箱护栏（默认开启，`LAS_SANDBOX=off` 关闭）：`write_file` 只允许写工作目录内；`run_shell` 拦截明显高危命令（rm -rf /、mkfs、格式化磁盘、关机、fork bomb）。护栏性质，非操作系统级隔离
- 工具执行有超时（`TOOL_EXEC_TIMEOUT=60s`）和轮次上限（`MAX_TOOL_ROUNDS=20`）防失控
- 尚无完整沙箱，避免在「总是允许」模式下让模型处理不可信指令

## 开发

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q     # 122 个单元测试；LLM 传输层 mock，HOME/APPDATA 隔离
```

CI：`.github/workflows/test.yml` 在 ubuntu / windows / macos × Python 3.12 矩阵上跑 py_compile + pytest。UI 对话框已拆到 `ui_panel_*.py` 模块，`App` 方法为薄委托。
