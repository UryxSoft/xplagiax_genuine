"""Port for Job state persistence (RF-13)."""

from __future__ import annotations

from typing import Protocol

from app.domain.entities.job import Job


class JobRepository(Protocol):
    def save(self, job: Job) -> None:
        ...

    def by_id(self, job_id: str) -> Job | None:
        ...
