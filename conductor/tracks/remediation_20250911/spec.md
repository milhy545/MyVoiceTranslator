# Specification: Fix portability blockers, GPU leaks, and core logic bugs

## Overview
Remediate 29 issues identified in the multi-agent review (MiMo + Mistral + clean-context audit). Critical blockers: hardcoded Whisper cache path breaks portability; GPU memory leak on TUI restart; config `chunk_seconds` ignored causing wrong STT context window. High-severity logic bugs in LocalFallbackTranslator and STT language handling. Architecture improvements: protocol interfaces, immutable config, device cache, structured logging.

## Motivation
- Application fails on any machine other than developer's (hardcoded `/home/milhy777/LLM/Whisper`)
- "Apply + Restart" in TUI leaks CUDA memory → OOM after few restarts
- STT receives 1s chunks instead of configured 8s → fragmented transcripts
- Local translator produces broken Czech (diacritics, punctuation spacing)
- No unit tests for translation logic; integration tests require system binaries

## Functional Requirements
- STT model cache directory configurable via `AppConfig.state_dir` (default `~/.local/state/myvoicetranslator/whisper_models/`)
- Live audio chunk = 1.0s (low latency); STT accumulation = 8.0s (context) — separate config fields
- `WhisperTranscriber` reused across TUI restarts; STT config changes require full app restart (documented)
- `list_input_devices()` cached with explicit `force_refresh`; TUI refresh button invalidates cache
- LocalFallbackTranslator: diacritic-insensitive map lookup via `unicodedata.normalize('NFD')`; ~50 tokens; correct punctuation spacing
- STT language configurable via `stt_language` (env `MVT_STT_LANGUAGE`), default `en`; TUI model selector shows multilingual warning
- compute_type selector in TUI (auto, int8, float16, int8_float16) passed to WhisperTranscriber
- deep-translator dependency removed; HybridTranslator uses only LocalFallbackTranslator; `--offline` is default/only mode
- Protocol interfaces: `AudioSource`, `Transcriber`, `Translator` for dependency injection
- Immutable `AppConfig` (`frozen=True`) with `with_changes()`; TUI creates new config on apply
- Structured JSONL logging alongside markdown session logs

## Non-Functional Requirements
- Performance: Unit tests <10s; first live transcript <3s; GPU memory flat across 5 restarts
- Reliability: No hardcoded paths; graceful degradation when optional deps missing
- Security: No network calls in default config; no subprocess shell injection vectors
- Portability: Runs on clean machine with only `pip install -e .` + system audio deps

## Acceptance Criteria
- [ ] `python3 -m unittest discover -s tests -v` passes (all 11+ new unit tests)
- [ ] `python3 shield.py --offline --stt-device cpu test-file test_audio/fixture_voice.mp3` outputs valid JSON with transcripts
- [ ] TUI mounts, shows devices, capture starts, "Apply+Restart" ×5 with stable `nvidia-smi` memory
- [ ] No hardcoded paths in codebase (`grep -r "/home/milhy777" --include="*.py"` returns nothing)
- [ ] `deep-translator` removed from `pyproject.toml` and imports
- [ ] New unit tests in `tests/test_translate.py` cover LocalFallbackTranslator
- [ ] Integration tests marked opt-in, run only with `MVT_RUN_INTEGRATION=1`
- [ ] `pyproject.toml` pins `faster-whisper>=1.1.0,<2.0.0`

## Constraints and Dependencies
- Must preserve backward compatibility for CLI file mode JSON output format
- TUI keybindings and visual layout unchanged
- `faster-whisper` API stability within pinned version range
- System deps: portaudio, pulseaudio/pipewire, nvidia-driver (optional)

## Risks
- **ctranslate2 model unload**: `WhisperTranscriber.close()` cannot reliably free CUDA memory → mitigation: reuse instance, document full restart for STT config changes
- **Device hotplug**: Cache stale until explicit refresh → mitigation: document Refresh button, low priority for solo dev
- **Model download race**: Cache dir created lazily in `_load_model()` before `WhisperModel()` init

## Out of Scope
- ElevenLabs TTS integration
- Subprocess isolation for STT (separate process)
- pyudev hotplug listeners
- Major UI redesign or new visual themes
- Web UI or server deployment
- Cloud translation backends