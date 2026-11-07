import hashlib
import json
import logging
import secrets
import sys
from datetime import timedelta

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .models import SupportConversation, SupportMessage
from .rubika import (
    RubikaAPIError,
    process_rubika_update_payload,
    rubika_configuration_ready,
    send_visitor_message,
    summarize_support_reply_updates,
)
from .realtime import publish_support_message


logger = logging.getLogger(__name__)
SESSION_TOKEN_KEY = 'keshtazar_support_chat_token'
MAX_MESSAGE_LENGTH = 3000
MAX_MESSAGES_PER_MINUTE = 8
SAFE_DELIVERY_ERROR_CODES = frozenset({
    'missing_configuration',
    'timeout',
    'network_error',
    'invalid_response',
    'api_rejected_request',
    'missing_message_id',
})


def _write_support_webhook_diagnostic(event, **fields):
    """Write privacy-safe webhook diagnostics to Passenger stderr."""
    parts = [f'time={timezone.now().isoformat(timespec="seconds")}', f'event={event}']
    for key, value in fields.items():
        if not isinstance(key, str) or not key.isascii() or not key.replace('_', '').isalnum():
            continue
        if isinstance(value, bool):
            safe_value = 'true' if value else 'false'
        elif isinstance(value, int):
            safe_value = str(value)
        elif isinstance(value, str) and value.isascii() and value.replace('_', '').replace('-', '').isalnum():
            safe_value = value
        else:
            safe_value = 'unknown'
        parts.append(f'{key}={safe_value}')

    try:
        sys.stderr.write('Rubika support webhook ' + ' '.join(parts) + '\n')
        sys.stderr.flush()
    except Exception:
        # Logging must never prevent Rubika from receiving an HTTP response.
        pass


def _conversation_for_request(request):
    """Create or retrieve a private conversation bound to this browser session."""
    for _ in range(2):
        token = request.session.get(SESSION_TOKEN_KEY)
        if not isinstance(token, str) or len(token) < 32:
            token = secrets.token_urlsafe(36)
            request.session[SESSION_TOKEN_KEY] = token
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        user = request.user if request.user.is_authenticated else None
        conversation, _ = SupportConversation.objects.get_or_create(
            session_token_hash=token_hash,
            defaults={'user': user},
        )
        if conversation.user_id and (not user or conversation.user_id != user.pk):
            request.session.pop(SESSION_TOKEN_KEY, None)
            continue
        if user and conversation.user_id is None:
            SupportConversation.objects.filter(pk=conversation.pk, user__isnull=True).update(user=user)
            conversation.user = user
        return conversation
    raise RuntimeError('Unable to restore the support conversation for this session.')


def _serialize(message):
    error_code = message.delivery_error if message.delivery_error in SAFE_DELIVERY_ERROR_CODES else ''
    created_at = message.created_at
    if timezone.is_naive(created_at):
        created_at = timezone.make_aware(created_at, timezone.get_current_timezone())
    return {
        'id': message.pk,
        'sender': message.sender,
        'body': message.body,
        'created_at': created_at.isoformat(),
        'delivery_status': message.delivery_status,
        'delivery_error_code': error_code,
    }


@never_cache
@require_GET
def chat_session(request):
    conversation = _conversation_for_request(request)
    messages = conversation.messages.order_by('-id')[:60]
    return JsonResponse({
        'conversation': conversation.public_code,
        'authenticated': bool(conversation.user_id),
        'support_connected': rubika_configuration_ready(),
        'websocket_enabled': bool(getattr(settings, 'SUPPORT_WEBSOCKET_REDIS_URL', '')),
        'phone': settings.SUPPORT_PHONE,
        'messages': [_serialize(message) for message in reversed(list(messages))],
    })


@require_GET
def websocket_http_fallback(request):
    """A WebSocket handshake must be served by the ASGI application."""
    return HttpResponse(status=426)


