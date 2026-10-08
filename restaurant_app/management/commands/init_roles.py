from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Restoran rollari uchun Django guruhlarini yaratadi'

    def handle(self, *args, **options):
        Group.objects.get_or_create(name='Oshpaz')
        self.stdout.write(self.style.SUCCESS('Oshpaz guruhi tayyor. Administrator is_staff orqali aniqlanadi.'))
