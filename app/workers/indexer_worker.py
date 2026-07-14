"""Indexer worker: the single writer of the vector index (ADR-010).

Run as: python -m app.workers.indexer_worker

Consumes the Redis Streams job queue with a consumer group (at-least-once:
un-acked messages of a crashed worker are reclaimed via XAUTOCLAIM) and
executes each job through JobService, which records DONE/FAILED state for
polling. The message is acked after execute() returns -- including the
FAILED outcome, which is a recorded result, not a redeliverable error; a
crash before ack leaves the message pending for redelivery, and execution
is idempotent (content-hash dedup + deterministic chunk ids), so
reprocessing is safe.
"""

from __future__ import annotations

import logging
from typing import Callable

from app.application.jobs.job_service import JobService, UnknownJobError
from app.infrastructure.jobs.redis_jobs import RedisStreamJobConsumer

logger = logging.getLogger(__name__)


def run_worker_loop(
    consumer: RedisStreamJobConsumer,
    job_service: JobService,
    should_stop: Callable[[], bool] = lambda: False,
) -> None:
    consumer.ensure_group()
    while not should_stop():
        item = consumer.read_one()
        if item is None:
            continue
        message_id, job_id = item

        try:
            job = job_service.execute(job_id)
        except UnknownJobError:
            # job state expired (TTL) or was never written: nothing to
            # execute, nothing to retry -- drop the message
            logger.warning("job %s not found; dropping message %s", job_id, message_id)
        else:
            logger.info("job %s finished with status %s", job_id, job.status.value)

        consumer.ack(message_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    from app.bootstrap import build_worker

    job_service, consumer = build_worker()
    logger.info("indexer worker started")
    run_worker_loop(consumer, job_service)


if __name__ == "__main__":
    main()
