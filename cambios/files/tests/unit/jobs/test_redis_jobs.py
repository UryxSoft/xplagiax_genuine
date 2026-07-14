"""Redis job adapters against an in-memory stub honoring the redis-py
surface actually used (set/get/xadd/xreadgroup/xack/xautoclaim/xgroup_create)."""

from __future__ import annotations

import pytest

from app.domain.entities.job import Job
from app.infrastructure.jobs.redis_jobs import (
    RedisJobRepository,
    RedisStreamJobConsumer,
    RedisStreamJobQueue,
)


class _StubRedis:
    def __init__(self) -> None:
        self.kv: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.stream: list[tuple[str, dict[str, str]]] = []
        self.groups: set[str] = set()
        self.pending: dict[str, tuple[str, dict[str, str]]] = {}
        self.acked: list[str] = []
        self._next_id = 1

    # -- strings --
    def set(self, key, value, ex=None):
        self.kv[key] = value
        if ex is not None:
            self.ttls[key] = ex

    def get(self, key):
        return self.kv.get(key)

    # -- streams --
    def xadd(self, stream, fields):
        message_id = f"{self._next_id}-0"
        self._next_id += 1
        self.stream.append((message_id, dict(fields)))
        return message_id

    def xgroup_create(self, stream, group, id="0", mkstream=False):
        if group in self.groups:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self.groups.add(group)

    def xreadgroup(self, group, consumer, streams, count=1, block=None):
        if not self.stream:
            return []
        entries = self.stream[:count]
        self.stream = self.stream[count:]
        for message_id, fields in entries:
            self.pending[message_id] = (message_id, fields)
        return [("stream", entries)]

    def xack(self, stream, group, message_id):
        self.pending.pop(message_id, None)
        self.acked.append(message_id)

    def xautoclaim(self, stream, group, consumer, min_idle_time, count=1):
        # the stub treats every pending message as idle enough to reclaim
        reclaimed = list(self.pending.values())[:count]
        return ("0-0", reclaimed, [])


def test_job_repository_round_trip_with_ttl() -> None:
    stub = _StubRedis()
    repo = RedisJobRepository(stub, ttl_seconds=100)
    job = Job(id="j1", tenant_id="t", kind="index", payload={"text": "x"})

    repo.save(job)
    loaded = repo.by_id("j1")

    assert loaded == job
    assert stub.ttls["xplagiax:job:j1"] == 100
    assert repo.by_id("missing") is None


def test_queue_enqueues_job_id() -> None:
    stub = _StubRedis()
    RedisStreamJobQueue(stub, stream_key="s").enqueue("j1")
    assert stub.stream == [("1-0", {"job_id": "j1"})]


def test_consumer_reads_and_acks() -> None:
    stub = _StubRedis()
    RedisStreamJobQueue(stub).enqueue("j1")
    consumer = RedisStreamJobConsumer(stub)
    consumer.ensure_group()

    message_id, job_id = consumer.read_one()
    assert job_id == "j1"

    consumer.ack(message_id)
    assert stub.acked == [message_id]
    assert not stub.pending


def test_consumer_reclaims_pending_before_new_messages() -> None:
    stub = _StubRedis()
    queue = RedisStreamJobQueue(stub)
    consumer = RedisStreamJobConsumer(stub)
    consumer.ensure_group()

    queue.enqueue("j1")
    consumer.read_one()  # delivered but never acked: crashed worker
    queue.enqueue("j2")

    _mid, job_id = consumer.read_one()
    assert job_id == "j1"  # reclaimed pending message wins over the new one


def test_ensure_group_tolerates_existing_group() -> None:
    stub = _StubRedis()
    consumer = RedisStreamJobConsumer(stub)
    consumer.ensure_group()
    consumer.ensure_group()  # BUSYGROUP swallowed


def test_ensure_group_propagates_other_errors() -> None:
    class _Broken(_StubRedis):
        def xgroup_create(self, *args, **kwargs):
            raise Exception("connection refused")

    with pytest.raises(Exception, match="connection refused"):
        RedisStreamJobConsumer(_Broken()).ensure_group()


def test_consumer_decodes_bytes_payloads() -> None:
    stub = _StubRedis()
    stub.stream.append(("9-0", {b"job_id": b"j9"}))
    consumer = RedisStreamJobConsumer(stub)
    consumer.ensure_group()

    _mid, job_id = consumer.read_one()
    assert job_id == "j9"


def test_read_one_returns_none_on_empty_stream() -> None:
    stub = _StubRedis()
    consumer = RedisStreamJobConsumer(stub)
    consumer.ensure_group()
    assert consumer.read_one() is None
