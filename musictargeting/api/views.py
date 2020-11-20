from django.http import HttpResponse
from rest_framework import viewsets, views, status
from rest_framework import permissions
from django.shortcuts import get_object_or_404, get_list_or_404
from rest_framework.response import Response

from .models import User, AdsCabinet, Campaign, Ad
from .serializers import UserSerializer, AdsCabinetSerializer, CampaignSerializer, AdSerializer, \
    CampaignSettingsSerializer


def start_campaign(campaign_settings, request):
    # TODO  Допилить код запуска и сохранения кампании в отдельном процессе
    started_campaign = {}   # Вот сюда что-то должно вернуть все параметры запущенной кампании
    campaign_serializer = CampaignSerializer(data=started_campaign)
    if campaign_serializer.is_valid():
        campaign_serializer.save()
    # TODO После сохранения кампании нужно насохранять объявлений


def api_index_view(response):
    return HttpResponse('This is api root page. Use method names after "api/"')


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-pk')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]


class AdsCabinetViewSet(viewsets.ModelViewSet):
    queryset = AdsCabinet.objects.all().order_by('-pk')
    serializer_class = AdsCabinetSerializer
    permission_classes = [permissions.IsAdminUser]


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by('-create_datetime')
    serializer_class = CampaignSerializer
    permission_classes = [permissions.IsAdminUser]


class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all().order_by('ad_name')
    serializer_class = AdSerializer
    permission_classes = [permissions.IsAdminUser]


class UserView(views.APIView):

    def get(self, request):
        user = get_object_or_404(User, username=request.user.username)
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdsCabinetListView(views.APIView):

    def get(self, request):
        ads_cabinets = get_list_or_404(AdsCabinet, owner=request.user)
        serializer = AdsCabinetSerializer(ads_cabinets, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AdsCabinetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignListView(views.APIView):

    def get(self, requset):
        campaign = get_list_or_404(Campaign, owner=requset.user)
        serializer = CampaignSerializer(campaign, many=True)
        return Response(serializer.data)

    def post(self, request):
        campaign_settings_serializer = CampaignSettingsSerializer(data=request.data)
        if campaign_settings_serializer.is_valid():
            start_campaign(campaign_settings_serializer.data, request)
            return Response({'response': 'campaign is starting, it takes some time'})
        else:
            return Response(campaign_settings_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdListView(views.APIView):

    def get(self, request):
        if 'campaign_id' not in dict(request.query_params).keys():
            return Response({'detail': 'campaign_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            campaign_id = int(request.query_params.get('campaign_id'))
        except ValueError:
            return Response({'detail': 'campaign_id must be int'}, status=status.HTTP_400_BAD_REQUEST)

        ads = get_list_or_404(Ad, campaign_id=campaign_id)
        serializer = AdSerializer(ads, many=True)
        return Response(serializer.data)
