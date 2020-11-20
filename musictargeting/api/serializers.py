from rest_framework import serializers

from .models import User, AdsCabinet, Campaign, Ad, CampaignSettings


class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = 'ad_name', 'spent', 'reach', 'cpm', 'clicks', 'subscribes', 'listens'


class CampaignSerializer(serializers.ModelSerializer):
    ads = AdSerializer(many=True)

    class Meta:
        model = Campaign
        fields = 'campaign_name', 'campaign_budget', 'spent', 'listens', 'reach', 'clicks', 'subscribes', \
                 'release_cover_url', 'create_datetime', 'ads'


class AdsCabinetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdsCabinet
        fields = 'cabinet_type', 'cabinet_id', 'cabinet_name', 'client_id', 'client_name'


class UserSerializer(serializers.ModelSerializer):
    ads_cabinets = AdsCabinetSerializer(many=True)
    campaigns = CampaignSerializer(many=True)

    class Meta:
        model = User
        fields = 'username', 'vk_user_id', 'vk_token', 'ads_cabinets', 'campaigns'





class CampaignSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSettings
