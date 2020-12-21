"""tutorial URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework import routers
from musictargeting.api import views as api_views


api_router = routers.DefaultRouter()
api_router.register(r'users', api_views.UserViewSet, basename='user')
api_router.register(r'ads_cabinets', api_views.CabinetViewSet, basename='adscabinet')
api_router.register(r'campaigns', api_views.CampaignViewSet, basename='campaign')
api_router.register(r'ads', api_views.AdViewSet, basename='ad')


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('musictargeting.api.urls')),
    path('api-admin/', include((api_router.urls, 'api-admin'), namespace='api-admin')),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

]
