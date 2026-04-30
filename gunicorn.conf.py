"""
Gunicorn settings: no access log stream; errors go to stderr by default (visible in Docker logs).

ASGI (Channels / WebSockets), e.g.:
  gunicorn -c gunicorn.conf.py config.asgi:application

Docker: the image entrypoint runs migrate/collectstatic then starts Gunicorn; bind uses PORT from the environment.

Override worker class via GUNICORN_WORKER_CLASS (default: uvicorn.workers.UvicornWorker).

Silence errors (not recommended): GUNICORN_ERROR_LOG=/dev/null
"""
import os
import multiprocessing

bind = "0.0.0.0:" + os.environ.get("PORT", "8080")
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "uvicorn.workers.UvicornWorker")
default_workers = (2 * multiprocessing.cpu_count()) + 1
workers = int(os.environ.get("WEB_CONCURRENCY", str(default_workers)))
# Uvicorn workers are async; avoid multi-thread sync worker semantics.
_threads_env = os.environ.get("GUNICORN_THREADS")
if _threads_env is not None:
    threads = int(_threads_env)
else:
    threads = 1 if "uvicorn" in worker_class.lower() else 2
worker_connections = int(os.environ.get("GUNICORN_WORKER_CONNECTIONS", "1000"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", "100"))

loglevel = "warning"
accesslog = None
_error_log = os.environ.get("GUNICORN_ERROR_LOG", "-")
if _error_log in (os.devnull, "/dev/null"):
    errorlog = os.devnull
else:
    errorlog = _error_log
