"""Job aggregate for async processing (RF-13, docs/ARCHITECTURE.md sect 8.2).

State machine: PENDING -> RUNNING -> DONE | FAILED. Transitions are
enforced here so no adapter can, e.g., resurrect a FAILED job into DONE --
the repository stores whatever the entity produced, it never mutates state
on its own.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class InvalidJobTransition(ValueError):
    def __init__(self, current: JobStatus, target: JobStatus) -> None:
        super().__init__(f"cannot transition job from {current} to {target}")


_ALLOWED: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING}),
    JobStatus.RUNNING: frozenset({JobStatus.DONE, JobStatus.FAILED}),
    JobStatus.DONE: frozenset(),
    JobStatus.FAILED: frozenset(),
}


class Job(BaseModel):
    model_config = {"frozen": True}

    id: str
    tenant_id: str
    kind: str  # "index" | "search"
    payload: dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def start(self) -> "Job":
        return self._transition(JobStatus.RUNNING)

    def complete(self, result: dict[str, Any]) -> "Job":
        return self._transition(JobStatus.DONE, result=result)

    def fail(self, error: str) -> "Job":
        return self._transition(JobStatus.FAILED, error=error)

    def _transition(self, target: JobStatus, **updates: Any) -> "Job":
        if target not in _ALLOWED[self.status]:
            raise InvalidJobTransition(self.status, target)
        return self.model_copy(
            update={"status": target, "updated_at": datetime.now(timezone.utc), **updates}
        )
