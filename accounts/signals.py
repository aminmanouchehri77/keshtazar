import logging

logger = logging.getLogger(__name__)


def my_callback(sender, **kwargs):
    logger.debug('Request completed')


def create_new_user(sender, instance, created, **kwargs):
    if created:
        logger.info('User account created')


def update_user(sender, instance, created, **kwargs):
    if not created:
        logger.info('User account updated')


