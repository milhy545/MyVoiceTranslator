from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


def _default_state_dir() -> Path:
    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "myvoicetranslator"
    return Path.home() / ".local" / "state" / "myvoicetranslator"


def _default_log_dir() -> Path:
    return Path.home() / "logs"


@dataclass(frozen=True, slots=True)
class AppConfig:
    input_mode: str = "auto"
    device_name: str | None = None
    monitor_device_name: str | None = None
    online_backend: str = "google"
    offline_backend: str = "local"
    stt_device: str = "auto"
    stt_model: str = "base.en"
    stt_language: str = "en"
    stt_compute_type: str = "auto"
    sample_rate: int = 16_000
    channels: int = 1
    live_chunk_seconds: float = 1.0
    stt_chunk_seconds: float = 8.0
    live_poll_seconds: float = 0.2
    log_dir: Path = _default_log_dir()
    state_dir: Path = _default_state_dir()
    artifacts_dir: Path = _default_state_dir() / "artifacts"
    fixture_dir: Path = Path.cwd() / "test_audio"
    translation_model: str = "michaelfeil/ct2fast-opus-mt-en-cs"
    translation_device: str = "auto"
    translation_compute_type: str = "auto"
    force_offline: bool = False
    ui_enabled: bool = True
    vad_enabled: bool = True
    vad_silence_seconds: float = 0.5
    vad_max_seconds: float = 8.0
    vad_min_speech_seconds: float = 0.4

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            input_mode=os.environ.get("MVT_INPUT_MODE", "auto"),
            device_name=os.environ.get("MVT_DEVICE_NAME") or None,
            monitor_device_name=os.environ.get("MVT_MONITOR_DEVICE") or None,
            online_backend=os.environ.get("MVT_ONLINE_BACKEND", "google"),
            offline_backend=os.environ.get("MVT_OFFLINE_BACKEND", "local"),
            stt_device=os.environ.get("MVT_STT_DEVICE", "auto"),
            stt_model=os.environ.get("MVT_MODEL", "base.en"),
            stt_language=os.environ.get("MVT_STT_LANGUAGE", "en"),
            stt_compute_type=os.environ.get("MVT_STT_COMPUTE_TYPE", "auto"),
            translation_model=os.environ.get("MVT_TRANSLATION_MODEL", "michaelfeil/ct2fast-opus-mt-en-cs"),
            translation_device=os.environ.get("MVT_TRANSLATION_DEVICE", "auto"),
            translation_compute_type=os.environ.get("MVT_TRANSLATION_COMPUTE_TYPE", "auto"),
            force_offline=os.environ.get("MVT_FORCE_OFFLINE", "0") == "1",
            log_dir=Path(os.environ.get("MVT_LOG_DIR", str(_default_log_dir()))).expanduser(),
            state_dir=Path(os.environ.get("MVT_STATE_DIR", str(_default_state_dir()))).expanduser(),
            artifacts_dir=Path(
                os.environ.get("MVT_ARTIFACT_DIR", str(_default_state_dir() / "artifacts"))
            ).expanduser(),
            vad_enabled=os.environ.get("MVT_VAD_ENABLED", "1").lower() not in {"0", "false", "no"},
            vad_silence_seconds=float(os.environ.get("MVT_VAD_SILENCE_SECONDS", "0.5")),
            vad_max_seconds=float(os.environ.get("MVT_VAD_MAX_SECONDS", "8.0")),
            vad_min_speech_seconds=float(os.environ.get("MVT_VAD_MIN_SPEECH_SECONDS", "0.4")),
        )

    def with_changes(self, **kwargs) -> AppConfig:
        """Return new config with specified fields changed."""
        return replace(self, **kwargs)

    def ensure_directories(self) -> AppConfig:
        """Return new config with ensured directories."""
        return replace(
            self,
            log_dir=_ensure_writable_directory(self.log_dir, Path.cwd() / "logs"),
            state_dir=_ensure_writable_directory(self.state_dir, Path.cwd() / ".runtime" / "state"),
            artifacts_dir=_ensure_writable_directory(self.artifacts_dir, Path.cwd() / ".runtime" / "artifacts"),
            fixture_dir=_ensure_writable_directory(self.fixture_dir, Path.cwd() / "test_audio"),
        )


def _ensure_writable_directory(primary: Path, fallback: Path) -> Path:
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback