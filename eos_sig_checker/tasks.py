from celery import shared_task

from allianceauth.services.hooks import get_extension_logger

from . import client_text, sync

logger = get_extension_logger(__name__)


@shared_task
def delete_expired_signatures():
    """Housekeeping only: resolving already ignores rows past their age.

    Old rejected lines go too: one daily task, one CELERYBEAT entry.
    """
    deleted = sync.delete_expired()
    rejected = sync.delete_old_rejected()
    logger.info("Deleted %d expired signatures and %d old rejected lines", deleted, rejected)


@shared_task
def update_client_texts():
    """Fetch the client languages whose texts changed in the archive."""
    try:
        updated = client_text.update()
    except client_text.ClientTextError as error:
        # the next run tries again; a failed run must not flood Celery with retries
        logger.warning("Client texts not updated: %s", error)
        return
    logger.info("Client texts updated: %s", ", ".join(updated) or "nothing changed")
