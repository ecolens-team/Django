from django.urls import path, include
from .views import ObservationsView, ObservationDetailView, VerifyObservationView

urlpatterns = [
    path('', ObservationsView.as_view(), name='observations'),
    path('<int:pk>', ObservationDetailView.as_view(), name='observation-detail'),
    path('<int:pk>/verify/', VerifyObservationView.as_view(), name='observation-verify'),
]