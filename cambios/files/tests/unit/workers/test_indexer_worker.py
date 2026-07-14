"""run_worker_loop with scripted consumer/service fakes: execute-then-ack,
unknown jobs dropped but acked, idle reads skipped."""

from __future__ import annotations

from app.application.jobs.job_service import UnknownJobError
from app.domain.entities.job import Job, JobStatus
from app.workers.indexer_worker import run_worker_loop


class _ScriptedConsumer:
    def __init__(self, items: list[tuple[str, str] | None]) -> None:
        self._items = list(items)
        self.acked: list[str] = []
        self.group_ensured = False

    def ensure_group(self) -> None:
        self.group_ensured = True

    def read_one(self):
        return self._items.pop(0) if self._items else None

    def ack(self, message_id: str) -> None:
        self.acked.append(message_id)

    def exhausted(self) -> bool:
        return not self._items


class _FakeJobService:
    def __init__(self, unknown: set[str] | None = None) -> None:
        self.executed: list[str] = []
        self._unknown = unknown or set()

    def execute(self, job_id: str) -> Job:
        if job_id in self._unknown:
            raise UnknownJobError(job_id)
        self.executed.append(job_id)
        return Job(
            id=job_id, tenant_id="t", kind="index", payload={}, status=JobStatus.DONE
        )


def test_executes_and_acks_each_message() -> None:
    consumer = _ScriptedConsumer([("1-0", "job-a"), ("2-0", "job-b")])
    service = _FakeJobService()

    run_worker_loop(consumer, service, should_stop=consumer.exhausted)

    assert consumer.group_ensured
    assert service.executed == ["job-a", "job-b"]
    assert consumer.acked == ["1-0", "2-0"]


def test_unknown_job_is_acked_and_skipped() -> None:
    consumer = _ScriptedConsumer([("1-0", "ghost"), ("2-0", "job-a")])
    service = _FakeJobService(unknown={"ghost"})

    run_worker_loop(consumer, service, should_stop=consumer.exhausted)

    assert service.executed == ["job-a"]
    assert consumer.acked == ["1-0", "2-0"]


def test_idle_timeouts_do_not_ack_anything() -> None:
    consumer = _ScriptedConsumer([None, ("1-0", "job-a")])
    service = _FakeJobService()

    run_worker_loop(consumer, service, should_stop=consumer.exhausted)

    assert service.executed == ["job-a"]
    assert consumer.acked == ["1-0"]
