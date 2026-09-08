# Repository Guidelines

## Project Overview

Local AI Studio — offline-first desktop AI assistant (Tkinter GUI, Python 3.12+, stdlib-only core) shipped as multiple product variants from one kernel:

- `novelwriter` (**default**) — 短剧网文创作：outline→chapters pipeline with review/repair, fact ledger, export/publish
- `quant` — quantitative strategy translation (聚宽↔PTrade↔掘金↔QMT) via an intermediate representation (IR)
- `devtool` / `devtool_local` — general coding assistant (local-model support in `_local`)
- `devrag` — corporate multi-root knowledge-base RAG

Product selection: `LOCAL_AI_PRODUCT` env var or `python products/<name>/run.py`. Run default: `python main.py`.

## Architecture & Data Flow

```
main.py (3.12 guard) → ui.launch() → App (Tkinter mainloop)
  │ one daemon thread per message
  ▼
agent.Agent.run()  # synchronous function-calling loop, ≤MAX_TOOL_ROUNDS=24
  ├─ llm.py        SSE streaming, dual protocol via model.api_type (openai_compatible | anthropic)
  ├─ tools.py      built-in tool schemas + _EXECUTORS; sandbox; task_plan; call_model dispatch
  ├─ mcp.py        MCP stdio (JSON-RPC over pipes) + HTTP (SSE) clients, MCPManager singleton
  ├─ context.py    token budget + progressive compaction (tiktoken optional → CJK heuristic)
  └─ cache.py      LLM/tool-result cache (SQLite or memory backend)
```

- **Event contract**: agent emits dicts `{"type": ...}` consumed in `App._on_event` (ui.py): `text`, `reasoning`, `tool_start`, `tool_result`, `tool_denied`, `round`, `usage`, `cache_hit`, `context_compact`, `model_switch`, `plan {steps}`, `media {paths}`. Novel pipeline has its own stream marshaled through `_novel_event`.
- **Permissions**: `MODE_READONLY` / `MODE_ASK` (write tools need approval) / `MODE_ALWAYS`. Write tools = `write_file`, `run_shell`, plus MCP tools from non-readonly servers. Approval crosses threads via shared dict + `threading.Event`; timeout ⇒ auto-deny.
- **Caching invariants**: LLM cache keys use the *request-time* message list (never append the assistant reply before keying); aborted runs are never cached; MCP calls are never cached. Empty non-aborted rounds stop the loop; exhausting rounds triggers a forced no-tools summarization pass.
- **Cloud fallback**: only for `gpulocal-*` models, only on 503 / "Loading model" / connection failure, gated by `config.get_auto_cloud_fallback()`; emits `model_switch`.
- **Stage machine** (`pipeline.py`): `StageStopError` (fail chain) vs `StageDebtError` (record debt, continue) vs `StagePaused` (resume re-runs stage, which must skip completed work). Atomic JSON checkpoints in `CONFIG_DIR/pipelines/` + `.events.jsonl` log. `novel_chain.py` builds an 8-stage chain (setup→outline→world→contract→characters→volume→chapter_plan→chapters) with per-chapter review→one repair→debt, fact ledger (cap 60), foreshadow tracker, arc compression every 4 chapters, RAG indexing.
- **Quant iron rule**: never N×N platform-direct translation — always parse (deterministic AST, LLM only as `ParseError` fallback) → `StrategyIR` (ir.py) → deterministic template emit (emitters.py, no LLM) → validate (whitelist sandbox rules) → stub-runtime sim → benchmark.
- **Retrieval tiers**: workspace TF-IDF (`codeindex.py` → `index_search` tool), corporate KB RAG (`codera.py` → `kb_search` tool), quant keyword KB (`products/quant/kb.py`), vector store (`vecstore.py`: Qdrant REST + in-memory/hash-vector fallback).

## Key Directories

| Path | Purpose |
|---|---|
| `/` (root modules) | Shared kernel — engine (agent/llm/tools/mcp/config/context), UI (ui, ui_input, ui_panel_*), services (cache, sessions, codeindex, codera, vecstore, …). Flat layout, no src/ |
| `products/<name>/` | `profile.json` (title, features, exe_name) + identical `run.py` per variant; `quant/` holds the full IR subsystem |
| `tests/` | ~30 pytest files mirroring root modules |
| `packaging/` | `build.py` — product-aware PyInstaller wrapper |
| `docs/` | `harness-notes.md`, `novel-setup.md`, screenshots |
| `fonts/`, `assets/icons/`, `examples/` | Bundled fonts (JetBrains Mono, Noto Sans CJK), emoji icons, sample MCP server |

## Development Commands

