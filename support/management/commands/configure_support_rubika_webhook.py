from ipaddress import ip_address
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from support.rubika import RubikaAPIError, _api_call, verify_private_support_chat


class Command(BaseCommand):
    help = 'Verify the support account and register the Rubika webhook on the public HTTPS domain.'

    def handle(self, *args, **options):
        required = (
            settings.SUPPORT_RUBIKA_BOT_TOKEN,
            settings.SUPPORT_RUBIKA_CHAT_ID,
            settings.SUPPORT_RUBIKA_USER_ID,
            settings.SUPPORT_RUBIKA_WEBHOOK_SECRET,
        )
        if not all(required):
            raise CommandError('Bot token, support IDs, and webhook secret must all be configured.')
        if len(settings.SUPPORT_RUBIKA_WEBHOOK_SECRET) < 32:
            raise CommandError('SUPPORT_RUBIKA_WEBHOOK_SECRET must contain at least 32 characters.')
        if not settings.SUPPORT_RUBIKA_WEBHOOK_SECRET.replace('-', '').replace('_', '').isalnum():
            raise CommandError('SUPPORT_RUBIKA_WEBHOOK_SECRET must use URL-safe letters, numbers, - and _.')

        base_url = settings.SUPPORT_PUBLIC_URL.strip().rstrip('/')
        parsed = urlsplit(base_url)
        host = parsed.hostname or ''
        local_host = host.lower() in {'localhost', 'localhost.localdomain'} or host.lower().endswith('.local')
        try:
            local_ip = ip_address(host).is_loopback or ip_address(host).is_private
        except ValueError:
            local_ip = False
        if (
            parsed.scheme != 'https'
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or local_host
            or local_ip
        ):
            raise CommandError('SUPPORT_PUBLIC_URL must be a public HTTPS address, not localhost or a private IP.')

        try:
            if not verify_private_support_chat(settings.SUPPORT_RUBIKA_CHAT_ID, settings.SUPPORT_RUBIKA_USER_ID):
                raise CommandError('Support chat verification failed; the webhook was not registered.')
            endpoint_path = reverse(
                'support:rubika_webhook',
                kwargs={'secret': settings.SUPPORT_RUBIKA_WEBHOOK_SECRET},
            )
            _api_call('updateBotEndpoints', {
                'url': f'{base_url}{endpoint_path}',
                'type': 'ReceiveUpdate',
            })
        except RubikaAPIError as exc:
            raise CommandError(f'Rubika webhook registration failed ({exc}). Check the token and chat IDs.') from None

        self.stdout.write(self.style.SUCCESS('Rubika webhook registered. Set SUPPORT_RUBIKA_ENABLED=True and restart the app.'))
