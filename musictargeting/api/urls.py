from django.urls import path

from musictargeting.api import views as api_views

app_name = 'api'

urlpatterns = [
    path('', api_views.api_index_view),

    path('user.create', api_views.UserCreateView.as_view()),
    path('user.get', api_views.UserView.as_view()),                         # extended

    path('cabinets.get', api_views.CabinetListView.as_view()),              # extended
    path('cabinets.update', api_views.CabinetUpdateView.as_view()),

    path('groups.get', api_views.GroupListView.as_view()),

    path('retarget.get', api_views.RetargetListView.as_view()),
    path('retarget.update', api_views.RetargetUpdateView.as_view()),

    path('campaigns.create', api_views.CampaignCreateView.as_view()),
    path('campaigns.get', api_views.CampaignListView.as_view()),            # extended
    path('campaigns.getDetails', api_views.CampaignDetailView.as_view()),
    path('campaigns.updateStats', api_views.CampaignUpdateStatsView.as_view()),
    path('campaigns.startAutomate', api_views.CampaignStartAutomateView.as_view()),
    path('campaigns.stopAutomate', api_views.CampaignStopAutomateView.as_view()),

    path('ads.get', api_views.AdListView.as_view()),
]