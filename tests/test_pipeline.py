from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from interview_shield.config import AppConfig
from interview_shield.interfaces import STTStatus, TranslationResult
from interview_shield.logging_utils import SessionLogger
from interview_shield.pipeline import InterviewShieldPipeline


class MockTranscriber:
    def __init__(self) -> None:
        self.transcribed_samples: list[np.ndarray] = []
        self.transcribed_paths: list[Path] = []
        self.status = STTStatus(
            requested_device="cpu",
            actual_device="cpu",
            model_name="base.en",
            compute_type="int8",
        )

    def transcribe_path(self, audio_path: Path) -> list[str]:
        self.transcribed_paths.append(audio_path)
        return ["hello world"]

    def transcribe_samples(self, samples: np.ndarray, sample_rate: int = 16000) -> list[str]:
        self.transcribed_samples.append(samples)
        return ["hello world"]

    def normalise_segments(self, segments: Iterable[str]) -> str:
        return " ".join(segments)

    def close(self) -> None:
        pass


class MockTranslator:
    def __init__(self) -> None:
        self.translated_texts: list[str] = []

    def translate(self, text: str) -> TranslationResult:
        self.translated_texts.append(text)
        return TranslationResult(text="ahoj svete", backend="mock", online_ok=False)


def create_test_wav(
    path: Path,
    durations_and_types: list[tuple[float, str]],
    sample_rate: int = 16000,
) -> None:
    """Helper to create a synthetic WAV file with alternating speech/silence segments.
    type: 'speech' or 'silence'.
    """
    total_samples = []
    for duration, kind in durations_and_types:
        num_samples = int(sample_rate * duration)
        if kind == "speech":
            t = np.linspace(0, duration, num_samples, endpoint=False)
            samples = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        else:
            samples = np.zeros(num_samples, dtype=np.int16)
        total_samples.append(samples)

    full_audio = np.concatenate(total_samples) if total_samples else np.zeros(0, dtype=np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(full_audio.tobytes())


class TestPipelineVAD(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.log_dir = self.root / "logs"
        self.artifacts_dir = self.root / "artifacts"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.logger = SessionLogger(self.log_dir, self.artifacts_dir)
        self.mock_transcriber = MockTranscriber()
        self.mock_translator = MockTranslator()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_pipeline_vad_enabled_speech_and_pause(self) -> None:
        """VAD pipeline flushes speech immediately after pause."""
        wav_path = self.root / "speech_pause.wav"
        # 0.6s speech, 0.6s silence, 0.6s speech, 0.6s silence
        create_test_wav(
            wav_path,
            [
                (0.6, "speech"),
                (0.6, "silence"),
                (0.6, "speech"),
                (0.6, "silence"),
            ],
        )

        audio_states = []
        config = AppConfig(
            vad_enabled=True,
            vad_silence_seconds=0.5,
            vad_min_speech_seconds=0.4,
            live_chunk_seconds=0.1,
            stt_chunk_seconds=8.0,
            force_offline=True,
        )
        pipeline = InterviewShieldPipeline(
            config=config,
            logger=self.logger,
            transcriber=self.mock_transcriber,
            translator=self.mock_translator,
            on_audio_state=audio_states.append,
        )

        run = pipeline.run_simulated_live(wav_path, input_mode="mic")

        # Two distinct speech segments separated by pause should trigger 2 STT calls
        self.assertEqual(len(self.mock_transcriber.transcribed_samples), 2)
        self.assertEqual(len(run.transcripts), 2)
        self.assertIn("Speaking", audio_states)
        self.assertIn("Transcribing", audio_states)
        self.assertIn("Listening", audio_states)

    def test_pipeline_vad_pure_silence_suppressed(self) -> None:
        """VAD pipeline drops pure background silence without running Whisper STT."""
        wav_path = self.root / "pure_silence.wav"
        create_test_wav(wav_path, [(2.0, "silence")])

        config = AppConfig(
            vad_enabled=True,
            vad_silence_seconds=0.5,
            live_chunk_seconds=0.1,
            stt_chunk_seconds=8.0,
            force_offline=True,
        )
        pipeline = InterviewShieldPipeline(
            config=config,
            logger=self.logger,
            transcriber=self.mock_transcriber,
            translator=self.mock_translator,
        )

        run = pipeline.run_simulated_live(wav_path, input_mode="mic")

        # Zero STT calls should have been made
        self.assertEqual(len(self.mock_transcriber.transcribed_samples), 0)
        self.assertEqual(len(run.transcripts), 0)

    def test_pipeline_vad_disabled_legacy_buffering(self) -> None:
        """With VAD disabled, pipeline retains fixed stt_chunk_seconds threshold."""
        wav_path = self.root / "legacy_test.wav"
        # 1.0s audio with stt_chunk_seconds=0.5s -> 2 flushes during stream + empty flush ignored
        create_test_wav(wav_path, [(1.0, "speech")])

        config = AppConfig(
            vad_enabled=False,
            live_chunk_seconds=0.25,
            stt_chunk_seconds=0.5,
            force_offline=True,
        )
        pipeline = InterviewShieldPipeline(
            config=config,
            logger=self.logger,
            transcriber=self.mock_transcriber,
            translator=self.mock_translator,
        )

        run = pipeline.run_simulated_live(wav_path, input_mode="mic")

        # 1.0s total audio / 0.5s threshold = 2 flushes
        self.assertEqual(len(self.mock_transcriber.transcribed_samples), 2)
        self.assertEqual(len(run.transcripts), 2)

    def test_pipeline_run_file_audio_state(self) -> None:
        """run_file properly transitions audio state."""
        wav_path = self.root / "file_test.wav"
        create_test_wav(wav_path, [(0.5, "speech")])

        audio_states = []
        config = AppConfig(force_offline=True)
        pipeline = InterviewShieldPipeline(
            config=config,
            logger=self.logger,
            transcriber=self.mock_transcriber,
            translator=self.mock_translator,
            on_audio_state=audio_states.append,
        )

        run = pipeline.run_file(wav_path)
        self.assertEqual(len(run.transcripts), 1)
        self.assertIn("Transcribing", audio_states)
        self.assertEqual(pipeline.audio_state, "Listening")

    def test_pipeline_vad_stream_end_flushes_remaining_speech(self) -> None:
        """Stream end flushes remaining speech even if no trailing silence pause occurred."""
        wav_path = self.root / "stream_end_speech.wav"
        # 0.8s speech directly ending at EOF
        create_test_wav(wav_path, [(0.8, "speech")])

        config = AppConfig(
            vad_enabled=True,
            vad_silence_seconds=0.5,
            vad_min_speech_seconds=0.4,
            live_chunk_seconds=0.1,
            force_offline=True,
        )
        pipeline = InterviewShieldPipeline(
            config=config,
            logger=self.logger,
            transcriber=self.mock_transcriber,
            translator=self.mock_translator,
        )

        run = pipeline.run_simulated_live(wav_path, input_mode="mic")
        self.assertEqual(len(self.mock_transcriber.transcribed_samples), 1)
        self.assertEqual(len(run.transcripts), 1)


if __name__ == "__main__":
    unittest.main()
