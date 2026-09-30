# MyVoiceTranslator — Multi-Agent Review & Remediation Execution Guide

**Generated**: 2025-09-11  
**Workflow**: Multi-Agent Repository Review (MiMo + Mistral + Clean-Context)  
**Artifacts**:
- `REVIEW_REPORT.md` — Unified Critical Review (29 issues classified)
- `MASTER_STITCH_PLAN.md` — Remediation plan with exact code snippets
- `CLEAN_CONTEXT_REVIEW.md` — Clean-context architectural verdict (7 amendments)

---

## Executive Summary

| Metric | Before | After Plan |
|--------|--------|------------|
| Blocker/Critical Issues | 5 | 0 |
| Portability (other machines) | ❌ Broken | ✅ Fixed |
| GPU Memory Leak on Restart | ✅ Leaks | ✅ Fixed (reuse transcriber) |
| Live Latency | ~1s (accidental) | ~1s (intentional) |
| Test Suite Time | 53s | <10s (unit) + opt-in integration |
| Architecture Coupling | High | Protocol-based DI |

---

## Execution Order (Copy-Paste Ready)

### Phase 0: Blockers (MUST DO FIRST)

```bash
cd /home/milhy777/Develop/MyVoiceTranslator

# P0.1 Fix hardcoded Whisper cache
# Edit interview_shield/stt.py, pipeline.py, config.py per MASTER_STITCH_PLAN.md P0.1

# P0.2 Wire chunk_seconds correctly (with Amendment 2 fix)
# Edit config.py (add live_chunk_seconds), pipeline.py, audio.py per plan + amendment

# P0.3 Transcriber reuse (Amendment 3) — NOT close()
# Edit tui.py _apply_and_restart to reuse transcriber
# Edit stt.py to support dynamic config or document full restart needed

# P0.4 Device cache
# Edit audio.py (add cache + invalidate), tui.py (force_refresh=True)

# Verify
python3 -m unittest discover -s tests -v
# All 11 tests pass
```

### Phase 1: Core Logic

```bash
# P1.1 LocalFallbackTranslator fix + diacritics (Amendment 5)
# Edit interview_shield/translate.py per plan + unicodedata.normalize

# P1.2 STT language config
# Edit config.py, stt.py, pipeline.py, tui.py

# P1.3 Remove dead ElevenLabs code
# Edit translate.py (delete lines)

# P1.4 TUI force_offline toggle
# Edit tui.py action_toggle_offline

# Verify
python3 -m pytest tests/test_translate.py -v  # new unit tests
python3 shield.py --offline --stt-device cpu test-file test_audio/fixture_voice.mp3
```

### Phase 2: Architecture

```bash
# P2.1 Protocol interfaces
# Create interview_shield/interfaces.py
# Update pipeline.py type hints

# P2.2 Immutable config (with Amendment 6 fix)
# Edit config.py @dataclass(frozen=True), add with_changes()
# Update tui.py _apply_and_restart to create new config

# P2.3 SoundDeviceSource callback fix
# Edit audio.py _callback + iter_chunks

# P2.4 Structured logging (optional, can defer)
# Create structured_log.py, update logging_utils.py

# Verify
python3 -m unittest discover -s tests -v
```

### Phase 3: TUI Polish

```bash
# P3.1 Model/compute options (with Amendment 7)
# Edit tui.py MODEL_OPTIONS, add COMPUTE_TYPE_OPTIONS
# Update stt.py to accept compute_type

# P3.2 Debounce status refresh
# Edit tui.py _refresh_status + _do_refresh_status

# P3.3 Keyboard binding consistency
# Edit tui.py on_switch_changed for force-offline-switch

# Verify: Run TUI, test all controls
python3 shield.py run  # manual smoke test
```

### Phase 4: Tests & CI

