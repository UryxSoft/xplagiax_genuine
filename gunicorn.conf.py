"""Gunicorn tuned for the low-RAM profile (NFR-03/04).

preload_app is the key setting: the embedding model and the mmap'd
TurboVec index are loaded ONCE in the master before forking, so worker
processes share those pages copy-on-write / via the page cache instead of
each paying the full model footprint. With preload off, N workers cost
N x model RAM; with it on, roughly 1 x.

Workers are plain sync (one request per worker at a time): the hot path is
CPU-bound (embedding + SIMD search), where threads only add GIL contention.
Concurrency scales by worker count (WEB_CONCURRENCY) and horizontally by
node replicas (docs/SCALING.md).
"""

from __future__ import annotations

import os

bind = os.environ.get("BIND", "0.0.0.0:8000")
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "sync"
threads = 1
preload_app = True

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

# Recycle workers to bound slow leaks in long-lived native libs; the
# jitter avoids all workers restarting at once.
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "100"))

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
