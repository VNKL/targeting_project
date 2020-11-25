import json
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, get_list_or_404
from rest_framework import viewsets, views, status
from rest_framework import permissions
from rest_framework.response import Response
from django.http import JsonResponse
from django.core.management import call_command
from multiprocessing import Process

from .models import User, Cabinet, Campaign, Ad, Retarget
from . import serializers
from . import vk_framework
from ..settings import DEV_RUCAPTCHA_KEY, DEV_PROXY


def api_index_view(request):
    return JsonResponse({'detail': 'This is api root page. Use existing methods after api/'},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-pk')
    serializer_class = serializers.UserExtendedSerializer
    permission_classes = [permissions.IsAdminUser]


class CabinetViewSet(viewsets.ModelViewSet):
    queryset = Cabinet.objects.all().order_by('-pk')
    serializer_class = serializers.CabinetSerializer
    permission_classes = [permissions.IsAdminUser]


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by('-create_datetime')
    serializer_class = serializers.CampaignExtendedSerializer
    permission_classes = [permissions.IsAdminUser]


class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all().order_by('ad_name')
    serializer_class = serializers.AdSerializer
    permission_classes = [permissions.IsAdminUser]


class UserView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = get_object_or_404(User, username=request.user.username)
        if request.query_params.get('extended'):
            serializer = serializers.UserExtendedSerializer(user, context={'request': request})
        else:
            serializer = serializers.UserSerializer(user)
        return Response(serializer.data)

    def post(self, request):
        serializer = serializers.UserExtendedSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CabinetListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.query_params.get('update'):
            self._update_user_ads_cabinets(request)
        ads_cabinets = get_list_or_404(Cabinet, owner=request.user)
        if request.query_params.get('extended'):
            serializer = serializers.CabinetExtendedSerializer(ads_cabinets, many=True)
        else:
            serializer = serializers.CabinetSerializer(ads_cabinets, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = serializers.CabinetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _update_user_ads_cabinets(request):
        user = get_object_or_404(User, username=request.user.username)

        # Получение актуальных кабинетов
        vk = vk_framework.VkTools(token=user.vk_token, rucaptcha_key=DEV_RUCAPTCHA_KEY, proxy=DEV_PROXY)
        ads_cabinets = vk.get_all_ads_cabinets()

        # Удаление предыдущих объектов кабинетов
        Cabinet.objects.all().filter(owner=user).delete()

        # Создание и сохранений новых объектов кабинетов
        if ads_cabinets['user_cabinets']:
            for cab in ads_cabinets['user_cabinets']:
                cabinet = Cabinet(owner=user,
                                  cabinet_type='user',
                                  cabinet_name=cab['cabinet_name'],
                                  cabinet_vk_id=cab['cabinet_id'])
                cabinet.save()

        if ads_cabinets['client_cabinets']:
            for cab in ads_cabinets['client_cabinets']:
                cabinet = Cabinet(owner=user,
                                  cabinet_type='agency',
                                  cabinet_name=cab['cabinet_name'],
                                  cabinet_vk_id=cab['cabinet_id'],
                                  client_name=cab['client_name'],
                                  client_vk_id=cab['client_id'])
                cabinet.save()


class CampaignListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        campaigns = get_list_or_404(Campaign, owner=request.user)
        if request.query_params.get('extended'):
            serializer = serializers.CampaignExtendedSerializer(campaigns, many=True)
        else:
            serializer = serializers.CampaignSerializer(campaigns, many=True)
        return Response(serializer.data)

    def post(self, request):
        request_data = request.data
        request_data.update({'owner': request.user})
        campaign_settings_serializer = serializers.CampaignSettingsSerializer(data=request_data)
        if campaign_settings_serializer.is_valid():
            campaign = campaign_settings_serializer.save()
            process = Process(target=call_command, args=('start_campaign', f'-pk={campaign.pk}',))
            process.start()
            return Response({'info': 'campaign is starting, it takes some time'})
        else:
            return Response(campaign_settings_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignDetailView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, campaign_vk_id):
        campaign = get_object_or_404(Campaign, owner=request.user, campaign_vk_id=campaign_vk_id)

        if request.query_params.get('update'):
            campaign = self._update_campaign_stats(campaign, campaign_vk_id, request)

        elif request.query_params.get('automate'):
            return self._automate_campaign(campaign, request)

        serializer = serializers.CampaignExtendedSerializer(campaign)
        return Response(serializer.data)

    @staticmethod
    def _automate_campaign(campaign, request):
        automate_setting = {k: v[0] for k, v in dict(request.query_params).items()}
        automate_setting['campaign_primary_key'] = campaign.pk
        serializer = serializers.AutomateSettingsSerializer(data=automate_setting)
        if serializer.is_valid():
            call_command('automate_campaign', **serializer.data)
            return Response({'info': 'campaign automate is starting, it take some time'})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        campaign_settings_serializer = serializers.CampaignSettingsSerializer(data=request.data)
        if campaign_settings_serializer.is_valid():
            campaign = campaign_settings_serializer.save()
            call_command('start_campaign', pk=campaign.pk)
            return Response({'info': 'campaign is starting, it takes some time'})
        else:
            return Response(campaign_settings_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _update_campaign_stats(campaign, campaign_vk_id, request):
        # Получение юзера, чтобы взять его вк токен
        user = get_object_or_404(User, username=request.user.username)

        # Получение объявлений кампании и рефакторинг их для ВК фреймворка
        ads = get_list_or_404(Ad, campaign_vk_id=campaign_vk_id)
        ads_for_vk_framework = {ad.ad_vk_id: ad.playlist_url for ad in list(ads)}

        # Получение статы объявлений
        vk = vk_framework.VkAPI(token=user.vk_token, rucaptcha_key=DEV_RUCAPTCHA_KEY, proxy=DEV_PROXY,
                                ads_cabinet_id=campaign.cabinet_vk_id, ads_client_id=campaign.client_vk_id)
        ads_stat = vk.get_full_ads_stat(ads=ads_for_vk_framework)
        ads_statuses = vk.ads.get_ads(campaign_id=campaign_vk_id)

        # Обновление объектов объявлений и получение обновлений для объекта кампании
        updated_campaign_stat = CampaignDetailView._update_ads_objects(ads, ads_stat, ads_statuses)

        # Обновление статуса кампании
        campaign_status = vk.ads.get_campaigns()
        if campaign_status:
            updated_campaign_stat['status'] = campaign_status[campaign_vk_id]

        # Обновление объекта кампании и сохранение его в БД
        updated_campaign = CampaignDetailView._update_campaign_object(campaign, updated_campaign_stat)

        return updated_campaign

    @staticmethod
    def _update_campaign_object(campaign, updated_campaign_stat):
        campaign.spent = updated_campaign_stat['spent']
        campaign.listens = updated_campaign_stat['listens']
        campaign.listens = updated_campaign_stat['reach']
        campaign.listens = updated_campaign_stat['clicks']
        campaign.listens = updated_campaign_stat['subscribes']

        reach = updated_campaign_stat['reach']
        listens = updated_campaign_stat['listens']

        campaign.cpm = updated_campaign_stat['spent'] / (reach / 1000) if reach else 0
        campaign.cpl = updated_campaign_stat['spent'] / listens if listens else 0

        if 'status' in updated_campaign_stat.keys():
            campaign.status = updated_campaign_stat['status']

        campaign.save()

        return campaign

    @staticmethod
    def _update_ads_objects(ads, ads_stat, ads_statuses):
        updated_ad_objects = []
        updated_campaign_stat = {'spent': 0, 'listens': 0, 'reach': 0, 'clicks': 0, 'subscribes': 0}
        for ad in list(ads):
            # Если был охват (если он не ноль)
            if ads_stat[ad.ad_vk_id]['reach']:
                # Обновление статы в объектах объявлений
                ad.spent = ads_stat[ad.ad_vk_id]['spent']
                ad.reach = ads_stat[ad.ad_vk_id]['reach'],
                ad.cpm = ads_stat[ad.ad_vk_id]['cpm'],
                ad.clicks = ads_stat[ad.ad_vk_id]['clicks'],
                ad.subscribes = ads_stat[ad.ad_vk_id]['subscribes'],
                ad.listens = ads_stat[ad.ad_vk_id]['listens']
                # Обновление средней статы кампании
                for param in updated_campaign_stat.keys():
                    updated_campaign_stat[param] += ads_stat[ad.ad_vk_id][param]
            # Обновление статусов объявлений
            ad.status = ads_statuses[ad.ad_vk_id]['status']
            ad.approved = ads_statuses[ad.ad_vk_id]['approved']
            # Добавление обновленного объекта в лист
            updated_ad_objects.append(ad)

        # Сохранение обновленных объектво объявлений в БД
        Ad.objects.bulk_update(updated_ad_objects, ['spent', 'reach', 'cpm', 'clicks', 'subscribes', 'listens',
                                                    'status', 'approved'])

        # Возврат обновленной средней статы кампании
        return updated_campaign_stat


class AdListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.query_params.get('campaign_vk_id'):
            return Response({'detail': 'campaign_vk_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            campaign_vk_id = int(request.query_params.get('campaign_vk_id'))
        except (ValueError, TypeError):
            return Response({'detail': 'campaign_vk_id must be int'}, status=status.HTTP_400_BAD_REQUEST)

        ads = get_list_or_404(Ad, campaign_vk_id=campaign_vk_id)
        serializer = serializers.AdSerializer(ads, many=True)
        return Response(serializer.data)


class GroupListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = get_object_or_404(User, username=request.user.username)
        vk = vk_framework.VkTools(token=user.vk_token, rucaptcha_key=DEV_RUCAPTCHA_KEY, proxy=DEV_PROXY)
        groups = vk.get_groups()
        serializer = serializers.GroupSerializer(groups, many=True)
        return Response(serializer.data)


class RetargetListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = get_object_or_404(User, username=request.user.username)
        if request.query_params.get('update'):
            cabibets = Cabinet.objects.all().filter(owner=user)
            for cab in list(cabibets):
                self._update_cabinet_retarget(cab, user)
            return Response({'info': 'retarget was update'})

        elif request.query_params.get('cabinet_vk_id'):
            try:
                cabinet_vk_id = int(request.query_params.get('cabinet_vk_id'))
            except (ValueError, TypeError):
                return Response({'detail': 'cabinet_vk_id must be int'}, status=status.HTTP_400_BAD_REQUEST)
            retarget = get_list_or_404(Retarget, cabinet_vk_id=cabinet_vk_id)
            serializer = serializers.RetargetSerializer(retarget, many=True)
            return Response(serializer.data)

        elif request.query_params.get('client_vk_id'):
            try:
                client_vk_id = int(request.query_params.get('client_vk_id'))
            except (ValueError, TypeError):
                return Response({'detail': 'client_vk_id must be int'}, status=status.HTTP_400_BAD_REQUEST)
            retarget = get_list_or_404(Retarget, client_vk_id=client_vk_id)
            serializer = serializers.RetargetSerializer(retarget, many=True)
            return Response(serializer.data)

        else:
            return Response({'detail': 'cabinet_vk_id or client_vk_id is required'},
                            status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _update_cabinet_retarget(cabinet, user):
        vk = vk_framework.VkAds(token=user.vk_token,
                                cabinet_id=cabinet.cabinet_vk_id, client_id=cabinet.client_vk_id,
                                rucaptcha_key=DEV_RUCAPTCHA_KEY, proxy=DEV_PROXY)
        vk_retarget = vk.get_retarget(minimal_size=0)
        if vk_retarget:
            new_retarget_objects = []
            for retarget_item in vk_retarget:
                new_retarget_objects.append(Retarget(cabinet=cabinet,
                                                     cabinet_vk_id=cabinet.cabinet_vk_id,
                                                     client_vk_id=cabinet.client_vk_id,
                                                     retarget_name=retarget_item['retarget_name'],
                                                     retarget_vk_id=retarget_item['retarget_id'],
                                                     audience_count=retarget_item['audience_count']))
            Retarget.objects.bulk_create(new_retarget_objects)
