"""Flask application factory.

Takes a fully constructed AppDependencies rather than building adapters
from environment variables itself: production wiring lives in wsgi.py
(real PostgreSQL/TurboVec/e5/GROBID adapters), tests build one from fakes.
This keeps the HTTP layer testable without live infrastructure.
"""

from __future__ import annotations

from flask import Flask

from app.api.dependencies import AppDependencies
from app.api.error_handlers import register_error_handlers
from app.api.routes.documents import documents_bp
from app.api.routes.health import health_bp
from app.api.routes.index import index_bp
from app.api.routes.jobs import jobs_bp
from app.api.routes.search import search_bp


def create_app(dependencies: AppDependencies) -> Flask:
    app = Flask(__name__)
    app.config["DEPENDENCIES"] = dependencies

    app.register_blueprint(health_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(index_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(jobs_bp)
    register_error_handlers(app)

    return app
