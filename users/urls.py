from django.urls import path, include
from .views import WsTokenView
from django.urls import re_path
from . import consumers
from .views import NotificationListView, MarkNotificationReadView

from .views import (
    ResearcherOnlyDemoView,
    ResearcherApplicationsListView,
    ReviewResearcherApplicationView,
    UserProfileView,
    FollowToggleView,
    GetUsersView,
    ToggleUserActiveView,
    AdminStatsView,
    ResearcherSpecializationsView,
    ObservationsOverTimeView,
    MyConversationsView,
    ConversationMessages,
)

urlpatterns = [
    path('ws-token/', WsTokenView.as_view(), name='ws-token'),
    path("auth/", include("dj_rest_auth.urls")),
    path("auth/registration/", include("dj_rest_auth.registration.urls")),
    path("admin/stats/", AdminStatsView.as_view(), name='admin-stats'),
    path("admin/stats/observations-over-time/", ObservationsOverTimeView.as_view(), name='admin-observations-over-time'),
    path("admin/applications/", ResearcherApplicationsListView.as_view(), name='admin-researcher-applications'),
    path("admin/applications/<int:pk>/review/", ReviewResearcherApplicationView.as_view(), name='admin-researcher-application-review'),
    path('researcher-only/', ResearcherOnlyDemoView.as_view(), name='reseracher-only'),
    path('users/<str:username>/', UserProfileView.as_view(), name='user-profile'),
    path('users/<str:username>/follow/', FollowToggleView.as_view(), name='follow-toggle'),
    path('users/', GetUsersView.as_view(), name='user-list'),
    path('users/<int:user_id>/toggle-active/', ToggleUserActiveView.as_view(), name='toggle-user'),
    path('me/specializations/', ResearcherSpecializationsView.as_view(), name='my-specializations'),
    path('conversations/', MyConversationsView.as_view(), name='my_conversations'),
    path('conversations/<int:id>/messages/', ConversationMessages.as_view(), name='conversation'),
]


websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]

urlpatterns += [
    path('notifications/', NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', MarkNotificationReadView.as_view(), name='notif-read'),
    path('notifications/read-all/', MarkNotificationReadView.as_view(), name='notif-read-all'),
]