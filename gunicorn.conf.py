"""Gunicorn runtime settings for Railway."""

from __future__ import annotations

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
workers = int(
    os.getenv("WEB_CONCURRENCY")
    or os.getenv("GUNICORN_WORKERS")
    or (multiprocessing.cpu_count() * 2 + 1)
)
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = 30
keepalive = 5
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "warning")
