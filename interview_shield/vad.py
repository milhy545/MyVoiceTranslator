from __future__ import annotations

import numpy as np


class EnergyVAD:
    """Voice Activity Detector based on frame RMS and adaptive noise floor."""

    def __init__(
        self,
        sample_rate: int = 16_000,
        min_threshold: float = 0.015,
        speech_multiplier: float = 2.5,
        adaptation_rate: float = 0.05,
        initial_noise_floor: float = 0.005,
    ) -> None:
        self.sample_rate = sample_rate
        self.min_threshold = min_threshold
        self.speech_multiplier = speech_multiplier
        self.adaptation_rate = adaptation_rate
        self.initial_noise_floor = initial_noise_floor
        self.noise_floor = initial_noise_floor
        self.last_rms: float = 0.0
        self.last_is_speech: bool = False

    def calculate_rms(self, frame: np.ndarray) -> float:
        """Calculate the Root Mean Square (RMS) energy of an audio frame."""
        if frame is None or len(frame) == 0:
            return 0.0
        frame_f = frame
        if frame_f.ndim > 1:
            frame_f = frame_f.mean(axis=1)
        if frame_f.dtype != np.float32:
            if np.issubdtype(frame_f.dtype, np.integer):
                frame_f = frame_f.astype(np.float32) / 32768.0
            else:
                frame_f = frame_f.astype(np.float32)
        elif frame_f.size > 0 and np.max(np.abs(frame_f)) > 1.5:
            frame_f = frame_f / 32768.0
        return float(np.sqrt(np.mean(frame_f**2)))

    @property
    def threshold(self) -> float:
        """Dynamic speech threshold based on adaptive noise floor."""
        return max(self.min_threshold, self.noise_floor * self.speech_multiplier)

    def is_speech(self, frame: np.ndarray) -> bool:
        """Determine if a frame contains speech, updating noise floor on silence."""
        rms = self.calculate_rms(frame)
        self.last_rms = rms
        thresh = self.threshold
        is_speech = rms >= thresh

        if not is_speech:
            # Adapt noise floor during silence frames
            self.noise_floor = (1.0 - self.adaptation_rate) * self.noise_floor + self.adaptation_rate * rms
            self.noise_floor = max(1e-5, min(self.noise_floor, 0.5))

        self.last_is_speech = is_speech
        return is_speech

    def reset(self) -> None:
        """Reset noise floor and state to initial configuration."""
        self.noise_floor = self.initial_noise_floor
        self.last_rms = 0.0
        self.last_is_speech = False


