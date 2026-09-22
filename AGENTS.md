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

## Drama Workshop (剧集工作台 / Pavo 三段式)

novelwriter 的制片模块，UI 在 `ui_panel_drama.py`，引擎在 `dramavideo.py`。流水线是"大纲 → 资产 → 分镜视频"，所有产物落到 `novels/<书名>/`，**文件存在即缓存**（断点续传天然成立，重新进入工作台自动跳过已完成环节）。

**四步流程**：

1. **大纲改写** — 工作台粘贴原始文本 → 「AI 改写」按集拆分剧本、标注场景与角色；可换文本模型、调语气（全局风格存 `models.json::globals.default_drama_style`，默认 `dramavideo.DEFAULT_STYLE = "电影感写实风格，统一色调与打光，画面细腻，短剧质感"`）。满意后「保存并进入制作」落盘 `novels/<书名>/剧本.json`。
2. **资产制作** — 对剧本「提取」得到 角色 / 场景 / 道具 清单（每条带 `name` + `appearance` + `type` + `path`）；逐个点「生成形象」产出一致性参考图（也可全选批量）。资产图存 `短剧资产/<名>.png` + `短剧资产/cast.json`（含 `_done_<类>` 完成标记），后续生视频时作为视觉参考注入。
3. **分镜与视频** — 「视频制作」页先拆分分镜（AI 按节奏切分并生成提示词）；顶栏选视频模型（Seedance / Wan 3.0 / MiniMax…），分辨率与时长档位联动；右侧微调每个分镜的提示词（`@角色名` 自动从 `cast.json` 映射参考图）。点「批量生成视频」并发调用 `videogen.py`；关键帧由 `dramavideo` 多图合成生成，再作首帧走图生视频（`text_to_video` 降级）。失败任务可「重试失败」/「重新生成单个镜头」/`/novel drama video 1-3 redo`。
4. **拼接导出** — 勾选镜头（悬停预览单镜视频），点「开始拼接」→ FFmpeg 合成到 `短剧成片/第N章-<标题>.mp4`，可下载 / 在 UI 播放。点「标记完成」点亮左侧进度栏；`剧集列表` 随时查看各集状态，点「进入制作」继续未完成的集。

**一致性三段传播**（`dramavideo.py:5-7`）：

1. **角色基础形象** — 详细外貌锚 + 统一风格，每角色一次，全剧复用（资产层）；
2. **镜头关键帧** — 分镜描述 + 出场角色形象图作参考图多图合成（长相由参考图锁定，资产 → 关键帧层）；
3. **镜头视频** — 关键帧作首帧图生视频（画面继承关键帧，不再漂移，关键帧 → 视频层）。

**目录约定**（dramavideo.py:10-11，所有路径相对 `novels/<书名>/`）：

| 目录 | 内容 |
|---|---|
| `短剧资产/` | `<角色>.png` + `cast.json` + 各章 `assets.json` |
| `短剧分镜/` | `第N章.json`（分镜表）+ `urls.json` |
| `短剧关键帧/` | `N-01.png` …（多图合成产物） |
| `短剧片段/` | `N-01.mp4` …（单镜视频） |
| `短剧成片/` | `第N章-<标题>.mp4`（FFmpeg 拼接终产物） |

**关键模块**：

| 文件 | 职责 |
|---|---|
| `ui_panel_drama.py` (≈45KB) | 剧集工作台 UI：`show(app)` 入口；三页（大纲 / 资产 / 分镜视频）由 `state` + `dramavideo` 状态驱动；后台线程跑生成，`win.after` 回主线程刷新 |
| `dramavideo.py` (≈70KB) | 三段流水线 + ffmpeg 拼接；`DEFAULT_STYLE`、`cast.json` I/O、`_done_<类>` 标记、关键帧多图合成、`redo=True` 重做关键帧/片段（角色形象/分镜表保留） |
| `videogen.py` (≈12KB) | 多 provider 视频生成（Seedance / Wan / MiniMax…）；分辨率×时长档位映射；并发任务管理；`text_to_video` / `image_to_video` 两路 |
| `imggen.py` (≈18KB) | 图像生成后端（角色参考图、关键帧多图合成）；PIL 可选（缺则降级为文本） |
| `tests/test_dramavideo.py` | pytest 覆盖；monkeypatch `llm._post_stream` 风格的 mock 流 |
| `i18n.py` (≈100KB) | 包含 `ds.shots`、`novel drama video` 等工作台文案；UI 字符串全走 `i18n.t` |

**FFmpeg**：拼接走 stdlib `subprocess` 调用 ffmpeg；macOS / Linux 走 PATH，Windows 走 PATH 或 `imageio-ffmpeg` bundled binary（`packaging/build.py` 已处理）。视频时长护栏：视频模型给多长画面只能说多长的话，镜头时长低于此数会截断（dramavideo.py:1077 注释）。

**注意**：当前 `ui_panel_drama.py` / `dramavideo.py` 文件头的 docstring 出现乱码（gbk/latin-1 被当 utf-8 解码），历史遗留；修改这两个文件时用 UTF-8 读写即可。
