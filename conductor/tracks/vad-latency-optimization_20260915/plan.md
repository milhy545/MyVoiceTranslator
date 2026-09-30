# Implementation Plan: VAD-Guided Audio Segmentation and Low-Latency Adaptive Flush

## Phase 1: VAD Engine & State Machine

- [x] **Task: Energy-based Voice Activity Detector** (interview_shield/vad.py, tests/test_vad.py)
  - [x] Implement `EnergyVAD` with frame RMS calculation and adaptive noise floor
  - [x] Support `is_speech(chunk: np.ndarray) -> bool` and speech state tracking
  - [x] Add unit tests verifying silence vs speech detection across varying amplitude levels

- [x] **Task: VAD State Machine & Boundary Segmenter** (interview_shield/vad.py, tests/test_vad.py)
  - [x] Implement `SpeechSegmenter` managing onset frames, speech accumulation, silence frames, and flush signals
  - [x] Implement sliding overlap carryover (200ms)
  - [x] Unit test state machine: silence -> voice -> silence -> trigger flush; voice -> max timeout -> trigger flush

## Phase 2: Pipeline Integration & Config

- [x] **Task: Integrate SpeechSegmenter into InterviewShieldPipeline** (interview_shield/pipeline.py, tests/test_pipeline_vad.py)
  - [x] Update `run_live` and `run_simulated_live` loops to evaluate segmenter after each chunk
  - [x] Trigger `_flush_buffer` on segmenter flush signal
  - [x] Drop pure silence buffers before Whisper STT
  - [x] Add unit tests simulating live chunk feed with pauses and verifying timely flushes

- [x] **Task: Add VAD configuration and CLI flags** (interview_shield/config.py, interview_shield/cli.py)
  - [x] Add `vad_enabled`, `vad_silence_seconds`, `vad_max_seconds`, `vad_min_speech_seconds` to `AppConfig`
  - [x] Wire CLI flags `--vad / --no-vad`, `--vad-silence-seconds`, `--vad-max-seconds`

## Phase 3: TUI Integration & Verification

- [x] **Task: TUI status badge and feedback** (interview_shield/tui.py)
  - [x] Display real-time audio state (`Listening`, `Speech`, `Transcribing`) in status bar
  - [x] Emit status events on audio activity transitions

- [x] **Task: Benchmark latency & test verification** (tests/test_vad.py, tests/test_pipeline.py)
  - [x] Run full test suite: `uv run python -m unittest discover -s tests`
  - [x] Verify latency reduction on standard audio fixture
