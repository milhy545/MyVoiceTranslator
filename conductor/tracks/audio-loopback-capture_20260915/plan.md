# Implementation Plan: Desktop Audio Loopback Monitor and Dual-Channel Capture

## Phase 1: Linux Monitor Device Discovery

- [x] **Task: PulseAudio / PipeWire monitor detector** (interview_shield/audio.py, tests/test_audio_devices.py)
  - [x] Implement monitor source discovery using system tools (`pactl list sources short`) with graceful fallback
  - [x] Update `list_input_devices` to mark monitor endpoints as `is_monitor_like = True`
  - [x] Add unit tests with mock device lists and mock pactl output

- [x] **Task: Monitor resolution and selection logic** (interview_shield/audio.py, tests/test_audio_devices.py)
  - [x] Enhance `resolve_input_device_name` to pick detected monitor devices in `input_mode="monitor"`
  - [x] Ensure backward compatibility with ALSA and standard sounddevice naming

## Phase 2: Dual Audio Stream Capture & Mixing

- [x] **Task: DualAudioSource implementation** (interview_shield/audio.py, tests/test_dual_audio.py)
  - [x] Implement `DualAudioSource` conforming to `AudioSource` protocol
  - [x] Open two streams (mic and monitor) concurrently with synchronized chunk queues
  - [x] Mix and normalize stereo/mono inputs into clean 16kHz mono chunks with soft limiter
  - [x] Handle error on one stream by falling back to surviving stream with status warning

- [x] **Task: Config and CLI wiring** (interview_shield/config.py, interview_shield/cli.py)
  - [x] Support `input_mode="dual"` in `AppConfig` and CLI choices
  - [x] Add `monitor_device_name` field and `--monitor-device` CLI flag

## Phase 3: TUI Integration & Verification

- [x] **Task: TUI dual-mode controls** (interview_shield/tui.py)
  - [x] Add Dual mode toggle in input mode selector
  - [x] Enable selecting secondary monitor device when in Dual mode

- [x] **Task: Verification and regression testing** (tests/test_dual_audio.py, tests/test_audio_devices.py)
  - [x] Run full test suite: `uv run python -m unittest discover -s tests`
  - [x] Run `python3 shield.py devices` and verify output on Milhy-PC
