# Local AI Writer

**English** | [简体中文](README.zh-CN.md)

**Local AI Writer** is a desktop AI writing studio for **short-drama screenplays (短剧) and web novels (网文)** — a Tkinter GUI backed by any OpenAI-compatible model, with streaming chat and an agent that actually reads and writes your manuscript files in a project directory. Python 3.12+, Linux / Windows / macOS.

Everything runs on your machine: no account, no bundled cloud service. Your manuscripts leave the computer only if you point the app at a cloud endpoint you configure yourself. The UI is bilingual (English / 简体中文) — switch via the model menu → 🌐 Language, persisted in `models.json`.

> This repo is the standalone home of the writing product, carved out of the **Local AI Studio** kernel ("one kernel, multiple products"). The default product is `novelwriter` — `python main.py` boots straight into the writing UI. The sibling profiles (`devtool`, `devtool_local`, `quant`, `devrag`) still ship in `products/` as kernel by-products; see [Products](#products-one-kernel-many-faces).

## Screenshot

![Main UI](docs/screenshots/main.png)

## Current status

**v0.1 — kernel migration + drama-video production.** The full creation kernel below works today: agent chat that writes real files, multi-root knowledge base, attachments, sessions, voice input, model management. The **drama-video chain runs end-to-end**: finished chapters → storyboard → character assets → keyframes → clips → dubbed episode MP4s (needs an image/video service + ffmpeg; see [docs/novel-setup.md](docs/novel-setup.md)). The writing-specific panels from the roadmap (chapter tree, character cards, beat templates) are not built yet — [Roadmap](#roadmap).

## Why a writing studio on an agent kernel

Most AI writing tools confine you to a chat box and a copy button. Here the agent has hands:

- **Your manuscript is a project directory.** Drafts, outlines, and settings live as plain files; the model uses `read_file` / `write_file` to revise chapter 12 in place instead of re-printing the whole script into a chat bubble.
- **A knowledge base keeps the canon straight.** Index your worldbuilding docs, character sheets, and previous volumes in a persistent multi-root KB; the model retrieves the relevant fragments itself (`kb_search`) instead of you re-pasting settings into every prompt.
- **Reference material goes in as attachments.** docx/pdf/txt/md/csv are analyzed in place; zips are extracted with a manifest; images go to vision models.
- **Long serials don't blow the context.** Three-stage compaction (1M-token budget by default) keeps a running story coherent, and the stats bar shows what you're spending.

## Features

- **Streaming chat** — body & reasoning stream live; tool calls shown as cards
- **File-backed writing** — agent reads/writes files inside the chosen workspace; drafts survive the chat
- **Multi-root knowledge base (RAG)** — index 设定/素材/往期作品 directories into SQLite; TF-IDF retrieval with optional embedding boost; `kb_search` tool + optional auto-inject into context
- **Attachments** — multi-select files with a message; txt/md/csv inlined, docx/pdf text-extracted, zip/tar.gz extracted with a file manifest; images downscaled to ≤1568px and sent to vision models (`"vision": true`)
- **Inline media** — images/GIFs displayed, audio player, video thumbnails in chat; text selectable, Ctrl+C / right-click copy
- **Drama video production (短剧成片)** — finished chapters → episode videos: storyboard → character image assets → shot keyframes (multi-image composition, appearance locked by character reference) → image-to-video → ffmpeg concat. Three-stage consistency keeps faces steady across shots; everything lands under the book's directory and re-runs skip existing files, so the chain resumes anywhere
- **Dialogue dubbing (TTS)** — dialogue lines are spoken with edge-tts neural voices (optional pip) or the Windows SAPI offline fallback, then muxed onto clips with ffmpeg; failure degrades to the model's original audio and never blocks the chain
- **Style library** — one visual style drives every generated asset; per-book default plus saved presets (persisted in `models.json`), picked once via a first-run dialog
- **Drama workbench** — three-step panel (`/novel drama`): script outline → asset library → episode videos; edit scripts, appearance anchors and storyboards, regenerate any single shot, then concat the episode
- **Auto link fetching** — image URLs in a message are downloaded for vision; web pages are fetched and summarized for the model (background thread)
- **Web search** — `web_search` over DuckDuckGo, zero deps, no API key
- **Smart dispatch** — `call_model` tool delegates a heavy subtask (a brutal plot surgery, image understanding) to a stronger configured model; targets (simple / high-end / vision) managed in a panel
- **Voice input** — one button: hold to talk, or quick-tap for auto-pause detection (local Whisper, faster-whisper)
- **Multi-session** — auto-save at send time, per-directory grouping, global search across projects
- **Context compaction** — over-budget conversations auto-truncate tool results, then collapse old rounds into summaries (system + first question + recent rounds kept)
- **Cache layer** — identical requests answered instantly; SQLite (persists) or in-memory backend; live token / cache-hit / fast-reply stats
- **Model management** — provider-first two-pane manager: providers grouped & renameable (uniqueness enforced), editable endpoint/key/API type (**OpenAI-compatible & Anthropic dual protocol**); per-model vision / reasoning-effort / context-window / max-output tokens — changes apply instantly, no restart
- **Slash commands** — `/init` generate AGENTS.md, `/brainstorm` ideate, `/plan` make an execution plan, `/work` execute it step by step, `/loop` iterate until verified, `/compress` compress session history; type `/` for the palette
- **@ file references** — type `@` to pick a workspace file/directory (Cursor-style); file references are auto-attached on send
- **Plan-first task steps** — multi-step tasks start from a `task_plan` checklist (functional descriptions, checked off as work proceeds); tool approval is an inline bar docked to the chat, no modal popups
- **Enter = newline, Shift+Enter = send** — long-form writing friendly; Ctrl+Enter queues a message
- **Three permission modes** — readonly / ask (default) / always, with sandbox guardrails
- **Workspace switching** — switch between works; relative paths follow the selected directory
- **Bundled fonts** — JetBrains Mono + Noto Sans CJK, consistent across platforms

## A writing session

```bash
mkdir 我的短剧 && python main.py     # then pick 我的短剧 as the workspace
```

1. Attach `大纲.docx` and ask: *“把大纲拆成 20 集的分集梗概，保存到 分集梗概.md”*
2. *“读分集梗概，把第 1 集扩写成 1200 字短剧剧本，存到 剧本/EP01.md，开场 30 秒内放钩子”*
3. Next day, open the session again (auto-saved), or switch to another work's directory — sessions are grouped per project.
4. Point the KB at your 设定集/ folder so character settings are retrieved automatically while writing.
5. When the chapters are done, run `/novel drama video 1-3` — storyboard, character assets, keyframes, image-to-video clips and dubbed episode MP4s appear under the book's `短剧成片/` directory (needs an image/video service + ffmpeg).

## Tools

| Tool | What it does | Permission |
|---|---|---|
| `read_file` | Read a file (with line numbers) | read |
| `write_file` | Write / overwrite a file | **write** |
| `list_dir` | List a directory | read |
| `glob_search` | Find files by wildcard | read |
| `grep_search` | Full-text search across the work | read |
| `index_search` | Semantic search over the workspace index | read |
| `web_search` | Search the web (DuckDuckGo, no key) | read |
| `run_shell` | Run a shell command (e.g. ffmpeg, pandoc exports) | **write** |
| `call_model` | Delegate a subtask to another configured model | read |
| `task_plan` | Create/update the task checklist shown in the plan panel | read |
| `kb_search` | Retrieve fragments from the multi-root knowledge base | read |
| `image_gen` | Text-to-image via the configured image service → `media/images/` | read |
| `video_gen` | Text/image-to-video (async task, ~1–3 min) → MP4 in `media/videos/` | read |
| `video_status` | Poll a running video-generation task | read |

(`lsp_diagnostics` also ships as a kernel tool; it only matters for code-like projects.)

## Architecture

```
main.py → ui.launch() → App (Tkinter mainloop; one worker thread per message)
   └─ agent.Agent.run()     synchronous function-calling loop
        ├─ llm.py           SSE streaming client: OpenAI-compatible & Anthropic (stdlib urllib)
        ├─ tools.py         built-in tools + executor + permission tiers + sandbox
        ├─ codera.py        multi-root knowledge base (TF-IDF + optional embedding)
        ├─ context.py       token budget + three-stage compaction
        ├─ cache.py         LLM/tool cache (SQLite WAL / memory)
        ├─ sessions.py      session DB (SQLite, per-directory grouping)
        ├─ attach.py        docx/pdf/zip attachment analysis
        ├─ dramavideo.py    drama-video chain: storyboard → assets → keyframes → clips → episode (ffmpeg)
        ├─ imggen.py · videogen.py · tts.py   image / video / TTS clients (agent tools + drama chain)
        ├─ voice.py         PortAudio capture + faster-whisper
        └─ weblinks.py      auto-fetch links from messages
```

**Agent loop**: stream chat request (with tool schemas) → tool_calls? → approval via the inline bar in `ask` mode → execute sandboxed → feed results back → repeat (≤ 24 rounds, then a forced no-tools wrap-up guarantees a final answer) → final text streamed.

## Products: one kernel, many faces

The repo root is the shared kernel; `products/<name>/profile.json` defines a product's brand and feature gates (`import products; products.feature("rag")`). This repo's default product:

| Gate | Value | Meaning |
|---|---|---|
| `dispatch` | ✅ | smart routing + `call_model` enabled |
| `rag` | ✅ | knowledge base + `kb_search` enabled |
| `attachments` / `sessions` / `voice` | ✅ | attachments, multi-session, voice input |
| `gpulocal` | ❌ | no embedded local-GPU model panel |
| `mcp` | ❌ | no external MCP tool servers |
| `editor` | ✅ | side file tree + editor panel |

Sibling profiles (`devtool`, `devtool_local`, `quant`, `devrag`) are still runnable for kernel development: `LOCAL_AI_PRODUCT=devtool python3 main.py`, or `python3 products/<name>/run.py`.

## Getting started: zero to first launch in 7 steps

Same walkthrough on Windows / macOS / Linux. Total time on a clean box: 5–15 minutes depending on pip cache.

### Step 1 — Install Python 3.12 or newer

Pick one:

- **Windows / macOS** — get the latest 3.14.x from [python.org/downloads](https://www.python.org/downloads/). **Make sure "Add Python to PATH" is checked** in the installer.
- **Cross-platform / sandboxed** — Miniconda:

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

> **Why 3.14?** It bundles Tcl/Tk 9.0, whose color-emoji engine draws the toolbar emojis in color. On 3.12/3.13 (Tk 8.6) those inline emoji glyphs render as monochrome on Windows. **The newly added PNG icons are unaffected** — they are raster images, not font glyphs.

### Step 2 — Clone and install dependencies

```bash
git clone https://github.com/hzerther-hub/drama.git
cd drama
pip install -r requirements.txt          # core: numpy, sounddevice, faster-whisper, psutil, tkinterdnd2, imageio-ffmpeg
pip install -r requirements-dev.txt      # optional: pytest (only needed for `tests/`)
```

If `pip install sounddevice` fails on Windows (PortAudio missing), retry after grabbing the C++ build tools:

```bat
:: easiest path — uninstall and reinstall usually picks up the prebuilt wheel:
pip uninstall sounddevice
pip install sounddevice
:: if it still complains, install Microsoft Visual C++ Build Tools
:: (https://visualstudio.microsoft.com/visual-cpp-build-tools/)
:: and tick "Desktop development with C++"
```

macOS:

```bash
xcode-select --install                  # Command Line Tools (gcc/clang) before pip
```

Linux Debian/Ubuntu:

```bash
sudo apt install python3-tk python3-venv libportaudio2 portaudio19-dev
```

### Step 3 — Install ffmpeg (drama production only)

Drama-video chain needs ffmpeg for dubbing mux and episode concat. Three options:

- **`imageio-ffmpeg`** (already in `requirements.txt`) — bundles a static ffmpeg binary under `imageio_ffmpeg/`; the app auto-detects it, no env setup required.
- **PATH ffmpeg** — [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) `release` zip; extract anywhere, add the `bin\` folder to PATH.
- **macOS** — `brew install ffmpeg`.
- **Linux** — `sudo apt install ffmpeg`.

If you only intend to author without producing short-drama MP4s, skip this step — the app prints a clear "ffmpeg missing" warning but writing continues.

### Step 4 — Launch

```bash
python main.py                                # default product: novelwriter
LOCAL_AI_PRODUCT=devtool python main.py       # switch to coding kernel
LOCAL_AI_PRODUCT=quant python main.py         # switch to quant-translation kernel
```

First launch does three things within seconds:

1. Copies the repo's `models.json` into `CONFIG_DIR/models.json` (`%APPDATA%\local-ai-studio\` on Windows).
2. Opens the main window; the model dropdown shows only the `deepseek/deepseek-chat` placeholder (no key yet).
3. The status bar at the bottom starts counting tokens — agent loop is live.

### Step 5 — Configure a model, send your first message

Click top-bar `⚙ Settings → Models`. You'll see three providers seeded:

- **deepseek** (default) — empty `api_key`. Paste your `sk-...` from [Step 5b below](#step-5b--deepseek-api-key) and Save.
- **agnes** — empty `api_key`. Paste your `sk-...` from [Step 5c below](#step-5c--agnes-api-key) and Save.
- **sensetime** (optional) — SenseNova; useful as a vision fallback.

After saving, the top-bar model dropdown lists `deepseek-chat`, `agnes-2.5-flash`, `agnes-3.0-flash`, etc. Pick one, type "hi" in the input box, hit Enter. A first reply means the chain works end-to-end. If you get `_post_stream` errors, the model id is wrong — re-select from the dropdown's suggestions.

### Step 6 — (optional) Run the test suite

```bash
python -m pytest tests/ -q
```

Expect `471 passed, 1 skipped`. The single failure is `test_quant_qmt.py::test_probe_not_found`, a pre-existing issue in the upstream quant path; it does not block novel writing.

### Step 7 — (optional) Build a single-file binary

```bash
pip install pyinstaller
python packaging/build.py novelwriter          # → dist/LocalAIWriter-<platform>/
python packaging/build.py novelwriter --clean  # rebuild
```

The packager reads `products/novelwriter/profile.json` for the exe name and excludes the AI-heavy stack (torch / faster-whisper / onnx).

### Common pitfalls

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: tkinterdnd2` on launch | `pip install tkinterdnd2` |
| Toolbar emoji render in black | Tk 8.6 limitation. Switch to Python 3.14 (Tk 9.0), or ignore — **all colored icon PNGs are unaffected** |
| macOS mic not capturing | System Settings → Privacy & Security → Microphone → allow Python / Terminal |
| Model dropdown shows Agnes models but calls fail | `api_key` or `base_url` mismatch (international vs China station) |
| Drama workbench: "ffmpeg not found" | Install ffmpeg to PATH, or confirm `imageio-ffmpeg` is installed |
| Chinese gibberish in stdout (rare) | Set `PYTHONIOENCODING=utf-8` for the run |

### Config & data directory

`CONFIG_DIR` is the single runtime directory that survives restarts and auto-migrates from legacy names:

- **Linux/macOS** — `~/.config/local-ai-studio/`
- **Windows** — `%APPDATA%\local-ai-studio\`

Contents: `models.json` (provider config), `cache.json` (LLM cache), `state.json` (UI state), `sessions/`, `index/`, `media/`, `extract/`.

### Writing your first novel (quickstart)

Pick `deepseek-flash` (1M context, supports vision) in the top-bar model dropdown. In the input box:

```
/novel start A female lead is reborn in an apocalyptic world and hunts her ex-fiancé who killed her family. 8
```

The pipeline starts at `setup` (high-concept), writes the file, and pauses for review. Each stage — `setup` → `world` → `contract` → `characters` → `outline` → `volume_plan` → `chapter_plan` → `chapters` — stops for your review. Type `/novel ok` to advance, `/novel adjust <feedback>` to revise the current stage, `/novel show N` to read chapter N, `/novel rewrite N <feedback>` to redo a chapter. When the manuscript is done, `/novel drama 1-8` adapts it to a shooting script and pushes the rest into the drama workbench for shot / keyframe / video generation.

For the full command reference, type `/novel help` inside the app.

## Dual-provider setup: Agnes + DeepSeek

One project covers **code / web novel / short drama / comic** end-to-end. The minimum configuration that exercises every pipeline is **two providers**: **DeepSeek** for text reasoning and vision (the "brain"), and **Agnes** for image and video generation (the "camera"). Both are pay-as-you-go with free credits on signup, no enterprise gating.

### Why these two

- **DeepSeek** supplies the long-context reasoning the writing and coding kernels need (`agent.run()` has a 24-round tool-calling budget; novelwriter stages consume 30k–120k-token contexts). `deepseek-chat` is the default in `models.json`.
- **Agnes** exposes the image and video endpoints the drama-video and comic chains call into (`imggen.py` → `image_model`, `videogen.py` → `video_model`). One provider, two distinct model IDs the app picks up automatically from each provider's `image_model` / `video_model` field.

A single DeepSeek key with no Agnes configuration gives you a complete writing experience (大綱 / 世界观 / 合约 / 章节剧本 / 分镜表) but no rendered frames; adding Agnes unlocks 短剧 to MP4, 漫画 to image grid, and `image_gen` / `video_gen` tools.

### Apply for DeepSeek API access

1. **Open the platform** — visit <https://platform.deepseek.com/sign_in>. Registration is in **Simplified Chinese** with phone-number verification; non-CN numbers can use `password login` after a `+86` SMS code is delivered to a Chinese number, or sign in with a Google / GitHub OAuth provider if exposed in your locale.
2. **Create the account** — enter a mobile number, request a verification code (SMS), accept the user agreement. New phones register automatically.
3. **Top up** — go to <https://platform.deepseek.com/top_up>. DeepSeek charges per 1M tokens; the smallest top-up is roughly US\$5 and gives access to every model. Payment methods at signup time support Alipay and WeChat Pay for CN users; international cards are accepted via Stripe-backed options in the billing dashboard. There is no monthly subscription — you buy credits that don't expire.
4. **Create a key** — <https://platform.deepseek.com/api_keys> → "Create new secret key". Copy the `sk-...` string immediately; DeepSeek shows it once. Drop it into the app's provider form as `api_key`, set `base_url` to `https://api.deepseek.com` (Anthropic-compatible calls go under `https://api.deepseek.com/anthropic`).

**Current model lineup (verified on `api-docs.deepseek.com/quick_start/pricing`):**

| Model id | Context | Max out | Reasoning | Vision | Notes |
|---|---|---|---|---|---|
| `deepseek-chat` | 64K | 8K | yes (toggleable) | no | default; cheap everyday text |
| `deepseek-flash` (alias `deepseek-v4-flash`) | 1M | 384K | yes | **yes** | cheapest Vision-capable model |
| `deepseek-v4-pro` (alias `deepseek-v4-pro`) | 1M | 384K | no | no | Pro-tier text (0813 release) |
| `deepseek-reasoner` | 64K | 8K | yes (always) | no | pure chain-of-thought |

`deepseek-v4-flash` and `deepseek-v4-flash-vision-exp` are accepted legacy aliases; both are now served by `DeepSeek-V4.1-Flash`. Add new ids to `models.json` under the existing `deepseek` provider if you need a model not yet listed; the kernel re-reads the file at launch.

### Apply for Agnes API access

1. **Open the platform** — visit <https://platform.agnes-ai.com/login> (international) or <https://platform.agnes-ai.cn/login> (China mainland). Both expose the same form; the `.cn` site may be faster from inside China.
2. **Create the account** — click "注册 / Sign up". The form takes **email + email verification code + password + password confirm**. There is no phone-only path; use an email you can receive a 6-digit code at. Google and GitHub SSO are exposed alongside the email form if you prefer OAuth.
3. **Add credits** — Agnes advertises "免费畅享前沿模型" (free tier) on signup. The free quota covers a small number of image and short-clip generations to validate the pipeline. For sustained drama production, top up on the billing page (Alipay / WeChat Pay on `.cn`; cards on `.com`).
4. **Create a key** — the API-keys page is reached from the left sidebar (often labelled "API Keys" or "令牌"). Generate a new key, copy it once, paste into the provider form. Set `base_url` to whichever platform your account lives on:
   - `https://apihub.agnes-ai.com/v1` for international
   - the equivalent `apihub.agnes-ai.cn/v1` for China-mainland accounts (check the dashboard; the model IDs are the same either way)

**Current model lineup (verified on `platform.agnes-ai.com` home + AA benchmark page):**

| Capability | Model id | Use in this app |
|---|---|---|
| Text reasoning | `agnes-3.0-flash` | agent loop, novelwriter chain, comic dialogue |
| Text (lighter) | `agnes-2.5-flash` | cheap sub-agent for routine tool calls |
| Image generation | `agnes-image-2.5-flash` (older: `agnes-image-2.0`) | character ref sheet, keyframe multi-image compose |
| Video generation | `agnes-video-v2.0` (current: `agnes-video-2.5`) | per-shot clip generation |
| Text-to-speech | not advertised on the home page | drama-comedia only — set `LAS_TTS_*` env or wire a TTS provider manually |

**A note on versioning.** `models.json` in this repo currently carries `image_model: agnes-image-2.5-flash` and `video_model: agnes-video-v2.0`. The AA homepage in 2026 shows the latest branded names as `Agnes-Image-2.0` and `Agnes-Video-2.5`. Both old and new names are accepted by the Agnes gateway in practice; if your account returns "model not found" for the legacy id, switch to the new id in model management — the app reads `image_model` / `video_model` per call, so changing it does not require a restart.

### What you can produce from one project

Configure once, the same app instance flips between the four editorial genres via the top-level product dropdown or by editing `products/<name>/profile.json`. The kernel is shared; only the prompt presets and pipeline stages differ.

| Product | What runs | Required providers |
|---|---|---|
| `devtool` / `devtool_local` | coding agent, file read/write, run shell, code-graph search, MCP tools, multi-round chat | one text model (DeepSeek or Agnes text) |
| `novelwriter` | 大綱 / 世界观 / 故事合约 / 角色表 / 摄影剧本 / 分镜表 → MP4 chapters | text (DeepSeek) + image (Agnes) + video (Agnes) + ffmpeg locally |
| `quant` | JoinQuant ↔ PTrade ↔ 掘金 ↔ QMT cross-platform translation via deterministic IR | one text model (only used as `ParseError` fallback) |
| `devrag` | corporate multi-root knowledge base, hybrid TF-IDF + embedding | one text model + optional embedding endpoint (`LAS_EMBED_*`) |
| `novelwriter` 短剧台 | drama workbench (`ui_panel_drama.py`): script → assets → storyboard → keyframes → clips → dubbed MP4 | text + image + video + TTS (optional) |
| `novelwriter` 漫画 | per-panel image generation (script acts as panel caption) | text + image |

The drama and comic paths are not separate products; they're modes inside `novelwriter` opened from the drama workbench and the comic panel that the writing kernel triggers. One project, one dependency set, four editorial surfaces.

## Packaging

```bash
pip install pyinstaller
python packaging/build.py novelwriter          # → dist/LocalAIWriter-<platform>/
python packaging/build.py novelwriter --clean  # rebuild without cache
```

The build is product-aware: `profile.json` decides the exe name (`LocalAIWriter`) and drops the AI heavy stack (torch/faster-whisper/onnx excluded, ~tens of MB). CI (`.github/workflows/test.yml`) runs tests and builds packages on ubuntu / windows / macos.

## Roadmap

From [`PLAN-五产品矩阵.md`](PLAN-五产品矩阵.md) (product 3; market analysis in [`PLAN-市场前景分析.md`](PLAN-市场前景分析.md)):

| Version | Scope |
|---|---|
| v0.1 ✅ | Kernel migration: chat, model management, sessions, file-backed writing (this repo today) |
| v0.5 | Creation skeleton: chapter-tree panel, character cards, worldbuilding cards, style templates, serialization management; txt/docx export |
| v1.0 | Template library: short-drama hook structures (first-3-episode hooks, paywall cliffhangers), web-novel pacing templates (golden three chapters, payoff density); shareable configs |
| v1.1 | Sensitivity/compliance check, multi-model comparative drafting, rewrite/expand/continue commands |

## Security notes

- `run_shell` / `write_file` really execute commands and write files; the default **ask** mode confirms every write
- Sandbox guardrails (default on, `LAS_SANDBOX=off` to disable): `write_file` is confined to the workspace; `run_shell` rejects obviously destructive commands (rm -rf /, mkfs, shutdown, fork bombs). Guardrails, not OS-level isolation
- Tool execution timeout (60 s) and a 24-round cap (with a forced wrap-up answer) prevent runaway loops
- Avoid `always` mode when feeding the model untrusted text

## Development

```bash
pip install -r requirements-dev.txt
python -m py_compile *.py            # syntax gate (same as CI)
python -m pytest tests/ -q           # 540+ unit tests; LLM transport mocked, HOME/APPDATA isolated
```

Core modules import stdlib only; optional deps (numpy, faster-whisper, psutil, Pillow, tkinterdnd2) degrade gracefully. UI dialogs live in `ui_panel_*.py`. Conventions in [`AGENTS.md`](AGENTS.md).

## License

[Mulan Permissive Software License, v2](LICENSE) (木兰宽松许可证，第2版).
