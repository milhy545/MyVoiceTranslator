# Unified Critical Review Report — MyVoiceTranslator

**Date**: 2025-09-11  
**Reviewers**: MiMo (Bug/Harsh) + Mistral (Architecture/Security)  
**Scope**: `interview_shield/` package, `shield.py` entry, `tests/`, `scripts/`  
**Health**: ✅ All 11 tests pass (53s), syntax clean, pyc for 3.11/3.13 but runtime 3.14.7

---

## Severity Classification

| Tier | Count | Criteria |
|------|-------|----------|
| **Blocker** | 1 | Hardcoded absolute path breaks portability completely |
| **Critical** | 4 | Security risk, resource leaks, config ignored, test infrastructure deps |
| **High** | 6 | Logic bugs, inconsistent config, broken fallback, dead code |
| **Medium** | 11 | Coupling, missing abstractions, performance, UX gaps |
| **Low** | 7 | Code hygiene, timezone, logging, options completeness |

---

## Blocker

### B1. Hardcoded Whisper Model Cache Path — `interview_shield/stt.py:51`
```python
self.model = WhisperModel(
    self.model_name,
    device=device,
    compute_type=compute_type,
    download_root="/home/milhy777/LLM/Whisper"  # ← HARDCODED
)
```
**Impact**: Application **will not work on any other machine**. Model download fails silently if dir missing/permission denied.  
**Provenance**: Observed in source; not configurable via env/CLI/config.  
**Fix**: Use `AppConfig.state_dir / "whisper_models"` or `faster_whisper` default (`~/.cache/huggingface`).

---

## Critical

### C1. Audio Device Enumeration Spawns Subprocess Per Call — `audio.py:54-79`
```python
helper = """
import json
try:
    import sounddevice as sd
except Exception as exc:
    ...
"""
completed = subprocess.run([sys.executable, "-c", helper], ...)
```
**Risk**: 
- Called from `list_input_devices()` → `run_doctor()`, `TUI on_mount()`, `refresh_devices()`, `cli devices` command
- 100-200ms per call; TUI mounts call it twice
- If `sounddevice` import fails, returns empty list silently
**Fix**: Cache result; move to module-level init or singleton; run in thread pool for TUI.

### C2. Config Value `chunk_seconds` Ignored by Audio Sources — `config.py:14` vs `audio.py:138,184`
```python
# config.py
chunk_seconds: float = 8.0

# audio.py (both WavChunkSource and SoundDeviceSource)
chunk_seconds: float = 1.0  # hardcoded default in __init__
```
**Impact**: 8× mismatch between configured and actual audio chunking. STT receives 1s chunks instead of 8s → poor context, more API calls, fragmented transcripts.  
**Fix**: Pass `config.chunk_seconds` from pipeline to audio sources.

### C3. No GPU/Model Cleanup on Live Capture Failure — `tui.py:406-430`
```python
except Exception as exc:
    self.call_from_thread(self.debug_log.write, f"[red]Live failure:[/] {exc}")
    self.call_from_thread(self._set_capture_state, "error")
finally:
    self.call_from_thread(self._handle_capture_finished)
```
**Risk**: `WhisperModel` may hold CUDA memory (`ctranslate2` backend). No `__del__` or explicit `model.__exit__()`. Repeated "Apply + Restart" leaks GPU memory.  
**Fix**: Implement `WhisperTranscriber.close()` / context manager; call in `finally`.

### C4. E2E Tests Require System Binaries (`espeak-ng`, `ffmpeg`) — `fixtures.py:28-42`, `test_e2e.py`
```python
subprocess.run(["espeak-ng", ...], check=True)
subprocess.run(["ffmpeg", ...], check=True)
```
**Risk**: CI fails on clean runners. 53s test suite.  
**Fix**: Mock fixtures in unit tests; mark e2e as `@pytest.mark.integration` requiring opt-in; provide pre-generated fixtures in repo.

---

## High

### H1. LocalFallbackTokenizer Broken — `translate.py:33-53`
```python
pieces = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
# "Hello,world" → ["Hello", ",", "world"] → "Hello , world"
```
**Bugs**:
- Spurious space before punctuation
- `\w` excludes accented Czech chars (`ř`, `ž`, `ě`) → treated as punctuation
- No handling of contractions, numbers, URLs
**Fix**: Use `regex` module with `\p{L}+` or proper tokenization; or accept this is a *toy* fallback and document clearly.

### H2. `transcribe_samples` Hardcodes `language="en"` — `stt.py:67`
```python
segments, _ = self.model.transcribe(audio, beam_size=3, language="en")
```
**Impact**: Multilingual models (`small`, `medium`, `large-v3`) forced to English. Czech input would hallucinate.  
**Fix**: Add `language` to `AppConfig`; default `"en"`; pass through.

