# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Local AI Studio (formerly WellFuture Coder) — a local coding assistant with a Tkinter GUI, a local Qwen3.8-27B
backend (or any OpenAI-compatible endpoint), and streaming function-calling. The
model can call built-in tools (`read_file`, `write_file`, `grep_search`, `run_shell`,
`web_search`, …) and MCP tools to complete coding tasks. Chinese UI, Chinese
comments/docstrings throughout; English identifiers.

## Commands

The project requires **Python 3.12+** (main.py enforces it). On this Windows
machine the dev venv is `D:\A-local-coding\.venv` (Python 3.12, built from the
`py312` conda env of `D:\miniconda3`) — use `.venv\Scripts\python` for
everything below; the system `python` is older and will refuse to run.

```bash
.venv/Scripts/python main.py              # run the app (main.py → ui.launch())
.venv/Scripts/python -m pip install -r requirements.txt   # optional — voice input only
.venv/Scripts/python examples/mcp_echo_server.py   # sample stdio MCP server (echo/calc/image tools)
.venv/Scripts/python -m py_compile *.py   # fast syntax check of all modules
```

Testing & CI:

```bash
.venv/Scripts/python -m pip install -r requirements-dev.txt   # pytest
.venv/Scripts/python -m pytest tests/ -q    # unit tests (mock LLM transport, isolated HOME/APPDATA)
```

`.github/workflows/test.yml` runs py_compile + pytest on a matrix of
ubuntu/windows/macos × Python 3.12 on every push/PR.

Packaging (PyInstaller):

```bash
pyinstaller --onefile --windowed --name LocalAIStudio main.py
pyinstaller LocalAIStudio.spec      # preferred — the spec excludes torch/faster-whisper/onnx
                                    # so the AI heavy stack stays out of the bundle
```

There is **no linter/CI gate locally beyond the test suite** (`pyrightconfig.json`
is a minimal stub; nothing runs it automatically). Verify changes with
`python -m pytest tests/ -q` + `py_compile` and by running the app.

## Architecture

A flat module layout, all stdlib except the optional voice stack. No web framework,
no OpenAI/requests SDK — the LLM client and web search are hand-rolled on
`urllib.request`.

```
main.py ──► ui.launch() ──► App (Tkinter)
              │  spawns a daemon worker thread per message
              ▼
        agent.Agent.run()          # synchronous function-calling loop
              │
      ┌───────┼────────────────────────────┐
      ▼       ▼                            ▼
  llm.py   tools.py                    mcp.py
  (SSE     (8 built-in tools +         (MCP client: stdio subprocess
  stream)   executor + permission)      OR streamable HTTP; tools
                                        prefixed mcp_<server>_<tool>)
```

`localmodels.py` bridges the in-repo `gpulocal/` subdirectory (the local model
panel is now maintained inside this repo): it imports that panel's `MODELS`
registry by file path (mtime-cached, no UI side effects), starts/stops the same
cross-platform services via `svc_*` (serial: starting one model stops the
others), polls status, and syncs the registry into models.json as providers
`gpulocal-<port>` at App startup. Local models show in the model dropdown with a
live ●/◐/○ status dot plus start/stop/restart; a started model is auto-selected
once its `/v1/models` health check passes.

`weblinks.py` auto-fetches http(s) URLs pasted into the chat input
(background thread in `ui.py:send` → `_send_with`): `image/*` responses are
downloaded to media/ and appended as vision attachments (same vision gating
as file attachments); `text/html` pages are stripped to plain text and
inlined into the message body (capped at 6000 chars); other content types
are saved to media/ with a path note for the model's tools. Fetch failures
become annotation lines, never exceptions. Max 3 links per message.

`ui.py` is the Tk shell (chat, menus, media); its dialog panels were extracted
into `ui_panel_cache.py` / `ui_panel_models.py` / `ui_panel_mcp.py` /
`ui_panel_sessions.py` / `ui_panel_help.py` / `ui_panel_approval.py`. Each panel
module exposes `show(app)`-style entry points, imports `ui` lazily **inside
functions** (for current FONT_* globals and shared helpers like `_make_modal`),
and the `App` methods are thin delegates — call sites unchanged.

The loop (in `agent.py:run`): stream a chat request with tool schemas → if the model
returns `tool_calls`, approve (ask mode) → execute each tool → feed results back as
`tool` messages → repeat, up to `config.MAX_TOOL_ROUNDS`. `context.maybe_compact`
runs before each round. On a plain-text reply, the event list is cached.

