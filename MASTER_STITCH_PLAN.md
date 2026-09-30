# Master Stitch Plan — MyVoiceTranslator Remediation

**Generated**: 2025-09-11  
**From**: Unified Critical Review Report  
**Strategy**: Incremental, test-preserving, backward-compatible. Each fix is independent and verifiable.

---

## Phase 0: Immediate Blockers (Do First)

### P0.1 — Fix Hardcoded Whisper Cache Path (B1)
**File**: `interview_shield/stt.py`  
**Change**: Replace hardcoded path with config-driven cache dir.

```python
# BEFORE (line 51)
self.model = WhisperModel(
    self.model_name,
    device=device,
    compute_type=compute_type,
    download_root="/home/milhy777/LLM/Whisper"
)

# AFTER
from .config import AppConfig  # or pass cache_dir to constructor

class WhisperTranscriber:
    def __init__(
        self,
        model_name: str = "base.en",
        requested_device: str = "auto",
        cache_dir: Path | None = None,  # NEW
    ) -> None:
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "faster_whisper")
        # ...
    
    def _load_model(self) -> STTStatus:
        # ...
        self.model = WhisperModel(
            self.model_name,
            device=device,
            compute_type=compute_type,
            download_root=str(self.cache_dir),  # USE cache_dir
        )
```

**Pipeline wiring** (`pipeline.py:38`):
```python
self.transcriber = WhisperTranscriber(
    model_name=config.stt_model,
    requested_device=config.stt_device,
    cache_dir=config.state_dir / "whisper_models",  # NEW
)
```

**Config addition** (`config.py`): No new field needed; reuse `state_dir`.

**Verification**: Run on clean machine / different user; model downloads to `~/.local/state/myvoicetranslator/whisper_models`.

---

### P0.2 — Wire `config.chunk_seconds` to Audio Sources (C2)
**Files**: `interview_shield/pipeline.py`, `interview_shield/audio.py`

**Pipeline** (`pipeline.py:78, 107`):
```python
# BEFORE
source = WavChunkSource(wav_path=wav_path, sample_rate=..., chunk_seconds=1.0)
source = SoundDeviceSource(..., chunk_seconds=1.0)

# AFTER
source = WavChunkSource(
    wav_path=wav_path,
    sample_rate=self.config.sample_rate,
    chunk_seconds=self.config.chunk_seconds,  # USE CONFIG
)
# and
source = SoundDeviceSource(
    sample_rate=self.config.sample_rate,
    channels=self.config.channels,
    chunk_seconds=self.config.chunk_seconds,  # USE CONFIG
    ...
)
```

**Audio sources** (`audio.py:138, 184`): Remove default `chunk_seconds=1.0`; make required param.

```python
# WavChunkSource.__init__
def __init__(self, wav_path: Path, sample_rate: int, chunk_seconds: float) -> None:
    self.chunk_frames = int(sample_rate * chunk_seconds)

# SoundDeviceSource.__init__
def __init__(
    self,
    sample_rate: int,
    channels: int,
    chunk_seconds: float,  # REQUIRED
    device_name: str | None = None,
    input_mode: str = "auto",
) -> None:
    self.chunk_frames = int(sample_rate * chunk_seconds)
```

**Default in config** (`config.py:14`): Keep `chunk_seconds: float = 8.0` (or reduce to 2.0-4.0 for lower latency; 8s is high).

**Verification**: `test_file_pipeline_offline_e2e` still passes; debug bundle shows chunk timing.

---

### P0.3 — Add WhisperTranscriber Close / Context Manager (C3)
**File**: `interview_shield/stt.py`

```python
class WhisperTranscriber:
    def __init__(self, ...) -> None:
        # ...
        self._model: WhisperModel | None = None
    
    def _load_model(self) -> STTStatus:
        # ...
        self._model = WhisperModel(...)
        return STTStatus(...)
    
    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            raise RuntimeError("Model not loaded")
        return self._model
    
    def close(self) -> None:
        """Release GPU memory held by ctranslate2."""
        if self._model is not None:
            # ctranslate2 models don't have explicit close; drop ref
            self._model = None
            # Force GC for CUDA memory
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
    
    def __enter__(self) -> "WhisperTranscriber":
        return self
    
    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
```