### H3. `HybridTranslator.elevenlabs_api_key` Dead Code — `translate.py:84`
```python
self.elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
# Never used
```
**Risk**: Confusion; suggests TTS integration exists but doesn't.  
**Fix**: Remove or implement ElevenLabs TTS backend.

### H4. `force_offline` Toggle in TUI Doesn't Mark Dirty — `tui.py:377`
```python
def action_toggle_offline(self) -> None:
    self.force_offline_switch.value = not self.force_offline_switch.value
    # Missing: self._mark_controls_dirty(...)
```
**Impact**: User toggles offline → "Apply + Restart" button doesn't highlight → user confusion.  
**Fix**: Call `_mark_controls_dirty`.

### H5. `WhisperTranscriber` No Context Manager / Explicit Close — `stt.py`
```python
class WhisperTranscriber:
    def __init__(...): ...
    # No __enter__, __exit__, close()
```
**Risk**: `ctranslate2` models hold GPU memory; `__del__` unreliable.  
**Fix**: Add `close()` method; use in pipeline `finally`.

### H6. Inconsistent Error Handling — `translate.py` vs `stt.py`
- `HybridTranslator.translate()` → returns `TranslationResult` with `error` field
- `WhisperTranscriber.__init__()` → raises `RuntimeError`
- `SoundDeviceSource.__init__()` → raises `RuntimeError`
- `AudioDeviceInfo` subprocess → returns `[]` on failure
**Fix**: Adopt consistent pattern: either all raise typed exceptions, or all return `Result[T, E]`.

---

## Medium

### M1. Tight Coupling — No Interfaces for Audio/STT/Translation
- `InterviewShieldPipeline` directly constructs `WhisperTranscriber`, `HybridTranslator`, `SoundDeviceSource`
- Unit testing requires full stack or monkeypatching internals
**Fix**: Define `Protocol` classes (`AudioSource`, `Transcriber`, `Translator`); inject via constructor.

### M2. Mutable Config Shared Across TUI + Pipeline — `tui.py:106`
```python
self.config = config  # same instance
# Later: self.config.input_mode = value  # mutates live
```
**Risk**: Race if pipeline reads config mid-mutation. Restart logic mitigates but fragile.  
**Fix**: Config should be frozen (`@dataclass(frozen=True)`) or TUI creates new config on apply.

### M3. `list_input_devices` No Caching — `audio.py:81-112`
Called: `run_doctor(include_audio_devices=True)` → TUI mount → refresh button → CLI `devices` command.  
**Fix**: Memoize with `functools.lru_cache` or module-level cached var; invalidate on explicit refresh.

### M4. `SoundDeviceSource` Callback Does Heavy Work — `audio.py:160`
```python
def _callback(self, indata, frames, time_info, status):
    self._queue.put(indata.copy().flatten())  # copy + flatten in PortAudio callback
```
**Risk**: PortAudio callbacks must return < 1-2ms. `copy()` + `flatten()` on large buffers may xrun.  
**Fix**: Put raw `indata` (view) to queue; flatten in consumer thread.

### M5. TUI `_refresh_status` Rebuilds Entire Status String Frequently — `tui.py:286-306`
Called on every transcript, status, keystroke.  
**Fix**: Debounce or cache; only update changed fields.

### M6. No Abstraction for Debug/Session Logging — `logging_utils.py`
Custom markdown + JSON. No structured logging (JSONL), no log levels beyond status.  
**Fix**: Use `structlog` or stdlib `logging` with JSON formatter; keep markdown as human view.

### M7. `_ensure_writable_directory` Race Condition — `config.py:58-68`
```python
probe = primary / ".write_test"
probe.write_text("ok")
probe.unlink()
```
**Risk**: TOCTOU between write and unlink if multiple processes.  
**Fix**: Use `tempfile.NamedTemporaryFile(dir=primary, delete=True)` or `os.access(primary, os.W_OK)`.

### M8. STT Device/Compute Type Not Configurable from TUI — `tui.py:200-203`
```python
STT_DEVICE_OPTIONS = [("Auto", "auto"), ("CPU", "cpu"), ("CUDA", "cuda")]
MODEL_OPTIONS = [("tiny.en", "tiny.en"), ("base.en", "base.en"), ("small.en", "small.en")]
```
Missing: `medium.en`, `large-v3`, compute_type selector (int8/float16/int8_float16).  
**Fix**: Add options; pass `compute_type` to `WhisperTranscriber`.

### M9. `SessionLogger` Opens/Closes File Per Entry — `logging_utils.py:34,44`
```python
with self.session_log.open("a", encoding="utf-8") as handle:
```
**Fix**: Keep file handle open; flush periodically; rotate daily.

### M10. `events.py` Uses Naive Datetime — `events.py:10,17`
```python
created_at: datetime = field(default_factory=datetime.now)
```
**Fix**: `datetime.now(timezone.utc)`; store ISO8601 with Z.

