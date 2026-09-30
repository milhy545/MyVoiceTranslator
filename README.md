# MyVoiceTranslator

Milhy's Interview Shield je low-HW Python TUI pro real-time STT a překlad EN -> CS s CPU-first fallback strategií. Aplikace umí:

- běžet interaktivně přes Textual TUI,
- zpracovat audio soubor,
- simulovat live microphone i internal-audio workflow bez lidského zásahu,
- zapsat session log do Markdownu,
- vyexportovat debug bundle pro troubleshooting.

## Stav projektu

CPU-first varianta je otestovaná a zelená. Online překlad i GPU větev jsou implementované tak, aby se při problému automaticky přepnuly na bezpečný fallback, ale v aktuálním sandboxu nešlo finálně ověřit reálný DNS přístup ani NVIDIA runtime.
Na hostu mimo sandbox už je potvrzené, že online Google překlad funguje. GPU větev je teď blokovaná host kernel lockdownem a chybějícími `/dev/nvidia*`, ne aplikací.

## Spuštění

Používej lokální `.venv`:

```bash
source .venv/bin/activate
python shield.py doctor
python shield.py run
```

## Jednoduchá instalace na jiný Linux PC

Primární distribuční cesta je user-level installer. Pro TUI + audio workflow je spolehlivější než Docker a praktičtější než AppImage, protože zachová přístup k PipeWire/Pulse, přidá položku do menu a zároveň připraví shell command.

Instalace:

```bash
bash scripts/install_myvoice.sh
```

Co to udělá:

- vytvoří nebo aktualizuje `.venv` přes `uv`,
- nainstaluje projekt v editable režimu,
- vytvoří wrapper `~/.local/bin/myvoice`,
- přidá položku do aplikačního menu jako `My Voice Translator`,
- nainstaluje ikonu do `~/.local/share/icons/...`.

Po instalaci:

```bash
myvoice doctor
myvoice run
```

Odinstalace launcherů:

```bash
bash scripts/uninstall_myvoice.sh
```

Rychlé unattended scénáře:

```bash
source .venv/bin/activate
python shield.py prepare-fixtures
python shield.py --offline --stt-device cpu test-file
python shield.py --offline --stt-device cpu test-live-mic
python shield.py --offline --stt-device cpu test-live-monitor
python scripts/run_final_verification.py
```

Legacy kompatibilita:

```bash
source .venv/bin/activate
python shield.py --offline --stt-device cpu --test test_audio/fixture_voice.mp3
```

## Offline přepnutí

Jednorázově:

```bash
source .venv/bin/activate
python shield.py --offline run
```

Natrvalo pro session:

```bash
export MVT_FORCE_OFFLINE=1
source .venv/bin/activate
python shield.py run
```

## Logy a artefakty

- Preferovaný produkční log path: `~/logs/interview_YYYYMMDD.md`
- Pokud prostředí nedovolí zapisovat do home, aplikace automaticky spadne do fallbacku v repu: `./logs/`
- Debug bundly: `~/.local/state/myvoicetranslator/artifacts/`
- Pokud home není zapisovatelné, fallback: `./.runtime/artifacts/`

## Hlavní příkazy

- `python shield.py doctor` - environment readiness report
- `python shield.py devices` - best-effort seznam input devices
- `python shield.py prepare-fixtures` - vygeneruje deterministické WAV/MP3 fixtures
- `python shield.py test-file [audio]` - file-based E2E
- `python shield.py test-live-mic` - simulated microphone E2E
- `python shield.py test-live-monitor` - simulated internal-audio E2E
- `python shield.py run` - interaktivní TUI

## TUI ovládání

Live TUI už není jen read-only status bar. Pravý panel je konfigurační centrum:

- `Input mode` - přepíná `auto`, `microphone`, `internal audio / monitor`
- `Input device` - vybírá konkrétní capture device nebo `Auto / default`
- `STT device` - přepíná `auto`, `cpu`, `cuda`
- `Whisper model` - přepíná aktivní STT model
- `Online backend` - přepíná `google` nebo `disabled / local only`
- `Force offline fallback` - okamžitě přepíná offline režim do pending konfigurace

Změny v panelu se aplikují přes `Apply + Restart`, který restartuje live capture worker bez vypnutí celé appky.
Hlavní okno má teď samostatné translation window:

- horní `ENG` panel se aktualizuje okamžitě po zachycení věty
- spodní zvýrazněný `CZE` panel se doplní po dokončení překladu
- history zůstává oddělená a zapisuje až hotové dvojice `ENG -> CZE`

Klávesy:

- `r` - apply + restart capture
- `s` - stop capture
- `f` - refresh devices
- `o` - toggle offline switch
- `d` - export debug bundle
- `c` - clear translation window bez zásahu do history
- `l` - hide/show log panel
- `p` - doctor snapshot
- `q` - quit

## Bootstrap prostředí

Pokud bude potřeba vytvořit čisté prostředí přes `uv`:

```bash
bash scripts/bootstrap_env.sh
```

## Distribuční poznámka

- Docker není hlavní cesta pro desktop použití, protože komplikuje audio capture, TUI a menu integraci.
- AppImage zatím není primární artefakt. Installer řeší skutečný use-case rychleji a s menší chybovostí.

## Omezení

- Lokální fallback překlad je momentálně rule-based emergency backend. Je deterministický a testovatelný, ale není to plnohodnotný neurální překladač.
- `doctor` a `devices` jsou navržené tak, aby nikdy nevisely na rozbitém audio stacku; proto používají safe discovery s timeoutem.
- GPU/STT auto mode nejdřív zkouší CUDA a pak padá na CPU. Pokud `doctor` hlásí chybějící `nvidia-smi`, `nvidia_device_nodes.ok=false` nebo `kernel_lockdown.ok=false`, je to host-level problém, ne pád aplikace.

Detailní postupy jsou v [docs/e2e-debugging.md](/home/milhy777/Develop/MyVoiceTranslator/docs/e2e-debugging.md) a [docs/architecture.md](/home/milhy777/Develop/MyVoiceTranslator/docs/architecture.md).
