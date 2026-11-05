from django.urls import path

from . import views

app_name = 'support'

urlpatterns = [
    path('api/session/', views.chat_session, name='session'),
    path('api/messages/', views.chat_messages, name='messages'),
    path('rubika/<str:secret>/', views.rubika_webhook, name='rubika_webhook'),
]