Key facts that span multiple files:

- **Threading model** (`ui.py`): the Tkinter mainloop is single-threaded. Each send
  spawns a daemon `threading.Thread` that runs `Agent.run()` synchronously. UI
  updates from the worker must go through `root.after(0, ...)` / event callbacks —
  never touch widgets directly from the worker thread. `App._on_event` is the
  single sink for all agent events (text/reasoning/tool/media/usage).
- **Mutable singletons, now test-isolable**: `tools.WORKSPACE` (switchable cwd —
  use the `tools.push_workspace(path)` context manager for temporary switches),
  `cache` state (public `cache.reset()` resets settings/connections/memory store;
  cache paths derive from `config.CONFIG_DIR` at call time, so redirecting that
  one attribute fully isolates a test), and `mcp.get_manager()` /
  `mcp.reset_manager()` (one process-wide `MCPManager`, resettable).
  The workspace is restored from `state.json` at import time in `config.py`.
- **Config lives in the platform config dir**, not the repo: `~/.config/local-ai-studio/`
  on Linux/macOS, `%APPDATA%\local-ai-studio\` on Windows (single source:
  `config.CONFIG_DIR`; `cache.py`/`sessions.py`/`codeindex.py` all derive from it).
  Contents: `models.json`, `mcp.json`, `cache.json`, `state.json`,
  `sessions/*.json`, `index/<hash>.db`, `media/`. The repo-root `models.json` is only
  a seed; `config._ensure_models_file` copies it on first run and migrates the old
  config dirs of previous names (`~/.config/qwen-coder`, `wellfuture-coder`).
- **Models** are `provider_id/model_id` keys (`config.ModelConfig`, frozen dataclass).
  A provider = one base_url + api_key + N model IDs. `vision: true` on a model
  enables image attachments as multimodal content.
- **Caching** (`cache.py`) has two backends: SQLite (default, `auto` falls back
  to memory). LLM replies are cached by `sha256(model + messages + tool schemas)`; tool
  results only for read-only tools. The cache key uses the *request-time* message
  list — do not append the assistant reply before keying (see `agent.py` comment).
- **Context compaction** (`context.py`) is a progressive 3-stage shrink (truncate
  long tool results → strip old images → collapse middle rounds into one-line
  summaries), driven by `config.CONTEXT_BUDGET`. Token counting: exact
  `cl100k_base` via tiktoken when installed, otherwise a CJK-aware heuristic
  (CJK ≈ 1 token/char, ASCII ≈ 1 token/4 chars) — much closer than the old
  len//2 estimate, but still an estimate without tiktoken.
- **Sandbox guardrails** (`tools.py`, `config.SANDBOX`, on by default;
  `LAS_SANDBOX=off` disables): `write_file` may only write inside the workspace
  (`tools.path_in_workspace`), and `run_shell` rejects obviously destructive
  commands (`rm -rf /`, `mkfs`, fork bombs, disk format, shutdown — see
  `_BLOCKED_SHELL_PATTERNS`). This is a guardrail, not OS-level isolation.
- **MCP** (`mcp.py`) supports both stdio (subprocess, line-delimited JSON-RPC) and
  streamable HTTP (POST, JSON or SSE). Servers marked `readonly` in `mcp.json` are
  treated as read-only (no approval, cacheable); all others are "write" and require
  approval in `ask` mode. Image results are base64-decoded to `media/` and surfaced
  as `{"type": "media"}` events.
- **Permissions** (`agent.py` + `tools.py`): three modes — `readonly` (only read
  tools), `ask` (approve `write_file`/`run_shell` and non-readonly MCP tools via
  `on_approval`), `always`. `tools.is_write_tool` and `MCPManager.is_write_tool`
  are the two authorities.

## Conventions

- Chinese docstrings/comments; follow the existing style (module-level docstring
  explaining purpose, section-divider comment bars like `# ---------------- 标题`).
- Errors are returned as Chinese strings from tools (e.g. `"错误：文件不存在 …"`),
  not raised, so the model sees them as ordinary tool output. `llm.py`/`mcp.py` raise
  `LLMError`/`MCPError` for transport-level failures.
- Graceful degradation is a theme: Pillow, ffmpeg, audio players are all
  optional; code falls back when they're absent.
