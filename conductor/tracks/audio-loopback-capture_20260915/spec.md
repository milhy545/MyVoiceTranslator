# Specification: Desktop Audio Loopback Monitor and Dual-Channel Capture

## Overview
Enable reliable capture of remote interviewer speech directly from desktop audio output (PipeWire / PulseAudio monitor loopback) and introduce a dual-channel capture mode that mixes both candidate microphone audio and system monitor audio into a unified real-time pipeline.

## Motivation
- In a remote video interview (Google Meet, Zoom, MS Teams), the interviewer's speech comes through the operating system's audio output (headphones/speakers).
- The current sounddevice enumeration in `interview_shield/audio.py` fails to mark PipeWire/Pulse devices as `is_monitor_like` because Linux ALSA/Pulse default device strings do not contain naive keywords like "monitor".
- Furthermore, `input_mode` only allows either `mic` OR `monitor`. If set to `monitor`, the candidate's own questions/answers cannot be captured. If set to `mic`, the interviewer cannot be heard.
- To serve as a complete "Interview Shield", the tool must reliably capture both audio streams.

## Functional Requirements
1. **Linux Loopback & Monitor Device Detection (`interview_shield/audio.py`)**:
   - Enhance `list_input_devices()` to detect PulseAudio / PipeWire monitor sources.
   - Use `pactl list sources short` / `pw-cli` or ALSA device matching to identify sink monitor endpoints (e.g. `*.monitor`, `Monitor of ...`).
   - Accurately populate `AudioDeviceInfo.is_monitor_like = True` for loopback devices.
2. **Dual-Channel / Mixed Audio Source (`interview_shield/audio.py`)**:
   - Implement `DualAudioSource` conforming to `AudioSource` protocol:
     - Concurrently opens microphone input stream AND system loopback/monitor input stream.
     - Synchronously reads and mixes both streams into a normalized 16kHz mono audio chunk stream.
     - Handles sample rate conversion and clipping prevention (soft limiter / RMS gain balance).
3. **Configuration & Mode Support (`interview_shield/config.py`)**:
   - Add `dual` to `input_mode` choices: `{auto, mic, monitor, dual}`.
   - Add `monitor_device_name: str | None = None` to `AppConfig` (with env `MVT_MONITOR_DEVICE`).
   - Provide CLI option `--monitor-device` and `--input-mode dual`.
4. **TUI & CLI Controls**:
   - TUI device selector updated to allow choosing both microphone device and monitor device when `dual` mode is selected.
   - Status indicators showing capture health for both sources.

## Non-Functional Requirements
- **Robustness**: If one of the two devices in dual mode disconnects or fails to open, gracefully degrade to single-source capture with a warning event rather than crashing.
- **Latency**: Audio mixing overhead <5ms per chunk.
- **Portability**: Must function on Linux (MX Linux / Debian with PipeWire or PulseAudio) and gracefully fall back on generic sounddevice setups.

## Acceptance Criteria
- [x] `shield.py devices` correctly labels system monitor sources as monitor-capable.
- [x] `DualAudioSource` successfully mixes microphone and loopback audio into a single stream.
- [x] Unit tests in `tests/test_audio_devices.py` and `tests/test_dual_audio.py` verify monitor resolution and dual-stream mixing logic.
- [x] All existing test suites pass.

## Out of Scope
- Direct per-application audio stream interception (e.g. hooking directly into Zoom binary via LD_PRELOAD).
- Acoustic Echo Cancellation (AEC) algorithms (handled natively by headphones/OS).