**Pipeline cleanup** (`pipeline.py`):
```python
def run_live(self, stop_event: threading.Event | None = None) -> PipelineRun:
    try:
        # ... existing code ...
    finally:
        self.transcriber.close()  # NEW
        self._status("info", "Live capture stopped.")
```

**Verification**: Run TUI, "Apply + Restart" 5x; check `nvidia-smi` memory stable.

---

### P0.4 — Cache `list_input_devices` Result (C1, M3)
**File**: `interview_shield/audio.py`

```python
# Module-level cache
_cached_devices: list[AudioDeviceInfo] | None = None
_cache_valid = False

def list_input_devices(force_refresh: bool = False) -> list[AudioDeviceInfo]:
    global _cached_devices, _cache_valid
    if _cache_valid and not force_refresh and _cached_devices is not None:
        return _cached_devices
    
    # ... existing subprocess logic ...
    _cached_devices = devices
    _cache_valid = True
    return devices

def invalidate_device_cache() -> None:
    global _cache_valid
    _cache_valid = False
```

**TUI refresh** (`tui.py:159`):
```python
def action_refresh_devices(self) -> None:
    from .audio import invalidate_device_cache
    invalidate_device_cache()
    current_device = self.config.device_name
    self._load_devices()  # now calls list_input_devices(force_refresh=True)
    # ...
```

**Modify `_load_devices`** (`tui.py:153`):
```python
def _load_devices(self) -> None:
    self.available_devices = list_input_devices(force_refresh=True)
    # ...
```

**Verification**: TUI mount + refresh button fast (<50ms after first load).

---

## Phase 1: Core Logic Fixes (High Severity)

### P1.1 — Fix LocalFallbackTokenizer (H1)
**File**: `interview_shield/translate.py`

```python
# REPLACE entire LocalFallbackTranslator.translate method
class LocalFallbackTranslator:
    backend_name = "local"
    
    # Simple word-for-word with punctuation preservation
    def translate(self, text: str) -> TranslationResult:
        # Split on word boundaries, keep punctuation attached to preceding word
        import re
        # Pattern: word chars + optional trailing punctuation, or standalone punctuation
        tokens = re.findall(r"\w+(?:[.,!?;:]*)|[.,!?;:]+", text, flags=re.UNICODE)
        translated_tokens = []
        for token in tokens:
            # Separate word from trailing punctuation
            match = re.match(r"^(\w+)([.,!?;:]*)$", token, flags=re.UNICODE)
            if match:
                word, punct = match.groups()
                translated = LOCAL_TOKEN_MAP.get(word.lower(), word)
                translated_tokens.append(translated + punct)
            else:
                translated_tokens.append(token)
        
        # Join with spaces, but don't add space before punctuation
        translated = ""
        for i, token in enumerate(translated_tokens):
            if i == 0:
                translated = token
            elif re.match(r"^[.,!?;:]+$", token):
                translated += token
            else:
                translated += " " + token
        
        return TranslationResult(text=translated, backend=self.backend_name, online_ok=False)
```

**Add more tokens to LOCAL_TOKEN_MAP** (expand to ~50 common words):
```python
LOCAL_TOKEN_MAP = {
    # Original
    "good": "dobré", "morning": "ráno", "python": "python",
    "automation": "automatizace", "works": "funguje",
    "offline": "offline", "online": "online", "and": "a",
    # Expanded
    "hello": "ahoj", "hi": "ahoj", "bye": "nashledanou",
    "yes": "ano", "no": "ne", "please": "prosím",
    "thank": "děkuji", "thanks": "děkuji", "you": "vy",
    "the": "", "a": "", "an": "", "is": "je", "are": "jsou",
    "was": "bylo", "were": "byly", "have": "mám", "has": "má",
    "do": "dělám", "does": "dělá", "did": "udělal",
    "will": "budu", "would": "bych", "can": "mohu", "could": "mohl",
    "should": "měl", "must": "musím", "want": "chci",
    "need": "potřebuji", "like": "mám rád", "love": "miluje",
    "time": "čas", "day": "den", "night": "noc",
    "today": "dnes", "tomorrow": "zítra", "yesterday": "včera",
    "meeting": "schůzka", "call": "hovor", "interview": "pohovor",
    "question": "otázka", "answer": "odpověď", "problem": "problém",
    "solution": "řešení", "test": "test", "code": "kód",
    "bug": "chyba", "fix": "oprava", "deploy": "nasazení",
}
```

