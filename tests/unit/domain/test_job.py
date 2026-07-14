import pytest

from app.domain.entities.job import InvalidJobTransition, Job, JobStatus


def _job() -> Job:
    return Job(id="j1", tenant_id="tenant-a", kind="index", payload={"text": "x"})


def test_new_job_is_pending() -> None:
    assert _job().status == JobStatus.PENDING


def test_happy_path_pending_running_done() -> None:
    job = _job().start()
    assert job.status == JobStatus.RUNNING

    job = job.complete({"document_id": "d1"})
    assert job.status == JobStatus.DONE
    assert job.result == {"document_id": "d1"}
    assert job.error is None


def test_failure_path_records_error() -> None:
    job = _job().start().fail("boom")
    assert job.status == JobStatus.FAILED
    assert job.error == "boom"


def test_cannot_complete_without_starting() -> None:
    with pytest.raises(InvalidJobTransition):
        _job().complete({})


def test_cannot_restart_terminal_job() -> None:
    done = _job().start().complete({})
    with pytest.raises(InvalidJobTransition):
        done.start()

    failed = _job().start().fail("x")
    with pytest.raises(InvalidJobTransition):
        failed.start()


def test_transitions_return_new_frozen_instances() -> None:
    job = _job()
    started = job.start()
    assert job.status == JobStatus.PENDING  # original untouched
    assert started is not job
    assert started.updated_at >= job.updated_at
