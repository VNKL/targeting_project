from django.urls import path

from . import views as api_views

app_name = 'api'

urlpatterns = [
    path('', api_views.api_index_view),
    path('user/', api_views.UserView.as_view()),
    path('ads_cabinets/', api_views.AdsCabinetListView.as_view()),
    path('campaigns/', api_views.CampaignListView.as_view()),
    path('ads/', api_views.AdListView.as_view()),
]