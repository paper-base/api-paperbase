"""
Gunicorn settings for quieter stdout (warning-level + no access log spam).

Use in production start command, e.g.:
  gunicorn -c gunicorn.conf.py config.wsgi:application

Railway / Docker: set start command to run migrate with low verbosity, then gunicorn:
  python manage.py migrate --verbosity 0 && exec gunicorn -c gunicorn.conf.py config.wsgi:application
"""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8080")
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))

# Hide boot/worker INFO lines and per-request access lines in the deploy log stream.
loglevel = "warning"
accesslog = None
errorlog = "-"
