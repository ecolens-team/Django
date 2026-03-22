from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from observations.views import SpeciesDetailView, SpeciesListView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")), 
    path("api/observations/", include("observations.urls")),
    path("api/species/", SpeciesListView.as_view(), name="species"),
    path("api/quests/", include("gamification.urls")),
    path("api/species/<int:pk>", SpeciesDetailView.as_view(), name="species-detail"),
    path("accounts/", include("allauth.urls")),
    path(
        'reset-password/<uidb64>/<token>/', 
        TemplateView.as_view(), 
        name='password_reset_confirm'
    ),
]