"""Full search use case producing the /search response body (ADR sect 11).

Extracted from the HTTP route so the synchronous endpoint and the async
job worker (RF-13) execute exactly the same code path; the route adds
validation and caching on top, the worker adds job state transitions.

Returns plain dicts (the wire contract of docs/ARCHITECTURE.md sect 9)
rather than API-layer schemas: application code must not import from
app.api (dependency direction, ADR-001).
"""

from __future__ import annotations

from typing import Any

from app.application.ranking.plagiarism_scorer import PlagiarismScorer
from app.application.ranking.reranker import Reranker
from app.application.search.search_pipeline import SearchPipeline
from app.domain.ports.chunk_repository import ChunkRepository
from app.domain.ports.document_repository import DocumentRepository
from app.domain.ports.language_detector import LanguageDetector
from app.domain.ports.topic_classifier import TopicClassifier


class SearchService:
    def __init__(
        self,
        search_pipeline: SearchPipeline,
        language_detector: LanguageDetector,
        topic_classifier: TopicClassifier,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        reranker: Reranker,
        plagiarism_scorer: PlagiarismScorer,
    ) -> None:
        self._pipeline = search_pipeline
        self._language_detector = language_detector
        self._topic_classifier = topic_classifier
        self._documents = document_repository
        self._chunks = chunk_repository
        self._reranker = reranker
        self._scorer = plagiarism_scorer

    def run(self, text: str, tenant_id: str) -> dict[str, Any]:
        query_language = self._language_detector.detect(text)
        query_topic = self._topic_classifier.classify(text)

        matches = self._pipeline.search(text, tenant_id)

        documents: list[dict[str, Any]] = []
        for match in matches:
            document = self._documents.by_id(match.document_id)
            if document is None:
                continue  # metadata inconsistency: skip defensively, do not surface an orphan match

            signals = self._reranker.compute_signals(
                match, text, query_language, query_topic, document
            )
            score = self._scorer.score(signals)

            best_chunk_texts = self._chunks.by_ids([match.best_hit.chunk_id])
            best_chunk_text = best_chunk_texts[0].text if best_chunk_texts else ""
            best_chunk_page = best_chunk_texts[0].span.page if best_chunk_texts else None

            documents.append(
                {
                    "documento": document.source.filename,
                    "universidad": document.bibliography.institution,
                    "autores": list(document.bibliography.authors),
                    "idioma": document.language.code if document.language else None,
                    "tema": document.topic.domain if document.topic else None,
                    "similaridad": score.percent,
                    "chunks": match.chunk_count,
                    "chunk_mas_parecido": {
                        "texto": best_chunk_text,
                        "score": match.best_hit.score,
                        "pagina": best_chunk_page,
                    },
                }
            )

        documents.sort(key=lambda d: d["similaridad"], reverse=True)

        return {
            "query_language": query_language.code,
            "query_topic": query_topic.domain,
            "global_plagiarism_percent": documents[0]["similaridad"] if documents else 0.0,
            "documents": documents,
        }
