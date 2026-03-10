from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('USER', 'Normal User'),
        ('RESEARCHER', 'Researcher'),
        ('ADMIN', 'Admin')
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    bio = models.TextField(blank=True, default='')
    phone_number = models.CharField(max_length=20, null=True)
    profile_picture = models.ImageField(blank=True, null=True, upload_to='profiles/')

    def __str__(self):
        return f"{self.username} - {self.role}"
    


class ResearcherProfile(models.Model):
    user = models.OneToOneField(
        User,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name='researcher_profile'
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending Review'), 
        ('REJECTED', 'Application Rejected'), 
        ('APPROVED', 'Approved Researcher')
    )

    application_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    institute = models.CharField(max_length=255)
    credentials = models.FileField(upload_to='researcher_credentials/')

    def __str__(self):
        return f"Researcher Profile: {self.user.username} ({self.institute})"