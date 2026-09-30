# Specification: Chrome Extension, Server Backend & Desktop Launcher

## Overview
Cílem tohoto tracku je transformovat `MyVoiceTranslator` na plnohodnotnou systémovou aplikaci a integrovat ji s Google Chrome pomocí lokálního WebSocket backendu a rozšíření. Původní terminálové TUI zůstává zachováno. 

**Pro implementující AI modely:** Postupujte přísně iterativně, pište čistý kód, respektujte Goat Principle a testujte každý krok před jeho odškrtnutím. Nesmíte rozbít stávající asynchronní STT pipeline.

## Functional Requirements

### 1. Desktop Integrace & Launcher
- **`.desktop` spouštěč**: Vytvořit bash instalační skript (např. `install_desktop.sh`), který vygeneruje `MyVoiceTranslator.desktop` a umístí ho do `~/.local/share/applications/`.
- **Hybridní `shield.py`**: Úprava hlavního vstupního bodu tak, aby nejprve nabídl jednoduché menu v terminálu: 
  `[1] TUI Mode (Local Mic)`
  `[2] Server Mode (Chrome Extension)`
- **Přepínání stavů**: TUI musí po zachycení speciálního signálu/klávesy ukončit svůj běh a vrátit řízení do `shield.py`, které plynule nastartuje FastAPI server (a naopak).

### 2. FastAPI Backend
- Vytvořit `interview_shield/server.py` obsluhující port `8000`.
- Endpoint `ws://localhost:8000/transcribe`: Přijímá binární PCM audio chunks (Float32, 16kHz) přes WebSocket.
- Integrovat hotovou `InterviewShieldPipeline` (viz `pipeline.py`), která převezme audio a vrátí zpět přes WebSocket vygenerované JSON eventy (CZ/EN text).
- Endpoint pro přepnutí do TUI: `POST /api/switch-to-tui`, který bezpečně ukončí server a umožní `shield.py` znovu nahodit TUI.

### 3. Chrome Rozšíření (Manifest V3)
- **Umístění**: Vytvořit složku `chrome_extension/`.
- **Architektura**: Pure Vanilla JS, HTML, CSS. Žádný Node.js, žádný Webpack!
- **Core (`background.js`)**: Použití `chrome.tabCapture` a `AudioContext` k zachycení, převzorkování na 16kHz a odeslání do Python WS serveru.
- **Side Panel (`sidepanel.html`)**: Design sladěný s Textual TUI (černá, tyrkysová). Zobrazení přepisů a přidání velkého tlačítka "Přepnout na Terminál", které zavolá `POST /api/switch-to-tui`.
- **Content Script (`content.js`)**: Pomocí Shadow DOM (pro izolaci stylů) injektovat plovoucí titulky přímo přes aktuální video (draggabilní, průhledné pozadí).

## Acceptance Criteria
- [ ] Aplikaci lze spustit systémově kliknutím na ikonu (Linux `.desktop`).
- [ ] TUI a FastAPI server se mohou bezpečně střídat (nikdy neběží zároveň).
- [ ] Přenos audia z Chrome do Pythonu funguje přes WebSockets bez padání nebo memory leaků.
- [ ] Side Panel a plovoucí titulky správně renderují český a anglický text obdržený ze serveru.
- [ ] Všechny existující unit testy (`uv run pytest tests/`) procházejí.
- [ ] Kód prochází přísnou kontrolou linterů (`ruff`) a typů (`mypy`).

## AI Directives
- **Žádné halucinace**: Zkontrolujte existující `pipeline.py` a metody jako `normalise_segments`, než je zavoláte.
- **Žádné dummy data**: Neposílejte do produkce mockované odpovědi.
