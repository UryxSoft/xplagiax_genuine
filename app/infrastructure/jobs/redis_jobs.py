"""Redis job backend: string-keyed job state + Streams transport (ADR sect 6,
Redis Streams as the work queue).

Job state lives under a TTL'd string key (finished jobs age out on their
own); the stream message carries only the job id (see JobQueue port).
Consumer groups give at-least-once delivery: a worker that crashes before
ack leaves the message pending and a restarted worker reclaims it via
XAUTOCLAIM. Execution is idempotent (dedup by content hash, deterministic
chunk ids), so redelivery is safe.

Clients are injected redis-py compatible objects; tests use a stub.
"""

from __future__ import annotations

import json
from typing import Any

from app.domain.entities.job import Job

DEFAULT_JOB_TTL_SECONDS = 7 * 24 * 3600
DEFAULT_BLOCK_MS = 5_000
DEFAULT_MIN_IDLE_MS = 60_000


class RedisJobRepository:
    def __init__(self, client: Any, ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS) -> None:
        self._redis = client
        self._ttl = ttl_seconds

    def save(self, job: Job) -> None:
        self._redis.set(self._key(job.id), job.model_dump_json(), ex=self._ttl)

    def by_id(self, job_id: str) -> Job | None:
        raw = self._redis.get(self._key(job_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return Job.model_validate(json.loads(raw))

    @staticmethod
    def _key(job_id: str) -> str:
        return f"xplagiax:job:{job_id}"


class RedisStreamJobQueue:
    """Producer side: XADD one message per submitted job."""

    def __init__(self, client: Any, stream_key: str = "xplagiax:jobs") -> None:
        self._redis = client
        self._stream = stream_key

    def enqueue(self, job_id: str) -> None:
        self._redis.xadd(self._stream, {"job_id": job_id})


class RedisStreamJobConsumer:
    """Worker side: consumer-group reads with explicit acks."""

    def __init__(
        self,
        client: Any,
        stream_key: str = "xplagiax:jobs",
        group: str = "xplagiax-workers",
        consumer_name: str = "worker-1",
        block_ms: int = DEFAULT_BLOCK_MS,
        min_idle_ms: int = DEFAULT_MIN_IDLE_MS,
    ) -> None:
        self._redis = client
        self._stream = stream_key
        self._group = group
        self._consumer = consumer_name
        self._block_ms = block_ms
        self._min_idle_ms = min_idle_ms

    def ensure_group(self) -> None:
        try:
            self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
        except Exception as exc:  # redis raises ResponseError BUSYGROUP if it exists
            if "BUSYGROUP" not in str(exc):
                raise

    def read_one(self) -> tuple[str, str] | None:
        """Returns (message_id, job_id) or None on timeout.

        Abandoned pending messages (a previous worker died mid-job) are
        reclaimed before new ones are read.
        """
        claimed = self._redis.xautoclaim(
            self._stream, self._group, self._consumer, min_idle_time=self._min_idle_ms, count=1
        )
        messages = claimed[1] if isinstance(claimed, (list, tuple)) and len(claimed) > 1 else []
        if messages:
            return self._decode(messages[0])

        response = self._redis.xreadgroup(
            self._group, self._consumer, {self._stream: ">"}, count=1, block=self._block_ms
        )
        if not response:
            return None
        _stream_name, entries = response[0]
        if not entries:
            return None
        return self._decode(entries[0])

    def ack(self, message_id: str) -> None:
        self._redis.xack(self._stream, self._group, message_id)

    @staticmethod
    def _decode(entry: tuple[Any, dict[Any, Any]]) -> tuple[str, str]:
        message_id, fields = entry
        if isinstance(message_id, bytes):
            message_id = message_id.decode("utf-8")
        decoded = {
            (k.decode("utf-8") if isinstance(k, bytes) else k): (
                v.decode("utf-8") if isinstance(v, bytes) else v
            )
            for k, v in fields.items()
        }
        return message_id, decoded["job_id"]
