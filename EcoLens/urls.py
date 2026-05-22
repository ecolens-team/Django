from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([AllowAny])
def cicd_demo(request):
    return Response({"message": "This is an example feature added to test the CI/CD piplines"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")),
    path("api/cicd-demo/", cicd_demo),
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