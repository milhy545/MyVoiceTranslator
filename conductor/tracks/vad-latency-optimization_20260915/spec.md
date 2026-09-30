# Specification: VAD-Guided Audio Segmentation and Low-Latency Adaptive Flush

## Overview
Transform the audio processing pipeline from a rigid, fixed 8.0-second accumulator into an intelligent, low-latency streaming pipeline powered by Voice Activity Detection (VAD) and speech pause segmentation. Flush audio buffer immediately when a speaker pauses (e.g. 400–600ms of silence), cutting live latency from up to 8 seconds down to <1 second, while eliminating chopped words at arbitrary boundaries.

## Motivation
- Current behavior buffers audio until a strict threshold (`stt_chunk_seconds = 8.0`) is reached.
- Short questions ("Can you introduce yourself?", "Why Python?") cause an 8-second delay before the user sees the transcription and translation.
- Sentences spoken across the 8-second mark are split mid-phrase, severely degrading Whisper's transcription accuracy and causing word omissions or hallucinations.
- Silence during pauses still triggers Whisper inference on background noise, wasting GPU/CPU cycles.

## Functional Requirements
1. **Voice Activity Detector (`interview_shield/vad.py`)**:
   - Provide an efficient energy / RMS voice activity detector with dynamic noise estimation.
   - Support frame-by-frame speech probability / activity determination.
   - Track speech onset (minimum contiguous speech to confirm voice) and speech offset (silence duration indicating end of thought/sentence).
2. **Adaptive Pipeline Buffer Flush (`interview_shield/pipeline.py`)**:
   - Instead of waiting for `frame_count >= frame_threshold`:
     - Accumulate incoming live chunks.
     - When speech is detected followed by silence exceeding `vad_silence_seconds` (default 0.5s) AND total speech duration >= `vad_min_speech_seconds` (default 0.4s): immediately flush buffer to STT + translation.
     - Hard maximum window (`vad_max_seconds` default 8.0s): force flush if speech continues unbroken.
     - Sliding overlap buffer: carry forward a small trailing segment (e.g. 200ms) to ensure smooth phonetic transitions across utterances.
     - Ignore buffers consisting purely of silence/background noise below threshold.
3. **Configuration in `AppConfig`**:
   - `vad_enabled: bool = True` (with env `MVT_VAD_ENABLED`)
   - `vad_silence_seconds: float = 0.5` (with env `MVT_VAD_SILENCE_SECONDS`)
   - `vad_max_seconds: float = 8.0` (with env `MVT_VAD_MAX_SECONDS`)
   - `vad_min_speech_seconds: float = 0.4`
4. **TUI & Visual Feedback**:
   - Add a lightweight visual indicator to TUI (e.g. status bar badge: `[LISTENING]` vs `[VOICE DETECTED]` vs `[PROCESSING]`).

## Non-Functional Requirements
- **Latency**: Time from speaker concluding an utterance to transcript display <1.0s.
- **CPU Overhead**: VAD calculation must add <1% CPU load on Intel Core i5-4690K.
- **Stability**: Zero audio dropouts or buffer overflow under continuous streaming.

## Acceptance Criteria
- [x] Energy-based VAD correctly distinguishes speech from silence in synthetic and real audio fixtures.
- [x] Audio chunks with speech followed by 0.5s silence flush immediately without waiting 8 seconds.
- [x] Silence-only audio produces no STT transcripts and consumes minimal CPU.
- [x] Unit tests in `tests/test_vad.py` cover thresholding, onset/offset state transitions, and edge cases.
- [x] Existing file-based test commands continue to function identically.

## Out of Scope
- Speaker diarization (identifying multiple distinct speakers).
- Neural VAD fine-tuning.
