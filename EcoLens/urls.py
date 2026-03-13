from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")), 
    path("accounts/", include("allauth.urls")),
    path(
        'reset-password/<uidb64>/<token>/', 
        TemplateView.as_view(), 
        name='password_reset_confirm'
    ),
]