from __future__ import annotations

import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .interfaces import AudioSource


@dataclass(slots=True)
class AudioDeviceInfo:
    name: str
    index: int
    max_input_channels: int
    default_samplerate: float
    is_monitor_like: bool


def _is_virtual_device(device: AudioDeviceInfo) -> bool:
    name = device.name.lower()
    return name in {"pipewire", "pulse", "default"} or "default" in name


def detect_linux_monitor_sources() -> list[str]:
    """Detect Linux system monitor / loopback sources via pactl or pw-cli."""
    sources: list[str] = []
    # 1. Try pactl list sources short
    try:
        completed = subprocess.run(
            ["pactl", "list", "sources", "short"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout:
            for line in completed.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    name = parts[1]
                    if (
                        name.endswith(".monitor")
                        or ".monitor." in name
                        or "monitor" in name.lower()
                        or "loopback" in name.lower()
                    ):
                        if name not in sources:
                            sources.append(name)
            if sources:
                return sources
    except Exception:
        pass

    # 2. Fallback to pw-cli list-objects Node
    try:
        completed = subprocess.run(
            ["pw-cli", "list-objects", "Node"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout:
            current_node_name = ""
            is_sink = False
            for line in completed.stdout.splitlines():
                line = line.strip()
                if line.startswith("id "):
                    if is_sink and current_node_name:
                        mon_name = f"{current_node_name}.monitor"
                        if mon_name not in sources:
                            sources.append(mon_name)
                    current_node_name = ""
                    is_sink = False
                elif 'node.name = "' in line:
                    current_node_name = line.split('node.name = "', 1)[1].rstrip('"')
                elif 'media.class = "Audio/Sink"' in line:
                    is_sink = True
            if is_sink and current_node_name:
                mon_name = f"{current_node_name}.monitor"
                if mon_name not in sources:
                    sources.append(mon_name)
    except Exception:
        pass

    return sources


def detect_default_sink_monitor() -> str | None:
    """Detect default sink monitor name if available."""
    try:
        completed = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return f"{completed.stdout.strip()}.monitor"
    except Exception:
        pass
    return None


def resolve_input_device_name(
    requested_name: str | None = None,
    input_mode: str = "auto",
    devices: list[AudioDeviceInfo] | None = None,
) -> str | None:
    if requested_name:
        return requested_name
    if input_mode in {"auto", "dual"}:
        return None

    devices = devices if devices is not None else list_input_devices()
    if not devices:
        return None

    if input_mode == "monitor":
        # 1. Prefer default sink monitor if found in devices
        default_mon = detect_default_sink_monitor()
        if default_mon:
            for device in devices:
                if device.name == default_mon:
                    return device.name

        # 2. Prefer monitor-like device that is non-HDMI if possible
        monitor_devices = [d for d in devices if d.is_monitor_like]
        if monitor_devices:
            for d in monitor_devices:
                name_lower = d.name.lower()
                if not any(sub in name_lower for sub in ("hdmi", "pro-output", "pro 7", "pro 8", "pro 9")):
                    return d.name
            return monitor_devices[0].name

        # 3. Fallback to virtual devices
        for device in devices:
            if _is_virtual_device(device):
                return device.name
        return devices[0].name

    if input_mode == "mic":
        # 1. Physical mic candidates
        mic_candidates = [d for d in devices if not d.is_monitor_like and not _is_virtual_device(d)]
        if mic_candidates:
            for d in mic_candidates:
                if "mic" in d.name.lower():
                    return d.name
            return mic_candidates[0].name

        # 2. Non-monitor device
        for device in devices:
            if not device.is_monitor_like:
                return device.name
        return devices[0].name

    return None


# Module-level cache for device enumeration
_cached_devices: list[AudioDeviceInfo] | None = None
_cache_valid = False


def list_input_devices(force_refresh: bool = False) -> list[AudioDeviceInfo]:
    global _cached_devices, _cache_valid
    if _cache_valid and not force_refresh and _cached_devices is not None:
        return _cached_devices

    helper = """
import json
try:
    import sounddevice as sd
except Exception as exc:
    print(json.dumps({"error": str(exc), "devices": []}))
    raise SystemExit(0)
devices = []
for index, raw in enumerate(sd.query_devices()):
    if raw["max_input_channels"] < 1:
        continue
    name = str(raw["name"])
    devices.append({
        "name": name,
        "index": index,
        "max_input_channels": int(raw["max_input_channels"]),
        "default_samplerate": float(raw["default_samplerate"]),
        "is_monitor_like": ("monitor" in name.lower()) or ("loopback" in name.lower()) or name.endswith(".monitor"),
    })
print(json.dumps({"devices": devices}))
"""
    try:
        completed = subprocess.run(
            [sys.executable, "-c", helper],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return []

    devices = [
        AudioDeviceInfo(
            name=item["name"],
            index=item["index"],
            max_input_channels=item["max_input_channels"],
            default_samplerate=item["default_samplerate"],
            is_monitor_like=item["is_monitor_like"],
        )
        for item in payload.get("devices", [])
    ]

    detected_monitors = detect_linux_monitor_sources()
    existing_names = {d.name for d in devices}
    for d in devices:
        if d.name in detected_monitors or d.name.endswith(".monitor"):
            d.is_monitor_like = True

    for mon_name in detected_monitors:
        if mon_name not in existing_names:
            devices.append(
                AudioDeviceInfo(
                    name=mon_name,
                    index=-1,
                    max_input_channels=2,
                    default_samplerate=48000.0,
                    is_monitor_like=True,
                )
            )
            existing_names.add(mon_name)

    _cached_devices = devices
    _cache_valid = True
    return devices


def invalidate_device_cache() -> None:
    global _cache_valid
    _cache_valid = False


class WavChunkSource:
    def __init__(self, wav_path: Path, sample_rate: int = 16_000, chunk_seconds: float = 1.0) -> None:
        self.wav_path = wav_path
        self.sample_rate = sample_rate
        self.chunk_frames = int(sample_rate * chunk_seconds)

    def iter_chunks(self) -> Iterator[np.ndarray]:
        with wave.open(str(self.wav_path), "rb") as handle:
            sample_width = handle.getsampwidth()
            channels = handle.getnchannels()
            while True:
                raw = handle.readframes(self.chunk_frames)
                if not raw:
                    break
                if sample_width != 2:
                    raise RuntimeError(f"Unsupported sample width: {sample_width}")
                data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                if channels > 1:
                    data = data.reshape(-1, channels).mean(axis=1)
                yield data


class ProcessAudioSource:
    """Streams 16kHz mono float32 chunks using parec or pw-record."""

    def __init__(
        self,
        device_name: str,
        sample_rate: int = 16_000,
        chunk_seconds: float = 1.0,
    ) -> None:
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.chunk_seconds = chunk_seconds
        self.chunk_bytes = int(sample_rate * chunk_seconds) * 2
        self._proc: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> ProcessAudioSource:
        parec_path = shutil.which("parec")
        pw_record_path = shutil.which("pw-record")
        if parec_path:
            cmd = [
                parec_path,
                "-d",
                self.device_name,
                f"--rate={self.sample_rate}",
                "--channels=1",
                "--format=s16le",
            ]
        elif pw_record_path:
            cmd = [
                pw_record_path,
                "--target",
                self.device_name,
                "--rate",
                str(self.sample_rate),
                "--channels",
                "1",
                "--format",
                "s16",
                "-",
            ]
        else:
            raise RuntimeError(
                f"Cannot capture monitor device '{self.device_name}': neither parec nor pw-record found."
            )

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self.chunk_bytes * 4,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None

    def iter_chunks(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[np.ndarray]:
        if self._proc is None or self._proc.stdout is None:
            return
        stdout = self._proc.stdout
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            raw = stdout.read(self.chunk_bytes)
            if not raw or len(raw) < self.chunk_bytes:
                break
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            yield samples


class SoundDeviceSource:
    def __init__(
        self,
        sample_rate: int = 16_000,
        channels: int = 1,
        chunk_seconds: float = 1.0,
        device_name: str | None = None,
        input_mode: str = "auto",
    ) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:  # pragma: no cover - handled by diagnostics
            raise RuntimeError("sounddevice is not installed in the active runtime") from exc

        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_frames = int(sample_rate * chunk_seconds)
        self.requested_device_name = device_name
        self.input_mode = input_mode
        self.device_name = resolve_input_device_name(device_name, input_mode=input_mode)
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream = None
        self._proc_source: ProcessAudioSource | None = None
        self._sd = sd

    def _callback(self, indata, frames, time_info, status) -> None:  # pragma: no cover - real audio callback
        del frames, time_info, status
        # Put raw view (first channel) to avoid copy/flatten in PortAudio callback
        self._queue.put(indata[:, 0] if indata.ndim > 1 else indata)

    def __enter__(self) -> SoundDeviceSource:
        # Check if device is a monitor endpoint not directly queryable by PortAudio
        if self.device_name and (self.device_name.endswith(".monitor") or "monitor" in self.device_name.lower()):
            if shutil.which("parec") or shutil.which("pw-record"):
                try:
                    self._proc_source = ProcessAudioSource(
                        device_name=self.device_name,
                        sample_rate=self.sample_rate,
                        chunk_seconds=self.chunk_frames / self.sample_rate,
                    )
                    self._proc_source.__enter__()
                    return self
                except Exception:
                    self._proc_source = None

        try:
            self._stream = self._sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.chunk_frames,
                callback=self._callback,
                device=self.device_name,
            )
            self._stream.start()
            return self
        except Exception as exc:
            # If sounddevice failed and device looks like a monitor, fallback to subprocess
            if self.device_name and (self.device_name.endswith(".monitor") or "monitor" in self.device_name.lower()):
                try:
                    self._proc_source = ProcessAudioSource(
                        device_name=self.device_name,
                        sample_rate=self.sample_rate,
                        chunk_seconds=self.chunk_frames / self.sample_rate,
                    )
                    self._proc_source.__enter__()
                    return self
                except Exception:
                    pass
            raise exc

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc_source is not None:
            self._proc_source.__exit__(exc_type, exc, tb)
            self._proc_source = None
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def iter_chunks(
        self,
        stop_event: threading.Event | None = None,
    ) -> Iterator[np.ndarray]:  # pragma: no cover - real audio callback
        if self._proc_source is not None:
            yield from self._proc_source.iter_chunks(stop_event=stop_event)
            return

        while True:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                chunk = self._queue.get(timeout=0.5)
                yield chunk.astype(np.float32) / 32768.0
            except queue.Empty:
                if stop_event is not None and stop_event.is_set():
                    break
                time.sleep(0.1)


class DualAudioSource:
    """Captures concurrently from microphone and system monitor, mixing into a 16kHz mono stream."""

    def __init__(
        self,
        sample_rate: int = 16_000,
        chunk_seconds: float = 1.0,
        mic_device_name: str | None = None,
        monitor_device_name: str | None = None,
        mic_source: AudioSource | None = None,
        monitor_source: AudioSource | None = None,
        on_status: Callable[[str, str], None] | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_seconds = chunk_seconds
        self.chunk_frames = int(sample_rate * chunk_seconds)
        self.requested_mic_device = mic_device_name
        self.requested_monitor_device = monitor_device_name
        self.on_status = on_status

        self.mic_device_name = resolve_input_device_name(mic_device_name, input_mode="mic")
        self.monitor_device_name = resolve_input_device_name(monitor_device_name, input_mode="monitor")

        self.mic_source = mic_source
        self.monitor_source = monitor_source

        self._mic_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=50)
        self._mon_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=50)
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._monitor_active = False

    def __enter__(self) -> DualAudioSource:
        self._stop_event.clear()

        # Primary source: microphone
        if self.mic_source is None:
            self.mic_source = SoundDeviceSource(
                sample_rate=self.sample_rate,
                channels=1,
                chunk_seconds=self.chunk_seconds,
                device_name=self.mic_device_name,
                input_mode="mic",
            )
        self.mic_source.__enter__()

        # Secondary source: system monitor (graceful fallback)
        if self.monitor_source is None:
            if self.monitor_device_name and (
                self.monitor_device_name.endswith(".monitor")
                or "monitor" in self.monitor_device_name.lower()
            ) and (shutil.which("parec") or shutil.which("pw-record")):
                self.monitor_source = ProcessAudioSource(
                    device_name=self.monitor_device_name,
                    sample_rate=self.sample_rate,
                    chunk_seconds=self.chunk_seconds,
                )
            else:
                self.monitor_source = SoundDeviceSource(
                    sample_rate=self.sample_rate,
                    channels=1,
                    chunk_seconds=self.chunk_seconds,
                    device_name=self.monitor_device_name,
                    input_mode="monitor",
                )

        try:
            self.monitor_source.__enter__()
            self._monitor_active = True
        except Exception as exc:
            self._monitor_active = False
            msg = f"Failed to initialize monitor audio stream: {exc}. Continuing with microphone only."
            if self.on_status:
                self.on_status("warning", msg)

        # Start capture threads
        t_mic = threading.Thread(target=self._mic_worker, daemon=True, name="DualAudio-Mic")
        self._threads.append(t_mic)
        t_mic.start()

        if self._monitor_active and self.monitor_source is not None:
            t_mon = threading.Thread(target=self._mon_worker, daemon=True, name="DualAudio-Mon")
            self._threads.append(t_mon)
            t_mon.start()

        return self

    def _mic_worker(self) -> None:
        try:
            assert self.mic_source is not None
            for chunk in self.mic_source.iter_chunks(stop_event=self._stop_event):
                if self._stop_event.is_set():
                    break
                self._mic_queue.put(chunk)
        except Exception as exc:
            if self.on_status and not self._stop_event.is_set():
                self.on_status("error", f"Microphone capture error: {exc}")
        finally:
            self._mic_queue.put(None)

    def _mon_worker(self) -> None:
        try:
            assert self.monitor_source is not None
            for chunk in self.monitor_source.iter_chunks(stop_event=self._stop_event):
                if self._stop_event.is_set():
                    break
                self._mon_queue.put(chunk)
        except Exception as exc:
            self._monitor_active = False
            if self.on_status and not self._stop_event.is_set():
                self.on_status("warning", f"Monitor capture error: {exc}. Continuing with microphone only.")
        finally:
            self._mon_queue.put(None)

    def iter_chunks(
        self, stop_event: threading.Event | None = None
    ) -> Iterator[np.ndarray]:
        while True:
            if (stop_event and stop_event.is_set()) or self._stop_event.is_set():
                break

            try:
                mic_chunk = self._mic_queue.get(timeout=0.5)
            except queue.Empty:
                if (stop_event and stop_event.is_set()) or self._stop_event.is_set():
                    break
                continue

            if mic_chunk is None:
                # Primary stream ended
                break

            mon_chunk: np.ndarray | None = None
            if self._monitor_active:
                try:
                    mon_chunk = self._mon_queue.get_nowait()
                    if mon_chunk is None:
                        self._monitor_active = False
                except queue.Empty:
                    mon_chunk = None

            if mon_chunk is None:
                mixed = mic_chunk
            else:
                if len(mon_chunk) < len(mic_chunk):
                    mon_chunk = np.pad(mon_chunk, (0, len(mic_chunk) - len(mon_chunk)))
                elif len(mon_chunk) > len(mic_chunk):
                    mon_chunk = mon_chunk[: len(mic_chunk)]

                raw_mixed = mic_chunk + mon_chunk
                peak = float(np.max(np.abs(raw_mixed))) if len(raw_mixed) > 0 else 0.0
                if peak > 1.0:
                    mixed = np.tanh(raw_mixed).astype(np.float32)
                else:
                    mixed = raw_mixed.astype(np.float32)

            yield np.clip(mixed, -1.0, 1.0)

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop_event.set()
        if self.monitor_source and self._monitor_active:
            try:
                self.monitor_source.__exit__(exc_type, exc, tb)
            except Exception:
                pass
        if self.mic_source:
            try:
                self.mic_source.__exit__(exc_type, exc, tb)
            except Exception:
                pass
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()
        self._monitor_active = False