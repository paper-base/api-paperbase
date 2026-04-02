from config.celery import app
from engine.core.trash_service import purge_expired_trash


@app.task(name="engine.core.purge_expired_trash")
def purge_expired_trash_task() -> int:
    """Celery beat: permanently remove expired trash rows and orphan media."""
    return purge_expired_trash()
