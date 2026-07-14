"""Document catalog endpoints (RF-14/RF-15): list, detail, delete, stats.

Every operation is tenant-scoped (ADR-011): tenant_id is a required query
parameter, and cross-tenant ids answer 404, indistinguishable from
nonexistent ones.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.api.dependencies import AppDependencies
from app.api.schemas import (
    DocumentListResponseSchema,
    DocumentSummarySchema,
    StatsResponseSchema,
)
from app.domain.entities.document import Document

documents_bp = Blueprint("documents", __name__)


def _summary(document: Document) -> DocumentSummarySchema:
    return DocumentSummarySchema(
        id=document.id,
        documento=document.source.filename,
        titulo=document.bibliography.title,
        autores=list(document.bibliography.authors),
        institucion=document.bibliography.institution,
        pais=document.bibliography.country,
        idioma=document.language.code if document.language else None,
        tema=document.topic.domain if document.topic else None,
        estado=document.status.value,
        indexado_en=document.indexed_at.isoformat() if document.indexed_at else None,
    )


def _require_tenant() -> str | None:
    tenant_id = request.args.get("tenant_id", "").strip()
    return tenant_id or None


@documents_bp.get("/documents")
def list_documents():
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    tenant_id = _require_tenant()
    if tenant_id is None:
        return jsonify({"error": "invalid_request", "message": "tenant_id query parameter is required"}), 400

    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        return jsonify({"error": "invalid_request", "message": "page must be an integer"}), 400
    if page < 1:
        return jsonify({"error": "invalid_request", "message": "page must be >= 1"}), 400

    documents = deps.document_repository.list(
        tenant_id,
        language=request.args.get("idioma"),
        topic=request.args.get("tema"),
        institution=request.args.get("institucion"),
        country=request.args.get("pais"),
        page=page,
    )
    response = DocumentListResponseSchema(documents=[_summary(d) for d in documents], page=page)
    return jsonify(response.model_dump()), 200


@documents_bp.get("/documents/<document_id>")
def get_document(document_id: str):
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    tenant_id = _require_tenant()
    if tenant_id is None:
        return jsonify({"error": "invalid_request", "message": "tenant_id query parameter is required"}), 400

    document = deps.document_repository.by_id(document_id)
    if document is None or document.tenant_id != tenant_id:
        return jsonify({"error": "not_found", "message": "document not found"}), 404

    body = _summary(document).model_dump()
    body["chunks"] = len(deps.chunk_repository.by_document(document_id))
    return jsonify(body), 200


@documents_bp.delete("/documents/<document_id>")
def delete_document(document_id: str):
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    tenant_id = _require_tenant()
    if tenant_id is None:
        return jsonify({"error": "invalid_request", "message": "tenant_id query parameter is required"}), 400

    deleted = deps.document_deleter.delete(document_id, tenant_id)
    if not deleted:
        return jsonify({"error": "not_found", "message": "document not found"}), 404
    return jsonify({"deleted": True, "document_id": document_id}), 200


@documents_bp.get("/stats")
def stats():
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    tenant_id = _require_tenant()
    if tenant_id is None:
        return jsonify({"error": "invalid_request", "message": "tenant_id query parameter is required"}), 400

    response = StatsResponseSchema(
        tenant_id=tenant_id,
        documents=deps.document_repository.count(tenant_id),
        chunks=deps.chunk_repository.count_for_tenant(tenant_id),
        index_dimension=deps.vector_index.dimension,
        index_version=deps.vector_index.version,
    )
    return jsonify(response.model_dump()), 200
