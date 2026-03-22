from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

class Species(models.Model):
    class SpeciesType(models.TextChoices):
        PLANT = 'PLANT', 'Plant'
        INSECT = 'INSECT', 'Insect'

    scientific_name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    type = models.CharField(max_length=10, choices=SpeciesType.choices)
    common_name_en = models.CharField(max_length=255, blank=True, default="")
    common_name_ar = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return self.scientific_name


class Observation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='observations')
    species = models.ForeignKey(Species, on_delete=models.SET_NULL, null=True, blank=True, related_name='observations')
    timestamp = models.DateTimeField(auto_now_add=True)
    longitude = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    confidence_level = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Observation {self.id} by {self.user.username}"


class Image(models.Model):
    observation = models.ForeignKey(Observation, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='observations/')
    image_quality = models.IntegerField(null=True, blank=True)
    date = models.DateTimeField()

    def __str__(self):
        return f"Image for Observation {self.observation_id}"