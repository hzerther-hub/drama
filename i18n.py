# -*- coding: utf-8 -*-
"""中英文双语界面层（默认英文，可切换中文并持久化）。

用法：
    from i18n import t, set_lang, get_lang, load_lang
    load_lang()            # 启动时读一次已保存语言
    label = t("btn.send")  # 按当前语言取文案

词典为稀疏表：key -> {"en": ..., "zh": ...}；缺任一语言回退到 en/原 key。
语言保存在 models.json 顶层 "language" 字段（localmodels 同步只重建
providers，不会破坏该字段）。未登记的中文原文保留原样，可随时往 STRINGS
补充。
"""

from __future__ import annotations

import config

# 默认语言（缺省 English）
DEFAULT_LANG = "en"

STRINGS: dict = {
    # —— 窗口 / 顶部条 ——
    "app.title":       {"en": "Local AI Studio — Local Coding & Models",
                        "zh": "本地 AI 工作室 — 本地编码与模型"},
    "top.select_model": {"en": "Select model", "zh": "选择模型"},
    "top.new_session": {"en": "💬 New session", "zh": "💬 新会话"},
    "top.sessions":    {"en": "💬 Sessions", "zh": "💬 会话"},
    "top.dir":         {"en": "Dir", "zh": "目录"},
    "top.ready":       {"en": "Ready", "zh": "就绪"},
    "top.attach":      {"en": "📎 Attach/Vision", "zh": "📎 附件/识图"},
    "top.voice":       {"en": "🎤 Voice input", "zh": "🎤 语音输入"},
    "top.send":        {"en": "➤ Send ⏎", "zh": "➤ 发送 ⏎"},
    "top.clear":       {"en": "🧹 Clear", "zh": "🧹 清空"},
    "btn.voice":       {"en": "🎤", "zh": "🎤"},
    "btn.send":        {"en": "➤", "zh": "➤"},
    "btn.stop":        {"en": "⏹", "zh": "⏹"},
    "btn.clear":       {"en": "🧹", "zh": "🧹"},
    "btn.save_icon":   {"en": "💾", "zh": "💾"},
    "btn.close_icon":  {"en": "🗙", "zh": "🗙"},

    # —— 输入占位 / 状态 ——
    "input.placeholder": {
        "en": "Type a message… (Enter to send, Shift+Enter for newline)\n"
              "· paste an image/file path (C:\\ or file://) to auto-attach\n"
              "· 🎤 hold to talk / auto transcribe · 📎 attach · ❓ full usage · build 0906-2",
        "zh": "输入消息…（回车发送，Shift+回车换行）\n"
              "· 粘贴图片/文件路径（C:\\ 或 file://）自动转附件\n"
              "· 🎤 按住说话 / 自动识别 · 📎 附件识图 · ❓ 查看完整使用方式 · build 0906-2",
    },
    "status.idle":     {"en": "○ Idle", "zh": "○ 空闲"},
    "status.thinking": {"en": "Thinking", "zh": "思考"},

    # —— 权限模式 ——
    "mode.readonly":   {"en": "Read-only (no writes)", "zh": "只读（禁止写）"},
    "mode.ask":        {"en": "Ask every time", "zh": "每次询问"},
    "mode.always":     {"en": "Always allow", "zh": "总是允许"},

    # —— 模型菜单 ——
    "model.manage":    {"en": "⚙ Manage models (add / edit / delete)…", "zh": "⚙ 管理模型（添加 / 编辑 / 删除）…"},
    "model.mcp":       {"en": "🔌 Manage MCP servers…", "zh": "🔌 管理 MCP 服务器…"},
    "model.cache":     {"en": "⚡ Manage cache…", "zh": "⚡ 管理缓存…"},
    "model.index":     {"en": "🗂 Rebuild code index…", "zh": "🗂 重建代码索引…"},
    "model.reasoning": {"en": "🧠 Reasoning effort", "zh": "🧠 推理等级"},
    "model.current":   {"en": "✓ Current: {name}", "zh": "✓ 当前：{name}"},
    "model.menu.cloud":   {"en": "☁ {name}  ({n})", "zh": "☁ {name}  ({n})"},
    "model.menu.empty":   {"en": "— 暂无模型 —", "zh": "— 暂无模型 —"},
    "settings.menu":   {"en": "⚙ Settings", "zh": "⚙ 设置"},
    "settings.btn":    {"en": "⚙ Settings", "zh": "⚙ 设置"},
    "model.reasoning.default": {"en": "Model default", "zh": "模型默认"},
    "model.reasoning.set": {"en": "Reasoning effort set: {v}", "zh": "推理等级已设置：{v}"},
    "think.toggle":   {"en": "🧠 Think", "zh": "🧠 思考"},
    "think.off":      {"en": "🌫 No think", "zh": "🌫 不思考"},
    "think.on":       {"en": "🧠 Think on", "zh": "🧠 思考开"},
    "think.set":      {"en": "Thinking mode: {v}", "zh": "思考模式：{v}"},
    "lang.menu":       {"en": "🌐 Language", "zh": "🌐 语言"},
    "lang.en":         {"en": "English", "zh": "English"},
    "lang.zh":         {"en": "中文", "zh": "中文"},

    # —— 会话菜单 ——

    # —— 通用按钮 ——
    "btn.save":        {"en": "Save", "zh": "保存"},
    "btn.close":       {"en": "Close", "zh": "关闭"},
    "font.title":      {"en": "Font size", "zh": "字号"},
    "font.chat":       {"en": "Chat", "zh": "聊天"},
    "font.editor":     {"en": "Editor", "zh": "编辑器"},
    "btn.cancel":      {"en": "Cancel", "zh": "取消"},
    "btn.confirm":     {"en": "OK", "zh": "确定"},

    # —— 通用占位 ——
    "misc.no_title":   {"en": "(no title)", "zh": "（无标题）"},
    "misc.webpage":    {"en": "(webpage)", "zh": "（网页）"},
    "tool.preview_more":{"en": "…{n} lines · ", "zh": "…共 {n} 行 · "},
    "view.full":       {"en": "［📄 View full］", "zh": "［📄 查看全文］"},

    # —— 对话框标题 ——
    "dlg.model_mgmt":  {"en": "Manage models", "zh": "模型管理"},
    "dlg.add_model":   {"en": "Add model", "zh": "添加模型"},
    "dlg.edit_model":  {"en": "Edit model — {name}", "zh": "编辑模型 — {name}"},
    "dlg.cache":       {"en": "Cache management", "zh": "缓存管理"},
    "dlg.fetch_models":{"en": "Models fetched — click to fill 'Model ID'",
                        "zh": "获取到的模型 — 点选填入『模型 ID』"},

    # —— 添加模型字段 ——
    "add.base_url":    {"en": "API endpoint base_url (e.g. https://api.deepseek.com/v1)",
                        "zh": "API 端点 base_url（如 https://api.deepseek.com/v1）"},
    "add.api_key":     {"en": "API Key (blank for local models)", "zh": "API Key（本地模型可留空）"},
    "add.ids":         {"en": "Model IDs (one per line, multiple allowed)",
                        "zh": "模型 ID（每行一个，可一次添加多个）"},
    "add.vision":      {"en": "👁 Vision (this model group can receive image attachments)",
                        "zh": "👁 识图（这批模型可接收图片附件）"},
    "add.reasoning":   {"en": "🧠 Reasoning effort",
                        "zh": "🧠 推理等级"},
    "add.reasoning_hint": {"en": "blank = model default; none/low/medium/high/xhigh/max",
                           "zh": "留空 = 模型默认；none/low/medium/high/xhigh/max"},
    "add.context_window": {"en": "Context window (tokens; 0 = unset)",
                           "zh": "上下文窗口（token；0 = 不设置）"},
    "add.max_tokens":     {"en": "Max output tokens (0 = unset, capped to 32768)",
                           "zh": "最大输出 token（0 = 不设置，上限 32768）"},
    "add.tokens_hint":    {"en": "blank/0 → fall back to heuristic (16K local / global cloud)",
                           "zh": "留空或 0 → 按启发式兜底（本地 16K / 云端全局）"},
    "add.api_type":       {"en": "API type",
                           "zh": "API 类型"},
    "add.api_type_hint":  {"en": "Anthropic uses /messages + x-api-key; OpenAI uses /chat/completions",
                           "zh": "Anthropic 走 /messages + x-api-key；OpenAI 走 /chat/completions"},
    "add.endpoint_fixed": {"en": "Endpoint: {url} · API type: {api} (follows the provider)",
                           "zh": "端点：{url} · API 类型：{api}（随 Provider，修改请编辑 Provider）"},
    "add.fetch":       {"en": "🔍 Fetch model list (auto-fill)", "zh": "🔍 获取模型列表（自动填入）"},
    "add.require":     {"en": "base_url and at least one model ID required",
                        "zh": "base_url 和至少一个模型 ID 必填"},
    "add.done":        {"en": "Added {n} model(s): {url}", "zh": "已添加 {n} 个模型：{url}"},

    # —— 编辑模型 ——
    "edit.name":       {"en": "Display name", "zh": "显示名称"},
    "edit.id":         {"en": "Model ID", "zh": "模型 ID"},
    "edit.base_url":   {"en": "API endpoint base_url", "zh": "API 端点 base_url"},
    "edit.api_key":    {"en": "API Key (blank = keep unchanged)", "zh": "API Key（留空 = 不修改）"},
    "edit.vision":     {"en": "👁 Vision (can receive image attachments)", "zh": "👁 识图（可接收图片附件）"},
    "edit.reasoning":  {"en": "🧠 Reasoning effort",
                        "zh": "🧠 推理等级"},
    "edit.reasoning_hint": {"en": "blank = model default; none/low/medium/high/xhigh/max",
                            "zh": "留空 = 模型默认；none/low/medium/high/xhigh/max"},
    "edit.context_window": {"en": "Context window (tokens; 0 = unset)",
                            "zh": "上下文窗口（token；0 = 不设置）"},
    "edit.max_tokens":     {"en": "Max output tokens (0 = unset, capped to 32768)",
                            "zh": "最大输出 token（0 = 不设置，上限 32768）"},
    "edit.tokens_hint":    {"en": "blank/0 → fall back to heuristic (16K local / global cloud)",
                            "zh": "留空或 0 → 按启发式兜底（本地 16K / 云端全局）"},
    "edit.api_type":       {"en": "API type",
                            "zh": "API 类型"},
    "edit.api_type_hint":  {"en": "Anthropic uses /messages + x-api-key; OpenAI uses /chat/completions",
                            "zh": "Anthropic 走 /messages + x-api-key；OpenAI 走 /chat/completions"},
    "edit.fetch":      {"en": "🔍 Fetch / refresh model list", "zh": "🔍 获取 / 刷新模型列表"},
    "edit.done":       {"en": "Updated model: {name}", "zh": "已修改模型：{name}"},
    "ui.thinking": {"en": "Thinking…", "zh": "思考中…"},
    "ui.processing": {"en": "Processing", "zh": "处理中"},
    "ui.busy": {"en": "Busy", "zh": "进行中"},
    "ui.running": {"en": "Running", "zh": "进行中"},
    "ui.ok": {"en": "✓ Done", "zh": "✓ 完成"},
    "ui.err": {"en": "✗ Failed", "zh": "✗ 出错"},
    "ui.usage_reset": {"en": "Usage stats reset", "zh": "token 统计已清零"},
    "ui.error": {"en": "❌ Error: {e}", "zh": "❌ 错误: {e}"},
    "ui.you": {"en": "You · {model}: {label}", "zh": "你 · {model}：{label}"},
    "ui.send_attach": {"en": "(send attachment)", "zh": "(发送附件)"},
    "ui.fetching": {"en": "🔗 Fetching links in message…", "zh": "🔗 正在抓取消息中的链接…"},
    "dlg.approve_tool": {"en": "Approve tool call: {name}", "zh": "审批工具调用：{name}"},
    "ui.approve_want": {"en": "The model wants to run a write tool: {name}", "zh": "模型想执行可写工具：{name}"},
    "btn.allow": {"en": "Allow", "zh": "允许"},
    "btn.deny": {"en": "Deny", "zh": "拒绝"},
    "ui.approve_err": {"en": "⚠️ Approval window error: {e}", "zh": "⚠️ 审批窗口异常：{e}"},
    "ui.approve_timeout": {"en": "⏱️ Approval timed out, auto-denied", "zh": "⏱️ 审批超时，已自动拒绝"},
    "ui.stopping": {"en": "⏹ Stopping…", "zh": "⏹ 正在停止…"},
    "ui.stop_req": {"en": "⏹ Stop requested, aborting…", "zh": "⏹ 已请求停止，正在中止…"},
    "evt.tool_run": {"en": "▶ Running tool: {name}…", "zh": "执行工具: {name}…"},
    "evt.tool": {"en": "Tool", "zh": "工具"},
    "evt.round": {"en": "Round {n} tool calls done, continuing", "zh": "第 {n} 轮工具调用完成，继续处理"},
    "evt.compact": {"en": "📉 Context compacted: ~{before} → ~{after} tk", "zh": "📉 上下文已压缩：~{before} → ~{after} tk"},
    "evt.denied": {"en": "⛔ Denied: {name}", "zh": "⛔ 已拒绝: {name}"},
    "btn.play": {"en": "▶ Play", "zh": "▶ 播放"},
    "btn.stop2": {"en": "⏸ Stop", "zh": "⏸ 停止"},
    "btn.ext_play": {"en": "▶ External", "zh": "▶ 外部播放"},
    "btn.ext_open": {"en": "Open externally", "zh": "外部打开"},
    "ui.attach_n": {"en": "📎 Attached {n} file(s) ({kinds})", "zh": "📎 已加入 {n} 个附件（{kinds}）"},
    "menu.copy":        {"en": "Copy", "zh": "复制"},
    "menu.copy_block":  {"en": "Copy this message", "zh": "复制本条消息"},
    "menu.select_all":  {"en": "Select all", "zh": "全选"},
    "btn.copy_all":     {"en": "Copy all", "zh": "复制全部"},
    "btn.save_as":      {"en": "Save as…", "zh": "另存为…"},
    "dlg.save_as_title":{"en": "Save as", "zh": "另存为"},
    "msg.saved":        {"en": "Saved", "zh": "已保存"},
    "msg.saved_to":     {"en": "Saved to: {p}", "zh": "已保存到：{p}"},
    "msg.save_fail":    {"en": "Save failed", "zh": "保存失败"},
    "popup.page":       {"en": "Page content — {title}", "zh": "网页内容 — {title}"},
    "popup.tool":       {"en": "Tool result — {name}", "zh": "工具返回 — {name}"},
    "help.title":     {"en": "Help — Local AI Studio", "zh": "帮助 — Local AI Studio"},
    "chat.welcome": {
        "en": """👋 Welcome to Local AI Studio

· Type below, Enter to send, Shift+Enter for newline
· 📎 Attach/Vision (status bar): send images for recognition, plus audio/video;
  pasting a file path (C:\\... or file:///) into the message auto-attaches it
· 🎤 Voice input: hold to talk, release to finish; a quick tap switches to
  auto stop-on-silence (1.5s)
· ➤ Send becomes ⏹ Stop while a task is running (Esc also stops)
· 🧹 Clear only clears the view — sessions are kept in the 💬 menu (top)
· 📁 Dir (top): click the path to switch the working directory
  (the scope the model can read/write files in)
· ❓ Help (top right): full feature guide
""",
        "zh": """👋 欢迎使用 Local AI Studio

· 下方输入消息，回车发送，Shift+回车换行
· 📎 附件/识图（状态行）：发图片可识图，也支持音频/视频；
  消息里粘贴文件路径（C:\\... 或 file:///）会自动转为附件
· 🎤 语音输入：长按说话、松手结束；轻点一下则静音 1.5 秒自动结束
· ➤ 发送：任务运行中变为 ⏹ 停止（Esc 同样停止）
· 🧹 清空：只清屏不删会话；历史会话在顶部 💬 菜单
· 📁 目录（顶部）：点击路径切换工作目录（模型读写文件的范围）
· ❓ 右上角帮助：完整功能说明
""",
    },
    "help.text": {
        "en": """Local AI Studio — Help

[Basics]
· Type in the box, press Enter to send; Shift+Enter for newline
· "Clear" only clears the view, does not delete the session; sessions are managed in the top "＋ New session" menu
· Context toggle (top bar): "🔗 Keep context" continues the session history by default;
  "⚡ Standalone" sends each message without history — saves tokens and keeps questions
  independent; replies are still saved to the session

[Session]
· Each conversation auto-saves; switch history sessions in the "＋ New session" menu
· History continues context; auto-compacts when too long (a note appears in the chat)

[Model management]
· Top model button: quickly switch model
· ⚙ Manage models: add (one endpoint can hold multiple model IDs) / edit / delete
· Endpoint models auto-sync into the dropdown (fetch /models when opening)

[Permission mode]
· Read-only: only read-only tools, the model cannot write files or run commands
· Ask every time (default): confirm before write operations (Enter=allow, Esc=deny)
· Always allow: executes directly, use with care!

[Tools]
The model can call: read_file / write_file / list_dir / glob / grep /
index_search (semantic code search) / shell / web_search (web)
External MCP servers add more tools (model menu → 🔌 Manage MCP servers)
· Tool results are auto-formatted: search result cards, clickable links,
  long content has a "View full" popup with copy/save

[Web search]
· Ask questions needing the latest info; the model calls web_search
· Search auto-picks an available engine (Bing / Baidu / DuckDuckGo), no dependencies, no API key

[📎 Attach / media]
· 📎 Attach: pick image/audio/video files to send with the message
· Images auto-convert to vision input (requires a vision model, models.json "vision": true)
· A file:/// URI or a plain Windows path (C:\\...) in the message auto-converts to an attachment (e.g. an image path copied from WeChat)
· Attachments auto-analyzed: txt/md/csv inlined, docx/pdf extracted text, zip/tar.gz extracted then operable with tools
· Audio/video attach a path; the model can analyze with ffmpeg/ffprobe
· Inline in chat: images, GIF animation, audio player, video thumbnail; double-click an image or "Open externally"

[MCP external tools]
· Model menu → 🔌 Manage MCP servers: add stdio JSON-RPC servers
· "Read-only" servers' tools bypass approval and are cacheable; unmarked = writable
· Tool names look like mcp_server_tool; the model auto-discovers them

[Cache (speed + save tokens)]
· Model menu → ⚡ Manage cache: SQLite / memory backends
· Duplicate requests reply instantly, no token cost
· Bottom stats bar: token usage, cache hit rate, fast-reply count (click to reset)

[Code index]
· Model menu → 🗂 Rebuild code index
· Let index_search retrieve code by relevance to answer "where is X implemented"

[Voice]
· 🎤 Voice input: press the button to record — release to transcribe (push-to-talk);
  a quick tap switches to auto-stop (ends after 1.5s of silence)

[Shortcuts]
· Enter: send / allow in approval dialogs
· Esc: stop while running / deny in approval dialogs
""",
        "zh": """Local AI Studio — 使用帮助

【基本操作】
· 输入框回车发送；Shift+回车换行
· 「清空」只清屏，不删会话；会话在顶部「＋ 新会话」菜单管理
· 上下文开关（顶部工具栏）：默认「🔗 续上下文」延续会话历史；
  切为「⚡ 独立提问」后每条消息不带历史单独发送——省 token、问题互不干扰，
  回复仍会存入会话记录

【会话】
· 每次对话自动保存，可在「＋ 新会话」菜单切换历史会话
· 历史会话延续上下文；过长时自动压缩（聊天区会提示）

【模型管理】
· 顶部模型按钮：快速切换模型
· ⚙ 管理模型：添加（一个端点可加多个模型 ID）/ 编辑 / 删除
· 端点模型自动同步进下拉（打开时拉取 /models）

【权限模式】
· 只读：仅只读工具，模型无法写文件/执行命令
· 每次询问（默认）：写操作前弹窗审批（回车=允许，Esc=拒绝）
· 总是允许：直接执行，慎用！

【工具】
模型可调用：读文件 / 写文件 / 列目录 / glob / grep /
index_search（语义检索代码库）/ shell / web_search（联网搜索）
另可通过 MCP 接入外部服务器工具（模型菜单 → 🔌 管理 MCP 服务器）
· 工具返回自动美化：搜索结果卡片、链接可直接点击、
  超长内容点「查看全文」弹窗看完整内容并复制/另存

【联网搜索】
· 直接问需要最新信息的问题，模型会调 web_search
· 搜索自动选择可用引擎（Bing / 百度 / DuckDuckGo），零依赖、无需 API Key

【📎 附件 / 媒体】
· 📎 附件：选图片/音频/视频文件随消息发送
· 图片自动转视觉输入（需模型支持识图，models.json 加 "vision": true）
· 消息里的 file:/// 链接或 C:\\ 裸盘符路径自动转附件（如从微信复制的图片路径）
· 附件自动分析：txt/md/csv 内联原文，docx/pdf 提取文本，zip/tar.gz 解压后可继续用工具操作
· 音视频附上路径，模型可用 ffmpeg/ffprobe 分析处理
· 聊天区内嵌显示：图片、GIF 动画、音频播放条、视频缩略图；
  双击图片或点「外部打开」调系统程序

【MCP 外部工具】
· 模型菜单 → 🔌 管理 MCP 服务器：添加 stdio JSON-RPC 服务器
· 「只读」标记的服务器工具免审批可缓存；未标记视为可写
· 工具名形如 mcp_服务器_工具，模型自动发现并调用

【缓存（提速+省 token）】
· 模型菜单 → ⚡ 管理缓存：SQLite / 内存后端
· 重复请求秒回，不消耗 token
· 底部统计栏：token 用量、缓存命中率、秒回次数（点击统计栏可清零）

【代码索引】
· 模型菜单 → 🗂 重建代码索引
· 让 index_search 按相关度检索代码，回答「XX 在哪实现」类问题

【语音】
· 🎤 语音输入：按下按钮录音，松开识别（按住说话）；轻点一下自动检测停顿（静音 1.5 秒结束）

【快捷键】
· 回车：发送 / 审批弹窗中=允许
· Esc：任务运行中=停止；审批弹窗中=拒绝
""",
    },
    "msg.index_done": {"en": "Index complete: {files} files / {chunks} chunks ({sec}s)",
                       "zh": "索引完成：{files} 文件 / {chunks} 代码块（{sec}s）"},
    "msg.indexing":   {"en": "🗂 Building index…", "zh": "🗂 建索引中…"},
    "msg.index_fail": {"en": "Index failed: {err}", "zh": "索引失败：{err}"},
    "msg.file":       {"en": "File", "zh": "文件"},
    "msg.attached":   {"en": "📎 Attached {n} file(s) ({kinds}), sent with next message",
                       "zh": "📎 已附加 {n} 个（{kinds}），随下条消息发送"},
    "tag.file":       {"en": "[File] {path}", "zh": "[文件] {path}"},
    "stat.tokens":  {"en": "Tokens", "zh": "Tokens"},
    "stat.in":      {"en": "input", "zh": "输入"},
    "stat.out":     {"en": "output", "zh": "输出"},
    "stat.think":   {"en": "Think", "zh": "思考"},
    "stat.cache":   {"en": "Cache hits", "zh": "缓存命中"},
    "stat.req":     {"en": "Requests", "zh": "请求"},
    "stat.fast":    {"en": "Fast replies", "zh": "秒回"},
    "stat.save_tk": {"en": "saves ~{n}k tokens", "zh": "省~{n}tk"},

    # —— 工具返回渲染 ——
    "render.search_done": {"en": "🔎 Search done, {n} result(s)\n",
                           "zh": "🔎 搜索完成，共 {n} 条结果\n"},
    "render.json":    {"en": "🧾 Structured data (JSON)\n",
                       "zh": "🧾 结构化数据（JSON）\n"},

    # —— 状态栏 ——
    "st.model": {"en": "Model: {m}", "zh": "模型：{m}"},
    "st.perm":  {"en": "Permission: {m}", "zh": "权限：{m}"},
    "st.dir":   {"en": "Dir: {p}", "zh": "目录：{p}"},
    "st.dir_branch": {"en": "Dir: {p} · {b}", "zh": "目录：{p} · {b}"},

    # —— 文件/目录选择 ——
    "pick.dir":    {"en": "Choose working directory", "zh": "选择工作目录"},
    "pick.attach": {"en": "Choose attachments", "zh": "选择附件"},

    # —— 发送/门控 ——
    "ui.stop_btn":   {"en": "⏹ Stop", "zh": "⏹ 停止"},
    "ui.vision_hint": {"en": "(models marked \"vision\": true in models.json)",
                       "zh": "（models.json 中标记 vision: true 的模型）"},
    "ui.no_vision": {
        "en": "⛔ Current model {model} has no vision support; the image was not sent.\n"
              "Switch to a 👁 vision model in the model menu first: {names}, then resend.\n",
        "zh": "⛔ 当前模型 {model} 不支持识图，图片未发送。\n"
              "请先在模型菜单切换到 👁 识图模型：{names}，再重新发送。\n"},
    "ui.dispatch_vision_switch": {
        "en": "🔁 Smart routing: {on} has no vision → using {to} for this image.\n",
        "zh": "🔁 智排识图：当前模型 {on} 不识图，本次已切换到 {to}。\n"},
    "ui.dispatch_vision_status": {
        "en": "Smart routing: {model} (vision)",
        "zh": "智排识图：{model}（识图）"},
    # —— LSP 多语言智能提示 ——
    "lsp.warmed": {"en": "LSP smart completion prewarmed for: {langs}",
                   "zh": "已预热 LSP 智能提示：{langs}"},
    "lsp.first_diag": {"en": "LSP line {line}: {msg}",
                       "zh": "LSP 第{line}行：{msg}"},

    # —— 回复模型署名 / 会话载入恢复派发 ——
    "reply.model": {"en": "— by {model} —", "zh": "—— 由 {model} 处理 ——"},
    "sess.dispatch_restored": {
        "en": "Dispatch restored (brain {name} running).",
        "zh": "已随历史会话开启派发（本地大脑 {name} 运行中）。"},
    "sess.dispatch_fallback": {
        "en": "This session used dispatch, but the local brain is not running — replying with the default model.",
        "zh": "该会话原开启派发，但本地大脑未运行——回退非派发，用默认模型回复。"},

    # —— 模型派发设置面板 ——
    "model.dispatch":  {"en": "🔀 Model dispatch…", "zh": "🔀 模型派发…"},
    "dlg.dispatch":    {"en": "Model Dispatch", "zh": "模型派发"},
    "dispatch.master": {"en": "Enable model dispatch (call_model tool)",
                        "zh": "开启模型派发（call_model 工具）"},
    "dispatch.smart":  {"en": "Smart routing: auto-switch to a vision model for images",
                        "zh": "智排：识图预路由（带图自动切识图模型）"},
    "dispatch.brain":  {"en": "Local brain (dispatch_model)",
                        "zh": "本地大脑（dispatch_model）"},
    "dispatch.cloud":  {"en": "Cloud targets", "zh": "云端目标"},
    "dispatch.flash":  {"en": "Simple", "zh": "云端简单"},
    "dispatch.pro":    {"en": "Complex", "zh": "云端高性能"},
    "dispatch.vision": {"en": "Vision *", "zh": "云端识图（必选）"},
    "dispatch.none_local": {"en": "(no local models)", "zh": "（无本地模型）"},
    "dispatch.off":    {"en": "○ Dispatch disabled (master switch off)",
                        "zh": "○ 模型派发未开启（总开关关闭）"},
    "dispatch.no_brain": {"en": "⚠ No local brain selected — dispatch inactive",
                          "zh": "⚠ 未选择本地大脑，派发视为未开启"},
    "dispatch.active": {"en": "● Active: brain is running & healthy, call_model available",
                        "zh": "● 已生效：本地大脑运行中，call_model 工具可用"},
    "dispatch.inactive": {"en": "○ Not active: brain not running (start it in the model menu; never auto-started)",
                          "zh": "○ 未生效：本地大脑未运行（请在模型菜单手动启动，不会自动拉起）"},
    "dispatch.hint":   {"en": "Only local models already running are used; local models are serial "
                             "(starting one stops others). Text subtasks go to the cloud targets; "
                             "images are routed by smart routing (local vision first).",
                        "zh": "仅派发给已在运行的本地模型；本地模型串行互斥（启动一个会停掉其它）。"
                              "文本子任务派发给云端目标；识图走智排（本地识图优先，回退云端识图）。"},
    "dispatch.vision_required": {"en": "Cloud vision target is required.",
                                 "zh": "云端识图目标为必选项。"},
    "dispatch.no_vision_models": {"en": "(no vision models — set vision:true)",
                                  "zh": "（暂无识图模型，需 models.json 标记 vision:true）"},
    "dispatch.vision_not_vision": {
        "en": "⚠ {model} has no vision support; pick a 👁 model.",
        "zh": "⚠ {model} 不支持识图，请选择带 👁 的模型。"},
    "dispatch.brain_not_running_q": {
        "en": "Local brain {brain} is not running.\nSave anyway (dispatch stays inactive until you start it)?",
        "zh": "本地大脑 {brain} 未运行。\n仍要保存吗？（保存后派发仍视为未生效，直到手动启动该模型）"},
    "dispatch.brain_not_running": {
        "en": "⚠ Brain {brain} not running — dispatch inactive.",
        "zh": "⚠ 本地大脑 {brain} 未运行，派发视为未生效。"},
    "dispatch.saved":  {"en": "Dispatch settings saved.", "zh": "模型派发设置已保存。"},
    "dispatch.save_fail": {"en": "Save failed: {e}", "zh": "保存失败：{e}"},
    "dispatch.refresh": {"en": "Refresh", "zh": "刷新"},
    # —— 顶栏快捷开关 ——
    "dispatch.topbar.off": {"en": "🔀 Dispatch OFF", "zh": "🔀 派发：关"},
    # —— 量化产品：策略互转面板 ——
    "quant.topbar":    {"en": "📈 Quant", "zh": "📈 策略互转"},
    "quant.panel.title": {"en": "Strategy Transfer — JoinQuant ↔ PTrade",
                          "zh": "策略互转 — 聚宽 ↔ PTrade"},
    "quant.panel.title_fmt": {"en": "Strategy Transfer — {src} → {dst}",
                              "zh": "策略互转 — {src} → {dst}"},
    "quant.src":       {"en": "From:", "zh": "源平台："},
    "quant.dst":       {"en": "To:", "zh": "目标平台："},
    "quant.use_llm":   {"en": "LLM fallback (handwritten code)",
                        "zh": "LLM 兜底（手写策略）"},
    "quant.btn.translate": {"en": "Translate →", "zh": "互转 →"},
    "quant.btn.load_demo": {"en": "Load MA demo", "zh": "载入双均线示例"},
    "quant.btn.load_example": {"en": "Load selected", "zh": "载入所选示例"},
    "quant.btn.copy":  {"en": "Copy result", "zh": "复制结果"},
    "quant.copied":    {"en": "Result copied to clipboard.",
                        "zh": "结果已复制到剪贴板。"},
    "quant.example.ma": {"en": "MA Cross demo", "zh": "双均线示例"},
    "quant.example.etf": {"en": "Global ETF rotation", "zh": "全球宽基ETF轮动"},
    "quant.example.smallcap": {"en": "Early small-cap (clean)", "zh": "早小市值（干净版）"},
    "quant.report.idle": {"en": "Paste a strategy on the left, or load an example.",
                          "zh": "在左侧粘贴策略代码，或载入示例。"},
    "quant.report.empty": {"en": "Source code is empty.",
                           "zh": "源代码为空。"},
    "quant.report.same": {"en": "Source and target platform are the same.",
                          "zh": "源平台与目标平台相同。"},
    "quant.report.converting": {"en": "Converting…",
                                "zh": "正在转换…"},
    "quant.report.ok": {"en": "✅ Done: {name} — syntax & whitelist passed.",
                        "zh": "✅ 互转完成：{name}，语法与白名单校验通过。"},
    "quant.report.ok_llm": {"en": "✅ Done via LLM fallback: {name} — checks passed.",
                            "zh": "✅ LLM 兜底互转完成：{name}，校验通过。"},
    "quant.report.parse_fail": {
        "en": "❌ Structure not recognized: {e} — enable LLM fallback to continue.",
        "zh": "❌ 结构无法确定性解析：{e}——勾选「LLM 兜底」可继续。"},
    "quant.report.llm_running": {"en": "LLM parsing (RAG)…",
                                 "zh": "LLM 解析中（RAG 知识库）…"},
    "quant.report.demo_loaded": {"en": "Demo loaded. Click Translate →",
                                 "zh": "示例已载入，点击「互转 →」。"},
    "quant.report.etf_loaded": {"en": "ETF rotation example loaded (auto-converts across 4 platforms).",
                                "zh": "已载入 ETF 轮动示例（可四平台确定性互转）。"},
    "quant.report.smallcap_loaded": {"en": "Small-cap example loaded (JoinQuant source; needs LLM fallback to convert — not deterministic).",
                                     "zh": "已载入小市值示例（聚宽源码，互转需勾选「LLM 兜底」，不保证一致率）。"},
    "quant.qmt.label":   {"en": "QMT terminal:", "zh": "QMT 终端："},
    "quant.qmt.refresh": {"en": "Re-probe", "zh": "重新探活"},
    # —— 公司知识库（企业代码 RAG） ——
    "kb.topbar":         {"en": "📚 KB", "zh": "📚 知识库"},
    "kb.panel.title":    {"en": "Company Code Base (RAG)",
                          "zh": "公司知识库（企业代码 RAG）"},
    "kb.roots":          {"en": "Knowledge roots (code repos + docs):",
                          "zh": "知识根目录（代码仓库 + 文档）："},
    "kb.roots.add":      {"en": "+ Add dir", "zh": "+ 添加目录"},
    "kb.roots.del":      {"en": "Remove", "zh": "移除"},
    "kb.enabled":        {"en": "Enable knowledge base (kb_search tool)",
                          "zh": "启用知识库（提供 kb_search 工具）"},
    "kb.inject":         {"en": "Auto-inject retrieved context each turn (more tokens)",
                          "zh": "每次提问自动注入检索上下文（更耗 token）"},
    "kb.top_k":          {"en": "Top-k:", "zh": "返回条数："},
    "kb.embedding":      {"en": "Embedding model:", "zh": "embedding 模型："},
    "kb.embedding.none": {"en": "(TF-IDF only)", "zh": "（仅 TF-IDF）"},
    "kb.stats.idle":     {"en": "Add roots and click Build index.",
                          "zh": "添加根目录后点击「建立索引」。"},
    "kb.stats.empty":    {"en": "No index yet — add roots and build.",
                          "zh": "尚未建索引——添加根目录后建立。"},
    "kb.stats":          {"en": "Files: {files}  ·  Chunks: {chunks}\n{db}",
                          "zh": "文件数：{files}  ·  块数：{chunks}\n{db}"},
    "kb.building":       {"en": "Building index…", "zh": "正在建立索引…"},
    "kb.built":          {"en": "✅ Built: {files} files, {updated} updated ({mode}, {sec}s).",
                          "zh": "✅ 已建立：{files} 个文件，更新 {updated}（{mode}，{sec}s）。"},
    "kb.auto":           {"en": "Auto incremental refresh before each search",
                          "zh": "检索前自动增量刷新"},
    "kb.refresh":        {"en": "🔄 Incremental", "zh": "🔄 增量更新"},
    "kb.refreshed":      {"en": "✅ Incremental done: {updated} updated, {skipped} unchanged ({mode}, {sec}s).",
                          "zh": "✅ 增量更新完成：更新 {updated}、未变 {skipped}（{mode}，{sec}s）。"},
    "kb.need_roots":     {"en": "Add at least one knowledge root first.",
                          "zh": "请先添加至少一个知识根目录。"},
    "kb.saved":          {"en": "Knowledge base settings saved.",
                          "zh": "知识库设置已保存。"},
    "kb.test":           {"en": "Test query:", "zh": "测试查询："},
    "kb.test.run":       {"en": "Search", "zh": "检索"},
    "kb.test.none":      {"en": "No relevant result. Try another keyword.",
                          "zh": "未检索到相关内容，换个关键词试试。"},
    "dispatch.topbar.on_active": {"en": "🔀 Dispatch ●", "zh": "🔀 派发 ●"},
    "dispatch.topbar.on_inactive": {"en": "🔀 Dispatch ○", "zh": "🔀 派发 ○"},
    "dispatch.topbar.now_on_active": {
        "en": "Dispatch ON — brain {name} running, call_model available.",
        "zh": "模型派发已开启：本地大脑 {name} 运行中，call_model 可用。"},
    "dispatch.topbar.now_on_inactive": {
        "en": "Dispatch ON, but brain {name} is not running — inactive until you start it.",
        "zh": "派发已开启，但本地大脑 {name} 未运行——启动后才生效（不会自动拉起）。"},
    "dispatch.topbar.now_off": {"en": "Dispatch OFF.",
                                "zh": "模型派发已关闭。"},
    "dispatch.topbar.hint": {
        "en": "Click: toggle dispatch · Right-click: settings",
        "zh": "左键：开关派发 · 右键：派发设置"},
    # —— 派发守护（自动关掉） ——
    "dispatch.auto_off.brain": {
        "en": "🔁 Dispatch auto-OFF: local brain {name} is not running/healthy.",
        "zh": "🔁 模型派发已自动关闭：本地大脑 {name} 未运行或不健康。"},
    "dispatch.auto_off.cloud": {
        "en": "🔁 Dispatch auto-OFF: cloud targets unreachable: {models} (network/endpoint issue).",
        "zh": "🔁 模型派发已自动关闭：云端目标探测不通：{models}（网络或端点异常）。"},
    "ui.media_fail": {"en": "[Media display failed: {p} ({e})]",
                      "zh": "[媒体显示失败: {p}（{e}）]"},

    # —— 上下文模式（续上下文 / 独立提问） ——
    "ctx.keep":        {"en": "🔗 Keep context", "zh": "🔗 续上下文"},
    "ctx.standalone":  {"en": "⚡ Standalone", "zh": "⚡ 独立提问"},
    "ctx.keep_hint":   {"en": "Context kept: each message continues the session history",
                        "zh": "续上下文：每条消息延续会话历史"},
    "ctx.standalone_hint": {"en": "Standalone: each message is sent without history (saves tokens; replies still saved to the session)",
                            "zh": "独立提问：每条消息不带历史单独发送（省 token；回复仍存入会话）"},

    # —— 缓存管理 ——
    "cache.backend":  {"en": "Cache backend", "zh": "缓存后端"},
    "cache.auto":     {"en": "Auto (SQLite→memory)", "zh": "自动（SQLite→内存）"},
    "cache.memory":   {"en": "Memory only (not persisted)", "zh": "仅内存（不持久）"},
    "cache.info":     {"en": "Active: {b} (configured: {c})    Entries: {n}",
                       "zh": "当前生效：{b}（配置：{c}）    条目：{n}"},
    "cache.ttl":      {"en": "Cache TTLs (seconds, 0 = off)",
                       "zh": "缓存时长（秒，0 = 关闭该类缓存）"},
    "cache.llm_ttl":  {"en": "LLM replies", "zh": "LLM 回复"},
    "cache.tool_ttl": {"en": "Tool results", "zh": "工具结果"},
    "cache.cleared":  {"en": "Cache cleared", "zh": "缓存已清空"},
    "cache.clear_fail": {"en": "Clear failed", "zh": "清空失败"},
    "cache.saved":    {"en": "Cache saved: {b}", "zh": "缓存已保存：{b}"},
    "cache.ttl_int":  {"en": "TTLs must be integers", "zh": "TTL 必须是整数"},
    "cache.clear":    {"en": "Clear cache", "zh": "清空缓存"},

    # —— 模型管理 ——
    "mm.list_title":  {"en": "Configured models (double-click to use)",
                       "zh": "已配置的模型（双击选用）"},
    "mm.pick_first":  {"en": "Select a model in the list first",
                       "zh": "请先在列表中选择一个模型"},
    "mm.del_title":   {"en": "Delete model", "zh": "删除模型"},
    "mm.del_confirm": {"en": "Delete model {name}?", "zh": "确定删除模型：{name}？"},
    "mm.deleted":     {"en": "Deleted model: {name}", "zh": "已删除模型：{name}"},
    "mm.del_missing": {"en": "Delete failed: model not found", "zh": "删除失败：未找到该模型"},
    "mm.add":         {"en": "＋ Add", "zh": "＋ 添加"},
    "mm.edit":        {"en": "✏ Edit", "zh": "✏ 编辑"},
    "mm.delete":      {"en": "🗑 Delete", "zh": "🗑 删除"},
    # —— 两栏：providers / models ——
    "mm.providers":            {"en": "Providers",          "zh": "服务提供商"},
    "mm.models":               {"en": "Models",             "zh": "模型"},
    "mm.add_provider":         {"en": "＋ Add provider",   "zh": "＋ 添加 Provider"},
    "mm.edit_provider":        {"en": "✏ Edit provider",    "zh": "✏ 编辑 Provider"},
    "mm.rename_provider":      {"en": "✏ Edit provider",    "zh": "✏ 编辑 Provider"},
    "mm.del_provider":         {"en": "🗑 Delete provider", "zh": "🗑 删除 Provider"},
    "mm.col_ctx":              {"en": "Context",  "zh": "上下文"},
    "mm.col_out":              {"en": "Max out",  "zh": "最大输出"},
    "mm.use":                  {"en": "✓ Use this model",  "zh": "✓ 选用此模型"},
    "mm.in_use":               {"en": "✓ In use",          "zh": "✓ 使用中"},
    "mm.pick_provider":        {"en": "Select a provider on the left first",
                                "zh": "请先在左侧选择一个 Provider"},
    "mm.pick_model":           {"en": "Select a model on the right first",
                                "zh": "请先在右侧选择一个模型"},
    "mm.provider_current":     {"en": "✓ current", "zh": "✓ 当前"},
    # —— 添加 / 重命名 provider 对话框 ——
    "dlg.add_provider":        {"en": "Add provider",       "zh": "添加 Provider"},
    "dlg.edit_provider":       {"en": "Edit provider — {id}",
                                "zh": "编辑 Provider — {id}"},
    "dlg.rename_provider":     {"en": "Edit provider — {id}",
                                "zh": "编辑 Provider — {id}"},
    "add_provider.id":         {"en": "Provider id (a-z, 0-9, _, -)",
                                "zh": "Provider id（小写字母、数字、_、-）"},
    "add_provider.id_hint":    {"en": "Lowercase letters, digits, _ or -; must be unique",
                                "zh": "小写字母、数字、_ 或 -；不能与现有重复"},
    "add_provider.name":       {"en": "Display name", "zh": "显示名"},
    "add_provider.name_hint":  {"en": "Shown in dropdowns (must be unique)",
                                "zh": "下拉里显示的名字（不能与现有重复）"},
    "add_provider.base_url":   {"en": "API endpoint base_url (optional)",
                                "zh": "API 端点 base_url（可后填）"},
    "add_provider.api_key":    {"en": "API Key (blank for local)",
                                "zh": "API Key（本地可留空）"},
    "add_provider.api_type":   {"en": "API type", "zh": "API 类型"},
    "add_provider.done":       {"en": "Added provider: {name}", "zh": "已添加 Provider：{name}"},
    "add_provider.fail":       {"en": "Add provider failed: {e}",
                                "zh": "添加 Provider 失败：{e}"},
    "rename_provider.new":     {"en": "New display name", "zh": "新显示名"},
    "rename_provider.dup":     {"en": "Another provider already uses this name",
                                "zh": "已有 Provider 使用该名称"},
    "rename_provider.empty":   {"en": "Name cannot be empty", "zh": "名称不能为空"},
    "rename_provider.missing": {"en": "Provider not found: {id}",
                                "zh": "未找到 Provider：{id}"},
    "rename_provider.done":    {"en": "Renamed: {name}", "zh": "已重命名为：{name}"},
    "edit_provider.done":      {"en": "Provider updated: {name}",
                                "zh": "已更新 Provider：{name}"},
    "rename_provider.fail":    {"en": "Rename failed: {e}", "zh": "重命名失败：{e}"},
    "del_provider.confirm":    {"en": "Delete provider {name} and its {n} model(s)?",
                                "zh": "删除 Provider {name} 及其 {n} 个模型？"},
    "del_provider.deleted":    {"en": "Deleted provider: {name}",
                                "zh": "已删除 Provider：{name}"},
    "del_provider.missing":    {"en": "Provider not found: {id}",
                                "zh": "未找到 Provider：{id}"},
    "add.base_first": {"en": "Fill in the endpoint base_url first", "zh": "请先填端点 base_url"},
    "add.fetching":   {"en": "🔍 Fetching model list…", "zh": "🔍 正在拉取模型列表…"},
    "edit.fetching":  {"en": "🔍 Fetching model list…", "zh": "🔍 正在获取模型列表…"},
    "fetch.fail":     {"en": "Fetch failed: {e}", "zh": "获取失败：{e}"},
    "add.filled":     {"en": "✔ Filled in {n} model(s)", "zh": "✔ 已填入 {n} 个模型"},
    "add.got":        {"en": "✔ Fetched {n} model(s)", "zh": "✔ 已获取 {n} 个模型"},
    "add.got_new":    {"en": " ({a} new added to dropdown)", "zh": "（新增 {a} 已入下拉）"},
    "add.pick_hint":  {"en": "Click a model → fills the \"Model ID\" field",
                       "zh": "点击一个模型 → 填入\"模型 ID\"字段"},
    "add.fill_id":    {"en": "Fill model ID", "zh": "填入模型 ID"},
    "add.fail":       {"en": "Add failed: {e}", "zh": "添加失败：{e}"},
    "edit.missing":   {"en": "Update failed: model not found", "zh": "修改失败：未找到该模型"},
    "edit.fail":      {"en": "Update failed: {e}", "zh": "修改失败：{e}"},
    "probe.found":    {"en": "🔍 Discovered {n} new model(s), added to dropdown",
                       "zh": "🔍 已探测到 {n} 个新模型，已加入下拉"},
    "probe.working":  {"en": "🔍 Probing endpoint models… reopen the dropdown shortly to see all",
                       "zh": "🔍 正在探测端点模型…，稍后重开下拉即可看到全部"},
    "fetch.e.empty":  {"en": "Endpoint base_url is empty", "zh": "端点 base_url 为空"},
    "fetch.e.nodata": {"en": "Response has no models (data empty)", "zh": "返回数据里没有模型（data 为空）"},
    "fetch.e.auth":   {"en": "Auth failed (HTTP {c}): check/fill the correct API Key",
                       "zh": "鉴权失败（HTTP {c}）：请检查/填写正确的 API Key"},
    "fetch.e.404":    {"en": "Endpoint not found (404): check whether base_url needs /v1",
                       "zh": "端点不存在（404）：请确认 base_url 是否带 /v1"},
    "fetch.e.server": {"en": "Endpoint server error (HTTP {c}): model service may not be running",
                       "zh": "端点服务器错误（HTTP {c}）：模型服务可能未启动"},
    "fetch.e.http":   {"en": "Request failed (HTTP {c}): {u}", "zh": "请求失败（HTTP {c}）：{u}"},

    # —— MCP 服务器管理 ——
    "mcp.ready":      {"en": "🔌 MCP: {n} external tools available",
                       "zh": "🔌 MCP：{n} 个外部工具可用"},
    "mcp.conn_fail":  {"en": "MCP connect failed: {e}", "zh": "MCP 连接失败：{e}"},
    "mcp.title":      {"en": "MCP servers", "zh": "MCP 服务器"},
    "mcp.enabled":    {"en": "enabled", "zh": "启用"},
    "mcp.disabled":   {"en": "disabled", "zh": "停用"},
    "mcp.readonly":   {"en": "read-only", "zh": "只读"},
    "mcp.writable":   {"en": "writable", "zh": "可写"},
    "mcp.col.name":    {"en": "Name", "zh": "名称"},
    "mcp.col.command": {"en": "Command (local)", "zh": "命令(本地)"},
    "mcp.col.url":     {"en": "URL (remote, preferred)", "zh": "URL(远程,优先)"},
    "mcp.col.headers": {"en": "Headers (JSON, opt.)", "zh": "请求头(JSON,可空)"},
    "mcp.col.args":    {"en": "Args (JSON array, opt.)", "zh": "参数(JSON数组,可空)"},
    "mcp.name_req":   {"en": "MCP: name required", "zh": "MCP：名称不能为空"},
    "mcp.cmd_req":    {"en": "MCP: fill in command or URL", "zh": "MCP：命令和 URL 至少填一个"},
    "mcp.json_req":   {"en": "MCP: args must be a JSON array; headers a JSON object",
                       "zh": "MCP：参数必须是 JSON 数组，请求头必须是 JSON 对象"},
    "mcp.saved":      {"en": "MCP server {name} saved (reconnect to apply)",
                       "zh": "MCP 服务器 {name} 已保存（重连后生效）"},
    "mcp.deleted":    {"en": "MCP server {name} deleted", "zh": "MCP 服务器 {name} 已删除"},
    "mcp.reconn":     {"en": "MCP reconnected: {n} tools", "zh": "MCP 重连完成：{n} 个工具"},
    "mcp.reconn_none": {"en": " (no usable server)", "zh": "（无可用服务器）"},
    "mcp.save":       {"en": "Save/Update", "zh": "保存/更新"},
    "mcp.toggle_en":  {"en": "Enable⇄Disable", "zh": "启用⇄停用"},
    "mcp.toggle_ro":  {"en": "Read-only⇄Writable", "zh": "只读⇄可写"},
    "mcp.reconnect":  {"en": "🔄 Reconnect all", "zh": "🔄 重连全部"},
    "mcp.hint":       {"en": "Example: name echo, command python3, args "
                            "[\"examples/mcp_echo_server.py\"]; click \"Reconnect all\" after saving",
                       "zh": "示例：名称 echo，命令 python3，参数 "
                            "[\"examples/mcp_echo_server.py\"]；保存后点「重连全部」生效"},

    # —— 会话管理 ——
    "sess.ws_header": {"en": "── Sessions in this dir ({ws}) ──", "zh": "── 当前目录会话（{ws}）──"},
    "sess.none":      {"en": "(no sessions in this dir)", "zh": "（本目录暂无会话）"},
    "sess.search":    {"en": "🔍 Search all sessions…", "zh": "🔍 搜索全部会话…"},
    "sess.all":       {"en": "📋 All sessions (across dirs)…", "zh": "📋 全部会话（跨目录）…"},
    "sess.del_cur":   {"en": "🗑 Delete current session", "zh": "🗑 删除当前会话"},
    "sess.search_title": {"en": "Search sessions", "zh": "搜索会话"},
    "sess.btn_search": {"en": "Search", "zh": "搜索"},
    "sess.unknown_ws": {"en": "(unknown dir)", "zh": "(未知目录)"},
    "sess.ungrouped": {"en": "Ungrouped", "zh": "未分组"},
    "sess.workspace": {"en": "Workspace", "zh": "工作区"},
    "panel.files":    {"en": "Files", "zh": "文件"},
    "file.search":    {"en": "Search by filename…", "zh": "按文件名搜索…"},
    "file.add_chat":  {"en": "Add to conversation", "zh": "添加到对话"},
    "file.add_code_chat": {"en": "Add selection to chat", "zh": "加入聊天"},
    "file.add_chat_short": {"en": "➕ Chat", "zh": "➕ 对话"},
    "file.open":    {"en": "Open", "zh": "打开"},
    "file.delete":  {"en": "Delete", "zh": "删除"},
    "file.deleted": {"en": "Deleted: {p}", "zh": "已删除：{p}"},
    "q.empty":      {"en": "Queued messages (Ctrl+Enter sends all)", "zh": "排队消息（Ctrl+Enter 发送全部）"},
    "q.queue":      {"en": "🕐 Queue", "zh": "🕐 排队"},
    "q.unknown":    {"en": "Unknown command: {c}", "zh": "未知命令：{c}"},
    "ui.dispatch_complex_switch": {"en": "Complex task → routed to {to} (was {on})", "zh": "复杂任务 → 已切到 {to}（原：{on}）"},
    "ui.dispatch_complex_status": {"en": "Routed complex task to {model}", "zh": "复杂任务已路由到 {model}"},
    "route.auto":   {"en": "🤖 Auto route", "zh": "🤖 自动"},
    "route.cloud":  {"en": "☁ Cloud", "zh": "☁ 云端"},
    "route.status": {"en": "Routing: {mode}", "zh": "路由模式：{mode}"},
    "quant.llm_model": {"en": "LLM model:", "zh": "LLM 模型："},
    "todo.title":    {"en": "Task steps", "zh": "任务步骤"},
    "todo.processing":{"en": "Processing…", "zh": "处理中…"},
    "todo.updated":  {"en": "Updated {p}", "zh": "已更新 {p}"},
    "q.fail":       {"en": "Command failed: {e}", "zh": "命令执行失败：{e}"},
    "cmd.help":     {"en": "Open help", "zh": "打开帮助"},
    "cmd.new":      {"en": "New session", "zh": "新建会话"},
    "cmd.clear":    {"en": "Clear chat (keep session)", "zh": "清空聊天区（不删会话）"},
    "cmd.permission": {"en": "Set permission (readonly/ask/always)", "zh": "设置权限模式 (readonly/ask/always)"},
    "cmd.context":  {"en": "Set context (keep/standalone)", "zh": "设置上下文 (keep/standalone)"},
    "cmd.reasoning": {"en": "Set reasoning (low/medium/high/xhigh/max)", "zh": "设置思考等级 (low/medium/high/xhigh/max)"},
    "cmd.model":    {"en": "Switch model", "zh": "切换模型"},
    "cmd.dir":      {"en": "Change working directory", "zh": "切换工作目录"},
    "cmd.index":    {"en": "Rebuild code index", "zh": "重建代码索引"},
    "cmd.cache":    {"en": "Manage cache", "zh": "管理缓存"},
    "cmd.mcp":      {"en": "Manage MCP servers", "zh": "管理 MCP 服务器"},
    "cmd.sessions": {"en": "Search/list sessions", "zh": "会话搜索/全部"},
    "cmd.delete":   {"en": "Delete current session", "zh": "删除当前会话"},
    "cmd.refresh":  {"en": "Refresh files/sessions/models", "zh": "刷新文件/会话/模型"},
    "cmd.compact":  {"en": "Compact context", "zh": "压缩上下文"},
    "cmd.novel":    {"en": "Write a novel: workbench (auto-director)",
                     "zh": "写小说：开书工作台（自动导演整本生产）"},
    "novel.title":  {"en": "Novel Workbench", "zh": "开书工作台"},
    "novel.tab.new": {"en": "New Book", "zh": "开书"},
    "novel.tab.run": {"en": "Run", "zh": "运行"},
    "novel.tab.tools": {"en": "Tools", "zh": "衍生"},
    "novel.idea":   {"en": "One-line idea", "zh": "一句灵感"},
    "novel.chapters": {"en": "Chapters (1-12)", "zh": "章数 (1-12)"},
    "novel.stepwise": {"en": "Pause after planning stages", "zh": "规划完成后暂停确认"},
    "novel.style":  {"en": "Style reference (optional)", "zh": "写法参考（可选，来自拆书）"},
    "novel.start":  {"en": "Start auto-director", "zh": "开书（自动导演）"},
    "novel.rag_local": {"en": "memory fallback", "zh": "内存降级（配 LAS_QDRANT_URL 启用持久库）"},
    "novel.img_off": {"en": "not configured", "zh": "未配置（配 LAS_IMAGE_* 启用漫画/形象图）"},
    "novel.pick_pipeline": {"en": "Pipeline", "zh": "流水线"},
    "novel.refresh": {"en": "⟳", "zh": "⟳"},
    "novel.continue": {"en": "▶ Continue", "zh": "▶ 继续"},
    "novel.stop":   {"en": "⏹ Stop", "zh": "⏹ 停止"},
    "novel.open_book": {"en": "📖 Open manuscript", "zh": "📖 打开书稿"},
    "novel.stage_status": {"en": "Stages", "zh": "阶段状态"},
    "novel.debts":  {"en": "Quality debts", "zh": "质量债"},
    "novel.need_idea": {"en": "Write the idea first", "zh": "请先填写一句灵感"},
    "novel.need_model": {"en": "No model configured", "zh": "未配置模型，请先在模型菜单选择"},
    "novel.none":   {"en": "No pipelines yet", "zh": "还没有流水线记录"},
    "novel.no_book": {"en": "Manuscript not found", "zh": "书稿文件不存在"},
    "novel.no_chapters": {"en": "No finished chapters yet", "zh": "还没有已完成的章节"},
    "novel.busy":   {"en": "Pipeline already running", "zh": "已有流水线在运行"},
    "novel.stopped": {"en": "⏹ Stop requested", "zh": "⏹ 已请求停止，当前章完成后暂停"},
    "novel.stage":  {"en": "Stage: {label}", "zh": "阶段：{label}"},
    "novel.chapter": {"en": "📖 Ch.{n}《{t}》done ({w} chars)", "zh": "📖 第 {n} 章《{t}》完成（{w} 字）"},
    "novel.debt":   {"en": "Chapter issue: {e}", "zh": "章节问题（质量债）：{e}"},
    "novel.done_msg": {"en": "✅ Done. Manuscript: {file}", "zh": "✅ 整本完成，书稿：{file}"},
    "novel.paused_msg": {"en": "⏸ Paused. Click Continue to resume", "zh": "⏸ 已暂停，点「继续」恢复"},
    "novel.failed_msg": {"en": "❌ Failed: {e}", "zh": "❌ 失败：{e}"},
    "novel.deconstruct": {"en": "Deconstruct a book (txt → report + style features)", "zh": "拆书（文本 → 题材/结构/人物/写法特征报告）"},
    "novel.pick_file": {"en": "Pick a text file", "zh": "选择文本文件"},
    "novel.deconstruct_done": {"en": "✅ Deconstruct report: {file}", "zh": "✅ 拆书报告已生成：{file}"},
    "novel.drama":  {"en": "Short-drama adaptation (chapters → script + shots)", "zh": "短剧改编（章节 → 剧本 + 分镜）"},
    "novel.drama_range": {"en": "Chapter range", "zh": "章节范围"},
    "novel.drama_go": {"en": "Adapt", "zh": "改编"},
    "novel.drama_ch": {"en": "🎬 Ch.{n} adapted", "zh": "🎬 第 {n} 章剧本完成"},
    "novel.drama_done": {"en": "✅ Drama script: {file}", "zh": "✅ 短剧剧本：{file}"},
    "cmd.undo":     {"en": "Undo last file overwrite (checkpoint)", "zh": "回滚最近一次文件覆盖（检查点）"},
    "cmd.init":     {"en": "Analyze workspace & create AGENTS.md", "zh": "分析项目并生成 AGENTS.md"},
    "cmd.brainstorm": {"en": "Brainstorm ideas for a topic (/brainstorm 主题)",
                       "zh": "头脑风暴（/brainstorm 主题）"},
    "cmd.plan":     {"en": "Make an execution plan, no code changes (/plan 任务)",
                     "zh": "制定执行计划，不改代码（/plan 任务）"},
    "cmd.work":     {"en": "Execute the latest plan step by step (/work)",
                     "zh": "按计划逐步执行（/work）"},
    "cmd.loop":     {"en": "Work in a loop until done & verified (/loop 任务)",
                     "zh": "循环执行直到完成且验证通过（/loop 任务）"},
    "cmd.compress": {"en": "Compress session history (/compress)",
                     "zh": "压缩会话历史（/compress）"},
    "q.need_arg":   {"en": "Fill in the task after the command, then send",
                     "zh": "请在命令后补全任务描述，再发送"},
    "compress.short":  {"en": "Session too short to compress", "zh": "会话较短，无需压缩"},
    "compress.working": {"en": "🧹 Compressing session…", "zh": "🧹 正在压缩会话…"},
    "compress.done":   {"en": "🧹 Session compressed: {before} → {after} tokens",
                        "zh": "🧹 会话已压缩：{before} → {after} tokens"},
    "compress.fail":   {"en": "Compress failed: {e}", "zh": "压缩失败：{e}"},
    "compress.prompt": {
        "en": "Summarize the conversation below into a coherent brief. Keep: all user requests "
              "and intents, decisions made, important file/code references, unfinished items. "
              "Use bullet points, stay under 600 words, no commentary.",
        "zh": "请把下面的对话历史压缩成一份连贯摘要，必须保留：用户的全部请求与意图、"
              "已做出的决定、重要文件/代码引用、未完成事项。用要点列出，控制在 600 字以内，"
              "不要附加评论。",
    },
    "compress.header": {"en": "[Summary of earlier conversation]\n",
                        "zh": "【此前会话的摘要】\n"},
    "compress.ack":    {"en": "OK, continuing from the summary above.",
                        "zh": "好的，我已根据摘要恢复上下文，请继续。"},
    "help.cmds_title": {"en": "Slash commands (type / in the input box):",
                        "zh": "斜杠命令（在输入框输入 / 触发）："},
    "help.copyright_title": {"en": "© Developer / Copyright", "zh": "© 开发者 / 版权"},
    "help.copyright": {"en": "Developer: 王海滨 (Wang Haibin)\n"
                             "Email: tbz@qq.com\n"
                             "QQ: 574574\n"
                             "WeChat: ningboyihao",
                       "zh": "开发者：王海滨（Wang Haibin）\n"
                             "邮箱：tbz@qq.com\n"
                             "QQ：574574\n"
                             "微信：ningboyihao"},
    "file.rename":     {"en": "Rename", "zh": "重命名"},
    "file.rename_to":  {"en": "Rename \"old\" to:", "zh": "把「old」重命名为："},
    "file.exists":     {"en": "Target name already exists", "zh": "目标名称已存在"},
    "file.renamed":    {"en": "Renamed: {old} → {new}", "zh": "已重命名：{old} → {new}"},
    "file.open_dir":   {"en": "Open in file manager", "zh": "在资源管理器中打开"},
    "file.dir_added":  {"en": "Directory reference inserted: {rel}/",
                        "zh": "已插入目录引用：{rel}/"},
    "file.preview":   {"en": "Preview", "zh": "预览"},
    "file.edit":      {"en": "Edit", "zh": "编辑"},
    "time.now":      {"en": "now", "zh": "刚刚"},
    "time.min":      {"en": "{n}m", "zh": "{n}分钟"},
    "time.hr":       {"en": "{n}h", "zh": "{n}小时"},
    "time.day":      {"en": "{n}d", "zh": "{n}天"},
    "sess.search_hint": {"en": "Type a keyword and press Enter; double-click a result to open (auto-switches to its dir)",
                         "zh": "输入关键词回车搜索；双击结果打开会话（自动切到原目录）"},
    "sess.all_title": {"en": "All sessions", "zh": "全部会话"},
    "sess.all_hint":  {"en": "Double-click to open a session (auto-switches to its dir)",
                       "zh": "双击打开会话（自动切到原目录）"},
    "sess.new":       {"en": "New session", "zh": "新会话"},
    "sess.started":   {"en": "New session started", "zh": "已开始新会话"},
    "sess.load_fail": {"en": "Failed to load session", "zh": "会话读取失败"},
    "sess.dir_switch": {"en": "Switched to the session's dir: {ws}", "zh": "目录已切到会话所属：{ws}"},
    "sess.you":       {"en": "You: {t}", "zh": "你：{t}"},
    "sess.n_imgs":    {"en": "  🖼 [{n} image(s) in this message]", "zh": "  🖼 [本条含 {n} 张图片]"},
    "sess.loaded":    {"en": "Session loaded: {t}", "zh": "已载入会话：{t}"},
    "sess.del_btn":   {"en": "🗑 Delete selected", "zh": "🗑 删除选中"},
    "sess.del_title": {"en": "Delete session", "zh": "删除会话"},
    "sess.del_confirm": {"en": "Delete session \"{t}\"?", "zh": "确定删除会话「{t}」？"},
    "sess.deleted":   {"en": "Session deleted", "zh": "会话已删除"},
    "sess.rename":    {"en": "✏ Rename…", "zh": "✏ 重命名…"},
    "sess.rename_title": {"en": "Rename session", "zh": "重命名会话"},
    "sess.rename_prompt": {"en": "New title:", "zh": "新标题："},
    "sess.renamed":   {"en": "Session renamed: {t}", "zh": "会话已重命名：{t}"},
    "sess.del_group": {"en": "🗑 Delete all {n} sessions here",
                       "zh": "🗑 删除此工作区全部会话（{n} 条）"},
    "sess.del_group_confirm": {"en": "Delete ALL {n} sessions in workspace \"{ws}\"?\nThis cannot be undone.",
                               "zh": "确定删除工作区「{ws}」下的全部 {n} 条会话？\n删除后不可恢复。"},

    # —— 语音 ——
    "v.recording":    {"en": "● Recording…", "zh": "● 录音中…"},
    "v.press_hint":   {"en": "🎤 Recording — release to transcribe; quick tap for auto-stop",
                       "zh": "🎤 录音中——松开即识别；轻点一下切换自动停顿"},
    "v.start_fail":   {"en": "Cannot start recording: {e}", "zh": "无法启动录音：{e}"},
    "v.transcribing": {"en": "Transcribing…", "zh": "识别中…"},
    "v.no_sound":     {"en": "No sound recorded", "zh": "未录到声音"},
    "v.no_speech":    {"en": "No speech detected", "zh": "未识别到语音"},
    "v.got":          {"en": "Recognized: {t}", "zh": "识别：{t}"},
    "v.fail":         {"en": "Speech recognition failed", "zh": "语音识别失败"},
    "v.err":          {"en": "❌ Speech recognition failed: {e}", "zh": "❌ 语音识别失败: {e}"},
    "v.vad_hint":     {"en": "🎤 Recording, please speak (auto-stops after 1.5s of silence)…",
                       "zh": "🎤 录音中，请说话（静音 1.5 秒自动结束）…"},

    # —— 模式命令的注入提示词（/init /brainstorm /plan /work /loop） ——
    "init.prompt": {
        "en": "Analyze the project in the current working directory and create an AGENTS.md "
              "at the workspace root (use write_file) so future AI assistants can get up to speed. "
              "1) Investigate first with list_dir/read_file: directory layout, README/config files, "
              "build/test/run commands, key modules and responsibilities; "
              "2) AGENTS.md must cover: project overview, common commands, architecture overview, "
              "conventions & gotchas; keep it under 100 lines; only verified facts, no invention; "
              "3) Register your steps with task_plan first; "
              "4) After writing, spot-check with read_file.",
        "zh": "请分析当前工作目录的项目，并用 write_file 在工作区根目录生成 AGENTS.md，"
              "供后续 AI 助手快速了解本项目。要求："
              "1) 先用 list_dir/read_file 调查：目录结构、README/配置文件、构建/测试/运行命令、"
              "关键模块与职责；"
              "2) AGENTS.md 覆盖：项目概述、常用命令、架构概览（核心模块及职责）、代码约定与注意事项；"
              "控制在 100 行以内；只写有真实依据的信息，不要编造；"
              "3) 先用 task_plan 登记调查与写作步骤；"
              "4) 写完后用 read_file 抽查确认。",
    },
    "brainstorm.prompt": {
        "en": "Enter BRAINSTORM mode for the topic below. Do NOT write or modify any files. "
              "Produce 3-5 distinctly different ideas/approaches; for each: core idea, pros, "
              "risks/costs, best-fit scenario. End with your recommendation + reasoning, and "
              "1-2 clarifying questions about key unknowns. Topic:\n{arg}",
        "zh": "进入头脑风暴模式：针对下面的主题给出 3~5 个明显不同的方案/创意。"
              "不要写代码、不要改任何文件。每个方案说明：核心思路、优点、风险/代价、适用场景。"
              "最后给出你的推荐与理由，并向用户提出 1~2 个澄清关键未知点的问题。主题：\n{arg}",
    },
    "plan.prompt": {
        "en": "Enter PLAN mode for the task below: investigate with read-only tools, then produce a "
              "detailed execution plan — do NOT modify any files. Requirements: 1) investigate relevant "
              "code first; 2) step-by-step plan: for each step state which files change, what to do, "
              "how to verify; 3) call task_plan to register the steps; 4) list risks and rollback "
              "points; 5) end with 'plan ready — confirm or run /work'. Task:\n{arg}",
        "zh": "进入计划模式：针对下面的任务制定详细执行计划，但不要修改任何文件。要求："
              "1) 先用只读工具调查相关代码/文件；2) 给出分步计划：每步写清楚改哪些文件、做什么、"
              "如何验证；3) 调用 task_plan 把步骤登记为任务清单；4) 指出风险与回滚点；"
              "5) 结尾注明『计划完成，可直接确认或用 /work 执行』。任务：\n{arg}",
    },
    "work.prompt": {
        "en": "Enter WORK mode: execute the most recent plan in this session step by step "
              "(if a new task is given below, plan it with task_plan first, then execute). "
              "Each step: state what you do → implement with tools → verify with tests/"
              "lsp_diagnostics/run; update task_plan after each step; if a step fails, fix and "
              "retry instead of skipping; only finish when all steps pass verification. "
              "Task (optional):\n{arg}",
        "zh": "进入执行模式：按本会话最近的计划逐步执行（下面给了新任务则先用 task_plan 规划再执行）。"
              "每一步：先说明做什么 → 用工具实施 → 用测试/lsp_diagnostics/运行验证；"
              "每完成一步调用 task_plan 更新状态；某步失败就修复后重试，不许跳过；"
              "全部步骤验证通过后才给最终总结。任务（可选）：\n{arg}",
    },
    "loop.prompt": {
        "en": "Enter AUTO-LOOP mode for the task below: keep running an implement→verify→fix loop "
              "until ALL verification passes. 1) register the plan with task_plan; 2) implement each "
              "step and verify immediately (tests/diagnostics/run); 3) on failure, fix and retry — "
              "never skip or declare partial completion; 4) do not pause to ask questions — make "
              "reasonable assumptions and record them; 5) when everything passes, output the final "
              "summary with verification evidence. Task:\n{arg}",
        "zh": "进入自动循环模式：对下面的任务持续执行『实现 → 验证 → 修复』循环，直到全部验证通过"
              "才算完成。要求：1) 先用 task_plan 建立计划；2) 逐项实现并立即验证（测试/诊断/运行）；"
              "3) 验证失败必须修复后重试，禁止跳过或宣告部分完成；4) 不要中途向用户提问——做出"
              "合理假设并记录；5) 全部通过后输出最终总结与验证证据。任务：\n{arg}",
    },
}


class _I18n:
    def __init__(self):
        self._lang = DEFAULT_LANG

    def get_lang(self) -> str:
        return self._lang

    def set_lang(self, lang: str | None):
        self._lang = "zh" if str(lang or "").lower() == "zh" else "en"
        try:
            config.set_language(self._lang)
        except Exception:                # noqa: BLE001  配置写入失败不影响界面
            pass

    def load_lang(self):
        try:
            self._lang = config.get_language()
        except Exception:                # noqa: BLE001
            self._lang = DEFAULT_LANG

    def t(self, key: str, **kw) -> str:
        e = STRINGS.get(key)
        if not e:
            return key
        s = e.get(self._lang) or e.get("en") or key
        return s.format(**kw) if kw else s


_I = _I18n()


def get_lang() -> str:
    return _I.get_lang()


def set_lang(lang):
    _I.set_lang(lang)


def load_lang():
    _I.load_lang()


def t(key: str, **kw) -> str:
    return _I.t(key, **kw)
