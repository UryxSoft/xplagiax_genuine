"""GET /jobs/{id} (RF-13): polling endpoint for async operations.

Tenant-scoped like every other resource: a job belonging to another tenant
answers 404 (ADR-011).
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.api.dependencies import AppDependencies
from app.api.schemas import JobStatusSchema

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    deps: AppDependencies = current_app.config["DEPENDENCIES"]

    tenant_id = request.args.get("tenant_id", "").strip()
    if not tenant_id:
        return jsonify({"error": "invalid_request", "message": "tenant_id query parameter is required"}), 400

    job = deps.job_service.get(job_id, tenant_id)
    if job is None:
        return jsonify({"error": "not_found", "message": "job not found"}), 404

    response = JobStatusSchema(
        job_id=job.id,
        kind=job.kind,
        status=job.status.value,
        result=job.result,
        error=job.error,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )
    return jsonify(response.model_dump()), 200
