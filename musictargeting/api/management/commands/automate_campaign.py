from django.core.management.base import BaseCommand
from rest_framework.generics import get_object_or_404

from musictargeting.api.management.commands._automate_campaign import automate_campaign
from musictargeting.api.models import Campaign


class Command(BaseCommand):
    help = 'get campaign  from db with pk, ' \
           'start or stop campaign automate'

    def add_arguments(self, parser):
        parser.add_argument('-campaign_primary_key', action='store', dest='pk', type=int)
        parser.add_argument('-automate', action='store', dest='ss', type=int)
        parser.add_argument('-target_cost', action='store', dest='tc', type=int)
        parser.add_argument('-start_tomorrow', action='store', dest='st', type=int)
        parser.add_argument('-finish_tomorrow', action='store', dest='ft', type=int)
        parser.add_argument('-is_restart', action='store', dest='rs', type=int)

    def handle(self, *args, **options):
        campaign = get_object_or_404(Campaign, pk=options['pk'])

        # Остановка возможно уже запущенной автоматизации в другом процессе.
        # Соседний процесс увидит изменение параметра в БД и завершится
        if campaign.automate:
            campaign.automate = 0
            campaign.save()

        # Если передан параметр запуска автоматизации - собственно запуск автоматизации
        if options['ss']:
            automate_campaign(campaign=campaign,
                              target_cost=options['tc'],
                              start_tomorrow=options['st'],
                              finish_tomorrow=options['ft'],
                              is_restart=options['rs'] if options['rs'] else 0)
