from django.urls import path, include
from .views import (
    ResearcherOnlyDemoView,
    ResearcherApplicationsListView,
    ReviewResearcherApplicationView,
    UserProfileView,
    FollowToggleView,
    GetUsersView,
    ToggleUserActiveView,
    AdminStatsView,
)

urlpatterns = [
    path("auth/", include("dj_rest_auth.urls")),
    path("auth/registration/", include("dj_rest_auth.registration.urls")),
    path("admin/stats/", AdminStatsView.as_view(), name='admin-stats'),
    path("admin/applications/", ResearcherApplicationsListView.as_view(), name='admin-researcher-applications'),
    path("admin/applications/<int:pk>/review/", ReviewResearcherApplicationView.as_view(), name='admin-researcher-application-review'),
    path('researcher-only/', ResearcherOnlyDemoView.as_view(), name='reseracher-only'),
    path('users/<str:username>/', UserProfileView.as_view(), name='user-profile'),
    path('users/<str:username>/follow/', FollowToggleView.as_view(), name='follow-toggle'),
    path('users/', GetUsersView.as_view(), name='user-list'),
    path('users/<int:user_id>/toggle-active/', ToggleUserActiveView.as_view(), name='toggle-user'),
]
