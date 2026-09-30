# Clean-Context Architectural Review — Master Stitch Plan

**Reviewer**: Mistral (clean context, senior systems architect)  
**Input**: MASTER_STITCH_PLAN.md only — no prior chat history  
**Date**: 2025-09-11

---

## Verdict: **CONDITIONALLY APPROVED** with 7 Amendments

The plan is coherent, incremental, and addresses the blocker/critical issues. However, 7 edge cases were missed that will cause production failures if not amended.

---

## Amendment 1: P0.1 Cache Dir — Race on First-Run Model Download

**Plan text**: `cache_dir=config.state_dir / "whisper_models"`  
**Issue**: `state_dir` is ensured in `AppConfig.ensure_directories()`, but `WhisperTranscriber.__init__` runs *before* pipeline calls `config.ensure_directories()` in CLI path.  
**Race**: If `state_dir` doesn't exist, `WhisperModel(download_root=...)` fails with `FileNotFoundError` before directory creation.

**Fix**: Move `ensure_directories()` call earlier, or make `WhisperTranscriber._load_model()` create cache dir lazily.

```python
# In WhisperTranscriber._load_model()
self.cache_dir.mkdir(parents=True, exist_ok=True)  # ADD before WhisperModel()
self.model = WhisperModel(..., download_root=str(self.cache_dir))
```

---

## Amendment 2: P0.2 Chunk Seconds — Breaking Change for Live Latency

**Plan text**: `chunk_seconds=self.config.chunk_seconds` (default 8.0)  
**Issue**: Current audio sources emit 1s chunks; pipeline buffers 8 chunks (8s) before transcribing. Changing audio source to 8s chunks means **8s latency** before first transcript — unacceptable for live use.

**Root cause**: The config value (8.0) was never wired; the 1s chunk was intentional for low-latency live feel.

**Fix**: 
- Keep audio source `chunk_seconds=1.0` (or configurable `live_chunk_seconds`)
- Pipeline `frame_threshold` = `config.chunk_seconds * sample_rate` (8s worth of 1s chunks)
- Rename config field: `stt_chunk_seconds` (accumulation window) vs `live_chunk_seconds` (capture granularity)

```python
# config.py
live_chunk_seconds: float = 1.0      # NEW: capture granularity
stt_chunk_seconds: float = 8.0       # RENAMED: accumulation before STT

# pipeline.py
source = SoundDeviceSource(..., chunk_seconds=self.config.live_chunk_seconds)
frame_threshold = int(self.config.sample_rate * self.config.stt_chunk_seconds)
```

**Impact**: Live latency stays ~1s; STT still gets 8s context. Backward compatible.

---

## Amendment 3: P0.3 Close() — ctranslate2 Doesn't Release CUDA Memory on `del`

**Plan text**: `self._model = None; gc.collect(); torch.cuda.empty_cache()`  
**Issue**: `ctranslate2` (faster-whisper backend) allocates via `cudaMalloc`; Python `del` + `gc` + `empty_cache()` **does not guarantee** release. The model holds `cudaMalloc`'d buffers until process exit.

**Evidence**: `ctranslate2` docs: "Models are not designed to be unloaded. Create one model per process."

**Fix Options**:
1. **Accept no unload** — document that "Apply + Restart" leaks GPU mem; user must restart app.
2. **Subprocess isolation** — run STT in separate process; kill process on restart (heavy).
3. **Model pooling** — keep single `WhisperTranscriber` instance across restarts; only swap config.

**Recommendation**: Option 3 — minimal change. Pipeline holds `transcriber` as singleton; TUI restart reuses it.

```python
# TUI _apply_and_restart
if self.pipeline is not None:
    # Reuse transcriber; only rebuild pipeline with new config
    self.pipeline = InterviewShieldPipeline(
        self.config,
        self.logger,
        transcriber=self.pipeline.transcriber,  # REUSE
        translator=self.pipeline.translator,
        ...
    )
```

**Note**: This requires `WhisperTranscriber` to support dynamic config changes (model, device) — or accept that STT config changes require full app restart.

---

## Amendment 4: P0.4 Device Cache — Stale Cache on Hotplug

**Plan text**: Module-level `_cached_devices` with `invalidate_device_cache()`  
**Issue**: 
- Hotplug (USB mic plugged in) → cache stale until explicit refresh
- TUI auto-refresh on mount doesn't call `invalidate_device_cache()` before `_load_devices()`

