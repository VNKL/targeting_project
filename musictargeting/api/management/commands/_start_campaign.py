from rest_framework.generics import get_object_or_404

from musictargeting.api import serializers
from musictargeting.api.vk import vk_framework
from musictargeting.api.models import User, Ad, CampaignSettings, Campaign
from musictargeting.settings import DEV_RUCAPTCHA_KEY, DEV_PROXY


def start_campaign(campaign_settings_pk):
    campaign_settings = CampaignSettings.objects.get(pk=campaign_settings_pk)
    campaign_settings = serializers.CampaignSettingsSerializer(campaign_settings)
    campaign_settings = campaign_settings.data

    user = get_object_or_404(User, id=campaign_settings['owner'])
    if user:
        # Запуск кампании в ВК
        campaign = _start_campaign_in_vk(campaign_settings, user)
        campaign.update({'owner': user})

        campaign_without_nested_fields = campaign.copy()
        campaign_without_nested_fields.pop('ads', None)

        campaign_instance = Campaign(**campaign_without_nested_fields)
        campaign_instance.save()

        _create_ads_in_db(campaign, campaign_instance)


def _create_ads_in_db(campaign, campaign_instance):
    ads = []
    for ad in campaign['ads']:
        ads.append(Ad(campaign=campaign_instance,
                      campaign_name=campaign['campaign_name'],
                      campaign_vk_id=campaign['campaign_vk_id'],
                      ad_name=ad['ad_name'],
                      ad_vk_id=ad['ad_vk_id'],
                      playlist_url=ad['playlist_url']))
    Ad.objects.bulk_create(ads)


def _start_campaign_in_vk(campaign_settings, user):
    # Инициализация VK
    vk = vk_framework.VkAPI(token=user.vk_token,
                            rucaptcha_key=DEV_RUCAPTCHA_KEY,
                            proxy=DEV_PROXY,
                            ads_cabinet_id=campaign_settings['cabinet_vk_id'],
                            ads_client_id=campaign_settings['client_vk_id'])
    # Запуск кампании в VK
    campaign = vk.start_new_campaign(release_url=campaign_settings['release_url'],
                                     artist_group_id=campaign_settings['group_id'],
                                     post_text=campaign_settings['post_text'],
                                     campaign_budget=campaign_settings['budget'],
                                     artist_names=campaign_settings['musician_names'],
                                     sex_filter=campaign_settings['sex_filter'],
                                     age_disclaimer=campaign_settings['age_disclaimer'],
                                     age_from=campaign_settings['age_from'],
                                     age_to=campaign_settings['age_to'],
                                     find_related_artists=campaign_settings['find_related_artists'])
    return campaign