**Verification**: Unit test for `LocalFallbackTranslator` (new test file).

---

### P1.2 — Make STT Language Configurable (H2)
**Files**: `config.py`, `stt.py`, `pipeline.py`, `tui.py`

**Config** (`config.py`):
```python
@dataclass(slots=True)
class AppConfig:
    # ...
    stt_language: str = "en"  # NEW
    # ...
    @classmethod
    def from_env(cls) -> "AppConfig":
        # ...
        cfg.stt_language = os.environ.get("MVT_STT_LANGUAGE", cfg.stt_language)
```

**STT** (`stt.py:67`):
```python
def transcribe_samples(self, samples: np.ndarray, sample_rate: int = 16_000) -> list[str]:
    audio = samples.astype(np.float32)
    segments, _ = self.model.transcribe(
        audio, 
        beam_size=3, 
        language=self.language,  # USE CONFIG
    )
    return [segment.text.strip() for segment in segments if segment.text.strip()]

# Add language to __init__
def __init__(self, model_name: str = "base.en", requested_device: str = "auto", language: str = "en") -> None:
    self.language = language
    # ...
```

**Pipeline** (`pipeline.py:38`):
```python
self.transcriber = WhisperTranscriber(
    model_name=config.stt_model,
    requested_device=config.stt_device,
    language=config.stt_language,  # NEW
    cache_dir=config.state_dir / "whisper_models",
)
```

**TUI** (`tui.py`): Add language selector to MODEL_OPTIONS or new STT_LANGUAGE_OPTIONS.

**Verification**: Test with Czech audio + `stt_language="cs"`.

---

### P1.3 — Remove Dead ElevenLabs Code or Implement (H3)
**Decision**: Remove for now (YAGNI).  
**File**: `translate.py` — delete lines 84, and `self.elevenlabs_api_key` reference.

---

### P1.4 — Fix TUI Force Offline Toggle (H4)
**File**: `interview_shield/tui.py:377`

```python
def action_toggle_offline(self) -> None:
    self.force_offline_switch.value = not self.force_offline_switch.value
    self._mark_controls_dirty(f"Force offline -> {self.force_offline_switch.value}")  # ADD
```

---

## Phase 2: Architecture Improvements (Medium)

### P2.1 — Define Protocol Interfaces (M1)
**New file**: `interview_shield/interfaces.py`

```python
from __future__ import annotations
from typing import Protocol, Iterator
from pathlib import Path
import numpy as np
from .events import TranscriptEvent, StatusEvent

class AudioSource(Protocol):
    def iter_chunks(self, stop_event: threading.Event | None = None) -> Iterator[np.ndarray]: ...
    def __enter__(self) -> AudioSource: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...

class Transcriber(Protocol):
    def transcribe_path(self, audio_path: Path) -> list[str]: ...
    def transcribe_samples(self, samples: np.ndarray, sample_rate: int) -> list[str]: ...
    def normalise_segments(self, segments: Iterator[str]) -> str: ...
    @property
    def status(self) -> STTStatus: ...
    def close(self) -> None: ...

class Translator(Protocol):
    def translate(self, text: str) -> TranslationResult: ...
```

**Pipeline** (`pipeline.py`): Accept injected instances (already does via callbacks; just type-hint with Protocol).

```python
def __init__(
    self,
    config: AppConfig,
    logger: SessionLogger,
    audio_source_factory: Callable[[], AudioSource] | None = None,
    transcriber: Transcriber | None = None,
    translator: Translator | None = None,
    ...
) -> None:
    self.transcriber = transcriber or WhisperTranscriber(...)
    self.translator = translator or HybridTranslator(...)
    self._audio_source_factory = audio_source_factory or self._default_audio_source
```

**Benefit**: Unit tests can inject fakes without subprocess/mock hell.

---

### P2.2 — Make Config Immutable (M2)
**File**: `config.py`

```python
@dataclass(frozen=True, slots=True)  # ADD frozen=True
class AppConfig:
    # ...
    
    def with_changes(self, **kwargs) -> "AppConfig":
        """Return new config with specified fields changed."""
        return replace(self, **kwargs)
    
    def ensure_directories(self) -> "AppConfig":
        """Return new config with ensured directories."""
        return replace(
            self,
            log_dir=_ensure_writable_directory(self.log_dir, Path.cwd() / "logs"),
            state_dir=_ensure_writable_directory(self.state_dir, Path.cwd() / ".runtime" / "state"),
            artifacts_dir=_ensure_writable_directory(self.artifacts_dir, Path.cwd() / ".runtime" / "artifacts"),
            fixture_dir=_ensure_writable_directory(self.fixture_dir, Path.cwd() / "test_audio"),
        )
```

