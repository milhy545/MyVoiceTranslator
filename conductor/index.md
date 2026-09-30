# Conductor Index: MyVoiceTranslator

## Project Context
- **Product**: `product.md` — Interview Shield, real-time STT+translation TUI
- **Guidelines**: `product-guidelines.md` — UX, visual, safety, performance
- **Tech Stack**: `tech-stack.md` — Python 3.11+, textual, faster-whisper, offline-first
- **Workflow**: `workflow.md` — TDD, unittest, conventional commits, local deployment

## Active Tracks
- None

## Completed Tracks
- `audio-loopback-capture_20260915` — Desktop audio loopback monitor and dual-channel capture (completed 2026-09-15)
- `vad-latency-optimization_20260915` — VAD-guided audio segmentation and low-latency adaptive flush (completed 2026-09-15)
- `neural-translator_20260915` — Offline Neural Machine Translation via CTranslate2 OPUS-MT (completed 2026-09-15)
- `remediation_20250911` — Fix portability blockers, GPU leaks, core logic bugs (completed 2025-09-15)

## Archive
- None yet

## Quick Commands
```bash
# Status
python3 /home/milhy777/.gemini/config/skills/conductor/scripts/conductor.py status --root .

# Validate context
python3 /home/milhy777/.gemini/config/skills/conductor/scripts/conductor.py validate --root .

# Next task for active track
python3 /home/milhy777/.gemini/config/skills/conductor/scripts/conductor.py next --root . --track neural-translator_20260915
```

## Notes
- Brownfield project with modular `interview_shield/` architecture
- Conductor initialized 2025-09-11, updated 2026-09-15
- Primary user: Milhy (solo dev)