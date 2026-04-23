from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from observations.views import PredictSpeciesView, SpeciesDetailView, SpeciesListView, SpeciesUpdateView, TaxaOptionsView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")), 
    path("api/observations/", include("observations.urls")),
    path("api/species/", SpeciesListView.as_view(), name="species"),
    path("api/species/taxonomy-options/", TaxaOptionsView.as_view(), name="taxa-options"),
    path("api/species/predict/", PredictSpeciesView.as_view(), name="predict"),
    path("api/quests/", include("gamification.urls")),
    path("api/species/<int:pk>", SpeciesDetailView.as_view(), name="species-detail"),
    path("api/species/<int:pk>/update/", SpeciesUpdateView.as_view(), name="species-update"),
    path("accounts/", include("allauth.urls")),
    path(
        'reset-password/<uidb64>/<token>/', 
        TemplateView.as_view(), 
        name='password_reset_confirm'
    ),
]