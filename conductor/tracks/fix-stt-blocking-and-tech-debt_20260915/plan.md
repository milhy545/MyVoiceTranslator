# Implementation Plan: fix-stt-blocking-and-tech-debt

## Phase 1: Planning

- [x] Task: Approve specification and implementation plan

## Phase 2: Asynchronous STT Pipeline

- [x] Task: In `interview_shield/pipeline.py`, refactor `InterviewShieldPipeline` to use a `queue.Queue` or `concurrent.futures.ThreadPoolExecutor` for processing speech segments.
- [x] Task: Ensure `_flush_buffer` places the audio segment onto the worker queue and returns immediately.
- [x] Task: Create a worker loop that consumes the segments, runs `transcriber.transcribe_samples()`, normalises the text, and calls NMT.
- [x] Task: Update the `tests/test_pipeline.py` and `tests/test_e2e.py` to handle the asynchronous nature of the pipeline (e.g. wait for events).

## Phase 3: Technical Debt (Audio & Memory)

- [x] Task: In `interview_shield/stt.py`, implement `WhisperTranscriber.close()` to delete the model reference, empty CUDA cache (if applicable), and call `gc.collect()`.
- [x] Task: In `interview_shield/audio.py`, optimise `detect_linux_monitor_sources` to run asynchronously or cache results aggressively on disk/memory so it doesn't block the initial startup.
- [x] Task: Ensure TUI calls `close()` on the transcriber when a full app restart is triggered due to STT model changes.

## Phase 4: Verification

- [x] Task: Run full test suite (`uv run pytest tests/`).
- [x] Task: Run type checks and linter (`uv run mypy interview_shield/ tests/` and `uv run ruff check .`).
- [x] Task: Run STT benchmark to ensure it still works (`PYTHONPATH=. uv run pytest benchmarks/`).

## Completion

- [x] Acceptance criteria verified
- [x] Required project completion gate passed
