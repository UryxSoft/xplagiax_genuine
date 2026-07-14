"""POST /search (docs/ARCHITECTURE.md sect 9/11): text in, ranked plagiarism matches out.

mode=sync answers inline; mode=async returns a job_id for polling (RF-13).

L2 cache (ADR sect 14): a repeated sync query within TTL returns the
cached response body without touching the embedding model or TurboVec;
indexing or deleting a document of the tenant invalidates its namespace
(see the index/documents routes).
"""

from __future__ import annotations

import hashlib

from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError

from app.api.dependencies import AppDependencies
from app.api.schemas import JobSubmittedSchema, SearchRequestSchema

search_bp = Blueprint("search", __name__)


def _cache_key(payload: SearchRequestSchema) -> str:
    material = f"{payload.text}\x00{payload.top_k_per_segment}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@search_bp.post("/search")
def search():
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    raw_body = request.get_json(silent=True) or {}
    try:
        payload = SearchRequestSchema.model_validate(raw_body)
    except ValidationError as exc:
        return jsonify({"error": "invalid_request", "details": exc.errors()}), 400

    if payload.mode == "async":
        job_id = deps.job_service.submit_search(payload.text, payload.tenant_id)
        return jsonify(JobSubmittedSchema(job_id=job_id, status="PENDING").model_dump()), 202

    cache_key = _cache_key(payload)
    cached = deps.search_cache.get(payload.tenant_id, cache_key)
    if cached is not None:
        return jsonify(cached), 200

    body = deps.search_service.run(payload.text, payload.tenant_id)
    deps.search_cache.put(payload.tenant_id, cache_key, body)
    return jsonify(body), 200
