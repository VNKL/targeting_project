from abc import ABC

from rest_framework import serializers

from .models import User, Cabinet, Campaign, Ad, CampaignSettings, Retarget


class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = 'ad_name', 'spent', 'listens', 'cpl', 'reach', 'cpm', 'clicks', 'subscribes'


class CampaignSerializer(serializers.ModelSerializer):

    class Meta:
        model = Campaign
        fields = 'campaign_name', 'campaign_vk_id', 'campaign_budget', 'spent', 'listens', 'cpl', 'reach', 'cpm', \
                 'clicks', 'subscribes', 'release_cover_url', 'create_datetime'


class CampaignExtendedSerializer(serializers.ModelSerializer):
    ads = AdSerializer(many=True)

    class Meta:
        model = Campaign
        fields = 'cabinet_vk_id', 'client_vk_id', 'campaign_name', 'campaign_vk_id', 'campaign_budget', 'spent', \
                 'listens', 'cpl', 'reach', 'cpm', 'clicks', 'subscribes', 'release_cover_url', 'create_datetime', 'ads'


class RetargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Retarget
        fields = 'retarget_name', 'retarget_vk_id', 'audience_count'


class CabinetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cabinet
        fields = 'cabinet_type', 'cabinet_vk_id', 'cabinet_name', 'client_vk_id', 'client_name'


class CabinetExtendedSerializer(serializers.ModelSerializer):
    retarget = RetargetSerializer(many=True)

    class Meta:
        model = Cabinet
        fields = 'cabinet_type', 'cabinet_vk_id', 'cabinet_name', 'client_vk_id', 'client_name', 'retarget'


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = 'username', 'vk_user_id', 'vk_token'


class UserExtendedSerializer(serializers.ModelSerializer):
    cabinets = CabinetSerializer(many=True)
    campaigns = CampaignSerializer(many=True)

    class Meta:
        model = User
        fields = 'username', 'vk_user_id', 'vk_token', 'cabinets', 'campaigns'


class CampaignSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSettings
        fields = '__all__'


class GroupSerializer(serializers.Serializer):

    group_name = serializers.CharField()
    group_vk_id = serializers.IntegerField()
    ava_url = serializers.CharField()