**TUI** (`tui.py`): Instead of mutating `self.config`, create new config on apply:
```python
def _apply_and_restart(self) -> None:
    new_config = self.config.with_changes(
        input_mode=self.input_mode_select.value,
        device_name=None if self.device_select.value == self.AUTO_DEVICE_VALUE else self.device_select.value,
        stt_device=self.stt_device_select.value,
        stt_model=self.model_select.value,
        online_backend=self.online_backend_select.value,
        force_offline=self.force_offline_switch.value,
    ).ensure_directories()
    self.config = new_config
    self.controls_dirty = False
    # ... restart pipeline with new config
```

**Note**: Requires `from dataclasses import replace`.

---

### P2.3 — Fix SoundDeviceSource Callback (M4)
**File**: `audio.py:160`

```python
def _callback(self, indata, frames, time_info, status) -> None:
    del frames, time_info, status
    # Put raw view; avoid copy/flatten in callback
    self._queue.put(indata[:, 0] if indata.ndim > 1 else indata)  # first channel view
```

**Consumer** (`iter_chunks`):
```python
def iter_chunks(self, stop_event: threading.Event | None = None) -> Iterator[np.ndarray]:
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            chunk = self._queue.get(timeout=0.5)
            yield chunk.astype(np.float32) / 32768.0  # normalize here
        except queue.Empty:
            if stop_event is not None and stop_event.is_set():
                break
            time.sleep(0.1)
```

---

### P2.4 — Structured Logging (M6)
**New file**: `interview_shield/structured_log.py`

```python
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def setup_structured_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("myvoicetranslator")
    logger.setLevel(logging.DEBUG)
    
    # JSONL file handler
    date_key = datetime.now().strftime("%Y%m%d")
    jsonl_path = log_dir / f"interview_{date_key}.jsonl"
    file_handler = logging.FileHandler(jsonl_path, encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    
    return logger

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {"name", "msg", "args", "created", "filename", "funcName", 
                          "levelname", "levelno", "lineno", "module", "msecs",
                          "message", "name", "pathname", "process", "processName",
                          "relativeCreated", "thread", "threadName", "exc_info",
                          "exc_text", "stack_info"}:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)
```

**SessionLogger** (`logging_utils.py`): Keep markdown for human view; add structured logger for machine parsing.

---

## Phase 3: TUI & UX Polish

### P3.1 — Add Missing Model/Compute Options (M8)
**File**: `tui.py`

```python
MODEL_OPTIONS = [
    ("tiny.en", "tiny.en"),
    ("base.en", "base.en"),
    ("small.en", "small.en"),
    ("medium.en", "medium.en"),
    ("large-v3", "large-v3"),  # multilingual
]

COMPUTE_TYPE_OPTIONS = [
    ("Auto", "auto"),
    ("Int8 (CPU/GPU)", "int8"),
    ("Float16 (GPU)", "float16"),
    ("Int8-Float16 (GPU)", "int8_float16"),
]

# Add to compose(), on_select_changed(), _sync_controls_from_config()
```

**STT** (`stt.py`): Accept `compute_type` parameter; override candidates.

---

### P3.2 — Debounce Status Bar Refresh (M5)
**File**: `tui.py`

```python
def __init__(self, config: AppConfig) -> None:
    # ...
    self._status_refresh_pending = False

def _refresh_status(self) -> None:
    if self._status_refresh_pending:
        return
    self._status_refresh_pending = True
    self.set_timer(0.1, self._do_refresh_status)

def _do_refresh_status(self) -> None:
    self._status_refresh_pending = False
    # ... existing _refresh_status logic ...
```

---

### P3.3 — Fix Keyboard Binding Consistency (L4)
**File**: `tui.py`

Either bind `o` to toggle the switch programmatically, or remove binding. Simpler: make switch toggle trigger `_mark_controls_dirty`.