```bash
# P4.1 Unit tests for translators
# Create tests/test_translate.py

# P4.2 Mark integration tests
# Edit tests/test_e2e.py add @pytest.mark.integration or skipIf

# P4.3 py.typed marker
touch interview_shield/py.typed

# Verify
python3 -m pytest tests/test_translate.py tests/test_audio_devices.py -v  # unit only <10s
```

### Phase 5: Cleanup

```bash
# P5.1 Remove legacy fixtures
rm test_audio/test_audio.wav test_audio/sample.mp3

# P5.2 Fix datetime timezone
# Edit events.py use datetime.now(timezone.utc)

# P5.3 Type check fix
# Edit stt.py TYPE_CHECKING import

# Final verify
python3 -m unittest discover -s tests -v
python3 -m py_compile interview_shield/*.py shield.py
```

---

## Verification Gates

| Gate | Command | Pass Criteria |
|------|---------|---------------|
| **Syntax** | `python3 -m py_compile interview_shield/*.py shield.py` | No errors |
| **Unit Tests** | `python3 -m pytest tests/test_translate.py tests/test_audio_devices.py -v` | All pass, <10s |
| **Integration (opt-in)** | `MVT_RUN_INTEGRATION=1 python3 -m pytest tests/test_e2e.py -v` | All pass |
| **CLI File Mode** | `python3 shield.py --offline --stt-device cpu test-file test_audio/fixture_voice.mp3` | JSON output, backend=local |
| **TUI Smoke** | `timeout 10 python3 shield.py run` | Mounts, shows devices, no crash |
| **GPU Mem Stable** | Run TUI, "Apply+Restart" ×5, watch `nvidia-smi` | Memory flat |

---

## Rollback Commands

```bash
# Per-phase rollback
git diff HEAD~1 -- interview_shield/stt.py pipeline.py config.py  # P0.1
git checkout HEAD~1 -- interview_shield/stt.py pipeline.py config.py

# Full rollback
git reset --hard HEAD  # before any changes
```

---

## Amendments Checklist (from Clean-Context Review)

- [ ] **A1**: `WhisperTranscriber._load_model()` creates `cache_dir` before `WhisperModel()`
- [ ] **A2**: Split `chunk_seconds` → `live_chunk_seconds=1.0` + `stt_chunk_seconds=8.0`
- [ ] **A3**: Reuse `WhisperTranscriber` across restarts (no `close()`); document STT config changes need app restart
- [ ] **A4**: `_load_devices()` calls `force_refresh=True`; document hotplug requires Refresh
- [ ] **A5**: `LocalFallbackTranslator` uses `unicodedata.normalize('NFD')` for diacritic-insensitive map lookup
- [ ] **A6**: `_ensure_writable_directory` removes probe file; trusts `mkdir`
- [ ] **A7**: `MODEL_METADATA` dict; TUI warns on multilingual model + `stt_language="en"`

---

## Dependencies to Document

Add to `README.md` or `DEPENDENCIES.md`:

```markdown
## System Dependencies
- **Required**: `python3.11+`, `pip`
- **Audio**: `portaudio19-dev` (for sounddevice), `pulseaudio`/`pipewire`
- **Fixtures (dev/test)**: `espeak-ng`, `ffmpeg`
- **GPU (optional)**: `nvidia-driver`, `cuda-toolkit` (for faster-whisper cuda)

## Python Dependencies (pyproject.toml)
- numpy
- rich
- textual
- sounddevice
- faster-whisper
- deep-translator

## Install
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# For fixtures:
sudo apt install espeak-ng ffmpeg  # Debian/Ubuntu
```
```

---

## Sign-Off

| Role | Name | Status |
|------|------|--------|
| Lead Reviewer (MiMo) | — | ✅ Review Complete |
| Architect (Mistral) | — | ✅ Review Complete |
| Clean-Context Auditor | — | ✅ 7 Amendments Issued |
| **Ready for Execution** | — | **✅ YES** |

---

*Execute Phase 0 immediately. Subsequent phases can be batched per sprint.*