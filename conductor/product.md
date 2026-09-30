# Product: MyVoiceTranslator (Interview Shield)

## Users
- Primary: Milhy (sole developer and user)
- Use case: Real-time speech-to-text + translation during interviews/meetings

## Problem
Need a local-first, offline-capable TUI application for live English→Czech translation during interviews. Must work without cloud dependencies, on Linux, with GPU acceleration when available.

## Goals
- Live microphone/monitor capture → STT (faster-whisper) → translation → TUI display
- File-based testing with deterministic fixtures
- Zero cloud dependency for core workflow (offline-first)
- GPU acceleration via CUDA when available
- Portable across machines (no hardcoded paths)

## Non-Goals
- Cloud translation services (Google, DeepL, ElevenLabs)
- Multi-user or server deployment
- Web UI
- Real-time TTS output

## Core Capabilities
1. Live capture modes: microphone, system monitor (loopback), auto
2. STT via faster-whisper (tiny.en through large-v3)
3. Local-only translation (token-map fallback, no external API)
4. TUI with live windows, history, controls, device selection
5. File-based test mode with JSON output for CI
6. Doctor diagnostics for environment readiness

## Success Measures
- All unit tests pass <10s
- Integration tests opt-in, pass on dev machine
- TUI starts and captures without crash
- GPU memory stable across restarts
- Works on clean machine (no hardcoded paths)