from django.core.management.base import BaseCommand

from musictargeting.api.management.commands._start_campaign import start_campaign


class Command(BaseCommand):
    help = 'get new campaign settings from db with pk, ' \
           'start new campaign with settings, ' \
           'write started campaign objects to db'

    def handle(self, *args, **options):
        if options['pk']:
            start_campaign(options['pk'])

    def add_arguments(self, parser):
        parser.add_argument('-pk', action="store", dest='pk', type=int)
