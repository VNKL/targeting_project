from django.core.management import call_command
from django.core.management.base import BaseCommand

from musictargeting.api.models import Campaign


class Command(BaseCommand):
    help = 'continue automate campaigns after server restart'

    def handle(self, *args, **options):
        campaigns = Campaign.objects.all().filter(automate=1)
        for campaign in list(campaigns):
            automate_settings = list(campaign.automate_settings.all().order_by('-settings_create_datetime'))[0]
            call_command('automate_campaign',
                         campaign_primary_key=campaign.pk,
                         automate=campaign.automate,
                         target_cost=automate_settings.target_cost,
                         start_tomorrow=automate_settings.start_tomorrow,
                         finish_tomorrow=automate_settings.finish_tomorrow,
                         is_restart=1)
