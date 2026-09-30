from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from queue import Queue

import numpy as np

from .audio import DualAudioSource, SoundDeviceSource, WavChunkSource
from .config import AppConfig
from .events import StatusEvent, TranscriptEvent
from .interfaces import AudioSource, Transcriber, Translator
from .logging_utils import SessionLogger
from .stt import WhisperTranscriber
from .translate import HybridTranslator
from .vad import EnergyVAD, SpeechSegmenter


@dataclass(slots=True)
class PipelineRun:
    transcripts: list[TranscriptEvent]
    status_events: list[StatusEvent]
    debug_bundle: Path | None = None


class InterviewShieldPipeline:
    def __init__(
        self,
        config: AppConfig,
        logger: SessionLogger,
        on_partial_transcript: Callable[[TranscriptEvent], None] | None = None,
        on_transcript: Callable[[TranscriptEvent], None] | None = None,
        on_status: Callable[[StatusEvent], None] | None = None,
        on_audio_state: Callable[[str], None] | None = None,
        transcriber: Transcriber | None = None,
        translator: Translator | None = None,
        segmenter: SpeechSegmenter | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.on_partial_transcript = on_partial_transcript
        self.on_transcript = on_transcript
        self.on_status = on_status
        self.on_audio_state = on_audio_state
        self.audio_state: str = "Listening"
        self.transcriber = transcriber or WhisperTranscriber(
            model_name=config.stt_model,
            requested_device=config.stt_device,
            cache_dir=config.state_dir / "whisper_models",
            language=config.stt_language,
            compute_type=config.stt_compute_type,
        )
        self.translator = translator or HybridTranslator(
            online_backend=config.online_backend,
            force_offline=config.force_offline,
            model_name=config.translation_model,
            cache_dir=config.state_dir / "translation_models",
            device=config.translation_device,
            compute_type=config.translation_compute_type,
        )
        if segmenter is not None:
            self.segmenter: SpeechSegmenter | None = segmenter
        elif config.vad_enabled:
            self.segmenter = SpeechSegmenter(
                vad=EnergyVAD(sample_rate=config.sample_rate),
                sample_rate=config.sample_rate,
                vad_silence_seconds=config.vad_silence_seconds,
                vad_max_seconds=config.vad_max_seconds,
                vad_min_speech_seconds=config.vad_min_speech_seconds,
            )
        else:
            self.segmenter = None

        self.transcripts: list[TranscriptEvent] = []
        self.status_events: list[StatusEvent] = []
        self._stt_queue: Queue[tuple[np.ndarray, str] | None] = Queue()
        self._stt_thread: threading.Thread | None = None

        if isinstance(self.translator, HybridTranslator):
            if self.translator.nmt_error:
                self._status("warning", f"NMT unavailable ({self.translator.nmt_error}), using fallback")
            else:
                self._status("info", f"Translation active backend: {self.translator.active_backend_name}")

    def _set_audio_state(self, state: str) -> None:
        if self.audio_state != state:
            self.audio_state = state
            if self.on_audio_state is not None:
                self.on_audio_state(state)

    def _status(self, level: str, message: str) -> None:
        event = StatusEvent(level=level, message=message)
        self.status_events.append(event)
        self.logger.log_status(event)
        if self.on_status is not None:
            self.on_status(event)

    def _emit_transcript(self, english: str, input_mode: str) -> TranscriptEvent:
        partial = TranscriptEvent(
            english=english,
            input_mode=input_mode,
            phase="captured",
        )
        if self.on_partial_transcript is not None:
            self.on_partial_transcript(partial)

        translated = self.translator.translate(english)
        event = TranscriptEvent(
            english=english,
            input_mode=input_mode,
            czech=translated.text or "[translation unavailable]",
            backend=translated.backend,
            phase="translated",
        )
        self.transcripts.append(event)
        self.logger.log_transcript(event)
        if self.on_transcript is not None:
            self.on_transcript(event)
        if translated.error:
            self._status("warning", f"Translation fallback active: {translated.error}")
        return event

    def run_file(self, audio_path: Path) -> PipelineRun:
        self._status("info", f"Processing audio file: {audio_path}")
        self._set_audio_state("Transcribing")
        try:
            text = self.transcriber.normalise_segments(self.transcriber.transcribe_path(audio_path))
            if text:
                self._emit_transcript(text, input_mode="file")
        finally:
            self._set_audio_state("Listening")
        return PipelineRun(self.transcripts, self.status_events)

    def _start_worker(self) -> None:
        self._stt_queue = Queue()
        self._stt_thread = threading.Thread(target=self._stt_worker_loop, daemon=True)
        self._stt_thread.start()
        
    def _stop_worker(self) -> None:
        if self._stt_thread is not None:
            self._stt_queue.put(None)
            self._stt_thread.join()
            self._stt_thread = None

    def _stt_worker_loop(self) -> None:
        while True:
            item = self._stt_queue.get()
            if item is None:
                self._stt_queue.task_done()
                break
            
            joined, input_mode = item
            self._set_audio_state("Transcribing")
            try:
                text = self.transcriber.normalise_segments(
                    self.transcriber.transcribe_samples(joined, self.config.sample_rate)
                )
                if text:
                    self._emit_transcript(text, input_mode=input_mode)
            except Exception as e:
                self._status("error", f"STT processing failed: {e}")
            finally:
                self._set_audio_state("Listening")
                self._stt_queue.task_done()

    def run_simulated_live(self, wav_path: Path, input_mode: str) -> PipelineRun:
        self._status("info", f"Simulated live input: {input_mode} from {wav_path}")
        source = WavChunkSource(
            wav_path=wav_path,
            sample_rate=self.config.sample_rate,
            chunk_seconds=self.config.live_chunk_seconds,
        )
        self._start_worker()
        try:
            if not self.config.vad_enabled:
                buffer: list[np.ndarray] = []
                frame_count = 0
                frame_threshold = int(self.config.sample_rate * self.config.stt_chunk_seconds)
                for chunk in source.iter_chunks():
                    buffer.append(chunk)
                    frame_count += len(chunk)
                    if frame_count >= frame_threshold:
                        self._flush_buffer(buffer, input_mode)
                        buffer = []
                        frame_count = 0
                self._flush_buffer(buffer, input_mode)
            else:
                segmenter = self.segmenter or SpeechSegmenter(
                    vad=EnergyVAD(sample_rate=self.config.sample_rate),
                    sample_rate=self.config.sample_rate,
                    vad_silence_seconds=self.config.vad_silence_seconds,
                    vad_max_seconds=self.config.vad_max_seconds,
                    vad_min_speech_seconds=self.config.vad_min_speech_seconds,
                )
                segmenter.reset()
                self._set_audio_state("Listening")
                for chunk in source.iter_chunks():
                    was_speaking = segmenter.in_speech
                    should_flush, audio_to_flush = segmenter.process_chunk(chunk)
                    now_speaking = segmenter.in_speech
                    if not was_speaking and now_speaking:
                        self._set_audio_state("Speaking")
                    elif was_speaking and not now_speaking and not should_flush:
                        self._set_audio_state("Listening")

                    if should_flush and audio_to_flush is not None:
                        self._flush_buffer(audio_to_flush, input_mode)

                should_flush, audio_to_flush = segmenter.flush_remaining()
                if should_flush and audio_to_flush is not None:
                    self._flush_buffer(audio_to_flush, input_mode)
                self._set_audio_state("Listening")
        finally:
            self._stop_worker()

        return PipelineRun(self.transcripts, self.status_events)

    def _flush_buffer(self, buffer: list[np.ndarray] | np.ndarray, input_mode: str) -> None:
        if isinstance(buffer, np.ndarray):
            joined = buffer
        elif not buffer:
            return
        else:
            joined = np.concatenate(buffer)

        if len(joined) == 0:
            return

        # Drop pure background silence buffers to avoid running Whisper STT on silence
        if np.max(np.abs(joined)) < 1e-4:
            return

        if self._stt_thread is not None and self._stt_thread.is_alive():
            self._stt_queue.put((joined, input_mode))
        else:
            # Fallback to synchronous if worker is not running
            self._set_audio_state("Transcribing")
            try:
                text = self.transcriber.normalise_segments(
                    self.transcriber.transcribe_samples(joined, self.config.sample_rate)
                )
                if text:
                    self._emit_transcript(text, input_mode=input_mode)
            finally:
                self._set_audio_state("Listening")

    def run_live(
        self,
        stop_event: threading.Event | None = None,
    ) -> PipelineRun:  # pragma: no cover - interactive mode
        source: AudioSource
        if self.config.input_mode == "dual":
            source = DualAudioSource(
                sample_rate=self.config.sample_rate,
                chunk_seconds=self.config.live_chunk_seconds,
                mic_device_name=self.config.device_name,
                monitor_device_name=self.config.monitor_device_name,
                on_status=lambda lvl, msg: self._status(lvl, msg),
            )
            resolved_mic = source.mic_device_name or "system default mic"
            resolved_mon = source.monitor_device_name or "system default monitor"
            self._status(
                "info",
                f"Starting live capture in DUAL mode. Mic={resolved_mic}, Monitor={resolved_mon}. Press Ctrl+C to stop.",
            )
        else:
            source = SoundDeviceSource(
                sample_rate=self.config.sample_rate,
                channels=self.config.channels,
                chunk_seconds=self.config.live_chunk_seconds,
                device_name=self.config.device_name,
                input_mode=self.config.input_mode,
            )
            resolved_device = source.device_name or "system default"
            self._status(
                "info",
                f"Starting live capture. InputMode={self.config.input_mode}, Device={resolved_device}. Press Ctrl+C to stop.",
            )
            
        self._start_worker()
        try:
            with source:
                if not self.config.vad_enabled:
                    buffer: list[np.ndarray] = []
                    frame_count = 0
                    frame_threshold = int(self.config.sample_rate * self.config.stt_chunk_seconds)
                    for chunk in source.iter_chunks(stop_event=stop_event):
                        buffer.append(chunk)
                        frame_count += len(chunk)
                        if frame_count >= frame_threshold:
                            self._flush_buffer(buffer, input_mode=self.config.input_mode)
                            buffer = []
                            frame_count = 0
                    self._flush_buffer(buffer, input_mode=self.config.input_mode)
                else:
                    segmenter = self.segmenter or SpeechSegmenter(
                        vad=EnergyVAD(sample_rate=self.config.sample_rate),
                        sample_rate=self.config.sample_rate,
                        vad_silence_seconds=self.config.vad_silence_seconds,
                        vad_max_seconds=self.config.vad_max_seconds,
                        vad_min_speech_seconds=self.config.vad_min_speech_seconds,
                    )
                    segmenter.reset()
                    self._set_audio_state("Listening")
                    for chunk in source.iter_chunks(stop_event=stop_event):
                        was_speaking = segmenter.in_speech
                        should_flush, audio_to_flush = segmenter.process_chunk(chunk)
                        now_speaking = segmenter.in_speech
                        if not was_speaking and now_speaking:
                            self._set_audio_state("Speaking")
                        elif was_speaking and not now_speaking and not should_flush:
                            self._set_audio_state("Listening")

                        if should_flush and audio_to_flush is not None:
                            self._flush_buffer(audio_to_flush, input_mode=self.config.input_mode)

                    should_flush, audio_to_flush = segmenter.flush_remaining()
                    if should_flush and audio_to_flush is not None:
                        self._flush_buffer(audio_to_flush, input_mode=self.config.input_mode)
                    self._set_audio_state("Listening")
        finally:
            self._stop_worker()

        self._status("info", "Live capture stopped.")
        return PipelineRun(self.transcripts, self.status_events)
