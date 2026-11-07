import json
from unittest.mock import patch

from django.test import LiveServerTestCase, TestCase, override_settings
from django.urls import reverse

from .models import SupportMessage


@override_settings(
    SUPPORT_RUBIKA_ENABLED=True, SUPPORT_RUBIKA_BOT_TOKEN='token',
    SUPPORT_RUBIKA_CHAT_ID='chat', SUPPORT_RUBIKA_USER_ID='user',
    SUPPORT_RUBIKA_WEBHOOK_SECRET='test-secret', SUPPORT_WEBSOCKET_REDIS_URL='',
    SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'],
)
class WebhookReplyTests(TestCase):
    def setUp(self):
        self.client.get(reverse('support:session'))
        with patch('support.rubika._api_call', return_value={'message_id': 'notification'}):
            response = self.client.post(reverse('support:messages'), data=json.dumps({'body': 'question'}), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.visitor_id = response.json()['message']['id']
        self.webhook = reverse('support:rubika_webhook', kwargs={'secret': 'test-secret'})
        self.update = {'type': 'NewMessage', 'chat_id': 'chat', 'new_message': {'sender_id': 'user', 'sender_type': 'User', 'message_id': 'answer', 'reply_to_message_id': 'notification', 'text': 'reply'}}

    def send_update(self, update):
        return self.client.post(self.webhook, data=json.dumps({'update': update}), content_type='application/json')

    def test_webhook_reply_reaches_original_browser_once(self):
        self.assertEqual(self.send_update(self.update).json()['processed'], 1)
        self.assertEqual(self.send_update(self.update).json()['processed'], 0)
        response = self.client.get(reverse('support:messages'), {'after': self.visitor_id})
        self.assertEqual([m['body'] for m in response.json()['messages']], ['reply'])

    def test_wrong_sender_and_secret_are_rejected(self):
        self.update['new_message']['sender_id'] = 'other'
        self.assertEqual(self.send_update(self.update).json()['processed'], 0)
        response = self.client.post(reverse('support:rubika_webhook', kwargs={'secret': 'wrong'}), data=json.dumps({'update': self.update}), content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(SupportMessage.objects.filter(sender=SupportMessage.SUPPORT).exists())


@override_settings(
    SUPPORT_RUBIKA_ENABLED=True, SUPPORT_RUBIKA_BOT_TOKEN='test-token',
    SUPPORT_RUBIKA_CHAT_ID='support-chat', SUPPORT_RUBIKA_USER_ID='support-user',
    SUPPORT_RUBIKA_WEBHOOK_SECRET='test-webhook-secret', SUPPORT_WEBSOCKET_REDIS_URL='',
    SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'],
)
class LiveWebhookReplyTests(LiveServerTestCase):
    def test_reply_over_http_reaches_same_browser_session(self):
        import requests
        from .models import SupportConversation

        browser = requests.Session()
        session = browser.get(self.live_server_url + reverse('support:session'), timeout=5)
        self.assertEqual(session.status_code, 200)
        conversation = SupportConversation.objects.get()
        question = SupportMessage.objects.create(
            conversation=conversation, sender=SupportMessage.VISITOR, body='local question',
            rubika_message_id='local-notification', delivery_status=SupportMessage.DELIVERY_SENT,
        )
        webhook_url = self.live_server_url + reverse('support:rubika_webhook', kwargs={'secret': 'test-webhook-secret'})
        update = {'update': {'type': 'NewMessage', 'chat_id': 'support-chat', 'new_message': {
            'sender_id': 'support-user', 'sender_type': 'User', 'message_id': 'local-reply',
            'reply_to_message_id': 'local-notification', 'text': 'local support reply',
        }}}
        result = requests.post(webhook_url, json=update, timeout=5)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['processed'], 1)
        response = browser.get(self.live_server_url + reverse('support:messages'), params={'after': question.pk}, timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['body'] for item in response.json()['messages']], ['local support reply'])
        repeated = requests.post(webhook_url, json=update, timeout=5)
        self.assertEqual(repeated.json()['processed'], 0)
        print('LOCAL HTTP TEST: webhook=200, processed=1, browser received reply, duplicate=0')
