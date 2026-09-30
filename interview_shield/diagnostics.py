from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from .config import AppConfig


def _command_output(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return False, str(exc)
    output = completed.stdout.strip() or completed.stderr.strip()
    return completed.returncode == 0, output


def run_doctor(config: AppConfig, include_audio_devices: bool = True) -> dict[str, object]:
    imports = {}
    for module in [
        "textual",
        "sounddevice",
        "numpy",
        "faster_whisper",
        "deep_translator",
    ]:
        imports[module] = bool(importlib.util.find_spec(module))

    nvidia_ok, nvidia_text = _command_output(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    ffmpeg_ok, ffmpeg_text = _command_output(["ffmpeg", "-version"])
    espeak_ok, espeak_text = _command_output(["espeak-ng", "--version"])
    lockdown_text = ""
    lockdown_path = Path("/sys/kernel/security/lockdown")
    if lockdown_path.exists():
        try:
            lockdown_text = lockdown_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            lockdown_text = str(exc)
    nvidia_nodes = sorted(str(path) for path in Path("/dev").glob("nvidia*"))
    try:
        socket.getaddrinfo("translate.google.com", 443)
        google_dns = {"ok": True, "detail": "DNS resolution succeeded"}
    except Exception as exc:
        google_dns = {"ok": False, "detail": str(exc)}

    if include_audio_devices:
        from .audio import list_input_devices

        audio_devices = [
            {
                "name": device.name,
                "index": device.index,
                "max_input_channels": device.max_input_channels,
                "default_samplerate": device.default_samplerate,
                "is_monitor_like": device.is_monitor_like,
            }
            for device in list_input_devices()
        ]
    else:
        audio_devices = []

    return {
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "paths": {
            "log_dir": str(config.log_dir),
            "state_dir": str(config.state_dir),
            "artifacts_dir": str(config.artifacts_dir),
            "fixture_dir": str(config.fixture_dir),
        },
        "env": {
            "MVT_INPUT_MODE": os.environ.get("MVT_INPUT_MODE"),
            "MVT_ONLINE_BACKEND": os.environ.get("MVT_ONLINE_BACKEND"),
            "MVT_FORCE_OFFLINE": os.environ.get("MVT_FORCE_OFFLINE"),
            "ELEVENLABS_API_KEY": bool(os.environ.get("ELEVENLABS_API_KEY")),
        },
        "imports": imports,
        "binaries": {
            "ffmpeg": shutil.which("ffmpeg"),
            "espeak-ng": shutil.which("espeak-ng"),
            "nvidia-smi": shutil.which("nvidia-smi"),
        },
        "runtime_checks": {
            "ffmpeg": {"ok": ffmpeg_ok, "detail": ffmpeg_text.splitlines()[0] if ffmpeg_text else ""},
            "espeak-ng": {"ok": espeak_ok, "detail": espeak_text.splitlines()[0] if espeak_text else ""},
            "nvidia-smi": {"ok": nvidia_ok, "detail": nvidia_text},
            "nvidia_device_nodes": {"ok": bool(nvidia_nodes), "detail": nvidia_nodes},
            "kernel_lockdown": {"ok": "integrity" not in lockdown_text.lower(), "detail": lockdown_text},
            "google_dns": google_dns,
        },
        "audio_devices": audio_devices,
    }
