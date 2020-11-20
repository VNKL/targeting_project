from rest_framework import serializers

from .models import User, AdsCabinet, Campaign, Ad, CampaignSettings


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = 'username', 'user_cabinets', 'client_cabinets', 'campaigns'


class AdsCabinetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdsCabinet
        fields = 'cabinet_type', 'cabinet_id', 'cabinet_name', 'client_id', 'client_name'


class CampaignSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Campaign
        fields = 'campaign_name', 'campaign_budget', 'spent', 'listens', 'reach', 'clicks', 'subscribes', \
                 'release_cover_url', 'create_datetime'


class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = 'ad_name', 'spent', 'reach', 'cpm', 'clicks', 'subscribes', 'listens'


class CampaignSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSettings
