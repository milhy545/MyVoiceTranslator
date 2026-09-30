from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIELD = REPO_ROOT / "shield.py"


def run_command(*args: str) -> dict[str, object]:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(REPO_ROOT))
    completed = subprocess.run(
        [sys.executable, str(SHIELD), *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def main() -> int:
    steps = [
        ("doctor", ["doctor"]),
        ("prepare-fixtures", ["prepare-fixtures"]),
        ("test-file-offline", ["--offline", "--stt-device", "cpu", "test-file"]),
        ("test-live-mic", ["--offline", "--stt-device", "cpu", "test-live-mic"]),
        ("test-live-monitor", ["--offline", "--stt-device", "cpu", "test-live-monitor"]),
        ("test-file-online-fallback", ["--stt-device", "cpu", "test-file"]),
    ]
    report = {}
    for label, args in steps:
        report[label] = run_command(*args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
