# AGENTS.md

## Quick Reference

- Run: `python3 main.py` (default product: devtool_local)
- Env: `LOCAL_AI_PRODUCT=quant python3 main.py`
- Tests: `python -m pytest tests/ -q`
- Syntax: `python -m py_compile *.py`
- Build: `python packaging/build.py [product] [--clean]`

## Architecture

```
main.py → ui.launch() → App (Tkinter mainloop)
   │ spawns one daemon worker thread per message
   ▼
agent.Agent.run()   # synchronous function-calling loop
   │
   ├─ llm.py         SSE streaming LLM client (stdlib urllib)
   ├─ tools.py       8 built-in tools + executor
   ├─ mcp.py          MCP stdio/HTTP client
   └─ context.py      Token budget + compaction
```

## Key Files

| File | Purpose |
|------|---------|
| `ui.py` | Tkinter shell, ~5100 lines, panels in `ui_panel_*.py` |
| `agent.py` | Agent loop, permission modes, event emission, MCP routing |
| `tools.py` | Built-in tool executor, `is_write_tool` guard |
| `mcp.py` | MCP manager, stdio + HTTP transport |
| `config.py` | `ModelConfig`, `CONFIG_DIR` singleton |
| `codeindex.py` | Workspace TF-IDF index (`index_search` tool) |
| `codera.py` | Corporate KB RAG (`kb_search` tool) |
| `products/` | Product profiles; `quant/` has strategy IR |
| `tests/` | pytest suite (~284 tests, 24 files) |

## Conventions

- Python 3.12+ only; Chinese docstrings/comments; English identifiers
- Stdlib only in core; optional deps fall back gracefully
- UI updates from worker threads: `root.after(0, fn)` — never touch widgets directly
- Tool errors returned as Chinese strings (not raised) — LLM sees them as output
- Cache keys use *request-time* message list (don't append assistant reply before keying)
- `CONFIG_DIR` in `config.py` is the single source of truth for cache/session/codeindex paths

## Product Variants

- `devtool_local` (default) — devtool with local model support
- `devtool` — general developer tool
- `novelwriter` — novel writing assistant
- `quant` — quantitative strategy translation (JoinQuant↔PTrade↔gm↔QMT)
- `devrag` — corporate multi-root knowledge base

Set via `LOCAL_AI_PRODUCT` env var or by running `products/<name>/run.py`.