### M11. `pipeline.py` Chunk Logic Uses 1.0s Hardcoded — `pipeline.py:85,114`
```python
frame_threshold = int(self.config.sample_rate * self.config.chunk_seconds)
# But audio sources use chunk_seconds=1.0 → frame_threshold = 16000
# Config says 8.0 → frame_threshold = 128000
```
**Wait** — pipeline uses `config.chunk_seconds` (8.0) but audio sources emit 1s chunks → pipeline buffers 8 chunks before transcribing. That's actually *correct* if audio source chunk=1s. But audio source `chunk_seconds` is hardcoded to 1.0, not configurable. See C2.

---

## Low

### L1. `LOCAL_TOKEN_MAP` Only 9 Words — `translate.py:16-25`
```python
LOCAL_TOKEN_MAP = {"good": "dobré", "morning": "ráno", ...}
```
Not a real translator. Document as "demo fallback only".

### L2. `TranscriptEvent.phase` Values Inconsistent — `events.py:8`
```python
phase: str = "translated"  # but pipeline emits "captured" then "translated"
```
**Fix**: Use `Literal["captured", "translated"]`.

### L3. `WhisperModel` Type Ignored — `stt.py:15`
```python
WhisperModel = None  # type: ignore[assignment]
```
**Fix**: `from typing import TYPE_CHECKING; if TYPE_CHECKING: from faster_whisper import WhisperModel`

### L4. TUI Keyboard Binding `o` (toggle_offline) Doesn't Match Button — `tui.py:54`
```python
("o", "toggle_offline", "Toggle offline"),
# But no button bound to this; only Switch
```
**Fix**: Either bind switch to action or remove binding.

### L5. `doctor` Command Outputs Full JSON to Stdout — `cli.py:96`
```python
print(json.dumps(run_doctor(...), ensure_ascii=False, indent=2))
```
**Fix**: Add `--json` flag; default human-readable summary.

### L6. `test_audio/` Contains Legacy Empty Files — `fixtures.py:44-47`
```python
legacy_wav = target_dir / "test_audio.wav"
legacy_mp3 = target_dir / "sample.mp3"
if not legacy_wav.exists() or legacy_wav.stat().st_size == 0:
    copyfile(wav_path, legacy_wav)
```
**Fix**: Remove legacy files from repo; keep only `fixture_voice.wav/mp3`.

### L7. No `py.typed` Marker — Package claims typing but no marker file.

---

## Security Summary (Mistral)

| Issue | Severity | File |
|-------|----------|------|
| Hardcoded path leaks dev machine structure | Medium | `stt.py:51` |
| Subprocess helper string interpolation | Low | `audio.py:54-79` |
| No path validation on audio input | Low | `stt.py:62` |
| `subprocess.check=True` on external binaries | Low | `fixtures.py:28-42` |
| No auth on TUI (local-only, acceptable) | Info | — |

**Overall**: Low risk for local tool. Primary concern is hardcoded path (B1) and subprocess pattern (C1).

---

## Architecture Summary (Mistral)

| Principle | Status | Notes |
|-----------|--------|-------|
| Dependency Inversion | ❌ | Concrete classes instantiated directly |
| Single Responsibility | ⚠️ | Pipeline does audio+STT+TL+logging |
| Immutable Config | ❌ | Mutable dataclass shared |
| Interface Segregation | ❌ | No `Protocol`/ABC for swappable backends |
| Testability | ⚠️ | Integration-heavy; unit mocks difficult |
| Observability | ⚠️ | Custom markdown+JSON; no structured logs |
| Resource Management | ❌ | No cleanup for GPU models |

---

## Test Coverage Gap

| Module | Unit Tests | Integration Tests |
|--------|------------|-------------------|
| `audio.py` | 4 (device resolution) | 0 |
| `stt.py` | 0 | 0 (covered via e2e) |
| `translate.py` | 0 | 0 (covered via e2e) |
| `pipeline.py` | 0 | 5 (e2e) |
| `config.py` | 0 | 0 |
| `diagnostics.py` | 1 | 0 |
| `logging_utils.py` | 0 | 0 |
| `fixtures.py` | 0 | 1 (e2e) |
| `tui.py` | 0 | 0 (no TUI tests) |

---

## Recommended Priority Order

1. **B1** — Hardcoded path (blocks all other machines)
2. **C2** — Config chunk_seconds ignored (core functionality broken)
3. **C3** — GPU memory leak on restart
4. **C1** — Subprocess per device enum (perf + TUI lag)
5. **H1/H2** — STT/Translation logic bugs
6. **M1/M2** — Architecture: interfaces + immutable config
7. **M3/M8** — Caching + missing TUI options
8. Remaining Medium/Low

---

*End of Unified Critical Review Report*