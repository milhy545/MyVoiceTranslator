from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from interview_shield.diagnostics import run_doctor
from interview_shield.fixtures import ensure_fixture_audio

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIELD = REPO_ROOT / "shield.py"


@unittest.skipUnless(os.environ.get("MVT_RUN_INTEGRATION"), "Integration test - set MVT_RUN_INTEGRATION=1 to run")
class ShieldE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.tempdir.name) / "logs"
        self.artifact_dir = Path(self.tempdir.name) / "artifacts"
        self.fixture_dir = Path(self.tempdir.name) / "fixtures"
        self.fixture_set = ensure_fixture_audio(self.fixture_dir)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _run(self, *args: str) -> dict[str, object]:
        env = os.environ.copy()
        env["MVT_LOG_DIR"] = str(self.log_dir)
        env["MVT_ARTIFACT_DIR"] = str(self.artifact_dir)
        env["MVT_STATE_DIR"] = str(Path(self.tempdir.name) / "state")
        env["PYTHONPATH"] = str(REPO_ROOT)
        completed = subprocess.run(
            [sys.executable, str(SHIELD), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def _assert_english_tokens(self, payload: dict[str, object]) -> None:
        transcripts = payload["transcripts"]
        self.assertTrue(transcripts, "Expected at least one transcript entry")
        english = " ".join(item["english"] for item in transcripts)
        for token in self.fixture_set.expected_tokens:
            self.assertIn(token, english.lower())

    def test_prepare_fixtures_replaces_empty_legacy_files(self) -> None:
        self.assertTrue(self.fixture_set.wav_path.exists())
        self.assertTrue(self.fixture_set.mp3_path.exists())
        self.assertGreater((self.fixture_dir / "test_audio.wav").stat().st_size, 0)
        self.assertGreater((self.fixture_dir / "sample.mp3").stat().st_size, 0)

    def test_file_pipeline_offline_e2e(self) -> None:
        payload = self._run(
            "--stt-device",
            "cpu",
            "test-file",
            str(self.fixture_set.mp3_path),
        )
        self._assert_english_tokens(payload)
        self.assertEqual(payload["transcripts"][0]["backend"], "local")
        self.assertTrue(Path(payload["session_log"]).exists())
        self.assertTrue(Path(payload["debug_bundle"]).exists())

    def test_legacy_test_flag_still_works(self) -> None:
        payload = self._run(
            "--stt-device",
            "cpu",
            "--test",
            str(self.fixture_set.mp3_path),
        )
        self._assert_english_tokens(payload)

    def test_simulated_live_mic_e2e(self) -> None:
        payload = self._run(
            "--stt-device",
            "cpu",
            "test-live-mic",
            "--wav",
            str(self.fixture_set.wav_path),
        )
        self._assert_english_tokens(payload)

    def test_simulated_live_monitor_e2e(self) -> None:
        payload = self._run(
            "--stt-device",
            "cpu",
            "test-live-monitor",
            "--wav",
            str(self.fixture_set.wav_path),
        )
        self._assert_english_tokens(payload)

    def test_offline_only_translation_works(self) -> None:
        payload = self._run(
            "--stt-device",
            "cpu",
            "test-file",
            str(self.fixture_set.mp3_path),
        )
        self._assert_english_tokens(payload)
        self.assertEqual(payload["transcripts"][0]["backend"], "local")
        bundle = json.loads(Path(payload["debug_bundle"]).read_text(encoding="utf-8"))
        # No online fallback warnings in offline-only mode
        online_warnings = [
            item["message"]
            for item in bundle["status_events"]
            if item["level"] == "warning" and "online" in item["message"].lower()
        ]
        self.assertEqual(len(online_warnings), 0)

    def test_doctor_snapshot_contains_runtime_checks(self) -> None:
        doctor = run_doctor(
            type(
                "Config",
                (),
                {
                    "log_dir": self.log_dir,
                    "state_dir": Path(self.tempdir.name) / "state",
                    "artifacts_dir": self.artifact_dir,
                    "fixture_dir": self.fixture_dir,
                },
            )(),
            include_audio_devices=False,
        )
        self.assertIn("runtime_checks", doctor)
        self.assertIn("google_dns", doctor["runtime_checks"])


if __name__ == "__main__":
    unittest.main()
