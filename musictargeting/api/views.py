from django.shortcuts import get_object_or_404, get_list_or_404
from rest_framework import viewsets, views, status
from rest_framework import permissions
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from django.http import JsonResponse
from django.core.management import call_command
from multiprocessing import Process

from musictargeting.api.models import User, Cabinet, Campaign, Ad, Retarget
from musictargeting.api import serializers
from musictargeting.api.vk import vk_framework
from musictargeting.settings import DEV_RUCAPTCHA_KEY, DEV_PROXY


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


class UserCreateView(CreateAPIView):
    model = User
    serializer_class = serializers.UserCreateSerializer
    permission_classes = [permissions.AllowAny]


class CabinetListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        ads_cabinets = get_list_or_404(Cabinet, owner=request.user)
        if request.query_params.get('extended'):
            serializer = serializers.CabinetExtendedSerializer(ads_cabinets, many=True)
        else:
            serializer = serializers.CabinetSerializer(ads_cabinets, many=True)
        return Response(serializer.data)


class CabinetUpdateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cabinets = self._update_user_ads_cabinets(request)
        serializer = serializers.CabinetSerializer(cabinets, many=True)
        return Response(serializer.data)

    @staticmethod
    def _update_user_ads_cabinets(request):
        user = get_object_or_404(User, username=request.user.username)

        # Получение актуальных кабинетов
        vk = vk_framework.VkTools(token=user.vk_token, rucaptcha_key=DEV_RUCAPTCHA_KEY, proxy=DEV_PROXY)
        ads_cabinets = vk.get_all_ads_cabinets()

        # Удаление предыдущих объектов кабинетов
        Cabinet.objects.all().filter(owner=user).delete()

        # Создание и сохранений новых объектов кабинетов
        new_cabinets = []
        if ads_cabinets['user_cabinets']:
            for cab in ads_cabinets['user_cabinets']:
                new_cabinets.append(Cabinet(owner=user,
                                            cabinet_type='user',
                                            cabinet_name=cab['cabinet_name'],
                                            cabinet_vk_id=cab['cabinet_id']))

        if ads_cabinets['client_cabinets']:
            for cab in ads_cabinets['client_cabinets']:
                new_cabinets.append(Cabinet(owner=user,
                                            cabinet_type='agency',
                                            cabinet_name=cab['cabinet_name'],
                                            cabinet_vk_id=cab['cabinet_id'],
                                            client_name=cab['client_name'],
                                            client_vk_id=cab['client_id']))
        cabinets = Cabinet.objects.bulk_create(new_cabinets)
        return cabinets


class CampaignCreateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        params_list = ['cabinet_vk_id', 'release_url', 'post_text', 'group_id', 'budget', 'sex_filter',
                       'age_from', 'age_to', 'find_related_artists']
        params = {'owner': request.user}
        for param in params_list:
            if request.query_params.get(param):
                params[param] = request.query_params.get(param)

        campaign_settings_serializer = serializers.CampaignSettingsSerializer(data=params)
        if campaign_settings_serializer.is_valid():
            campaign = campaign_settings_serializer.save()
            process = Process(target=call_command, args=('start_campaign',), kwargs={'pk': campaign.pk})
            process.start()
            return Response({'info': 'campaign is starting, it takes some time'})
        else:
            return Response(campaign_settings_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        campaigns = get_list_or_404(Campaign, owner=request.user)
        if request.query_params.get('extended'):
            serializer = serializers.CampaignExtendedSerializer(campaigns, many=True)
        else:
            serializer = serializers.CampaignSerializer(campaigns, many=True)
        return Response(serializer.data)


class CampaignDetailView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        campaign_vk_id = request.query_params.get('campaign_vk_id')
        if not campaign_vk_id:
            return Response({'detail': 'campaign_vk_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        campaign = get_object_or_404(Campaign, owner=request.user, campaign_vk_id=campaign_vk_id)
        serializer = serializers.CampaignExtendedSerializer(campaign)
        return Response(serializer.data)


class CampaignUpdateStatsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        campaign_vk_id = request.query_params.get('campaign_vk_id')
        if not campaign_vk_id:
            return Response({'detail': 'campaign_vk_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            campaign_vk_id = int(campaign_vk_id)
        except TypeError:
            return Response({'detail': 'campaign_vk_id must be int'}, status=status.HTTP_400_BAD_REQUEST)

        campaign = get_object_or_404(Campaign, owner=request.user, campaign_vk_id=campaign_vk_id)
        campaign = self._update_campaign_stats(campaign, campaign_vk_id, request)
        serializer = serializers.CampaignExtendedSerializer(campaign)
        return Response(serializer.data)

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
        updated_campaign_stat = CampaignUpdateStatsView._update_ads_objects(ads, ads_stat, ads_statuses)

        # Обновление статуса кампании
        campaign_status = vk.ads.get_campaigns()
        if campaign_status:
            updated_campaign_stat['status'] = campaign_status[campaign_vk_id]['status']

        # Обновление объекта кампании и сохранение его в БД
        updated_campaign = CampaignUpdateStatsView._update_campaign_object(campaign, updated_campaign_stat)

        return updated_campaign

    @staticmethod
    def _update_campaign_object(campaign, updated_campaign_stat):
        spent = round(updated_campaign_stat['spent'], 2)
        reach = updated_campaign_stat['reach']
        listens = updated_campaign_stat['listens']
        clicks = updated_campaign_stat['clicks']
        subscribes = updated_campaign_stat['subscribes']

        campaign.spent = spent
        campaign.listens = listens
        campaign.reach = reach
        campaign.clicks = clicks
        campaign.subscribes = subscribes

        campaign.cpm = round((spent / (reach / 1000)), 2) if reach else 0
        campaign.cpl = round((spent / listens), 2) if listens else 0
        campaign.cpc = round((spent / clicks), 2) if clicks else 0
        campaign.cps = round((spent / subscribes), 2) if subscribes else 0

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
                ad.reach = ad.reach[0]
                ad.listens = ads_stat[ad.ad_vk_id]['listens']
                ad.clicks = ads_stat[ad.ad_vk_id]['clicks'],
                ad.clicks = ad.clicks[0]
                ad.subscribes = ads_stat[ad.ad_vk_id]['subscribes'],
                ad.subscribes = ad.subscribes[0]

                ad.cpm = ads_stat[ad.ad_vk_id]['cpm'],
                ad.cpm = ad.cpm[0]
                ad.cpl = round((ad.spent / ad.listens), 2) if ad.listens else 0
                ad.cpc = round((ad.spent / ad.clicks), 2) if ad.clicks else 0
                ad.cps = round((ad.spent / ad.subscribes), 2) if ad.subscribes else 0

                # Обновление средней статы кампании
                for param in updated_campaign_stat.keys():
                    updated_campaign_stat[param] += ads_stat[ad.ad_vk_id][param]

            # Обновление статусов объявлений
            ad.status = ads_statuses[ad.ad_vk_id]['status']
            ad.approved = ads_statuses[ad.ad_vk_id]['approved']

            # Добавление обновленного объекта в лист
            updated_ad_objects.append(ad)

        # Сохранение обновленных объектво объявлений в БД
        Ad.objects.bulk_update(updated_ad_objects,
                               ['spent', 'reach', 'cpm', 'clicks', 'cpc', 'subscribes', 'cps', 'listens', 'cpl',
                                'status', 'approved'],
                               batch_size=40)

        # Возврат обновленной средней статы кампании
        return updated_campaign_stat


class CampaignStartAutomateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        campaign_vk_id = request.query_params.get('campaign_vk_id')
        if not campaign_vk_id:
            return Response({'detail': 'campaign_vk_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        campaign = get_object_or_404(Campaign, owner=request.user, campaign_vk_id=campaign_vk_id)
        return self._automate_campaign(campaign, request)

    @staticmethod
    def _automate_campaign(campaign, request):
        automate_setting = {k: v[0] for k, v in dict(request.query_params).items()}
        automate_setting['campaign_primary_key'] = campaign.pk
        automate_setting['campaign'] = campaign
        serializer = serializers.AutomateSettingsSerializer(data=automate_setting)
        if serializer.is_valid():
            serializer.save()
            process = Process(target=call_command, args=('automate_campaign',), kwargs=serializer.data)
            process.start()
            return Response({'info': 'campaign automate is starting, it take some time'})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignStopAutomateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        campaign_vk_id = request.query_params.get('campaign_vk_id')
        if not campaign_vk_id:
            return Response({'detail': 'campaign_vk_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        campaign = get_object_or_404(Campaign, owner=request.user, campaign_vk_id=campaign_vk_id)
        campaign.automate = 0
        campaign.save()
        return Response({'info': 'campaign automate is stopping, it take some time'})


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
        groups = [{'group_name': x['group_name'],
                   'group_vk_id': x['group_id'],
                   'ava_url': x['ava_url']} for x in groups]
        serializer = serializers.GroupSerializer(groups, many=True)
        return Response(serializer.data)


class RetargetListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.query_params.get('cabinet_vk_id'):
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


class RetargetUpdateView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = get_object_or_404(User, username=request.user.username)
        cabibets = Cabinet.objects.all().filter(owner=user)
        for cab in list(cabibets):
            self._update_cabinet_retarget(cab, user)
        return Response({'info': 'retarget was update'})

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
