"""Single-process job backend: dict repository + inline execution.

InlineJobQueue runs the job synchronously inside enqueue() -- the HTTP
call still returns a job_id and the client polls GET /jobs/{id} exactly as
with the Redis backend, so switching backends never changes the API
contract. bind() breaks the construction cycle (the queue needs the
executor, the executor needs the queue).
"""

from __future__ import annotations

from typing import Callable

from app.domain.entities.job import Job


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def save(self, job: Job) -> None:
        self._jobs[job.id] = job

    def by_id(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)


class InlineJobQueue:
    def __init__(self) -> None:
        self._executor: Callable[[str], object] | None = None

    def bind(self, executor: Callable[[str], object]) -> None:
        self._executor = executor

    def enqueue(self, job_id: str) -> None:
        if self._executor is None:
            raise RuntimeError("InlineJobQueue.bind() must be called before enqueue()")
        self._executor(job_id)
