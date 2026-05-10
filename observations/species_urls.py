from django.urls import path
from .views import (
    SpeciesListView,
    SpeciesDetailView,
    SpeciesUpdateView,
    PredictSpeciesView,
    TaxaOptionsView,
)

urlpatterns = [
    path('', SpeciesListView.as_view(), name='species'),
    path('taxonomy-options/', TaxaOptionsView.as_view(), name='taxa-options'),
    path('predict/', PredictSpeciesView.as_view(), name='predict'),
    path('<int:pk>', SpeciesDetailView.as_view(), name='species-detail'),
    path('<int:pk>/update/', SpeciesUpdateView.as_view(), name='species-update'),
]
