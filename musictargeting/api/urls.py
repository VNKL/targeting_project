from django.urls import path

from . import views as api_views

app_name = 'api'

urlpatterns = [
    path('', api_views.api_index_view),
    path('user/', api_views.UserView.as_view()),
    path('groups/', api_views.GroupListView.as_view()),
    path('cabinets/', api_views.CabinetListView.as_view()),
    path('retarget/', api_views.RetargetListView.as_view()),
    path('campaigns/', api_views.CampaignListView.as_view()),
    path('campaigns/<int:campaign_vk_id>/', api_views.CampaignDetailView.as_view()),
    path('ads/', api_views.AdListView.as_view()),
]
