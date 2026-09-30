# Tech Stack: MyVoiceTranslator

## Runtime
- Python 3.11+ (tested on 3.14.7)
- Virtual environment via venv

## Core Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| numpy | ≥1.24 | Audio array processing |
| rich | ≥13.0 | Terminal formatting (via textual) |
| textual | ≥0.50 | TUI framework |
| sounddevice | ≥0.4.6 | Audio I/O via PortAudio |
| faster-whisper | ≥1.1.0,<2.0.0 | STT via CTranslate2 |
| deep-translator | REMOVED | Was: online translation (now offline-only) |

## System Dependencies
- portaudio19-dev (for sounddevice)
- pulseaudio/pipewire (audio routing)
- espeak-ng, ffmpeg (fixture generation, dev only)
- nvidia-driver + cuda-toolkit (optional, for GPU STT)

## Model Storage
- faster-whisper models cached in `~/.local/state/myvoicetranslator/whisper_models/`
- Default model: `base.en` (74 MB)

## Architecture
- Package: `interview_shield/` (CLI, pipeline, audio, STT, translate, TUI, config, diagnostics, logging, fixtures, events)
- Entry: `shield.py` → `interview_shield.cli:main`
- Console script: `myvoice`

## Testing
- Framework: unittest (stdlib)
- Unit tests: `tests/test_audio_devices.py`, `tests/test_translate.py`
- Integration tests: `tests/test_e2e.py` (marked `@pytest.mark.integration`, opt-in via `MVT_RUN_INTEGRATION=1`)
- Fixtures: deterministic audio in `test_audio/` (fixture_voice.wav/.mp3)

## Rejected Alternatives
- whisper.cpp: harder Python integration
- vosk: larger models, less accurate English
- Google Cloud Speech: requires network, billing
- PyQt/Tkinter: heavier, not terminal-native