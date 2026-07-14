"""Port for the job transport (RF-13).

enqueue() only carries the job id -- the payload lives in the
JobRepository, so a redelivered message can never disagree with the
stored job state.
"""

from __future__ import annotations

from typing import Protocol


class JobQueue(Protocol):
    def enqueue(self, job_id: str) -> None:
        ...
