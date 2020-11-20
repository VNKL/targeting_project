from django.contrib import admin

from . import models


@admin.register(models.User)
class UserAdmin(admin.ModelAdmin):
    list_display = 'username', 'vk_user_id'


@admin.register(models.AdsCabinet)
class AdsCabinetAdmin(admin.ModelAdmin):
    list_display = 'owner', 'cabinet_type'


@admin.register(models.Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = 'owner', 'campaign_name', 'campaign_budget', 'spent', 'listens', 'reach',  'create_datetime'


@admin.register(models.Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = 'campaign', 'campaign_name', 'ad_name', 'spent', 'listens', 'reach', 'cpm'
