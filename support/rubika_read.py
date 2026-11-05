import time

import requests
from django.conf import settings
from django.core.management.base import CommandError


API_ROOT = 'https://botapi.rubika.ir/v3'


def get_updates(offset_id='', limit=100):
    token = settings.SUPPORT_RUBIKA_BOT_TOKEN
    if not token:
        raise CommandError('SUPPORT_RUBIKA_BOT_TOKEN تنظیم نشده است.')
    payload = {'limit': int(limit)}
    if offset_id:
        payload['offset_id'] = str(offset_id)
    try:
        response = requests.post(
            f'{API_ROOT}/{token}/getUpdates',
            json=payload,
            timeout=(4, 12),
            allow_redirects=False,
        )
        response.raise_for_status()
        result = response.json()
    except requests.Timeout:
        raise CommandError('دریافت به‌روزرسانی روبیکا زمان‌بر شد.') from None
    except requests.RequestException:
        raise CommandError('ارتباط با API روبیکا برقرار نشد.') from None
    except ValueError:
        raise CommandError('پاسخ API روبیکا خوانا نبود.') from None
    if not isinstance(result, dict) or str(result.get('status', '')).lower() != 'ok':
        raise CommandError('API روبیکا درخواست دریافت به‌روزرسانی را نپذیرفت.')
    return result.get('data', {})


def extract_updates(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    value = data.get('updates')
    if isinstance(value, list):
        return value
    value = data.get('update')
    if isinstance(value, dict):
        return [value]
    nested = data.get('data')
    if isinstance(nested, dict):
        return extract_updates(nested)
    return [data]


def user_and_chat_ids(update):
    if not isinstance(update, dict):
        return '', ''
    event = update.get('event_data') if isinstance(update.get('event_data'), dict) else {}
    message = update.get('message') or update.get('new_message') or event.get('message') or event
    if not isinstance(message, dict):
        message = {}
    chat_id = message.get('chat_id') or update.get('chat_id') or event.get('chat_id') or ''
    user_id = (
        message.get('sender_id') or message.get('user_id')
        or update.get('sender_id') or update.get('user_id')
        or event.get('sender_id') or event.get('user_id') or ''
    )
    return str(chat_id), str(user_id)


def is_start_event(update):
    if not isinstance(update, dict):
        return False
    event = update.get('event_data') if isinstance(update.get('event_data'), dict) else {}
    message = update.get('message') or update.get('new_message') or event.get('message') or event
    if not isinstance(message, dict):
        message = {}
    text = str(message.get('text') or '').strip().lower()
    kind = str(update.get('type') or update.get('update_type') or '').replace('_', '').lower()
    return text == '/start' or kind in ('startedbot', 'start')


def wait_for_support_chat(timeout_seconds=180, interval_seconds=2, offset_id=''):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        data = get_updates(offset_id=offset_id)
        if isinstance(data, dict) and data.get('next_offset_id'):
            offset_id = str(data['next_offset_id'])
        for update in extract_updates(data):
            if not is_start_event(update):
                continue
            chat_id, user_id = user_and_chat_ids(update)
            if chat_id and user_id:
                return chat_id, user_id
        time.sleep(interval_seconds)
    return '', ''
