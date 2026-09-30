from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class AudioSource(Protocol):
    """Protocol for audio input sources."""

    def iter_chunks(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[np.ndarray]: ...
    def __enter__(self) -> AudioSource: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...


@runtime_checkable
class Transcriber(Protocol):
    """Protocol for speech-to-text backends."""

    def transcribe_path(self, audio_path: Path) -> list[str]: ...
    def transcribe_samples(self, samples: np.ndarray, sample_rate: int) -> list[str]: ...
    def normalise_segments(self, segments: Iterable[str]) -> str: ...

    @property
    def status(self) -> STTStatus: ...

    def close(self) -> None: ...


@runtime_checkable
class Translator(Protocol):
    """Protocol for translation backends."""

    def translate(self, text: str) -> TranslationResult: ...


# Re-export dataclasses for type hints
from .stt import STTStatus
from .translate import TranslationResult
