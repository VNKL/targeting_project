from rest_framework import serializers

from musictargeting.api.models import User, Cabinet, Campaign, Ad, CampaignSettings, Retarget


class AdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ad
        fields = 'ad_name', 'status', 'approved', 'spent', 'listens', 'cpl', 'reach', 'cpm', 'clicks', 'cpc', \
                 'subscribes', 'cps'


class CampaignSerializer(serializers.ModelSerializer):

    class Meta:
        model = Campaign
        fields = 'campaign_name', 'campaign_vk_id', 'status', 'campaign_budget', 'spent', 'listens', 'cpl', \
                 'reach', 'release_cover_url', 'create_datetime'


class CampaignExtendedSerializer(serializers.ModelSerializer):
    ads = AdSerializer(many=True)

    class Meta:
        model = Campaign
        fields = 'cabinet_vk_id', 'client_vk_id', 'campaign_name', 'campaign_vk_id', 'status', \
                 'campaign_budget', 'spent', 'listens', 'cpl', 'reach', 'cpm', 'clicks', 'cpc', \
                 'subscribes', 'cps', 'release_cover_url', 'create_datetime', 'ads'


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


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    def create(self, validated_data):
        user = User.objects.create(username=validated_data['username'],
                                   vk_user_id=validated_data['vk_user_id'],
                                   vk_token=validated_data['vk_token'])
        user.set_password(validated_data['password'])
        user.save()
        return user

    class Meta:
        model = User
        fields = 'username', 'vk_user_id', 'vk_token', 'id', 'password'


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


class AutomateSettingsSerializer(serializers.Serializer):

    campaign_primary_key = serializers.IntegerField()
    automate = serializers.BooleanField()
    target_cost = serializers.FloatField()
    start_tomorrow = serializers.BooleanField(default=False)
    finish_tomorrow = serializers.BooleanField(default=False)


class GroupSerializer(serializers.Serializer):

    group_name = serializers.CharField()
    group_vk_id = serializers.IntegerField()
    ava_url = serializers.CharField()
