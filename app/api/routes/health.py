"""Liveness/readiness probes (docs/ARCHITECTURE.md sect 16)."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


@health_bp.get("/ready")
def ready():
    dependencies = current_app.config.get("DEPENDENCIES")
    if dependencies is None:
        return jsonify({"status": "not_ready", "reason": "dependencies not configured"}), 503
    return jsonify({"status": "ready"}), 200
