# Local AI Writer · 短剧网文创作

[English](README.md) | **简体中文**

**Local AI Writer** 是一个桌面 AI 写作工作室，面向**短剧剧本和网文创作**——Tkinter 图形界面，接任意 OpenAI 兼容模型，流式对话，Agent 会真实读写你项目目录里的稿件文件。需要 Python 3.12+，支持 Linux / Windows / macOS。

一切都在本机运行：无账号、无内置云服务。只有当你自己配置了云端模型端点时，稿件内容才会发往你指定的服务器。界面中英双语——模型菜单 → 🌐 Language 切换，持久化在 `models.json`。

> 本仓库是写作产品的独立仓库，从 **Local AI Studio** 内核拆出（「一个内核，多个产品」）。默认产品是 `novelwriter`——`python main.py` 直接进入创作界面。兄弟产品（`devtool`、`devtool_local`、`quant`、`devrag`）仍在 `products/` 里作为内核附带产物运行；见 [产品：一个内核，多张面孔](#产品一个内核多张面孔)。

## 截图

![主界面](docs/screenshots/main.png)

## 当前状态

**v0.1 —— 内核平移 + 短剧成片。** 下述创作内核今天全部可用：Agent 对话真实写文件、多根知识库、附件分析、多会话、语音输入、模型管理。**短剧成片链可端到端跑通**：完稿章节 → 分镜 → 角色资产 → 关键帧 → 镜头视频 → 配音合成整集 MP4（需图像/视频服务 + ffmpeg；见 [docs/novel-setup.md](docs/novel-setup.md)）。路线图中的写作专属面板（章节树、角色卡、节拍模板）尚未开发——见[路线图](#路线图)。

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
- **短剧成片**——完稿章节 → 整集视频：分镜 → 角色形象资产 → 镜头关键帧（多图合成，长相由角色参考图锁定）→ 图生视频 → ffmpeg 拼接。三段式一致性传导让全剧面孔稳定；产物全部落在书籍目录下，重跑自动跳过已有文件，随时断点续造
- **台词配音（TTS）**——台词用 edge-tts 神经网络语音（可选 pip 安装）或 Windows 本地 SAPI 语音合成，ffmpeg 混流替换音轨；失败自动降级为模型原声，不阻断主链
- **风格库**——一个视觉风格驱动全部资产生成；每本书独立默认风格 + 可保存的预设（持久化在 `models.json`），首次生成前弹窗确认一次
- **短剧工作台**——三步面板（`/novel drama`）：剧本大纲 → 资产库 → 分集视频；可改剧本、外貌锚、分镜，单镜重生成，最后合成整集
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
5. 章节完稿后跑 `/novel drama video 1-3`——分镜、角色资产、关键帧、图生视频镜头和配音整集 MP4 依次出现在书籍的 `短剧成片/` 目录下（需图像/视频服务 + ffmpeg）。

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
| `image_gen` | 文生图（图像生成服务）→ `media/images/` | 只读 |
| `video_gen` | 文生视频/图生视频（异步任务，约 1–3 分钟）→ `media/videos/` | 只读 |
| `video_status` | 轮询进行中的视频生成任务 | 只读 |

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
        ├─ dramavideo.py    短剧成片链：分镜 → 资产 → 关键帧 → 镜头 → 整集（ffmpeg）
        ├─ imggen.py · videogen.py · tts.py   图像 / 视频 / TTS 客户端（agent 工具 + 成片链）
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

## 运行：从零搭建到首启

按 7 步走，Windows / macOS / Linux 全程通用。干净机器上 5–15 分钟。

### 第 1 步：装 Python 3.12 或更高

任选其一：

- **Windows / macOS**——到 [python.org/downloads](https://www.python.org/downloads/) 装最新的 3.14.x。**安装时务必勾选 "Add Python to PATH"**。
- **跨平台 / 想干净隔离**——Miniconda：

  ```bat
  :: Windows
  D:\miniconda3\Scripts\conda.exe create -n py314 python=3.14 -y
  %USERPROFILE%\.conda\envs\py314\python.exe -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  ```

  ```bash
  # macOS / Linux
  curl -L -o miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash miniconda.sh -b -p "$HOME/miniconda3" && eval "$("$HOME/miniconda3/bin/conda" shell.bash hook)"
  conda create -n py314 python=3.14 -y && conda activate py314
  python -m pip install --upgrade pip
  ```

> **版本说明**：Python 3.14 自带 Tcl/Tk 9.0，彩色 emoji 渲染正常；3.12/3.13 用 Tk 8.6，行内 emoji 字形在 Windows 上呈黑色。**这次换的彩色图标 PNG 是图片，不靠字体**，不受影响。

### 第 2 步：克隆并装依赖

```bash
git clone https://github.com/hzerther-hub/drama.git
cd drama
pip install -r requirements.txt          # 核心依赖：numpy / sounddevice / faster-whisper / psutil / tkinterdnd2 / imageio-ffmpeg
pip install -r requirements-dev.txt      # 可选，仅要跑测试时：pytest
```

Windows 上 `pip install sounddevice` 可能报缺 PortAudio，先装：

```bat
:: 先试重装，多数情况下 PyPI 轮子自带
pip uninstall sounddevice
pip install sounddevice
:: 还是缺就：
::   https://visualstudio.microsoft.com/visual-cpp-build-tools/ 勾 "Desktop development with C++"
```

macOS：

```bash
xcode-select --install                  # CLT（gcc/clang）装好再 pip
```

Linux Debian/Ubuntu：

```bash
sudo apt install python3-tk python3-venv libportaudio2 portaudio19-dev
```

### 第 3 步：装 ffmpeg（成片合成需要）

短剧台需要 ffmpeg 做配音混流和整集拼接。三种来源：

- **`imageio-ffmpeg`**（已列在 requirements.txt）—— 把 ffmpeg 二进制塞进 `imageio_ffmpeg/` 目录，应用自动找到，无需任何环境配置。
- **PATH 上的 ffmpeg**——[gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) 下载 `release` zip，解压到任意位置，把 `bin\` 加到系统 PATH。
- **macOS**：`brew install ffmpeg`
- **Linux**：`sudo apt install ffmpeg`

只写小说不跑成片可以跳过这步，应用会提示「未找到 ffmpeg」但写作不中断。

### 第 4 步：启动

```bash
python main.py                            # 默认产品 novelwriter
LOCAL_AI_PRODUCT=devtool python main.py   # 切到编程内核
LOCAL_AI_PRODUCT=quant python main.py     # 切到量化翻译内核
```

启动后 3 秒内会做三件事：

1. 自动把仓库根的 `models.json` 复制到 `CONFIG_DIR/models.json`（Windows 在 `%APPDATA%\local-ai-studio\`）。
2. 主窗口打开，顶栏模型菜单只显示 `deepseek/deepseek-chat` 占位（无 Key）。
3. 状态栏底部计数从 0 开始递增——agent loop 正常进入。

### 第 5 步：配模型，跑第一次对话

点顶栏 `⚙ 设置 → 模型`，看到三个供应商：

- **deepseek**（默认）——空 Key。在「DeepSeek」一栏粘贴 `sk-...`，点保存。
- **agnes**——空 Key。在「Agnes AI」一栏粘贴 `sk-...`，点保存。
- **sensetime**（可选）——商汤日日新，给识图备用。

保存后顶栏模型下拉能看到 `deepseek-chat`、`agnes-2.5-flash`、`agnes-3.0-flash` 等条目。点模型按钮选一个，输入框打「你好」，回车——收到首条回复说明配置成功；如果冒 `_post_stream` 错，模型 id 拼错，按模型下拉的菜单建议重选一次。

### 第 6 步（可选）：跑测试

```bash
python -m pytest tests/ -q
```

期望输出：`471 passed, 1 skipped`。那条 fail 是 `test_quant_qmt.py::test_probe_not_found`，是上游量化的预存在问题，不阻塞使用。

### 第 7 步（可选）：打包单文件可执行

```bash
pip install pyinstaller
python packaging/build.py novelwriter          # → dist/LocalAIWriter-<platform>/
python packaging/build.py novelwriter --clean  # 重建
```

打包器按 `products/novelwriter/profile.json` 决定 exe 名、压 torch/whisper 重量依赖。

### 常见坑

| 现象 | 原因 / 解决 |
|---|---|
| 启动报 `ModuleNotFoundError: tkinterdnd2` | 漏装：`pip install tkinterdnd2` |
| 顶栏 emoji 字形黑色 | Tk 8.6 局限。换 py314（Tk 9.0），或忽略——**所有彩色图标 PNG 仍正常** |
| macOS 麦克风不响应 | 系统设置 → 隐私与安全 → 麦克风 → 允许 Python / Terminal |
| 模型下拉选 Agnes 但调用失败 | 检查 Key 与 `base_url` 是否一致（国际 vs 中国站） |
| 短剧台报「未找到 ffmpeg」 | 装 ffmpeg 到 PATH，或确认 `imageio-ffmpeg` 已安装 |
| 中文乱码（少见） | Windows 控制台默认 GBK。脚本 stdout 加 `PYTHONIOENCODING=utf-8` |

### 配置与数据目录

`CONFIG_DIR` 是跨平台唯一的运行期目录，**重启不丢失**，旧名自动迁移：

- **Linux/macOS**：`~/.config/local-ai-studio/`
- **Windows**：`%APPDATA%\local-ai-studio\`

内部：`models.json`（供应商配置）、`cache.json`（LLM 缓存）、`state.json`（UI 状态）、`sessions/`、`index/`、`media/`、`extract/`。

### 写第一本书（最简流程）

顶栏模型下拉选 `deepseek-flash`（1M 上下文，支持识图）。输入框：

```
/novel start 末世重生女主复仇，猎杀灭门未婚夫 8
```

流水线从 `setup`（高概念）开始，写完一个文件就停下来等你审。每个阶段——`setup → world → contract → characters → outline → volume_plan → chapter_plan → chapters`——都停一审。`/novel ok` 进下一阶段、`/novel adjust <意见>` 改当前阶段、`/novel show N` 看第 N 章、`/novel rewrite N <反馈>` 重写指定章。书成后 `/novel drama 1-8` 改写成拍摄剧本，推到剧集工作台跑分镜/关键帧/视频。

完整命令参考：app 内输入 `/novel help`。

## 双供应商配置：Agnes + DeepSeek

这一个项目就能端到端地做 **代码 / 网文 / 短剧 / 漫画**。要把所有流水线都跑一遍，最少的配置是 **两个供应商**：**DeepSeek** 提供文本推理与识图（"大脑"），**Agnes** 提供图像与视频生成（"摄影机"）。两家都是注册即送免费额度、按量计费，没有企业门槛。

### 为什么是这两家

- **DeepSeek** 提供写作内核和编程内核需要的长上下文推理（`agent.run()` 单轮最多 24 次工具调用；novelwriter 各阶段实际吃 30k–120k token 上下文）。`deepseek-chat` 是 `models.json` 默认。
- **Agnes** 暴露短剧和漫画链路调用的图像和视频接口（`imggen.py` → `image_model`，`videogen.py` → `video_model`）。一个供应商、两个模型 ID，应用按每个供应商的 `image_model` / `video_model` 字段自动挑选。

只配 DeepSeek、不配 Agnes：完整的写作体验（大纲 / 世界观 / 合约 / 章节剧本 / 分镜表）能跑，但不会出帧。加 Agnes 解锁 短剧→MP4、漫画→分镜图，以及 `image_gen` / `video_gen` 工具。

### 申请 DeepSeek API

1. **进入平台**——访问 <https://platform.deepseek.com/sign_in>。注册页是 **简体中文 + 手机号验证**；非 +86 手机号可以走「密码登录」（先用一张 +86 号收一次短信），或在页面可见 OAuth 时改用 Google / GitHub 登录。
2. **创建账户**——填手机号 → 收短信验证码 → 同意用户协议。新手机号会自动注册。
3. **充值**——进入 <https://platform.deepseek.com/top_up>。DeepSeek 按 1M token 计费；最小充值约 5 美元（约 35 元），充一次所有模型都可用。CN 用户支持支付宝、微信支付；国际区可在结算面板用 Stripe 通道的银行卡。
4. **创建 Key**——<https://platform.deepseek.com/api_keys> → 「创建新密钥」。复制 `sk-...` 串（**只显示一次**，刷新页面就消失）。粘到 app 的 provider 表单 `api_key` 字段，`base_url` 填 `https://api.deepseek.com`（Anthropic 兼容格式走 `https://api.deepseek.com/anthropic`）。

**现行模型清单**（已在 `api-docs.deepseek.com/quick_start/pricing` 验证）：

| 模型 id | 上下文 | 最大输出 | 推理 | 识图 | 说明 |
|---|---|---|---|---|---|
| `deepseek-chat` | 64K | 8K | 是（可开关） | 否 | 默认；日常文本最便宜 |
| `deepseek-flash`（别名 `deepseek-v4-flash`） | 1M | 384K | 是 | **是** | 最便宜的识图模型 |
| `deepseek-v4-pro` | 1M | 384K | 否 | 否 | Pro 份文本（0813 版本） |
| `deepseek-reasoner` | 64K | 8K | 是（强总为） | 否 | 纯链式思考 |

`deepseek-v4-flash` 和 `deepseek-v4-flash-vision-exp` 是兼容旧名，实际都路由到 `DeepSeek-V4.1-Flash`。要新模型就往 `models.json` 现有 `deepseek` provider 里塞一条，启动时内核会自动重读。

### 申请 Agnes API

1. **进入平台**——访问 <https://platform.agnes-ai.com/login>（国际）或 <https://platform.agnes-ai.cn/login>（大陆）。两个站表单一致，国内访问 `.cn` 更快。
2. **创建账户**——点 "注册/ Sign up"。表单需要 **邮箱 + 邮箱验证码 + 密码 + 确认密码**。没有纯手机号路径，用一个能收 6 位验证码的邮箱。表单旁边还有 Google / GitHub OAuth 可用。
3. **充值**——首页大字写着「免费畅享前沿模型」。免费额度够跑几轮小规模图像/短视频做联调。短剧成片正经生产要在账单页充值（`.cn` 是支付宝/微信；`.com` 是银行卡）。
4. **创建 Key**——侧边栏里 "API Keys" 或 "令牌" 进入。新建一次、复制一次。`base_url` 看你账号所在站：
   - 国际：`https://apihub.agnes-ai.com/v1`
   - 大陆：`https://apihub.agnes-ai.cn/v1`（具体在仪表盘上确认，模型 id 同名）

**现行模型清单**（已在 `platform.agnes-ai.com` 首页 + AA 榜验证）：

| 能力 | 模型 id | 在本应用里的用途 |
|---|---|---|
| 文本推理 | `agnes-3.0-flash` | agent 循环、novelwriter 链路、漫画对白 |
| 文本（轻量） | `agnes-2.5-flash` | 例行工具调用的廉价子智能体 |
| 图像生成 | `agnes-image-2.5-flash`（新：`agnes-image-2.0`） | 角色参考图、关键帧多图合成 |
| 视频生成 | `agnes-video-v2.0`（新：`agnes-video-2.5`） | 单镜头视频片段 |
| 语音合成 | 首页没标注 | 仅短剧漫画用——配 `LAS_TTS_*` 环境变量或自行接一个 TTS 供应商 |

**版本号提醒**。仓库当前 `models.json` 写的是 `image_model: agnes-image-2.5-flash` 和 `video_model: agnes-video-v2.0`。AA 首页 2026 年现役叫 `Agnes-Image-2.0` / `Agnes-Video-2.5`。Agnes 网关新旧名都接受；如果旧名报「model not found」，在模型管理里换成对应的新名——应用每次都按 `image_model` / `video_model` 现读，不用重启。

### 一个项目能做什么

配置一次，**同一个应用实例**通过顶栏产品下拉切四种编辑形态（也可改 `products/<name>/profile.json`）。内核是共享的，只有 prompt 预设和流水线阶段不一样。

| 产品 | 跑什么 | 需要哪些供应商 |
|---|---|---|
| `devtool` / `devtool_local` | 编程 agent、文件读写、shell 执行、代码图谱检索、MCP 工具、多轮对话 | 1 个文本模型（DeepSeek 或 Agnes 文本） |
| `novelwriter` | 大纲 / 世界观 / 故事合约 / 角色表 / 摄影剧本 / 分镜表 → MP4 章节 | 文本（DeepSeek）+ 图像（Agnes）+ 视频（Agnes）+ 本机 ffmpeg |
| `quant` | 聚宽 ↔ PTrade ↔ 掘金 ↔ QMT 跨平台翻译（通过确定性 IR） | 1 个文本模型（仅在 `ParseError` 兜底时用） |
| `devrag` | 企业多根知识库，TF-IDF + 可选 embedding 混合 | 1 个文本模型 + 可选 embedding 端点（`LAS_EMBED_*`） |
| `novelwriter` 短剧台 | 剧集工作台（`ui_panel_drama.py`）：剧本 → 资产 → 分镜表 → 关键帧 → 片段 → 配音 MP4 | 文本 + 图像 + 视频 + TTS（可选） |
| `novelwriter` 漫画 | 按页图像生成（剧本作为分镜说明） | 文本 + 图像 |

短剧台和漫画不是独立产品，而是 `novelwriter` 内的两种形态（从工作台/触发面板进入）。**一套依赖，四种编辑产出**。

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
python -m pytest tests/ -q           # 540+ 单元测试；LLM 传输层 mock，HOME/APPDATA 隔离
```

核心模块只依赖标准库；可选依赖（numpy、faster-whisper、psutil、Pillow、tkinterdnd2）缺失时自动降级。UI 对话框在 `ui_panel_*.py`。代码约定见[`AGENTS.md`](AGENTS.md)。

## 许可证

[木兰宽松许可证，第2版](LICENSE)（Mulan Permissive Software License, v2）。
