from django.urls import path
from .views import ObservationsView, ObservationDetailView, VerifyObservationView, LikeObservationView, CommentListCreateView

urlpatterns = [
    path('', ObservationsView.as_view(), name='observations'),
    path('<int:pk>', ObservationDetailView.as_view(), name='observation-detail'),
    path('<int:pk>/verify/', VerifyObservationView.as_view(), name='observation-verify'),
    path('<int:pk>/like/', LikeObservationView.as_view(), name='observation-like'),
    path('<int:pk>/comments/', CommentListCreateView.as_view(), name='observation-comments'),
]