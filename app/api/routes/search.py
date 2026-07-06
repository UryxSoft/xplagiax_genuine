"""POST /search (docs/ARCHITECTURE.md sect 9/11): text in, ranked plagiarism matches out."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError

from app.api.dependencies import AppDependencies
from app.api.schemas import ChunkMatchSchema, DocumentMatchSchema, SearchRequestSchema, SearchResponseSchema

search_bp = Blueprint("search", __name__)


@search_bp.post("/search")
def search():
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    raw_body = request.get_json(silent=True) or {}
    try:
        payload = SearchRequestSchema.model_validate(raw_body)
    except ValidationError as exc:
        return jsonify({"error": "invalid_request", "details": exc.errors()}), 400

    query_language = deps.language_detector.detect(payload.text)
    query_topic = deps.topic_classifier.classify(payload.text)

    matches = deps.search_pipeline.search(payload.text, payload.tenant_id)

    documents: list[DocumentMatchSchema] = []
    for match in matches:
        document = deps.document_repository.by_id(match.document_id)
        if document is None:
            continue  # metadata inconsistency: skip defensively, do not surface an orphan match

        signals = deps.reranker.compute_signals(match, payload.text, query_language, query_topic, document)
        score = deps.plagiarism_scorer.score(signals)

        best_chunk_texts = deps.chunk_repository.by_ids([match.best_hit.chunk_id])
        best_chunk_text = best_chunk_texts[0].text if best_chunk_texts else ""
        best_chunk_page = best_chunk_texts[0].span.page if best_chunk_texts else None

        documents.append(
            DocumentMatchSchema(
                documento=document.source.filename,
                universidad=document.bibliography.institution,
                autores=list(document.bibliography.authors),
                idioma=document.language.code if document.language else None,
                tema=document.topic.domain if document.topic else None,
                similaridad=score.percent,
                chunks=match.chunk_count,
                chunk_mas_parecido=ChunkMatchSchema(
                    texto=best_chunk_text, score=match.best_hit.score, pagina=best_chunk_page
                ),
            )
        )

    documents.sort(key=lambda d: d.similaridad, reverse=True)

    response = SearchResponseSchema(
        query_language=query_language.code,
        query_topic=query_topic.domain,
        global_plagiarism_percent=documents[0].similaridad if documents else 0.0,
        documents=documents,
    )
    return jsonify(response.model_dump()), 200
