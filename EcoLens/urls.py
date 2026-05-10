from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")),
    path("api/observations/", include("observations.urls")),
    path("api/species/", include("observations.species_urls")),
    path("api/quests/", include("gamification.urls")),
    path("api/researcher/", include("researchers.urls")),
    path("accounts/", include("allauth.urls")),
    path(
        'reset-password/<uidb64>/<token>/',
        TemplateView.as_view(),
        name='password_reset_confirm'
    ),
]