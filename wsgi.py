"""Gunicorn entrypoint. All wiring lives in app/bootstrap.py (shared with
the indexer worker); this module only builds the Flask app and binds the
request-scoped session teardown.

Sessions are request-scoped: repositories hold a scoped_session proxy and
Flask's teardown_appcontext calls remove() after every request, so a
multi-threaded or multi-request worker never leaks one request's identity
map or failed transaction into the next.
"""

from __future__ import annotations

from app.api.app_factory import create_app
from app.bootstrap import build_web_dependencies

_dependencies, _session_scope = build_web_dependencies()
app = create_app(_dependencies)


@app.teardown_appcontext
def _remove_request_session(_exc: BaseException | None) -> None:
    _session_scope.remove()
