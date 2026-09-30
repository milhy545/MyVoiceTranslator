# Implementation Plan: Chrome Extension & Launcher

## Phase 1: Planning
- [x] Task: Approve specification and implementation plan (Approved by User).

## Phase 2: Desktop Integration & Unified Launcher
- [x] Task: Vytvořit instalační skript `install_desktop.sh` pro generování `.desktop` souboru a ikony.
- [x] Task: Refaktorovat `shield.py` – přidat úvodní menu (TUI vs Server).
- [x] Task: Upravit `tui.py`, aby uměl zachytit klávesovou zkratku pro přepnutí a vrátil příslušný exit code do `shield.py`.

## Phase 3: FastAPI Backend
- [x] Task: Přidat `fastapi` a `uvicorn` do `pyproject.toml` (pomocí `uv add`).
- [x] Task: Vytvořit `interview_shield/server.py` s funkčním WebSocket endpointem pro streamování audia a napojením na `InterviewShieldPipeline`.
- [x] Task: Implementovat endpoint `/api/switch-to-tui`, který provede bezpečný shutdown uvicornu.
- [x] Task: Zabezpečit spouštění serveru uvnitř smyčky v `shield.py`.

## Phase 4: Chrome Extension Core
- [x] Task: Založit složku `chrome_extension/` a vytvořit `manifest.json` s právy `tabCapture`, `sidePanel`, `activeTab`.
- [x] Task: Implementovat `background.js` (zachytávání zvuku přes tabCapture, převzorkování přes AudioContext a WebSocket odesílání).

## Phase 5: Chrome Extension UI (SidePanel & Content)
- [x] Task: Vytvořit `sidepanel.html` a `sidepanel.js` (načítání transkriptů ze socketu, zobrazení TUI-style designu, tlačítko na návrat do terminálu).
- [x] Task: Vytvořit `content.js` a `content.css` (Shadow DOM plovoucí titulky integrované přímo do stránky s videem).

## Phase 6: Verification & QA
- [x] Task: Spustit sadu testů (`uv run pytest tests/`).
- [x] Task: Spustit statickou analýzu (`uv run mypy interview_shield/ tests/` a `uv run ruff check .`).
- [x] Task: Napsat end-to-end test (nebo testovací skript `test_server.py`) ověřující funkčnost WebSocket endpointu nanečisto.

## Completion
- [x] Acceptance criteria verified
- [x] Required project completion gate passed
