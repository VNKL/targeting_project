import json
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, get_list_or_404
from rest_framework import viewsets, views, status
from rest_framework import permissions
from rest_framework.response import Response
from django.http import JsonResponse

from .models import User, AdsCabinet, Campaign, Ad
from . import serializers
from . import vk_framework
from ..settings import DEV_RUCAPTCHA_KEY, DEV_PROXY


def start_campaign(request, campaign_settings):
    # TODO  Допилить код запуска и сохранения кампании в отдельном процессе
    started_campaign = {}   # Вот сюда что-то должно вернуть все параметры запущенной кампании
    campaign_serializer = serializers.CampaignExtendedSerializer(data=started_campaign)
    if campaign_serializer.is_valid():
        campaign_serializer.save()
    # TODO После сохранения кампании нужно насохранять объявлений


def api_index_view(request):
    return JsonResponse({'detail': 'This is api root page. Use existing methods after api/'},
                        status=status.HTTP_405_METHOD_NOT_ALLOWED)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-pk')
    serializer_class = serializers.UserExtendedSerializer
    permission_classes = [permissions.IsAdminUser]


class AdsCabinetViewSet(viewsets.ModelViewSet):
    queryset = AdsCabinet.objects.all().order_by('-pk')
    serializer_class = serializers.AdsCabinetSerializer
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


class AdsCabinetListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.query_params.get('update_cabinets'):
            self._update_user_ads_cabinets(request)
        ads_cabinets = get_list_or_404(AdsCabinet, owner=request.user)
        serializer = serializers.AdsCabinetSerializer(ads_cabinets, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = serializers.AdsCabinetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _update_user_ads_cabinets(request):
        user = get_object_or_404(User, username=request.user.username)
        if user:
            vk = vk_framework.VkTools(token=user.vk_token, rucaptcha_key=DEV_RUCAPTCHA_KEY, proxy=DEV_PROXY)
            ads_cabinets = vk.get_all_ads_cabinets()

            if ads_cabinets['user_cabinets']:
                for cab in ads_cabinets['user_cabinets']:
                    cabinet = AdsCabinet(owner=user,
                                         cabinet_type='user',
                                         cabinet_name=cab['cabinet_name'],
                                         cabinet_id=cab['cabinet_id'])
                    cabinet.save()

            if ads_cabinets['client_cabinets']:
                for cab in ads_cabinets['client_cabinets']:
                    cabinet = AdsCabinet(owner=user,
                                         cabinet_type='user',
                                         cabinet_name=cab['cabinet_name'],
                                         cabinet_id=cab['cabinet_id'],
                                         client_name=cab['client_name'],
                                         client_id=cab['client_id'])
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
        campaign_settings_serializer = serializers.CampaignSettingsSerializer(data=request.data)
        if campaign_settings_serializer.is_valid():
            start_campaign(request, campaign_settings_serializer.data)
            return Response({'response': 'campaign is starting, it takes some time'})
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
            start_campaign(campaign_settings_serializer.data, request)
            return Response({'response': 'campaign is starting, it takes some time'})
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
