from django.contrib.auth.models import User as DjangoUser
from django.db import models


class User(DjangoUser):

    vk_user_id = models.IntegerField()
    vk_token = models.CharField(max_length=100)

    def __str__(self):
        return f'User "{self.username}"'


class AdsCabinet(models.Model):

    CABINET_TYPE_CHOICES = [
        ['user', 'Пользовательский кабинет'],
        ['agency', 'Клиент в кабинете агентства']
    ]

    owner = models.ForeignKey(User, related_name='ads_cabinets', on_delete=models.CASCADE)
    cabinet_type = models.CharField(max_length=6, choices=CABINET_TYPE_CHOICES)
    cabinet_name = models.CharField(max_length=100)
    cabinet_id = models.IntegerField()
    client_name = models.CharField(max_length=100, null=True, blank=True)
    client_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        if self.client_name:
            return f'Client "{self.client_name}" of agency ads cabinet "{self.cabinet_name}"'
        else:
            return f'User ads cabinet "{self.cabinet_name}"'


class Campaign(models.Model):

    owner = models.ForeignKey(User, related_name='campaigns', on_delete=models.CASCADE)
    cabinet_id = models.IntegerField()
    client_id = models.IntegerField(null=True, blank=True)
    campaign_vk_id = models.IntegerField()
    campaign_name = models.CharField(max_length=100)
    campaign_budget = models.IntegerField()
    release_artist = models.CharField(max_length=100)
    release_title = models.CharField(max_length=100)
    release_cover_url = models.TextField()
    artist_group_id = models.IntegerField()
    playlists_group_id = models.IntegerField()
    spent = models.FloatField(default=0.0)
    reach = models.IntegerField(default=0)
    cpm = models.FloatField(default=30.0)
    clicks = models.IntegerField(default=0)
    subscribes = models.IntegerField(default=0)
    listens = models.IntegerField(default=0)
    create_datetime = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Campaign "{self.campaign_name}"'


class Ad(models.Model):

    campaign = models.ForeignKey(Campaign, related_name='ads', on_delete=models.CASCADE)
    campaign_name = models.CharField(max_length=100)
    campaign_vk_id = models.IntegerField()
    ad_name = models.CharField(max_length=100)
    ad_id = models.IntegerField()
    playlist_url = models.CharField(max_length=100)
    spent = models.FloatField(default=0.0)
    reach = models.IntegerField(default=0)
    cpm = models.FloatField(default=30.0)
    clicks = models.IntegerField(default=0)
    subscribes = models.IntegerField(default=0)
    listens = models.IntegerField(default=0)

    def __str__(self):
        return f'Ad "{self.ad_name}" in campaign {self.campaign_name}'


class CampaignSettings(models.Model):

    AGE_DISCLAIMER_CHOICES = [[1, '0+'], [2, '6+'], [3, '12+'], [4, '16+'], [5, '18+']]
    SEX_FILTER_CHOICES = [[0, 'Любой'], [1, 'Мужской'], [2, 'Женский']]
    AGE_CHOICES = [[0, 'Любой']] + [[x, str(x)] for x in range(14, 80)]

    owner = models.ForeignKey(User, related_name='campaigns_settings', on_delete=models.CASCADE)
    ads_cabinet_id = models.IntegerField()
    ads_client_id = models.IntegerField(default=0)
    release_url = models.CharField(max_length=100)
    post_text = models.TextField()
    group_id = models.IntegerField()
    budget = models.IntegerField()
    musician_names = models.TextField(blank=True)
    sex_filter = models.IntegerField(choices=SEX_FILTER_CHOICES, default=1)
    age_disclaimer = models.IntegerField(choices=AGE_DISCLAIMER_CHOICES, default=5)
    age_from = models.IntegerField(choices=AGE_CHOICES, default=0)
    age_to = models.IntegerField(choices=AGE_CHOICES, default=0)
    find_related_artists = models.BooleanField(default=False)