class SpeechSegmenter:
    """State machine segmenting streaming audio chunks into speech utterances.

    Handles onset confirmation, speech accumulation, silence offset detection,
    maximum segment timeout flushes, sliding overlap carryover, and background
    silence suppression.
    """

    def __init__(
        self,
        vad: EnergyVAD | None = None,
        sample_rate: int = 16_000,
        vad_silence_seconds: float = 0.5,
        vad_max_seconds: float = 8.0,
        vad_min_speech_seconds: float = 0.4,
        overlap_seconds: float = 0.2,
        onset_frames: int = 1,
    ) -> None:
        self.vad = vad if vad is not None else EnergyVAD(sample_rate=sample_rate)
        self.sample_rate = sample_rate
        self.vad_silence_seconds = vad_silence_seconds
        self.vad_max_seconds = vad_max_seconds
        self.vad_min_speech_seconds = vad_min_speech_seconds
        self.overlap_seconds = overlap_seconds
        self.onset_frames = max(1, onset_frames)

        self._buffer: list[np.ndarray] = []
        self._pending_frames: list[np.ndarray] = []
        self._overlap_buffer: np.ndarray | None = None
        self._in_speech: bool = False
        self._consecutive_speech: int = 0
        self._consecutive_silence: int = 0
        self._speech_seconds: float = 0.0
        self._silence_seconds: float = 0.0

    @property
    def in_speech(self) -> bool:
        """Whether the segmenter is currently within an active speech utterance."""
        return self._in_speech

    @property
    def state(self) -> str:
        """Current audio state: 'speaking' or 'listening'."""
        return "speaking" if self._in_speech else "listening"

    @property
    def consecutive_speech_frames(self) -> int:
        return self._consecutive_speech

    @property
    def consecutive_silence_frames(self) -> int:
        return self._consecutive_silence

    @property
    def speech_seconds(self) -> float:
        return self._speech_seconds

    @property
    def silence_seconds(self) -> float:
        return self._silence_seconds

    def _normalize_chunk(self, chunk: np.ndarray) -> np.ndarray:
        if chunk.ndim > 1:
            chunk = chunk.mean(axis=1)
        if chunk.dtype != np.float32:
            if np.issubdtype(chunk.dtype, np.integer):
                chunk = chunk.astype(np.float32) / 32768.0
            else:
                chunk = chunk.astype(np.float32)
        elif chunk.size > 0 and np.max(np.abs(chunk)) > 1.5:
            chunk = chunk / 32768.0
        return chunk

    def _save_overlap(self, audio: np.ndarray) -> None:
        overlap_samples = int(self.sample_rate * self.overlap_seconds)
        if len(audio) > overlap_samples:
            self._overlap_buffer = audio[-overlap_samples:].copy()
        else:
            self._overlap_buffer = audio.copy()

    def _reset_segment(self) -> None:
        self._buffer.clear()
        self._pending_frames.clear()
        self._in_speech = False
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._speech_seconds = 0.0
        self._silence_seconds = 0.0

    def process_chunk(self, chunk: np.ndarray) -> tuple[bool, np.ndarray | None]:
        """Process an incoming audio chunk and return (should_flush, audio_to_flush)."""
        if chunk is None or len(chunk) == 0:
            return False, None

        chunk = self._normalize_chunk(chunk)
        chunk_duration = len(chunk) / self.sample_rate
        is_speech = self.vad.is_speech(chunk)

        if not self._in_speech:
            if is_speech:
                self._consecutive_speech += 1
                self._pending_frames.append(chunk)
                if self._consecutive_speech >= self.onset_frames:
                    # Speech onset confirmed
                    self._in_speech = True
                    if self._overlap_buffer is not None:
                        self._buffer.append(self._overlap_buffer)
                        self._overlap_buffer = None
                    self._buffer.extend(self._pending_frames)
                    self._speech_seconds += sum(len(f) for f in self._pending_frames) / self.sample_rate
                    self._pending_frames.clear()
                    self._silence_seconds = 0.0
                    self._consecutive_silence = 0
                return False, None
            else:
                # Silence outside of speech - drop pure background silence
                self._consecutive_speech = 0
                self._pending_frames.clear()
                return False, None

        # Already in active speech
        if is_speech:
            self._consecutive_speech += 1
            self._consecutive_silence = 0
            self._silence_seconds = 0.0
            self._speech_seconds += chunk_duration
            self._buffer.append(chunk)

            # Check max timeout for unbroken speech
            total_duration = sum(len(c) for c in self._buffer) / self.sample_rate
            if total_duration >= self.vad_max_seconds:
                audio_to_flush = np.concatenate(self._buffer)
                self._save_overlap(audio_to_flush)
                # For unbroken speech, carry overlap forward into new buffer immediately
                self._buffer = [self._overlap_buffer.copy()] if self._overlap_buffer is not None else []
                self._speech_seconds = len(self._buffer[0]) / self.sample_rate if self._buffer else 0.0
                self._silence_seconds = 0.0
                self._overlap_buffer = None
                self._in_speech = True
                return True, audio_to_flush

            return False, None
        else:
            # Trailing silence within active utterance
            self._consecutive_silence += 1
            self._consecutive_speech = 0
            self._silence_seconds += chunk_duration
            self._buffer.append(chunk)

            if self._silence_seconds >= self.vad_silence_seconds:
                if self._speech_seconds >= self.vad_min_speech_seconds:
                    audio_to_flush = np.concatenate(self._buffer)
                    self._save_overlap(audio_to_flush)
                    self._reset_segment()
                    return True, audio_to_flush
                else:
                    # Short burst (< vad_min_speech_seconds) rejected
                    self._reset_segment()
                    return False, None

            return False, None

    def flush_remaining(self) -> tuple[bool, np.ndarray | None]:
        """Flush any remaining valid speech when audio stream/capture ends."""
        if self._in_speech and self._buffer and self._speech_seconds >= self.vad_min_speech_seconds:
            audio_to_flush = np.concatenate(self._buffer)
            self._reset_segment()
            self._overlap_buffer = None
            return True, audio_to_flush

        self._reset_segment()
        self._overlap_buffer = None
        return False, None

    def reset(self) -> None:
        """Reset segmenter and underlying VAD state completely."""
        self._reset_segment()
        self._overlap_buffer = None
        self.vad.reset()
