from django.urls import path

from . import views

app_name = 'support'

urlpatterns = [
    path('api/session/', views.chat_session, name='session'),
    path('api/messages/', views.chat_messages, name='messages'),
    path('ws/', views.websocket_http_fallback, name='websocket'),
    # Match the working support_chat deployment path. Keep the earlier path
    # as an alias so an already-registered Rubika webhook does not break.
    path('rubika/webhook/<str:secret>/', views.rubika_webhook, name='rubika_webhook'),
    path('rubika/<str:secret>/', views.rubika_webhook, name='rubika_webhook_legacy'),
]