```python
def on_switch_changed(self, event: Switch.Changed) -> None:
    if not self.control_events_enabled:
        return
    if event.switch.id == "force-offline-switch":
        self.config.force_offline = event.value
        self._mark_controls_dirty(f"Force offline -> {event.value}")
    # Remove action_toggle_offline entirely
```

---

## Phase 4: Tests & CI

### P4.1 — Add Unit Tests for Translators
**New file**: `tests/test_translate.py`

```python
import unittest
from interview_shield.translate import LocalFallbackTranslator, HybridTranslator, TranslationResult

class LocalFallbackTest(unittest.TestCase):
    def test_known_words(self):
        t = LocalFallbackTranslator()
        r = t.translate("good morning python")
        self.assertEqual(r.text, "dobré ráno python")
        self.assertEqual(r.backend, "local")
    
    def test_unknown_words_pass_through(self):
        t = LocalFallbackTranslator()
        r = t.translate("hello world")
        self.assertEqual(r.text, "hello world")
    
    def test_punctuation_handling(self):
        t = LocalFallbackTranslator()
        r = t.translate("good morning!")
        self.assertEqual(r.text, "dobré ráno!")

class HybridTranslatorTest(unittest.TestCase):
    def test_force_offline_uses_local(self):
        t = HybridTranslator(force_offline=True)
        r = t.translate("good morning")
        self.assertEqual(r.backend, "local")
```

### P4.2 — Mark E2E Tests as Integration
**File**: `tests/test_e2e.py`

```python
import pytest
# Add marker
pytestmark = pytest.mark.integration

# Or use unittest skipIf
import os
@unittest.skipUnless(os.environ.get("MVT_RUN_INTEGRATION"), "Integration test")
class ShieldE2ETest(unittest.TestCase):
    ...
```

**CI**: Run unit tests by default; integration tests only on scheduled/self-hosted runners.

---

### P4.3 — Add `py.typed` Marker
**File**: `interview_shield/py.typed` (empty file)

---

## Phase 5: Cleanup (Low)

### P5.1 — Remove Legacy Fixture Files (L6)
```bash
rm test_audio/test_audio.wav test_audio/sample.mp3
# Keep only fixture_voice.wav, fixture_voice.mp3
```

### P5.2 — Fix Datetime Timezone (L10)
**File**: `events.py`

```python
from datetime import datetime, timezone

@dataclass(slots=True)
class TranscriptEvent:
    # ...
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass(slots=True)
class StatusEvent:
    # ...
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### P5.3 — Type Check Fix (L3)
**File**: `stt.py`

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from faster_whisper import WhisperModel
else:
    WhisperModel = None  # type: ignore
```

---

## Execution Order & Dependencies

```
P0.1 ──► P0.2 ──► P0.3 ──► P0.4
  │       │       │       │
  ▼       ▼       ▼       ▼
P1.1    P1.2    P1.3    P1.4
  │       │       │       │
  ▼       ▼       ▼       ▼
P2.1    P2.2    P2.3    P2.4
  │       │       │       │
  ▼       ▼       ▼       ▼
P3.1    P3.2    P3.3    P4.1
  │       │       │       │
  ▼       ▼       ▼       ▼
P4.2    P4.3    P5.1    P5.2
  │       │       │       │
  ▼       ▼       ▼       ▼
P5.3 ──────────────────────► DONE
```

---

## Verification Checklist Per Phase

| Phase | Command | Expected |
|-------|---------|----------|
| P0 | `python -m unittest discover -s tests -v` | 11 passed |
| P0 | `python shield.py --offline --stt-device cpu test-file test_audio/fixture_voice.mp3` | JSON output with transcripts |
| P0 | TUI: mount → refresh devices → Apply+Restart ×5 | No GPU mem leak (`nvidia-smi`) |
| P1 | New unit tests | `python -m pytest tests/test_translate.py -v` passes |
| P1 | TUI: toggle offline → Apply highlights | Button shows dirty state |
| P2 | Unit tests with mocked Transcriber | Fast, no model download |
| P3 | TUI: model selector shows medium/large | Options present |
| P4 | CI pipeline | Unit tests < 10s; integration opt-in |

---

## Rollback Strategy

Each phase is a single commit. If regression:
```bash
git revert <commit-sha>
```
Config changes are backward-compatible (new fields with defaults). No breaking CLI changes.

---

*End of Master Stitch Plan*