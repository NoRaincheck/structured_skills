from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TaskStatus = Literal["open", "in_progress", "done", "failed", "closed"]
TASK_STATUSES: tuple[TaskStatus, ...] = ("open", "in_progress", "done", "failed", "closed")


@dataclass
class TaskRecord:
    id: str
    name: str
    status: TaskStatus
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    last_run_at: str | None = None
    next_run_at: str | None = None
    recurrence: str | None = None
    attempts: int = 0
    last_error: str | None = None
    last_note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "failed_at": self.failed_at,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "recurrence": self.recurrence,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "last_note": self.last_note,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRecord":
        status = str(data.get("status", "open"))
        if status not in TASK_STATUSES:
            status = "open"

        raw_metadata = data.get("metadata")
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            status=status,  # type: ignore[arg-type]
            created_at=str(data["created_at"]),
            updated_at=str(data.get("updated_at", data["created_at"])),
            started_at=_to_optional_str(data.get("started_at")),
            completed_at=_to_optional_str(data.get("completed_at")),
            failed_at=_to_optional_str(data.get("failed_at")),
            last_run_at=_to_optional_str(data.get("last_run_at")),
            next_run_at=_to_optional_str(data.get("next_run_at")),
            recurrence=_to_optional_str(data.get("recurrence")),
            attempts=int(data.get("attempts", 0)),
            last_error=_to_optional_str(data.get("last_error")),
            last_note=_to_optional_str(data.get("last_note")),
            metadata=metadata,
        )


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