@never_cache
@require_http_methods(['GET', 'POST'])
def chat_messages(request):
    conversation = _conversation_for_request(request)
    if request.method == 'GET':
        try:
            after_id = max(0, int(request.GET.get('after', '0')))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'شناسهٔ پیام معتبر نیست.'}, status=400)
        messages = conversation.messages.filter(pk__gt=after_id).order_by('id')[:100]
        return JsonResponse({'messages': [_serialize(message) for message in messages]})

    if not rubika_configuration_ready():
        return JsonResponse({'error': 'گفتگوی روبیکا هنوز برای پشتیبانی پیکربندی نشده است.'}, status=503)
    if request.content_type != 'application/json':
        return JsonResponse({'error': 'قالب درخواست پشتیبانی نمی‌شود.'}, status=415)
    if len(request.body) > 16_384:
        return JsonResponse({'error': 'حجم درخواست بیش از حد مجاز است.'}, status=413)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': 'متن پیام خوانا نیست.'}, status=400)
    body = str(payload.get('body', '') if isinstance(payload, dict) else '').strip()
    if not body:
        return JsonResponse({'error': 'متن پیام را بنویسید.'}, status=400)
    if len(body) > MAX_MESSAGE_LENGTH:
        return JsonResponse({'error': f'پیام حداکثر {MAX_MESSAGE_LENGTH} نویسه باشد.'}, status=400)

    since = timezone.now() - timedelta(minutes=1)
    recent_count = conversation.messages.filter(
        sender=SupportMessage.VISITOR,
        created_at__gte=since,
    ).count()
    if recent_count >= MAX_MESSAGES_PER_MINUTE:
        return JsonResponse({'error': 'برای جلوگیری از پیام‌های ناخواسته، یک دقیقه صبر کنید.'}, status=429)

    conversation.status = SupportConversation.OPEN
    conversation.save(update_fields=('status', 'updated_at'))
    message = SupportMessage.objects.create(
        conversation=conversation,
        sender=SupportMessage.VISITOR,
        body=body,
        delivery_status=SupportMessage.DELIVERY_PENDING,
    )
    send_visitor_message(message)
    message.refresh_from_db(fields=('delivery_status', 'delivery_attempts', 'delivery_error', 'rubika_message_id'))
    publish_support_message(message)
    return JsonResponse({'message': _serialize(message)}, status=201)


@csrf_exempt
@never_cache
def rubika_webhook(request, secret):
    request_id = secrets.token_hex(4)
    _write_support_webhook_diagnostic('received', request_id=request_id, method=request.method)
    if request.method not in ('POST', 'HEAD'):
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='method_not_allowed')
        return JsonResponse({'ok': False}, status=405)

    if not settings.SUPPORT_RUBIKA_ENABLED:
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='support_disabled')
        raise Http404
    if not settings.SUPPORT_RUBIKA_BOT_TOKEN:
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='bot_token_missing')
        raise Http404
    if not settings.SUPPORT_RUBIKA_CHAT_ID or not settings.SUPPORT_RUBIKA_USER_ID:
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='support_ids_missing')
        raise Http404

    expected_secret = settings.SUPPORT_RUBIKA_WEBHOOK_SECRET
    if not expected_secret:
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='secret_not_configured')
        raise Http404
    if not secrets.compare_digest(str(secret), str(expected_secret)):
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='secret_mismatch')
        raise Http404
    if not rubika_configuration_ready():
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='configuration_not_ready')
        raise Http404
    if request.method == 'HEAD':
        _write_support_webhook_diagnostic('health_check', request_id=request_id)
        return HttpResponse(status=200)
    if len(request.body) > 65_536:
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='payload_too_large')
        return JsonResponse({'ok': False}, status=413)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _write_support_webhook_diagnostic('rejected', request_id=request_id, reason='invalid_json')
        return JsonResponse({'ok': False}, status=400)

    try:
        diagnostics = summarize_support_reply_updates(payload)
        processed = process_rubika_update_payload(payload)
    except RubikaAPIError:
        _write_support_webhook_diagnostic(
            'processing_error', request_id=request_id, error_type='RubikaAPIError'
        )
        logger.warning('Rubika support webhook could not process the update.')
        return JsonResponse({'ok': False}, status=502)
    except Exception as exc:
        _write_support_webhook_diagnostic(
            'processing_error', request_id=request_id, error_type=type(exc).__name__
        )
        logger.error('Rubika support webhook failed (%s).', type(exc).__name__)
        raise

    _write_support_webhook_diagnostic(
        'processed',
        request_id=request_id,
        updates=diagnostics['updates'],
        new_messages=diagnostics['new_messages'],
        payloads=diagnostics['message_payloads'],
        replies=processed,
        private_matches=diagnostics['private_chat_matches'],
        sender_matches=diagnostics['support_sender_matches'],
        reply_references=diagnostics['reply_references'],
        notification_matches=diagnostics['notification_matches'],
        message_ids=diagnostics['message_ids'],
        text_messages=diagnostics['text_messages'],
    )
    return JsonResponse({'ok': True, 'processed': processed})
