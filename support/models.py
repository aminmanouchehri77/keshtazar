import uuid

from django.conf import settings
from django.db import models


class SupportConversation(models.Model):
    OPEN = 'open'
    CLOSED = 'closed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # The browser keeps the random value in its Django session; only its digest is stored here.
    session_token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='support_conversations',
        verbose_name='کاربر سایت',
    )
    status = models.CharField(
        max_length=12,
        choices=[(OPEN, 'باز'), (CLOSED, 'بسته')],
        default=OPEN,
        db_index=True,
        verbose_name='وضعیت گفتگو',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان شروع')
    updated_at = models.DateTimeField(auto_now=True, db_index=True, verbose_name='آخرین فعالیت')

    class Meta:
        ordering = ('-updated_at',)
        verbose_name = 'گفتگوی پشتیبانی'
        verbose_name_plural = 'گفتگوهای پشتیبانی'

    @property
    def public_code(self):
        return self.pk.hex[:10].upper()

    def __str__(self):
        return f'گفتگو #{self.public_code}'


class SupportMessage(models.Model):
    VISITOR = 'visitor'
    SUPPORT = 'support'
    DELIVERY_PENDING = 'pending'
    DELIVERY_SENT = 'sent'
    DELIVERY_FAILED = 'failed'
    DELIVERY_NOT_APPLICABLE = 'not_applicable'

    conversation = models.ForeignKey(
        SupportConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='گفتگو',
    )
    sender = models.CharField(
        max_length=12,
        choices=[(VISITOR, 'بازدیدکننده'), (SUPPORT, 'پشتیبان')],
        db_index=True,
        verbose_name='فرستنده',
    )
    body = models.TextField(verbose_name='متن پیام')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان ارسال')
    delivery_status = models.CharField(
        max_length=20,
        choices=[
            (DELIVERY_PENDING, 'در انتظار ارسال'),
            (DELIVERY_SENT, 'ارسال‌شده به روبیکا'),
            (DELIVERY_FAILED, 'ارسال ناموفق'),
            (DELIVERY_NOT_APPLICABLE, 'نیازی به ارسال ندارد'),
        ],
        default=DELIVERY_NOT_APPLICABLE,
        db_index=True,
        verbose_name='وضعیت تحویل',
    )
    delivery_attempts = models.PositiveSmallIntegerField(default=0, verbose_name='تعداد تلاش ارسال')
    delivery_error = models.CharField(max_length=120, blank=True, verbose_name='کد خطای ارسال')
    rubika_message_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    rubika_inbound_message_id = models.CharField(max_length=128, null=True, blank=True, unique=True)

    class Meta:
        ordering = ('id',)
        verbose_name = 'پیام پشتیبانی'
        verbose_name_plural = 'پیام‌های پشتیبانی'

    def __str__(self):
        return f'{self.get_sender_display()}، گفتگو #{self.conversation.public_code}'
