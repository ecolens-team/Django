from django.urls import path, include
from .views import ResearcherOnlyDemoView, ResearcherApplicationsListView, ReviewResearcherApplicationView


urlpatterns = [
    path("auth/", include("dj_rest_auth.urls")),
    path("auth/registration/", include("dj_rest_auth.registration.urls")),
    path("admin/applications/", ResearcherApplicationsListView.as_view(), name='admin-researcher-applications'),
    path("admin/applications/<int:pk>/review", ReviewResearcherApplicationView.as_view(), name='admin-researcher-application-review'),
    path('researcher-only/', ResearcherOnlyDemoView.as_view(), name='reseracher-only')
]