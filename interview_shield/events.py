from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class TranscriptEvent:
    english: str
    input_mode: str
    czech: str = ""
    backend: str = "pending"
    phase: str = "translated"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class StatusEvent:
    level: str
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))