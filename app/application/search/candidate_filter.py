"""Filter-first candidate resolution (ADR-004): idioma+tema -> allowlist.

docs/DOMAIN_MODEL.md sect 11, CandidateFilterPolicy: if topic confidence is
below threshold, the topic restriction is dropped (search without topic
filter) rather than risk losing recall on a shaky classification -- the
language filter is kept regardless, since language detection is far more
reliable at the lengths we deal with (RESEARCH.md #3 confirms language
match is a strong, cheap signal).
"""

from __future__ import annotations

from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.ports.document_repository import DocumentRepository
from app.domain.value_objects.language import Language
from app.domain.value_objects.topic import Topic

DEFAULT_TOPIC_CONFIDENCE_THRESHOLD = 0.5


class CandidateFilter:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        topic_confidence_threshold: float = DEFAULT_TOPIC_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._documents = document_repository
        self._chunks = chunk_repository
        self._topic_threshold = topic_confidence_threshold

    def build_allowlist(
        self, tenant_id: str, language: Language | None, topic: Topic | None
    ) -> set[int] | None:
        if language is None and topic is None:
            return None  # unrestricted search: no signal to filter on

        effective_language = language.code if language is not None else None
        effective_topic = (
            topic.domain if topic is not None and topic.confidence >= self._topic_threshold else None
        )

        document_ids = self._documents.ids_matching(
            tenant_id, language=effective_language, topic=effective_topic
        )
        if not document_ids:
            return set()  # deliberate "match nothing", distinct from None

        return set(self._chunks.ids_for_documents(document_ids))
