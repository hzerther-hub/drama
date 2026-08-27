# Repository Guidelines

> Local AI Studio — Python 3.12 Tkinter desktop app with OpenAI-compatible LLM backend, streaming function-calling, MCP integration, and 5 product variants.

## Project Overview

A local-first coding assistant: Tkinter GUI + OpenAI-compatible LLM backend with SSE streaming function-calling. One kernel, many products — `LOCAL_AI_PRODUCT` env or `products/<name>/run.py` selects the build variant (`devtool_local`, `devtool`, `novelwriter`, `quant`, `devrag`). The model calls built-in tools and MCP tools; the app runs fully offline (no cloud dependency).

## Architecture & Data Flow

```
main.py → ui.launch() → App (Tkinter mainloop)
   │  spawns one daemon worker thread per message
   ▼
agent.Agent.run()   # synchronous function-calling loop
   │
   ├─ llm.py         SSE streaming LLM client (stdlib urllib, no SDK)
   ├─ tools.py       Built-in tool executor (8 tools)
   ├─ mcp.py          MCP client (stdio subprocess or streamable HTTP)
   └─ context.py     Token budget + compaction
```

**Agent loop**: stream chat request → tool_calls? → approve (ask mode) → execute → feed results back → repeat up to `MAX_TOOL_ROUNDS` (12). Auto-falls back to cloud model if local GPU model is unavailable.

**Threading model**: Tkinter mainloop is single-threaded. Worker threads must never touch widgets directly — UI updates go through `root.after(0, fn)`.

**Two RAG systems**:
- `codeindex.py` — workspace TF-IDF index (tool `index_search`)
- `codera.py` — corporate multi-root knowledge base with optional embedding (tool `kb_search`)

## Key Modules

| File | Purpose |
|------|---------|
| `main.py` | Entry point; Python 3.12 guard; calls `ui.launch()` |
| `ui.py` | Tk shell (~4900 lines); panels in `ui_panel_*.py`; drives `App` |
| `agent.py` | Agent loop, permission modes, event emission, MCP routing |
| `llm.py` | OpenAI-compatible SSE streaming client; raises `LLMError` |
| `tools.py` | 8 built-in tools + executor; `is_write_tool` guard; `push_workspace` context manager |
| `context.py` | Token budget (`estimate_tokens`); two-phase compaction |
| `config.py` | `ModelConfig` dataclass; `models.json` loader; `CONFIG_DIR` (single source) |
| `cache.py` | LLM/tool caching; SQLite WAL or in-memory; TTL 1h / 5min |
| `sessions.py` | SQLite WAL session DB; legacy JSON migration |
| `mcp.py` | `StdioMCPClient` + `HttpMCPClient`; tool discovery; `MCPManager` singleton |
| `lsp.py` | stdlib JSON-RPC LSP client over stdio; multi-language |
| `codeindex.py` | Workspace TF-IDF index; code-aware tokenization; incremental mtime build |
| `codera.py` | Multi-root KB RAG; TF-IDF + optional embedding hybrid |
| `screenshot.py` | Multi-monitor region screenshot; annotation editor |
| `voice.py` | faster-whisper transcription; PortAudio VAD |
| `attach.py` | Document analysis (docx/pdf/zip); file URI extraction |
| `media.py` | Image/audio/video loading; cross-platform playback |
| `localmodels.py` | GPU model bridge; systemd/process management |

## Key Directories

| Path | Purpose |
|------|---------|
| `products/` | Product profiles (`profile.json`, `run.py`); `quant/` and `devrag/` ship real sub-code |
| `gpulocal/` | Embedded local model panel; setup scripts; systemd services |
| `ui_panel_*.py` | Modal/dialog panels (annotate, cache, dispatch, kb, mcp, models, quant, sessions) |
| `tests/` | pytest suite (~284 tests, 24 files) |
| `packaging/` | `build.py` — product-aware PyInstaller script |

## Development Commands

