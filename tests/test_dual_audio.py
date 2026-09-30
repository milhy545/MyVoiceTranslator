from __future__ import annotations

import threading
import unittest
from collections.abc import Iterator

import numpy as np

from interview_shield.audio import DualAudioSource


class DummyChunkSource:
    def __init__(
        self,
        chunks: list[np.ndarray],
        fail_on_enter: bool = False,
        fail_on_iter_index: int | None = None,
    ) -> None:
        self.chunks = chunks
        self.fail_on_enter = fail_on_enter
        self.fail_on_iter_index = fail_on_iter_index
        self.entered = False
        self.exited = False

    def __enter__(self) -> DummyChunkSource:
        if self.fail_on_enter:
            raise RuntimeError("Hardware monitor device unavailable")
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exited = True

    def iter_chunks(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[np.ndarray]:
        for i, chunk in enumerate(self.chunks):
            if stop_event is not None and stop_event.is_set():
                break
            if self.fail_on_iter_index is not None and i == self.fail_on_iter_index:
                raise RuntimeError("Stream disconnected mid-capture")
            yield chunk


class DualAudioSourceTest(unittest.TestCase):
    def test_parallel_mixing_and_normalization(self) -> None:
        chunk_len = 1600  # 0.1s at 16kHz
        # Mic has 0.3 amplitude, Monitor has 0.4 amplitude -> sum is 0.7 (below 1.0)
        mic_chunks = [np.full(chunk_len, 0.3, dtype=np.float32) for _ in range(3)]
        mon_chunks = [np.full(chunk_len, 0.4, dtype=np.float32) for _ in range(3)]

        mic_src = DummyChunkSource(mic_chunks)
        mon_src = DummyChunkSource(mon_chunks)

        dual = DualAudioSource(
            sample_rate=16_000,
            chunk_seconds=0.1,
            mic_source=mic_src,
            monitor_source=mon_src,
        )

        with dual:
            results = list(dual.iter_chunks())

        self.assertEqual(len(results), 3)
        for chunk in results:
            self.assertEqual(len(chunk), chunk_len)
            self.assertEqual(chunk.dtype, np.float32)
            np.testing.assert_allclose(chunk, 0.7, atol=1e-4)

        self.assertTrue(mic_src.exited)
        self.assertTrue(mon_src.exited)

    def test_soft_limiter_prevents_clipping(self) -> None:
        chunk_len = 1600
        # Mic 0.8 + Mon 0.8 = 1.6 (> 1.0) -> soft limiter activates
        mic_chunks = [np.full(chunk_len, 0.8, dtype=np.float32)]
        mon_chunks = [np.full(chunk_len, 0.8, dtype=np.float32)]

        mic_src = DummyChunkSource(mic_chunks)
        mon_src = DummyChunkSource(mon_chunks)

        dual = DualAudioSource(
            sample_rate=16_000,
            chunk_seconds=0.1,
            mic_source=mic_src,
            monitor_source=mon_src,
        )

        with dual:
            results = list(dual.iter_chunks())

        self.assertEqual(len(results), 1)
        mixed = results[0]
        # Should be bounded strictly within [-1.0, 1.0]
        self.assertLessEqual(float(np.max(mixed)), 1.0)
        self.assertGreaterEqual(float(np.min(mixed)), -1.0)
        # Expected tanh(1.6) ≈ 0.921669
        expected = float(np.tanh(1.6))
        np.testing.assert_allclose(mixed[0], expected, atol=1e-3)

    def test_graceful_fallback_when_monitor_fails_on_enter(self) -> None:
        chunk_len = 1600
        mic_chunks = [np.full(chunk_len, 0.5, dtype=np.float32) for _ in range(2)]
        mon_chunks = [np.full(chunk_len, 0.5, dtype=np.float32) for _ in range(2)]

        mic_src = DummyChunkSource(mic_chunks)
        mon_src = DummyChunkSource(mon_chunks, fail_on_enter=True)

        status_logs: list[tuple[str, str]] = []

        def on_status(level: str, msg: str) -> None:
            status_logs.append((level, msg))

        dual = DualAudioSource(
            sample_rate=16_000,
            chunk_seconds=0.1,
            mic_source=mic_src,
            monitor_source=mon_src,
            on_status=on_status,
        )

        # Should NOT raise exception when entering or reading
        with dual:
            results = list(dual.iter_chunks())

        # Should yield mic chunks cleanly
        self.assertEqual(len(results), 2)
        for chunk in results:
            np.testing.assert_allclose(chunk, 0.5, atol=1e-4)

        # Status warning should have been logged
        warnings = [msg for lvl, msg in status_logs if lvl == "warning"]
        self.assertTrue(len(warnings) >= 1)
        self.assertIn("monitor", warnings[0].lower())

    def test_graceful_fallback_when_monitor_fails_mid_stream(self) -> None:
        chunk_len = 1600
        mic_chunks = [np.full(chunk_len, 0.2, dtype=np.float32) for _ in range(4)]
        # Monitor will fail on chunk index 2
        mon_chunks = [np.full(chunk_len, 0.3, dtype=np.float32) for _ in range(4)]

        mic_src = DummyChunkSource(mic_chunks)
        mon_src = DummyChunkSource(mon_chunks, fail_on_iter_index=2)

        status_logs: list[tuple[str, str]] = []

        def on_status(level: str, msg: str) -> None:
            status_logs.append((level, msg))

        dual = DualAudioSource(
            sample_rate=16_000,
            chunk_seconds=0.1,
            mic_source=mic_src,
            monitor_source=mon_src,
            on_status=on_status,
        )

        with dual:
            results = list(dual.iter_chunks())

        # All 4 mic chunks should be yielded without terminating early
        self.assertEqual(len(results), 4)

        # At least one warning logged for monitor stream failure
        warnings = [msg for lvl, msg in status_logs if lvl == "warning"]
        self.assertTrue(len(warnings) >= 1)

    def test_uneven_chunk_lengths_aligned(self) -> None:
        mic_chunks = [np.full(1600, 0.4, dtype=np.float32)]
        # Monitor chunk is shorter (800)
        mon_chunks = [np.full(800, 0.2, dtype=np.float32)]

        mic_src = DummyChunkSource(mic_chunks)
        mon_src = DummyChunkSource(mon_chunks)

        dual = DualAudioSource(
            sample_rate=16_000,
            chunk_seconds=0.1,
            mic_source=mic_src,
            monitor_source=mon_src,
        )

        with dual:
            results = list(dual.iter_chunks())

        self.assertEqual(len(results), 1)
        mixed = results[0]
        self.assertEqual(len(mixed), 1600)
        # First 800 samples have both (0.4 + 0.2 = 0.6)
        np.testing.assert_allclose(mixed[:800], 0.6, atol=1e-4)
        # Remaining 800 samples have only mic (0.4)
        np.testing.assert_allclose(mixed[800:], 0.4, atol=1e-4)

    def test_stop_event_terminates_stream(self) -> None:
        chunk_len = 1600
        mic_chunks = [np.full(chunk_len, 0.1, dtype=np.float32) for _ in range(10)]
        mon_chunks = [np.full(chunk_len, 0.1, dtype=np.float32) for _ in range(10)]

        mic_src = DummyChunkSource(mic_chunks)
        mon_src = DummyChunkSource(mon_chunks)

        dual = DualAudioSource(
            sample_rate=16_000,
            chunk_seconds=0.1,
            mic_source=mic_src,
            monitor_source=mon_src,
        )

        stop_event = threading.Event()
        results = []
        with dual:
            for chunk in dual.iter_chunks(stop_event=stop_event):
                results.append(chunk)
                if len(results) == 2:
                    stop_event.set()

        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()
