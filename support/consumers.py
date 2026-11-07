import hashlib
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import SupportConversation
from .realtime import serialize_support_message


SESSION_TOKEN_KEY = 'keshtazar_support_chat_token'


class SupportChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if not self.channel_layer:
            await self.close(code=1013)
            return

        session = self.scope.get('session')
        token = session.get(SESSION_TOKEN_KEY) if session else None
        conversation_id = await self._conversation_id(token)
        if not conversation_id:
            await self.close(code=4401)
            return

        self.group_name = f'support_{conversation_id.hex}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        query = parse_qs(self.scope.get('query_string', b'').decode('ascii', 'ignore'))
        try:
            after_id = max(0, int(query.get('after', ['0'])[0]))
        except (TypeError, ValueError):
            after_id = 0
        for message in await self._messages_after(conversation_id, after_id):
            await self.send_json({'type': 'message', 'message': message})

    async def disconnect(self, close_code):
        group_name = getattr(self, 'group_name', None)
        if group_name and self.channel_layer:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def support_message(self, event):
        await self.send_json({'type': 'message', 'message': event['message']})

    @database_sync_to_async
    def _conversation_id(self, token):
        if not isinstance(token, str) or len(token) < 32:
            return None
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        return SupportConversation.objects.filter(session_token_hash=token_hash).values_list('pk', flat=True).first()

    @database_sync_to_async
    def _messages_after(self, conversation_id, after_id):
        messages = SupportConversation.objects.get(pk=conversation_id).messages.filter(pk__gt=after_id).order_by('id')[:100]
        return [serialize_support_message(message) for message in messages]
