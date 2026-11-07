from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import SupportConversation, SupportMessage
from .realtime import publish_support_message
from .rubika_read import extract_updates


API_ROOT = 'https://botapi.rubika.ir/v3'
TIMEOUT = (4, 12)


class RubikaAPIError(Exception):
    """An API failure represented by a safe, non-sensitive error code."""


def rubika_configuration_ready():
    return bool(
        settings.SUPPORT_RUBIKA_ENABLED
        and settings.SUPPORT_RUBIKA_BOT_TOKEN
        and settings.SUPPORT_RUBIKA_CHAT_ID
        and settings.SUPPORT_RUBIKA_USER_ID
        and settings.SUPPORT_RUBIKA_WEBHOOK_SECRET
    )


def _api_call(method, payload):
    token = settings.SUPPORT_RUBIKA_BOT_TOKEN
    if not token:
        raise RubikaAPIError('missing_configuration')
    try:
        response = requests.post(
            f'{API_ROOT}/{token}/{method}',
            json=payload,
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        response.raise_for_status()
        result = response.json()
    except requests.Timeout:
        raise RubikaAPIError('timeout') from None
    except requests.RequestException:
        raise RubikaAPIError('network_error') from None
    except ValueError:
        raise RubikaAPIError('invalid_response') from None

    if not isinstance(result, dict) or str(result.get('status', '')).lower() != 'ok':
        raise RubikaAPIError('api_rejected_request')
    data = result.get('data')
    return data if isinstance(data, dict) else {}


def verify_private_support_chat(chat_id, user_id):
    """Confirm the configured private chat belongs to the intended Rubika account."""
    data = _api_call('getChat', {'chat_id': str(chat_id)})
    chat = data.get('chat') if isinstance(data.get('chat'), dict) else data
    actual_chat_id = str(chat.get('chat_id') or '')
    actual_user_id = str(chat.get('user_id') or '')
    actual_type = str(chat.get('chat_type') or chat.get('type') or '')
    if actual_chat_id != str(chat_id) or actual_user_id != str(user_id):
        return False
    return actual_type.lower() in ('user', 'private', '')


def _update_kind(update):
    return str(update.get('type') or update.get('update_type') or '').replace('_', '').replace('-', '').lower()


def _message_payload(update):
    message = update.get('new_message') or update.get('message')
    if not isinstance(message, dict) and isinstance(update.get('event_data'), dict):
        event_data = update['event_data']
        message = event_data.get('message') or event_data
    return message if isinstance(message, dict) else None


def _reply_target_id(message):
    reply_to = message.get('reply_to_message_id')
    if not reply_to and isinstance(message.get('reply_to_message'), dict):
        reply = message['reply_to_message']
        reply_to = reply.get('message_id') or reply.get('reply_to_message_id')
    return str(reply_to or '')


def summarize_support_reply_updates(payload):
    """Return counts for logs without exposing message text, IDs, or tokens."""
    counts = {
        'updates': 0,
        'new_messages': 0,
        'message_payloads': 0,
        'private_chat_matches': 0,
        'support_sender_matches': 0,
        'reply_references': 0,
        'notification_matches': 0,
        'message_ids': 0,
        'text_messages': 0,
    }
    expected_chat = str(settings.SUPPORT_RUBIKA_CHAT_ID)
    expected_sender = str(settings.SUPPORT_RUBIKA_USER_ID)
    updates = extract_updates(payload)
    counts['updates'] = len(updates)
    for update in updates:
        if not isinstance(update, dict) or _update_kind(update) != 'newmessage':
            continue
        counts['new_messages'] += 1
        message = _message_payload(update)
        if not message:
            continue
        counts['message_payloads'] += 1
        chat_id = str(update.get('chat_id') or message.get('chat_id') or '')
        sender_id = str(message.get('sender_id') or '')
        if chat_id == expected_chat:
            counts['private_chat_matches'] += 1
        if sender_id == expected_sender and str(message.get('sender_type') or '').lower() == 'user':
            counts['support_sender_matches'] += 1
        reply_to_id = _reply_target_id(message)
        if reply_to_id:
            counts['reply_references'] += 1
            if SupportMessage.objects.filter(
                rubika_message_id=reply_to_id,
                sender=SupportMessage.VISITOR,
            ).exists():
                counts['notification_matches'] += 1
        if message.get('message_id'):
            counts['message_ids'] += 1
        if str(message.get('text') or '').strip():
            counts['text_messages'] += 1
    return counts


def process_support_reply_update(update):
    """Store a reply only when it replies to this support account's own notification."""
    if not isinstance(update, dict) or _update_kind(update) != 'newmessage':
        return False
    message = _message_payload(update)
    if not isinstance(message, dict):
        return False
    chat_id = str(update.get('chat_id') or message.get('chat_id') or '')
    sender_id = str(message.get('sender_id') or '')
    if (
        chat_id != str(settings.SUPPORT_RUBIKA_CHAT_ID)
        or sender_id != str(settings.SUPPORT_RUBIKA_USER_ID)
        or str(message.get('sender_type') or '').lower() != 'user'
    ):
        return False

    reply_to_id = _reply_target_id(message)
    inbound_id = str(message.get('message_id') or '')
    body = str(message.get('text') or '').strip()
    if not reply_to_id or not inbound_id or not body or len(body) > 3000:
        return False
    visitor_message = SupportMessage.objects.filter(
        rubika_message_id=reply_to_id,
        sender=SupportMessage.VISITOR,
    ).select_related('conversation').first()
    if visitor_message is None:
        return False

    _, created = SupportMessage.objects.get_or_create(
        rubika_inbound_message_id=inbound_id,
        defaults={
            'conversation': visitor_message.conversation,
            'sender': SupportMessage.SUPPORT,
            'body': body,
            'delivery_status': SupportMessage.DELIVERY_NOT_APPLICABLE,
        },
    )
    if created:
        SupportConversation.objects.filter(pk=visitor_message.conversation_id).update(
            status=SupportConversation.OPEN,
            updated_at=timezone.now(),
        )
        support_message = SupportMessage.objects.get(rubika_inbound_message_id=inbound_id)
        transaction.on_commit(lambda: publish_support_message(support_message))
    return created


def process_rubika_update_payload(payload):
    return sum(1 for update in extract_updates(payload) if process_support_reply_update(update))


def send_visitor_message(message):
    """Send the visitor text to the verified private support chat."""
    if message.sender != SupportMessage.VISITOR:
        return False
    chat_id = settings.SUPPORT_RUBIKA_CHAT_ID
    if not chat_id or not settings.SUPPORT_RUBIKA_BOT_TOKEN:
        SupportMessage.objects.filter(pk=message.pk).update(
            delivery_status=SupportMessage.DELIVERY_FAILED,
            delivery_error='missing_configuration',
        )
        return False

    SupportMessage.objects.filter(pk=message.pk).update(
        delivery_status=SupportMessage.DELIVERY_PENDING,
        delivery_attempts=F('delivery_attempts') + 1,
        delivery_error='',
    )
    conversation_code = message.conversation.public_code
    notification = (
        f'پیام تازه از گفتگوی پشتیبانی #{conversation_code}\n\n'
        f'{message.body}\n\n'
        'برای پاسخ به بازدیدکننده، از قابلیت Reply روی همین پیام استفاده کنید.'
    )
    try:
        data = _api_call('sendMessage', {'chat_id': str(chat_id), 'text': notification})
        rubika_message_id = str(data.get('message_id') or '')
        if not rubika_message_id:
            raise RubikaAPIError('missing_message_id')
    except RubikaAPIError as exc:
        SupportMessage.objects.filter(pk=message.pk).update(
            delivery_status=SupportMessage.DELIVERY_FAILED,
            delivery_error=str(exc)[:120],
        )
        return False

    SupportMessage.objects.filter(pk=message.pk).update(
        delivery_status=SupportMessage.DELIVERY_SENT,
        delivery_error='',
        rubika_message_id=rubika_message_id,
    )
    return True
