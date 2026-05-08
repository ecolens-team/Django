from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit, Transpose

class Species(models.Model):
    class SpeciesType(models.TextChoices):
        PLANT = 'PLANT', 'Plant'
        INSECT = 'INSECT', 'Insect'

    scientific_name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    description_is_verified = models.BooleanField(default=False)
    type = models.CharField(max_length=10, choices=SpeciesType.choices)
    common_name_en = models.CharField(max_length=255, blank=True, default="")
    common_name_ar = models.CharField(max_length=255, blank=True, default="")
    is_endemic = models.BooleanField(default=False)
    is_endangered = models.BooleanField(default=False)
    is_invasive = models.BooleanField(default=False)
    genus = models.CharField(max_length=100, blank=True, default="")
    family = models.CharField(max_length=100, blank=True, default="")
    order = models.CharField(max_length=100, blank=True, default="")

    @property
    def best_image_url(self):
        """
        Dynamically grabs the image from the most confident observation.
        If a new observation this automatically updates.
        """
        best_obs = self.observations.filter(images__isnull=False).order_by('-confidence_level').first()
        if best_obs:
            best_image = best_obs.images.first()
            return best_image.image.url if best_image else None
        return None
    def __str__(self):
        return self.scientific_name


class Observation(models.Model):
    WEATHER_CHOICES = [
        ('Sunny', 'Clear/Sunny'),
        ('Partially Cloudy', 'Partially Cloudy'),
        ('Cloudy', 'Cloudy/Overcast'),
        ('Foggy', 'Fog/Mist'),
        
        ('Rainy', 'Rain'),
        ('Snowy', 'Snow'),
        ('Stormy', 'Thunderstorm'),
        
        ('Hazy', 'Haze/Smoke/Dust'),
    ]

    GOV_CHOICES = [
        ('Ajloun', 'Ajloun'), ('Amman', 'Amman'), ('Aqaba', 'Aqaba'),
        ('Balqa', 'Balqa'), ('Irbid', 'Irbid'), ('Jerash', 'Jerash'),
        ('Karak', 'Karak'), ('Maan', 'Maan'), ('Madaba', 'Madaba'),
        ('Mafraq', 'Mafraq'), ('Tafilah', 'Tafilah'), ('Zarqa', 'Zarqa')
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='observations')
    species = models.ForeignKey(Species, on_delete=models.SET_NULL, null=True, blank=True, related_name='observations')
    quest = models.ForeignKey('gamification.Quest', on_delete=models.SET_NULL, null=True, blank=True, related_name='observations')
    timestamp = models.DateTimeField()
    longitude = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    governorate = models.CharField(max_length=50, choices=GOV_CHOICES, blank=True, null=True)
    weather = models.CharField(max_length=50, choices=WEATHER_CHOICES, blank=True, null=True)
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
    thumbnail = ImageSpecField(
        source='image',
        processors=[Transpose(), ResizeToFit(1080, 1080)],
        format='JPEG',
        options={'quality': 80}
    )

    def __str__(self):
        return f"Image for Observation {self.observation_id}"
    

class Comment(models.Model):
    observation = models.ForeignKey(Observation, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="observation_comments")
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.observation.id}"

class Like(models.Model):
    observation = models.ForeignKey(Observation, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="observation_likes")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("observation", "user")

    def __str__(self):
        return f"Like by {self.user.username} on {self.observation.id}"


class ObservationReport(models.Model):
    observation = models.ForeignKey(Observation, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submitted_reports")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="resolved_reports"
    )

    class Meta:
        unique_together = ("observation", "reporter")

    def __str__(self):
        return f"Report by {self.reporter.username} on observation {self.observation_id}"
