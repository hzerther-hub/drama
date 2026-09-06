# AGENTS.md

## Quick Reference

- Run: `python main.py`（默认产品：短剧网文创作 novelwriter；Windows 用 Anaconda 的 python）
- Env: `LOCAL_AI_PRODUCT=quant python main.py` 或 `products/<name>/run.py`
- Tests: `python -m pytest tests/ -q`（~351 passed + 1 skipped；LLM mock，HOME/APPDATA 隔离）
- Syntax: `python -m py_compile *.py`
- Build: `python packaging/build.py [product] [--clean]`
- 窗口标题含 build 标记（如 `build 0906-3`）：多实例混用时先认标题再测试

## Architecture

```
main.py → ui.launch() → App (Tkinter mainloop)
   │ spawns one daemon worker thread per message
   ▼
agent.Agent.run()   # synchronous function-calling loop
   │
   ├─ llm.py         SSE streaming client: OpenAI 兼容 & Anthropic 双协议 (stdlib urllib)
   ├─ tools.py       内置工具（含 task_plan 计划工具）+ executor
   ├─ mcp.py          MCP stdio/HTTP client
   └─ context.py      Token budget + compaction

输入框键盘统一收口：`ui.py::_on_input_keypress`（KeyPress 阶段拦截）——
弹窗（@文件、/命令）打开时回车=确认候选、↑↓ 选择、Esc 关闭；
无弹窗时回车=发送、Shift+回车=换行、Ctrl+回车=排队。
IME 兼容：回车识别同时匹配 keysym(Return/KP_Enter) 与 char(\r/\n)。
```

## Key Files

| File | Purpose |
|------|---------|
| `ui.py` | Tkinter shell, ~5300 lines, panels in `ui_panel_*.py` |
| `ui_panel_models.py` | 模型管理（provider 优先两栏）+ @文件引用/命令弹窗共用组件 |
| `ui_panel_dispatch.py` `ui_panel_approval.py` `ui_panel_help.py` | 派发 / 审批条 / 帮助面板 |
| `agent.py` | Agent loop, permission modes, event emission, MCP routing |
| `tools.py` | Built-in tool executor, `is_write_tool` guard |
| `config.py` | ModelConfig（逐模型/逐 provider：`api_type` openai_compatible\|anthropic、`context_window`、`max_tokens`、`vision`、`reasoning`；provider 可重命名+唯一性校验）、`CONFIG_DIR` singleton |
| `mcp.py` | MCP manager, stdio + HTTP transport |
| `pipeline.py` | Stage-machine engine: checkpoints, resume, quality-debt policy |
| `novel_chain.py` | Novel production chain (outline→…→chapters, review/repair/feedback) |
| `vecstore.py` | Qdrant REST client + embedding + in-memory fallback |
| `imggen.py` | Image generation client (OpenAI-compatible images API) |
| `ui_panel_novel.py` | Novel workbench (pure Tkinter, 3 tabs) |
| `errlog.py` `checkpoints.py` `dircache.py` | Error log / write checkpoints / dir snapshot |
| `ui_input.py` | Input-box interaction (enter/@ // popups), extracted from ui.py |
| `docs/novel-setup.md` | novelwriter 外接工具安装与使用说明 |
| `codeindex.py` | Workspace TF-IDF index (`index_search` tool) |
| `codera.py` | Corporate KB RAG (`kb_search` tool) |
| `products/` | Product profiles; `quant/` has strategy IR |
| `tests/` | pytest suite (~351 tests, 25 files) |

## Conventions

- Python 3.12+ only; Chinese docstrings/comments; English identifiers
- Stdlib only in core; optional deps fall back gracefully
- UI updates from worker threads: `root.after(0, fn)` — never touch widgets directly
- Tool errors returned as Chinese strings (not raised) — LLM sees them as output
- Cache keys use *request-time* message list (don't append assistant reply before keying)
- `CONFIG_DIR` in `config.py` is the single source of truth for cache/session/codeindex paths
- 占位提示是悬浮 Label 覆盖层（`_setup_placeholder`）——绝不往输入缓冲里插占位文本
- 弹窗键盘在 `_on_input_keypress`（KeyPress 阶段 break）；`_popup_open_scan`/`_popup_rescan` 负责开/重建；改这部分先读 `docs/harness-notes.md`
- 状态栏 `_set_status` 显示在窗口右上角（就绪 旁边），2 秒后可能被徽标自动恢复
- `models.json` 存于 CONFIG_DIR；`gpulocal/localmodels.py` 已移除，遗留 `gpulocal-*` 条目可正常编辑删除

## Product Variants

- `devtool_local` (default) — devtool with local model support
- `devtool` — general developer tool
- `novelwriter` — novel writing assistant
- `quant` — quantitative strategy translation (JoinQuant↔PTrade↔gm↔QMT)
- `devrag` — corporate multi-root knowledge base

Set via `LOCAL_AI_PRODUCT` env var or by running `products/<name>/run.py`.