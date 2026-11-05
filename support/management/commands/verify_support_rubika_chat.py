from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from support.rubika import RubikaAPIError, verify_private_support_chat


class Command(BaseCommand):
    help = 'Verify that the configured private Rubika chat belongs to the support account.'

    def handle(self, *args, **options):
        try:
            valid = verify_private_support_chat(
                settings.SUPPORT_RUBIKA_CHAT_ID,
                settings.SUPPORT_RUBIKA_USER_ID,
            )
        except RubikaAPIError as exc:
            raise CommandError(f'Rubika verification failed ({exc}). Check the bot token and network.') from None
        if not valid:
            raise CommandError('Chat ID and support account ID do not match.')
        self.stdout.write(self.style.SUCCESS('Private Rubika chat and support account verified.'))
