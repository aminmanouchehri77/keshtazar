import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


def serialize_support_message(message):
    created_at = message.created_at
    if timezone.is_naive(created_at):
        created_at = timezone.make_aware(created_at, timezone.get_current_timezone())
    return {
        'id': message.pk,
        'sender': message.sender,
        'body': message.body,
        'created_at': created_at.isoformat(),
        'delivery_status': message.delivery_status,
        'delivery_error_code': '',
    }


def publish_support_message(message):
    """Publish a saved message to connected browsers when Redis is configured."""
    if not getattr(settings, 'SUPPORT_WEBSOCKET_REDIS_URL', ''):
        return False
    try:
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(
            f'support_{message.conversation_id.hex}',
            {'type': 'support.message', 'message': serialize_support_message(message)},
        )
        return True
    except Exception as exc:
        # HTTP polling remains available if the optional real-time service is down.
        logger.warning('Support WebSocket publish failed (%s).', type(exc).__name__)
        return False
