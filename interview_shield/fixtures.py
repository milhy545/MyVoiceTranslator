from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile

FIXTURE_TEXT = "Good morning. Python automation works offline and online."


@dataclass(slots=True)
class FixtureSet:
    wav_path: Path
    mp3_path: Path
    expected_tokens: tuple[str, ...]


def ensure_fixture_audio(target_dir: Path) -> FixtureSet:
    target_dir.mkdir(parents=True, exist_ok=True)
    wav_path = target_dir / "fixture_voice.wav"
    mp3_path = target_dir / "fixture_voice.mp3"
    if not wav_path.exists():
        subprocess.run(
            [
                "espeak-ng",
                "-v",
                "en-gb",
                "-s",
                "145",
                "-w",
                str(wav_path),
                FIXTURE_TEXT,
            ],
            check=True,
        )
    if not mp3_path.exists():
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(mp3_path),
            ],
            check=True,
            capture_output=True,
        )
    legacy_wav = target_dir / "test_audio.wav"
    legacy_mp3 = target_dir / "sample.mp3"
    if not legacy_wav.exists() or legacy_wav.stat().st_size == 0:
        copyfile(wav_path, legacy_wav)
    if not legacy_mp3.exists() or legacy_mp3.stat().st_size == 0:
        copyfile(mp3_path, legacy_mp3)
    return FixtureSet(
        wav_path=wav_path,
        mp3_path=mp3_path,
        expected_tokens=("good", "morning", "python", "automation", "offline", "online"),
    )
