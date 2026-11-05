import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportConversation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_token_hash', models.CharField(db_index=True, max_length=64, unique=True)),
                ('status', models.CharField(choices=[('open', 'باز'), ('closed', 'بسته')], db_index=True, default='open', max_length=12, verbose_name='وضعیت گفتگو')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان شروع')),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True, verbose_name='آخرین فعالیت')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='support_conversations', to=settings.AUTH_USER_MODEL, verbose_name='کاربر سایت')),
            ],
            options={
                'verbose_name': 'گفتگوی پشتیبانی',
                'verbose_name_plural': 'گفتگوهای پشتیبانی',
                'ordering': ('-updated_at',),
            },
        ),
        migrations.CreateModel(
            name='SupportMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender', models.CharField(choices=[('visitor', 'بازدیدکننده'), ('support', 'پشتیبان')], db_index=True, max_length=12, verbose_name='فرستنده')),
                ('body', models.TextField(verbose_name='متن پیام')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='زمان ارسال')),
                ('delivery_status', models.CharField(choices=[('pending', 'در انتظار ارسال'), ('sent', 'ارسال‌شده به روبیکا'), ('failed', 'ارسال ناموفق'), ('not_applicable', 'نیازی به ارسال ندارد')], db_index=True, default='not_applicable', max_length=20, verbose_name='وضعیت تحویل')),
                ('delivery_attempts', models.PositiveSmallIntegerField(default=0, verbose_name='تعداد تلاش ارسال')),
                ('delivery_error', models.CharField(blank=True, max_length=120, verbose_name='کد خطای ارسال')),
                ('rubika_message_id', models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ('rubika_inbound_message_id', models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='support.supportconversation', verbose_name='گفتگو')),
            ],
            options={
                'verbose_name': 'پیام پشتیبانی',
                'verbose_name_plural': 'پیام‌های پشتیبانی',
                'ordering': ('id',),
            },
        ),
    ]