**Fix**: 
- `_load_devices()` must call `list_input_devices(force_refresh=True)` (already in plan ✓)
- Add periodic auto-refresh (e.g., every 30s) or `pyudev` listener (Linux-only)
- Document: "Device list cached; press Refresh after hotplug"

---

## Amendment 5: P1.1 LocalFallback — Czech Diacritics Still Broken

**Plan text**: `re.findall(r"\w+(?:[.,!?;:]*)|[.,!?;:]+", text, flags=re.UNICODE)`  
**Issue**: `\w` in Python `re` with `UNICODE` **includes** accented letters (ř, ž, ě, š, č, ý, á, í, é, ó, ú, ů) — *but* `LOCAL_TOKEN_MAP` keys are ASCII-only. Czech words with diacritics won't match.

**Example**: Input "dobré ráno" → tokens ["dobré", "ráno"] → map lookup fails → passes through unchanged. Output "dobré ráno" (correct by accident). But "good morning" → "dobré ráno" works.

**Fix**: Normalize tokens to ASCII for map lookup (strip diacritics), or expand map with diacritic variants.

```python
import unicodedata

def _strip_diacritics(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

# In translate():
word_lower = _strip_diacritics(word).lower()
translated = LOCAL_TOKEN_MAP.get(word_lower, word)
```

---

## Amendment 6: P2.2 Immutable Config — `replace()` Fails on Path Fields

**Plan text**: `replace(self, log_dir=_ensure_writable_directory(...))`  
**Issue**: `_ensure_writable_directory` has side effects (creates dirs, writes probe file). Calling it inside `replace()` during config construction is fine, but:
- `replace()` creates *new* instance; old instance's dirs may differ
- If `ensure_directories()` called multiple times, probe file race (L7)

**Fix**: Make `_ensure_writable_directory` pure (no probe file) or accept that dirs are created lazily on first use.

```python
def _ensure_writable_directory(primary: Path, fallback: Path) -> Path:
    try:
        primary.mkdir(parents=True, exist_ok=True)
        # Remove probe file; trust mkdir
        return primary
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
```

**Rationale**: `mkdir(parents=True, exist_ok=True)` is atomic enough; probe file adds TOCTOU without real benefit.

---

## Amendment 7: P3.1 Model Options — `large-v3` Requires Multilingual Config

**Plan text**: Add `("large-v3", "large-v3")` to `MODEL_OPTIONS`  
**Issue**: `large-v3` is multilingual; current `stt_language` default "en" works, but:
- `WhisperTranscriber` hardcodes `language="en"` in `transcribe_samples` (fixed in P1.2 ✓)
- `base.en`/`tiny.en`/`small.en` are English-only; `large-v3` ignores `.en` suffix
- TUI should disable language selector for `.en` models, or warn

**Fix**: Add model metadata:
```python
MODEL_METADATA = {
    "tiny.en": {"multilingual": False, "size_mb": 39},
    "base.en": {"multilingual": False, "size_mb": 74},
    "small.en": {"multilingual": False, "size_mb": 244},
    "medium.en": {"multilingual": False, "size_mb": 769},
    "large-v3": {"multilingual": True, "size_mb": 1550},
}
```
TUI: Show warning if multilingual model selected but `stt_language="en"` (works but suboptimal).

---

## Additional Edge Cases Not in Plan

| Edge Case | Risk | Mitigation |
|-----------|------|------------|
| `sounddevice` not installed | `list_input_devices` returns `[]` silently | Diagnostics already catches; TUI shows empty list |
| `ffmpeg`/`espeak-ng` missing | Fixture generation fails | E2E tests skip gracefully; document deps |
| Multiple TUI instances | Shared config mutation | Immutable config (P2.2) fixes |
| Network timeout on Google Translate | Blocks pipeline | `deep_translator` has no timeout param; wrap in `asyncio.wait_for` or thread with timeout |
| `faster_whisper` version mismatch | API changes | Pin version in `pyproject.toml` |

---

## Final Amended Plan Integration

Apply these 7 amendments to MASTER_STITCH_PLAN.md before execution. Priority order unchanged.

**Sign-off**: ✅ Approved with amendments.

---

*End of Clean-Context Architectural Review*