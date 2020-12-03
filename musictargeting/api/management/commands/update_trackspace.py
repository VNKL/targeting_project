from django.core.management.base import BaseCommand

from musictargeting.api.management.commands._update_trackspace import update_trackspace


class Command(BaseCommand):
    help = 'update trackspace by vk chart and fit new StandardScaler'

    def handle(self, *args, **options):
        update_trackspace()


