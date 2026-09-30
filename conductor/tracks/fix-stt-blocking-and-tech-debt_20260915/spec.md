# Specification: fix-stt-blocking-and-tech-debt

## Overview

Based on the recent repository benchmark and analysis, several hidden bugs and architectural shortcomings were discovered. The most critical issue is that the STT (Speech-to-Text) inference blocks the main audio ingestion loop in `pipeline.py`. Because STT on a CPU can take up to ~3.2 seconds for a 3-second audio chunk, this synchronous blocking causes the audio pipeline to freeze, leading to massive lag stacking and dropped VAD processing.

This track aims to fix the blocking STT architecture, resolve residual technical debt regarding audio device enumeration, and handle memory release during STT restart.

## Functional Requirements

- **Asynchronous STT/NMT**: Move the STT transcription and NMT translation tasks into a dedicated worker thread or thread pool so they do not block the audio chunk iteration (`run_live`).
- **Memory Management in `WhisperTranscriber`**: Implement a proper `close()` method that deletes the model and calls `gc.collect()` to free GPU/CPU memory.
- **Audio Enumeration Optimisation**: Reduce or eliminate the need for `subprocess` calls in `audio.py` for Linux loopback detection, or push them into a lazy-loaded background thread to prevent TUI startup delays.

## Acceptance Criteria

- [ ] `pipeline.py`'s `_flush_buffer` does not block the audio consumption queue.
- [ ] Multiple rapid speech segments do not cause the audio queue to freeze (lag should be isolated to translation delivery, not audio capture).
- [ ] `WhisperTranscriber.close()` explicitly cleans up the `faster-whisper` model.
- [ ] `uv run pytest tests/` passes successfully.
- [ ] `uv run ruff check .` and `uv run mypy interview_shield/ tests/` report no errors.

## Out of Scope

- Introducing new STT models or changing the underlying `faster-whisper` backend.
- Major UI redesigns.