```bash
python main.py                                   # run default product (novelwriter)
LOCAL_AI_PRODUCT=quant python main.py            # run a variant (Windows: set LOCAL_AI_PRODUCT=quant)
python products/quant/run.py                     # same via product runner
python -m pytest tests/ -q                       # full suite (~404 passed + 1 skipped)
python -m py_compile *.py                        # syntax gate
python packaging/build.py [product] [--clean]    # PyInstaller build → dist/<exe_name>-<platform>/
python -m products.quant.benchmark               # quant consistency matrix (acceptance ≥90%, deterministic path must be 100%)
python -m products.quant.demo                    # dual-MA JoinQuant↔PTrade roundtrip demo
```

Window title carries a build marker: `<profile.title> - build <ui._BUILD_TAG>` (ui.py:49, currently `0906-3`). With multiple instances/builds mixed, confirm the title before testing.

## Code Conventions & Common Patterns

- **Language**: Chinese docstrings/comments, English identifiers, `from __future__ import annotations`.
- **Stdlib-only core; optional deps degrade gracefully**: always `try: import X except ...: X = None` + fallback (tiktoken, tkinterdnd2, akshare, LSP/MCP servers, `localmodels`). Never add third-party imports to core modules. (Known deviation: `ui_panel_annotate.py` imports PIL unguarded.)
- **Tool errors are Chinese strings, never raised** — `tools.execute_tool` catches everything and returns `错误：...` so the agent loop continues. Only internal errors (`LLMError`, `MCPError`, `ImgError`, `VecError`, `PublishError`) raise.
- **Threading**: worker threads NEVER touch widgets — marshal every UI mutation via `root.after(0, fn)` (panels use `win.after`). All long panel ops (MCP reconnect, KB build, quant LLM translate) run daemon threads.
- **Input placeholder** is a floating `tk.Label` overlay (`_setup_placeholder`), never text inserted into the input buffer. The input's `<<Modified>>` flag is sticky — handlers must call `edit_modified(False)`.
- **Keyboard handling** is unified in `ui_input.py::InputController` (pure decision fn `decide()` — testable without Tk). Popup open: Enter/Tab=confirm, ↑↓=navigate, Esc=close, typing=`rescan`. No popup: Enter=send, Shift+Enter=newline (falls through), Ctrl+Enter=queue (`App._on_ctrl_return`). IME-safe: Enter matches keysym (`Return`/`KP_Enter`) **or** char (`\r`/`\n`). **Read `docs/harness-notes.md` before touching this code.**
- **Panel pattern**: lazy `import ui` *inside* functions (circular import by design — a top-level `import ui` in a panel breaks startup); reuse `ui._make_modal`, `ui._flat_button`, `theme.*` tokens; read `ui.FONT_UI`/`ui.FONT_MONO` at open time (font globals mutate at launch — never cache at import).
- **i18n**: all user-visible strings via `i18n.t(key, **kw)`; sparse `STRINGS` table `key → {en, zh}`; language persisted in CONFIG_DIR `models.json`; `zh_only` product feature forces zh.
- **Storage**: everything derives from `config.CONFIG_DIR` (`%APPDATA%\local-ai-studio` on Windows, else `~/.config/local-ai-studio`) — resolved at import time. SQLite modules share a pattern: WAL + `RLock` + thread-local connections (`sessions.py`, `cache.py`, `codeindex.py`, `codera.py`). Pipeline saves are atomic (tmp + `os.replace`).
- **Silent degradation is intentional** (vecstore/codera/embed/weblinks/attach never interrupt business); detect health via metadata, e.g. `codera` search result `source='tfidf'` vs `'hybrid'`.
- **Checkpoints**: `write_file` snapshots before overwrite (`checkpoints.py`, 10 per file); `/undo` *consumes* snapshots (each call steps back one); new files are not snapshotted.
- **Quant sync contracts** (keep in lockstep when editing): `parsers._KIND_SIGNATURES` ↔ `emitters._INIT_ATTRS`, `parsers._TIME_IN` ↔ `emitters._TIME_OUT`, `ir.KNOWN_KINDS_HINT` ↔ `emitters._LOGICS`. Mapping truth lives in `products/quant/api_maps/*.md` (“改映射先改对照表”). IR symbols are canonical JoinQuant-style (`000001.XSHE`); convert only at parse/emit boundaries (`symbols.py`). QMT templates deliberately keep `TODO: 填资金账号` — compliance red line; xtquant is referenced, never vendored.

## Important Files

