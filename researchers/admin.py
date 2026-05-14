from django.contrib import admin
from users.models import ResearcherProfile, ResearcherSpecialization

admin.site.register(ResearcherSpecialization)
admin.site.register(ResearcherProfile)
