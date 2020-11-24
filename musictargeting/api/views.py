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
        if request.query_params.get('extended'):
            serializer = serializers.CampaignExtendedSerializer(campaign)
        else:
            serializer = serializers.CampaignSerializer(campaign)
        return Response(serializer.data)

    def post(self, request):
        campaign_settings_serializer = serializers.CampaignSettingsSerializer(data=request.data)
        if campaign_settings_serializer.is_valid():
            campaign = campaign_settings_serializer.save()
            call_command('start_campaign', f'--pk={campaign.pk}')
            return Response({'info': 'campaign is starting, it takes some time'})
        else:
            return Response(campaign_settings_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