| File | Purpose |
|---|---|
| `main.py` | 17-line entry: version guard **before** `import ui`, then `ui.launch()` |
| `ui.py` (~5900 lines) | `App` class: 3-pane layout, send path (`_send_with` spawns daemon worker), event consumption (`_on_event`), status (`_set_status`), slash commands, novel pipeline UI (inline — **`ui_panel_novel.py` does not exist**), `launch()` |
| `ui_input.py` | `InputController`: unified keypress dispatch, `@file` //`command` popups, pure `decide()` |
| `ui_panel_models.py` | Model/provider management (two-pane Treeview); shared popup component lives in ui_input, not here |
| `agent.py` | `Agent` loop: permission modes, event emission, caching, cloud fallback |
| `llm.py` | Streaming client; `_post_stream` is the seam tests monkeypatch; `_ThinkFilter` buffers `<think>` tags across chunks |
| `tools.py` | `TOOL_SCHEMAS` + `_EXECUTORS` + `WRITE_TOOLS = {'write_file','run_shell'}`; sandbox (`path_in_workspace`, shell regex blocklist, `LAS_SANDBOX=off` disables) |
| `config.py` | `CONFIG_DIR` + legacy migration; frozen `ModelConfig` (per-provider `api_type`, per-model `context_window`/`max_tokens`/`vision`/`reasoning`); dispatch/KB/MCP config |
| `pipeline.py` / `novel_chain.py` | Stage machine + checkpoints; novel production chain |
| `context.py` | Budget = `min(budget, context_window − output_max − 1024)`; folds middle rounds into a summary, keeps system + first user + last 2 rounds verbatim |
| `sessions.py` | SQLite `CONFIG_DIR/sessions.db`; `messages` JSON includes UI-only `notes` (never sent to model) |
| `models.json` (repo root) | **First-run seed only** — copied into CONFIG_DIR; live config is CONFIG_DIR/`models.json`. `api_type` is not in the seed (config.py-level field) |
| `products/__init__.py` | Profile loader: `DEFAULT_PRODUCT='novelwriter'`, `feature(key)` defaults **true** when absent, `KNOWN_FEATURES`, `_reset_for_test()` |
| `packaging/build.py` | Generates `packaging/<exe_name>.spec` (edit `_SPEC` template here, never the generated spec); excludes torch/whisper/onnx stack |
| `docs/harness-notes.md` | Design notes on turn budgets/compaction; required reading for input-box/popup work |
| `CLAUDE.md` | **Stale** — do not trust over AGENTS.md/README.md |

## Runtime/Tooling Preferences

- **Python 3.12+ required** (hard guard in main.py); 3.14+ recommended on Windows — Tk 9 renders emoji toolbar icons in color (conda py312/Tk 8.6 renders them black). `start_writer.bat` launches a machine-specific `py314` path (not portable).
- **No formatter/linter wired up**: `pyrightconfig.json` is a stub; nothing runs pyright. Syntax gate = `python -m py_compile *.py`. Tests: `pip install -r requirements-dev.txt` (pytest only).
- **Networking is stdlib `urllib`** throughout (`ProxyHandler({})` disables env proxies; 300s LLM timeout). Env-gated services: `LAS_QDRANT_URL/KEY`, `LAS_EMBED_*`, `LAS_IMAGE_*`, `LAS_PUBLISH_WATTPAD_TOKEN`, `LAS_PUBLISH_WEBHOOK_URL`.
- Provider id rules: regex `^[a-z0-9_-]+$`; `gpulocal-*` prefix reserved; provider id **and** display name must be unique. Legacy `gpulocal-*` entries (module removed) remain editable/deletable.

## Testing & QA

- **Runner**: `python -m pytest tests/ -q`. No fixtures in `conftest.py` — it redirects `HOME`/`USERPROFILE`/`APPDATA` to a temp dir and pops `LOCAL_AI_PRODUCT` at import time (config.py resolves CONFIG_DIR at import, so conftest must run before any project import). Suite: ~404 passed + 1 skipped, fully mocked (no network, no Tk windows).
- **LLM mock style**: `monkeypatch.setattr(llm, '_post_stream', lambda model, messages, tools: iter(fake_sse_dicts))`; errors via generators raising `llm.LLMError`. Build models with `config.ModelConfig` directly.
- **UI tests** exercise extracted pure functions (`ui_input.decide`), never real windows. Product tests: `monkeypatch.setenv(LOCAL_AI_PRODUCT, ...)` + `products._reset_for_test()` in try/finally.
- **Naming**: `tests/test_<module>.py`, plain module-level functions or `TestX` grouping, Chinese one-line module docstrings.
- **Quant QA gate**: after parser/emitter/kb changes run `python -m products.quant.benchmark` — any direction <100% (deterministic path) means template/parser semantic drift; overall acceptance ≥90%.
- Test-isolation helpers: `cache.reset()`, `vecstore.reset_memory()`, `products._reset_for_test()` — use them when a test mutates module singletons.
