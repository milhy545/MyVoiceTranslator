from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .events import StatusEvent, TranscriptEvent
from .structured_log import setup_structured_logger


class SessionLogger:
    def __init__(self, log_dir: Path, artifacts_dir: Path) -> None:
        self.log_dir = log_dir
        self.artifacts_dir = artifacts_dir
        date_key = datetime.now().strftime("%Y%m%d")
        self.session_log = self.log_dir / f"interview_{date_key}.md"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.debug_json = self.artifacts_dir / f"debug-{stamp}.json"
        self._ensure_headers()
        self._events: list[dict[str, object]] = []
        
        # Structured JSONL logger
        self._structured_logger = setup_structured_logger(log_dir)

    def _ensure_headers(self) -> None:
        if self.session_log.exists():
            return
        self.session_log.write_text(
            f"# Interview Shield Session Log - {datetime.now():%Y-%m-%d}\n\n",
            encoding="utf-8",
        )

    def log_status(self, event: StatusEvent) -> None:
        self._events.append({"kind": "status", **asdict(event)})
        # Markdown log (human-readable)
        with self.session_log.open("a", encoding="utf-8") as handle:
            handle.write(
                f"**[{event.created_at:%H:%M:%S}] {event.level.upper()}:** {event.message}\n\n"
            )
        # JSONL log (machine-parseable)
        self._structured_logger.log(
            logging.INFO if event.level == "info" else logging.WARNING if event.level == "warning" else logging.ERROR,
            event.message,
            extra={
                "kind": "status",
                "level": event.level,
                "msg_text": event.message,
                "created_at": event.created_at.isoformat(),
            },
        )

    def log_transcript(self, event: TranscriptEvent) -> None:
        self._events.append({"kind": "transcript", **asdict(event)})
        # Markdown log (human-readable)
        with self.session_log.open("a", encoding="utf-8") as handle:
            if event.phase == "captured":
                handle.write(f"**[{event.created_at:%H:%M:%S}] STT [ENG]:** {event.english}\n\n")
            else:
                handle.write(f"**[{event.created_at:%H:%M:%S}] STT [ENG]:** {event.english}\n\n")
                handle.write(
                    f"**[{event.created_at:%H:%M:%S}] Translate [CZE/{event.backend}]:** {event.czech}\n\n"
                )
        # JSONL log (machine-parseable)
        self._structured_logger.log(
            logging.INFO,
            f"Transcript: {event.english}",
            extra={
                "kind": "transcript",
                "phase": event.phase,
                "english": event.english,
                "czech": event.czech,
                "backend": event.backend,
                "input_mode": event.input_mode,
                "created_at": event.created_at.isoformat(),
            },
        )

    def export_debug_bundle(
        self,
        diagnostics: dict[str, object],
        transcripts: Iterable[TranscriptEvent],
        status_events: Iterable[StatusEvent],
    ) -> Path:
        payload = {
            "diagnostics": diagnostics,
            "transcripts": [asdict(event) for event in transcripts],
            "status_events": [asdict(event) for event in status_events],
            "session_log": str(self.session_log),
        }
        self.debug_json.write_text(
            json.dumps(payload, default=str, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.debug_json