```bash
# Run (default devtool_local)
python3 main.py

# Run specific product
LOCAL_AI_PRODUCT=quant python3 main.py
python3 products/quant/run.py

# Syntax check (all Python)
python -m py_compile *.py

# Run tests
python -m pytest tests/ -q

# Install dev deps
pip install -r requirements-dev.txt

# Install runtime deps (voice stack)
pip install -r requirements.txt

# Build executable
python packaging/build.py [product] [--clean]
```

## Code Conventions & Common Patterns

**Language**: Python 3.12+ only (enforced by `main.py`). Chinese docstrings/comments; English identifiers. Bilingual UI via `i18n.t("key")`.

**Imports**: Stdlib only in core (`urllib.request`, `json`, `sqlite3`, `hashlib`, `subprocess`, `threading`, `tkinter`). Optional deps (`numpy`, `sounddevice`, `faster-whisper`, `psutil`, `Pillow`) are gracefully absent — code falls back.

**Dependency injection**: Global module singletons, not constructor injection. Singletons are resettable via `reset()` / `push_workspace()` context managers for test isolation.

**Error handling**: Tool errors returned as Chinese strings (not raised) — the model sees them as tool output. Transport/parse failures raise `LLMError` / `MCPError`.

**UI updates from worker threads**: Always `root.after(0, fn)` — never touch widgets from the agent thread.

**Shell sandbox** (`config.SANDBOX`, default on): `write_file` restricted to workspace; `run_shell` blocks destructive patterns. Disable with `LAS_SANDBOX=off`.

**Model dispatch**: Config keys in `config.py` (`model_dispatch`, `dispatch_smart`, `dispatch_model` = local brain). Vision routing prefers local, else falls back to `dispatch_vision`.

**Permissions**: `readonly` / `ask` / `always` modes. Two authorities: `tools.is_write_tool` and `MCPManager.is_write_tool`.

**Cache keys**: Use *request-time* message list — do NOT append the assistant reply before keying.

## Important Files

| File | Notes |
|------|-------|
| `config.py` | `CONFIG_DIR` is single source of truth for all cache/session/codeindex paths |
| `models.json` | Seed model list; user-edited; synced by `localmodels.py` |
| `products/__init__.py` | `LOCAL_AI_PRODUCT`, `profile.json` schema, `feature()` API |
| `products/quant/` | Strategy translation IR (JoinQuant↔PTrade↔gm↔QMT) |
| `products/devrag/` | Company multi-root knowledge base |
| `pyrightconfig.json` | Pyright stub; no linter gate in CI |
| `.github/workflows/test.yml` | CI: py_compile + pytest on ubuntu/windows/macos × Python 3.12 |

## Runtime & Tooling

- **Runtime**: Python 3.12 (required)
- **Package manager**: pip
- **Build tool**: PyInstaller (via `packaging/build.py`)
- **Test framework**: pytest
- **Static analysis**: pyright (manual; not CI-enforced)
- **Formatters**: none
- **LSP support**: pyright, tsserver, gopls, rust-analyzer, clangd (pre-warmed at startup)
- **CI**: GitHub Actions; matrix: ubuntu/windows/macos × Python 3.12

## Testing & QA

**Framework**: pytest (~284 unit tests across 24 files).

**Isolation**: `conftest.py` fixtures redirect `HOME`/`APPDATA`/`USERPROFILE` to `tmp_path` and strip `LOCAL_AI_PRODUCT`. `cache.reset()`, `mcp.reset_manager()`, `tools.push_workspace(path)` context managers reset singletons between tests.

**Mocking**: `monkeypatch.setattr(module, 'func', fake)` throughout. LLM transport fully mocked in `test_agent.py` and `test_llm.py`. SQLite backed by `tmp_path`.

**Test categories**: Unit (most files), parametrized (`test_products.py` across all 5 products), integration-like (sessions with real SQLite, config with real JSON).

**CI gates**: `python -m py_compile *.py` + `pytest -q` → then PyInstaller package build.
