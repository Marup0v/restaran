import asyncio

from django.core.management.base import BaseCommand, CommandError

from restaurant_app.bot import run


class Command(BaseCommand):
    help = 'Telegram botni ishga tushiradi'

    def handle(self, *args, **options):
        try:
            asyncio.run(run())
        except RuntimeError as error:
            raise CommandError(str(error)) from error
