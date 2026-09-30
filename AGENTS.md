# Repository Guidelines

## Project Structure & Module Organization
The repository is currently a small Python application centered on [`shield.py`](./shield.py), which contains CLI parsing, logging, the mocked fallback path, and the Textual-based live UI. Runtime logs are written to `logs/`, and sample inputs for manual STT checks live in `test_audio/` (`sample.mp3`, `test_audio.wav`). There is no dedicated `src/` or `tests/` package yet, so keep new modules small and colocated until the codebase is split more formally.

## Build, Test, and Development Commands
- `python3 shield.py --test test_audio/test_audio.wav` runs the safe test path against a sample file.
- `python3 shield.py --test test_audio/sample.mp3` checks another audio fixture and appends to `logs/interview_YYYYMMDD.md`.
- `python3 shield.py` starts the live TUI mode and requires the optional audio/UI dependencies to be installed.
- `python3 -m py_compile shield.py` performs a quick syntax check before committing.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and keep functions focused. Use `snake_case` for functions, variables, and filenames; use `PascalCase` for classes like `HybridTranslator` and `InterviewShield`. Prefer explicit names over short abbreviations, except for user-facing log labels such as `ENG` and `CZE`. Keep imports grouped at the top and avoid introducing heavy abstractions unless the file is first split into modules.

## Testing Guidelines
There is no formal test framework configured yet. For now, treat `--test` runs with files in `test_audio/` as the regression path, and add fixtures there when reproducing bugs. If you add automated tests later, use `tests/test_<feature>.py` and target mocked behaviour first so CI does not depend on CUDA, microphones, or external translation services.

## Commit & Pull Request Guidelines
Git history is not available in this workspace, so use clear imperative commits such as `Add offline fallback for translation errors` or `Split audio processing from UI setup`. Keep PRs narrow, explain the user-visible effect, list manual verification commands, and attach screenshots for TUI changes. Link the issue or bug report when one exists.

## Configuration & Runtime Notes
Do not commit generated files from `logs/` or local virtual-environment state from `.venv/`. Any new dependency should degrade gracefully when missing, matching the current `HAS_DEPS` fallback pattern.

## Agent Context Notes
When repository decisions depend on prior machine context or user preferences, prefer the global source of truth in `~/.gemini/GEMINI.md`. If Mega Orchestrator MCP is available, use its advanced memory before making environment assumptions: start with `get_context`, then use `search_memories` for semantic lookup of hardware, homelab, or workflow details. In Codex, the server is configured in `~/.codex/config.toml` as `mcp_servers."Mega-Orchestrator"` pointing to `http://192.168.0.58:7000/mcp`; over Tailscale, prefer `http://home-automat-server.tailb42db0.ts.net:7000/mcp` or `http://100.90.137.86:7000/mcp` instead of exposing it publicly.
