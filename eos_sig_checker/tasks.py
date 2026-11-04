from celery import shared_task

from allianceauth.services.hooks import get_extension_logger

from . import sync

logger = get_extension_logger(__name__)


@shared_task
def delete_expired_signatures():
    """Housekeeping only: resolving already ignores rows past their age."""
    deleted = sync.delete_expired()
    logger.info("Deleted %d expired signatures", deleted)
