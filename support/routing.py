from django.urls import path

from .consumers import SupportChatConsumer


websocket_urlpatterns = [
    path('support/ws/', SupportChatConsumer.as_asgi(), name='support_websocket'),
]
