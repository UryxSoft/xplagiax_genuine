"""Async job orchestration (RF-13): submit returns a job id immediately,
execute runs the underlying use case and records the outcome.

execute() converts use-case exceptions into FAILED job state instead of
raising: the worker must ack the message either way, and the client learns
the outcome by polling GET /jobs/{id}. Only repository/transport errors
propagate (those SHOULD crash the worker so the message is redelivered).
"""

from __future__ import annotations

import uuid
from typing import Any

from app.application.indexing.document_deleter import DocumentDeleter
from app.application.indexing.indexing_pipeline import IndexCommand, IndexingPipeline
from app.application.search.search_service import SearchService
from app.domain.entities.job import Job
from app.domain.ports.job_queue import JobQueue
from app.domain.ports.job_repository import JobRepository
from app.domain.ports.search_result_cache import SearchResultCache
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata

KIND_INDEX = "index"
KIND_SEARCH = "search"
KIND_DELETE = "delete"


class UnknownJobError(KeyError):
    pass


class JobService:
    def __init__(
        self,
        job_repository: JobRepository,
        job_queue: JobQueue,
        indexing_pipeline: IndexingPipeline,
        search_service: SearchService,
        document_deleter: DocumentDeleter,
        search_cache: SearchResultCache,
    ) -> None:
        self._jobs = job_repository
        self._queue = job_queue
        self._indexing = indexing_pipeline
        self._search = search_service
        self._deleter = document_deleter
        self._cache = search_cache

    # -- submission (API side) ------------------------------------------

    def submit_index(self, command: IndexCommand) -> str:
        payload = {
            "text": command.text,
            "filename": command.filename,
            "language_code": command.language_code,
            "topic_domain": command.topic_domain,
            "bibliography": command.bibliography.model_dump(),
        }
        return self._submit(command.tenant_id, KIND_INDEX, payload)

    def submit_search(self, text: str, tenant_id: str) -> str:
        return self._submit(tenant_id, KIND_SEARCH, {"text": text})

    def submit_delete(self, document_id: str, tenant_id: str) -> str:
        return self._submit(tenant_id, KIND_DELETE, {"document_id": document_id})

    def _submit(self, tenant_id: str, kind: str, payload: dict[str, Any]) -> str:
        job = Job(id=str(uuid.uuid4()), tenant_id=tenant_id, kind=kind, payload=payload)
        self._jobs.save(job)
        self._queue.enqueue(job.id)
        return job.id

    # -- query (API side) ------------------------------------------------

    def get(self, job_id: str, tenant_id: str) -> Job | None:
        job = self._jobs.by_id(job_id)
        if job is None or job.tenant_id != tenant_id:
            return None
        return job

    # -- execution (worker side) ------------------------------------------

    def execute(self, job_id: str) -> Job:
        job = self._jobs.by_id(job_id)
        if job is None:
            raise UnknownJobError(job_id)

        job = job.start()
        self._jobs.save(job)

        try:
            result = self._run(job)
        except Exception as exc:  # use-case failure -> FAILED, never re-raise
            job = job.fail(f"{type(exc).__name__}: {exc}")
        else:
            job = job.complete(result)

        self._jobs.save(job)
        return job

    def _run(self, job: Job) -> dict[str, Any]:
        if job.kind == KIND_INDEX:
            result = self._indexing.index(self._index_command(job))
            if not result.duplicate:
                self._cache.invalidate_tenant(job.tenant_id)
            return {
                "document_id": result.document_id,
                "chunks_indexed": result.chunks_indexed,
                "duplicate": result.duplicate,
                "idioma": result.language_code,
                "tema": result.topic_domain,
            }
        if job.kind == KIND_SEARCH:
            return self._search.run(job.payload["text"], job.tenant_id)
        if job.kind == KIND_DELETE:
            deleted = self._deleter.delete(job.payload["document_id"], job.tenant_id)
            if deleted:
                self._cache.invalidate_tenant(job.tenant_id)
            return {"deleted": deleted, "document_id": job.payload["document_id"]}
        raise ValueError(f"unknown job kind: {job.kind}")

    def _index_command(self, job: Job) -> IndexCommand:
        payload = job.payload
        return IndexCommand(
            text=payload["text"],
            tenant_id=job.tenant_id,
            filename=payload.get("filename"),
            language_code=payload.get("language_code"),
            topic_domain=payload.get("topic_domain"),
            bibliography=BibliographicMetadata.model_validate(payload.get("bibliography") or {}),
        )
