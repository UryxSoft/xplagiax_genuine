"""POST /index (RF-01/RF-14 ingestion side): plain text in, document indexed.

Synchronous in Fase 1; Fase 3 adds the async job_id/polling variant
(RF-13) on the same schema.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError

from app.api.dependencies import AppDependencies
from app.api.schemas import IndexRequestSchema, IndexResponseSchema
from app.application.indexing.indexing_pipeline import (
    EmptyDocumentError,
    IndexCommand,
)
from app.domain.value_objects.bibliographic_metadata import BibliographicMetadata

index_bp = Blueprint("index", __name__)


@index_bp.post("/index")
def index_document():
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    raw_body = request.get_json(silent=True) or {}
    try:
        payload = IndexRequestSchema.model_validate(raw_body)
    except ValidationError as exc:
        return jsonify({"error": "invalid_request", "details": exc.errors()}), 400

    command = IndexCommand(
        text=payload.text,
        tenant_id=payload.tenant_id,
        filename=payload.filename,
        language_code=payload.idioma,
        topic_domain=payload.tema,
        bibliography=BibliographicMetadata(
            title=payload.titulo,
            authors=tuple(payload.autores),
            institution=payload.institucion,
            country=payload.pais,
            year=payload.anio,
        ),
    )

    try:
        result = deps.indexing_pipeline.index(command)
    except EmptyDocumentError as exc:
        return jsonify({"error": "empty_document", "message": str(exc)}), 400

    response = IndexResponseSchema(
        document_id=result.document_id,
        chunks_indexed=result.chunks_indexed,
        duplicate=result.duplicate,
        idioma=result.language_code,
        tema=result.topic_domain,
    )
    return jsonify(response.model_dump()), 200 if result.duplicate else 201
