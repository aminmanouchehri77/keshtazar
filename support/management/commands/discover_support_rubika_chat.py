from django.core.management.base import BaseCommand, CommandError

from support.rubika_read import get_updates, wait_for_support_chat


class Command(BaseCommand):
    help = 'Read the private chat ID and sender ID after the support account starts the Rubika bot.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=180, help='Maximum wait time in seconds.')

    def handle(self, *args, **options):
        timeout = max(10, min(options['timeout'], 900))
        try:
            baseline = get_updates()
        except CommandError:
            raise
        offset_id = baseline.get('next_offset_id', '') if isinstance(baseline, dict) else ''
        self.stdout.write('From the support Rubika account, open the bot and send /start now.')
        try:
            chat_id, user_id = wait_for_support_chat(timeout_seconds=timeout, offset_id=offset_id)
        except CommandError:
            raise
        if not chat_id or not user_id:
            raise CommandError('No start message received. Check the token, network, and private chat.')
        self.stdout.write(self.style.SUCCESS('IDs received. Verify they belong to the support account:'))
        self.stdout.write(f'SUPPORT_RUBIKA_CHAT_ID={chat_id}')
        self.stdout.write(f'SUPPORT_RUBIKA_USER_ID={user_id}')
        self.stdout.write('Save both IDs in the server environment. Never share the bot token.')
