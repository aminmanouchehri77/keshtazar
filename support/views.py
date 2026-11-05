import hashlib
import json
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import SupportConversation, SupportMessage
from .rubika import (
    RubikaAPIError,
    process_rubika_update_payload,
    rubika_configuration_ready,
    send_visitor_message,
    summarize_support_reply_updates,
)


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
        'phone': settings.SUPPORT_PHONE,
        'messages': [_serialize(message) for message in reversed(list(messages))],
    })


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
    return JsonResponse({'message': _serialize(message)}, status=201)


@csrf_exempt
@never_cache
@require_POST
def rubika_webhook(request, secret):
    expected_secret = settings.SUPPORT_RUBIKA_WEBHOOK_SECRET
    if not rubika_configuration_ready() or not expected_secret:
        raise Http404
    if not secrets.compare_digest(str(secret), str(expected_secret)):
        raise Http404
    if len(request.body) > 65_536:
        return JsonResponse({'ok': False}, status=413)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'ok': False}, status=400)

    try:
        diagnostics = summarize_support_reply_updates(payload)
        processed = process_rubika_update_payload(payload)
    except RubikaAPIError:
        logger.warning('Rubika support webhook could not process the update.')
        return JsonResponse({'ok': False}, status=502)
    except Exception as exc:
        logger.error('Rubika support webhook failed (%s).', type(exc).__name__)
        raise

    logger.info(
        'Rubika support webhook processed updates=%s replies=%s private_matches=%s sender_matches=%s',
        diagnostics['updates'],
        processed,
        diagnostics['private_chat_matches'],
        diagnostics['support_sender_matches'],
    )
    return JsonResponse({'ok': True, 'processed': processed})
