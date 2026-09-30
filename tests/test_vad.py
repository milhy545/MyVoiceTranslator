from __future__ import annotations

import unittest

import numpy as np

from interview_shield.vad import EnergyVAD, SpeechSegmenter


class TestEnergyVAD(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_rate = 16_000
        self.vad = EnergyVAD(
            sample_rate=self.sample_rate,
            min_threshold=0.015,
            speech_multiplier=2.5,
            adaptation_rate=0.1,
            initial_noise_floor=0.005,
        )

    def test_calculate_rms_silence_and_empty(self) -> None:
        self.assertEqual(self.vad.calculate_rms(np.array([])), 0.0)
        zeros = np.zeros(1600, dtype=np.float32)
        self.assertEqual(self.vad.calculate_rms(zeros), 0.0)

    def test_calculate_rms_sine_wave(self) -> None:
        # Sine wave with amplitude A has RMS = A / sqrt(2) ~ 0.707 * A
        t = np.linspace(0, 0.1, int(self.sample_rate * 0.1), endpoint=False)
        amp = 0.2
        sine = (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        rms = self.vad.calculate_rms(sine)
        expected = amp / np.sqrt(2)
        self.assertAlmostEqual(rms, expected, delta=0.01)

    def test_calculate_rms_int16_conversion(self) -> None:
        # int16 full scale sine wave (amplitude 16384 -> normalized ~0.5)
        t = np.linspace(0, 0.1, int(self.sample_rate * 0.1), endpoint=False)
        sine_int16 = (16384 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
        rms = self.vad.calculate_rms(sine_int16)
        expected = 0.5 / np.sqrt(2)
        self.assertAlmostEqual(rms, expected, delta=0.02)

    def test_calculate_rms_stereo(self) -> None:
        t = np.linspace(0, 0.1, int(self.sample_rate * 0.1), endpoint=False)
        sine = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        stereo = np.column_stack([sine, sine])
        rms = self.vad.calculate_rms(stereo)
        expected = 0.2 / np.sqrt(2)
        self.assertAlmostEqual(rms, expected, delta=0.01)

    def test_is_speech_detection(self) -> None:
        # Silence chunk (RMS = 0)
        silence = np.zeros(1600, dtype=np.float32)
        self.assertFalse(self.vad.is_speech(silence))
        self.assertFalse(self.vad.last_is_speech)
        self.assertEqual(self.vad.last_rms, 0.0)

        # Clear speech chunk (RMS ~ 0.14 >> min_threshold 0.015)
        t = np.linspace(0, 0.1, 1600, endpoint=False)
        speech = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        self.assertTrue(self.vad.is_speech(speech))
        self.assertTrue(self.vad.last_is_speech)
        self.assertGreater(self.vad.last_rms, 0.1)

    def test_adaptive_noise_floor(self) -> None:
        # Provide moderate background noise chunks (RMS ~ 0.008)
        # Threshold should adapt upwards
        noise_chunk = np.full(1600, 0.008, dtype=np.float32)
        initial_floor = self.vad.noise_floor
        for _ in range(10):
            self.assertFalse(self.vad.is_speech(noise_chunk))
        self.assertGreater(self.vad.noise_floor, initial_floor)

        # Threshold must be max(min_threshold, noise_floor * speech_multiplier)
        expected_threshold = max(self.vad.min_threshold, self.vad.noise_floor * self.vad.speech_multiplier)
        self.assertEqual(self.vad.threshold, expected_threshold)

    def test_reset(self) -> None:
        noise_chunk = np.full(1600, 0.01, dtype=np.float32)
        self.vad.is_speech(noise_chunk)
        self.assertNotEqual(self.vad.last_rms, 0.0)
        self.vad.reset()
        self.assertEqual(self.vad.noise_floor, self.vad.initial_noise_floor)
        self.assertEqual(self.vad.last_rms, 0.0)
        self.assertFalse(self.vad.last_is_speech)


class TestSpeechSegmenter(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_rate = 16_000
        self.vad = EnergyVAD(
            sample_rate=self.sample_rate,
            min_threshold=0.015,
            speech_multiplier=2.5,
            adaptation_rate=0.05,
            initial_noise_floor=0.005,
        )
        self.segmenter = SpeechSegmenter(
            vad=self.vad,
            sample_rate=self.sample_rate,
            vad_silence_seconds=0.5,
            vad_max_seconds=8.0,
            vad_min_speech_seconds=0.4,
            overlap_seconds=0.2,
            onset_frames=1,
        )
        # Helper chunks of 100ms (1600 samples)
        self.chunk_samples = int(self.sample_rate * 0.1)
        self.silence_chunk = np.zeros(self.chunk_samples, dtype=np.float32)
        t = np.linspace(0, 0.1, self.chunk_samples, endpoint=False)
        self.speech_chunk = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    def test_pure_silence_rejection(self) -> None:
        """Verify pure background silence is rejected and does not accumulate in memory."""
        for _ in range(20):  # 2.0s of pure silence
            should_flush, audio = self.segmenter.process_chunk(self.silence_chunk)
            self.assertFalse(should_flush)
            self.assertIsNone(audio)
        self.assertFalse(self.segmenter.in_speech)
        self.assertEqual(self.segmenter.state, "listening")
        self.assertEqual(len(self.segmenter._buffer), 0)

    def test_speech_burst_and_pause_flush(self) -> None:
        """Verify speech burst followed by 0.5s silence triggers immediate flush."""
        # Feed 6 chunks of speech = 0.6s (> vad_min_speech_seconds=0.4s)
        for i in range(6):
            should_flush, audio = self.segmenter.process_chunk(self.speech_chunk)
            self.assertFalse(should_flush)
            self.assertIsNone(audio)
            self.assertTrue(self.segmenter.in_speech)
            self.assertEqual(self.segmenter.state, "speaking")

        self.assertAlmostEqual(self.segmenter.speech_seconds, 0.6, places=2)

        # Feed 4 chunks of silence = 0.4s (< vad_silence_seconds=0.5s)
        for _ in range(4):
            should_flush, audio = self.segmenter.process_chunk(self.silence_chunk)
            self.assertFalse(should_flush)
            self.assertIsNone(audio)

        # 5th chunk of silence reaches 0.5s trailing silence -> FLUSH!
        should_flush, audio = self.segmenter.process_chunk(self.silence_chunk)
        self.assertTrue(should_flush)
        self.assertIsNotNone(audio)

        # Total audio should include 6 speech chunks + 5 silence chunks = 11 chunks
        assert audio is not None; self.assertEqual(len(audio), 11 * self.chunk_samples)
        self.assertFalse(self.segmenter.in_speech)
        self.assertEqual(self.segmenter.state, "listening")

    def test_min_speech_rejection(self) -> None:
        """Verify brief noise burst shorter than vad_min_speech_seconds is dropped."""
        # Feed 2 chunks of speech = 0.2s (< vad_min_speech_seconds=0.4s)
        for _ in range(2):
            self.segmenter.process_chunk(self.speech_chunk)

        # Feed 5 chunks of silence = 0.5s
        flushed = False
        for _ in range(5):
            should_flush, audio = self.segmenter.process_chunk(self.silence_chunk)
            if should_flush:
                flushed = True

        self.assertFalse(flushed)
        self.assertFalse(self.segmenter.in_speech)
        self.assertEqual(len(self.segmenter._buffer), 0)

    def test_max_timeout_flush(self) -> None:
        """Verify unbroken speech continuing past vad_max_seconds (8.0s) forces a flush."""
        # 80 chunks of 0.1s speech = 8.0s
        flush_chunk_index = -1
        flushed_audio = None
        for i in range(85):
            should_flush, audio = self.segmenter.process_chunk(self.speech_chunk)
            if should_flush:
                flush_chunk_index = i
                flushed_audio = audio
                break

        # Flush should occur at chunk 79 (8.0s reached)
        self.assertEqual(flush_chunk_index, 79)
        self.assertIsNotNone(flushed_audio)
        self.assertEqual(len(flushed_audio), 80 * self.chunk_samples)
        # In unbroken speech, in_speech should remain True with overlap carried into next buffer
        self.assertTrue(self.segmenter.in_speech)
        self.assertGreater(len(self.segmenter._buffer), 0)

    def test_overlap_carryover(self) -> None:
        """Verify 200ms overlap is carried forward into the subsequent segment."""
        # Utterance 1: 0.6s speech + 0.5s pause
        for _ in range(6):
            self.segmenter.process_chunk(self.speech_chunk)
        for _ in range(5):
            should_flush, audio1 = self.segmenter.process_chunk(self.silence_chunk)

        self.assertTrue(should_flush)
        self.assertIsNotNone(audio1)

        # Check that overlap was stored: 0.2s * 16000 = 3200 samples
        overlap_samples = int(self.sample_rate * 0.2)
        self.assertIsNotNone(self.segmenter._overlap_buffer)
        self.assertEqual(len(self.segmenter._overlap_buffer), overlap_samples)
        np.testing.assert_array_equal(self.segmenter._overlap_buffer, audio1[-overlap_samples:])

        # Utterance 2: 0.5s speech + 0.5s pause
        for _ in range(5):
            self.segmenter.process_chunk(self.speech_chunk)
        for _ in range(5):
            should_flush2, audio2 = self.segmenter.process_chunk(self.silence_chunk)

        self.assertTrue(should_flush2)
        self.assertIsNotNone(audio2)
        # audio2 must start with the overlap from audio1
        np.testing.assert_array_equal(audio2[:overlap_samples], audio1[-overlap_samples:])

    def test_flush_remaining_at_stream_end(self) -> None:
        """Verify remaining audio is flushed when stream ends while in active speech."""
        for _ in range(5):  # 0.5s speech
            self.segmenter.process_chunk(self.speech_chunk)

        # Stream ends without 0.5s silence pause
        should_flush, audio = self.segmenter.flush_remaining()
        self.assertTrue(should_flush)
        self.assertIsNotNone(audio)
        assert audio is not None; self.assertEqual(len(audio), 5 * self.chunk_samples)

        # Subsequent flush_remaining returns False
        should_flush2, audio2 = self.segmenter.flush_remaining()
        self.assertFalse(should_flush2)
        self.assertIsNone(audio2)

    def test_onset_frames_multi(self) -> None:
        """Verify onset_frames=2 ignores single speech spike, activates on 2nd frame."""
        seg = SpeechSegmenter(
            vad=self.vad,
            sample_rate=self.sample_rate,
            onset_frames=2,
        )
        # Single spike followed by silence
        seg.process_chunk(self.speech_chunk)
        self.assertFalse(seg.in_speech)
        seg.process_chunk(self.silence_chunk)
        self.assertFalse(seg.in_speech)
        self.assertEqual(len(seg._pending_frames), 0)

        # Two consecutive speech frames
        seg.process_chunk(self.speech_chunk)
        self.assertFalse(seg.in_speech)
        seg.process_chunk(self.speech_chunk)
        self.assertTrue(seg.in_speech)
        # Both chunks must be preserved in buffer
        self.assertEqual(len(seg._buffer), 2)


if __name__ == "__main__":
    unittest.main()
