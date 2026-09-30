from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from interview_shield.audio import (
    AudioDeviceInfo,
    detect_default_sink_monitor,
    detect_linux_monitor_sources,
    invalidate_device_cache,
    resolve_input_device_name,
)


class AudioDeviceResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        invalidate_device_cache()
        self.devices = [
            AudioDeviceInfo(
                name="USB Mic",
                index=1,
                max_input_channels=1,
                default_samplerate=44100.0,
                is_monitor_like=False,
            ),
            AudioDeviceInfo(
                name="Monitor of Built-in Audio",
                index=2,
                max_input_channels=2,
                default_samplerate=44100.0,
                is_monitor_like=True,
            ),
            AudioDeviceInfo(
                name="pipewire",
                index=3,
                max_input_channels=32,
                default_samplerate=44100.0,
                is_monitor_like=False,
            ),
        ]

    def test_explicit_device_wins(self) -> None:
        resolved = resolve_input_device_name(
            requested_name="Exact Device",
            input_mode="monitor",
            devices=self.devices,
        )
        self.assertEqual(resolved, "Exact Device")

    def test_monitor_mode_prefers_monitor_like_device(self) -> None:
        resolved = resolve_input_device_name(input_mode="monitor", devices=self.devices)
        self.assertEqual(resolved, "Monitor of Built-in Audio")

    def test_mic_mode_prefers_physical_mic(self) -> None:
        resolved = resolve_input_device_name(input_mode="mic", devices=self.devices)
        self.assertEqual(resolved, "USB Mic")

    def test_auto_mode_keeps_system_default(self) -> None:
        resolved = resolve_input_device_name(input_mode="auto", devices=self.devices)
        self.assertIsNone(resolved)

    def test_dual_mode_keeps_system_default(self) -> None:
        resolved = resolve_input_device_name(input_mode="dual", devices=self.devices)
        self.assertIsNone(resolved)

    @patch("interview_shield.audio.detect_default_sink_monitor")
    def test_monitor_mode_prefers_default_sink_monitor(self, mock_detect_default: MagicMock) -> None:
        mock_detect_default.return_value = "alsa_output.pci.analog-stereo.monitor"
        devices = [
            AudioDeviceInfo("alsa_output.pci.hdmi-stereo.monitor", 1, 2, 48000.0, True),
            AudioDeviceInfo("alsa_output.pci.analog-stereo.monitor", 2, 2, 48000.0, True),
        ]
        resolved = resolve_input_device_name(input_mode="monitor", devices=devices)
        self.assertEqual(resolved, "alsa_output.pci.analog-stereo.monitor")

    def test_monitor_mode_prefers_non_hdmi_monitor(self) -> None:
        devices = [
            AudioDeviceInfo("alsa_output.pci.hdmi-stereo.monitor", 1, 2, 48000.0, True),
            AudioDeviceInfo("alsa_output.pci.analog-stereo.monitor", 2, 2, 48000.0, True),
        ]
        with patch("interview_shield.audio.detect_default_sink_monitor", return_value=None):
            resolved = resolve_input_device_name(input_mode="monitor", devices=devices)
            self.assertEqual(resolved, "alsa_output.pci.analog-stereo.monitor")


class LinuxMonitorDetectionTest(unittest.TestCase):
    @patch("subprocess.run")
    def test_detect_linux_monitor_sources_pactl(self, mock_run: MagicMock) -> None:
        pactl_output = (
            "58\talsa_output.pci-0000_01_00.1.pro-output-3.monitor\tPipeWire\ts32le 8ch 48000Hz\tSUSPENDED\n"
            "66\talsa_input.usb-Camera.mono-fallback\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED\n"
            "67\talsa_output.pci-0000_00_1b.0.analog-stereo.monitor\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
        )
        mock_run.return_value = subprocess.CompletedProcess(
            args=["pactl", "list", "sources", "short"],
            returncode=0,
            stdout=pactl_output,
            stderr="",
        )
        sources = detect_linux_monitor_sources()
        self.assertIn("alsa_output.pci-0000_01_00.1.pro-output-3.monitor", sources)
        self.assertIn("alsa_output.pci-0000_00_1b.0.analog-stereo.monitor", sources)
        self.assertNotIn("alsa_input.usb-Camera.mono-fallback", sources)

    @patch("subprocess.run")
    def test_detect_linux_monitor_sources_pw_cli_fallback(self, mock_run: MagicMock) -> None:
        pw_cli_output = (
            '\tid 35, type PipeWire:Interface:Node/3\n'
            '\t\tnode.name = "alsa_output.pci-0000_00_1b.0.analog-stereo"\n'
            '\t\tmedia.class = "Audio/Sink"\n'
            '\tid 45, type PipeWire:Interface:Node/3\n'
            '\t\tnode.name = "alsa_input.usb-Camera"\n'
            '\t\tmedia.class = "Audio/Source"\n'
        )

        def side_effect(cmd, **kwargs):
            if cmd[0] == "pactl":
                raise FileNotFoundError("pactl not found")
            if cmd[0] == "pw-cli":
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=pw_cli_output, stderr="")
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        mock_run.side_effect = side_effect
        sources = detect_linux_monitor_sources()
        self.assertEqual(sources, ["alsa_output.pci-0000_00_1b.0.analog-stereo.monitor"])

    @patch("subprocess.run")
    def test_detect_linux_monitor_sources_failure_returns_empty(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("command failed")
        sources = detect_linux_monitor_sources()
        self.assertEqual(sources, [])

    @patch("subprocess.run")
    def test_detect_default_sink_monitor(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["pactl", "get-default-sink"],
            returncode=0,
            stdout="alsa_output.pci-0000_00_1b.0.analog-stereo\n",
            stderr="",
        )
        mon = detect_default_sink_monitor()
        self.assertEqual(mon, "alsa_output.pci-0000_00_1b.0.analog-stereo.monitor")


if __name__ == "__main__":
    unittest.main()
