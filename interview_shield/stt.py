from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from faster_whisper import WhisperModel
else:
    try:
        from faster_whisper import WhisperModel
    except ImportError:  # pragma: no cover - handled by diagnostics
        WhisperModel = None


@dataclass(slots=True)
class STTStatus:
    requested_device: str
    actual_device: str
    model_name: str
    compute_type: str
    error: str | None = None


class WhisperTranscriber:
    def __init__(
        self,
        model_name: str = "base.en",
        requested_device: str = "auto",
        cache_dir: Path | None = None,
        language: str = "en",
        compute_type: str = "auto",
    ) -> None:
        if WhisperModel is None:
            raise RuntimeError("faster-whisper is not installed in the active runtime")
        self.model_name = model_name
        self.requested_device = requested_device
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "faster_whisper")
        self.language = language
        self.compute_type = compute_type
        self.status = self._load_model()

    def _load_model(self) -> STTStatus:
        candidates: list[tuple[str, str]]
        if self.compute_type != "auto":
            # User-specified compute type
            if self.requested_device == "cpu":
                candidates = [("cpu", self.compute_type)]
            elif self.requested_device == "cuda":
                candidates = [("cuda", self.compute_type), ("cpu", "int8")]
            else:
                candidates = [("cuda", self.compute_type), ("cpu", "int8")]
        else:
            # Auto-select compute type
            if self.requested_device == "cpu":
                candidates = [("cpu", "int8")]
            elif self.requested_device == "cuda":
                candidates = [("cuda", "float16"), ("cpu", "int8")]
            else:
                candidates = [("cuda", "float16"), ("cpu", "int8")]

        # Ensure cache directory exists before model initialization
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []
        for device, compute_type in candidates:
            try:
                self.model = WhisperModel(
                    self.model_name,
                    device=device,
                    compute_type=compute_type,
                    download_root=str(self.cache_dir)
                )
                return STTStatus(
                    requested_device=self.requested_device,
                    actual_device=device,
                    model_name=self.model_name,
                    compute_type=compute_type,
                )
            except Exception as exc:  # pragma: no cover - depends on host runtime
                errors.append(f"{device}/{compute_type}: {exc}")

        raise RuntimeError("Unable to initialise WhisperModel: " + " | ".join(errors))

    def transcribe_path(self, audio_path: Path) -> list[str]:
        segments, _ = self.model.transcribe(str(audio_path), beam_size=3)
        return [segment.text.strip() for segment in segments if segment.text.strip()]

    def transcribe_samples(self, samples: np.ndarray, sample_rate: int = 16_000) -> list[str]:
        audio = samples.astype(np.float32)
        segments, _ = self.model.transcribe(audio, beam_size=3, language=self.language)
        return [segment.text.strip() for segment in segments if segment.text.strip()]

    @staticmethod
    def normalise_segments(segments: Iterable[str]) -> str:
        return " ".join(part.strip() for part in segments if part.strip()).strip()
    def close(self) -> None:
        if getattr(self, "model", None) is not None:
            del self.model
            self.model = None
            
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
