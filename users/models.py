from django.contrib.auth.models import AbstractUser
from django.db import models
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFit, Transpose

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
    thumbnail = ImageSpecField(
        source='profile_picture',
        processors=[Transpose(), ResizeToFit(600, 600)],
        format='JPEG',
        options={'quality': 80}
    )

    def save(self, *args, **kwargs):
        if self.role == 'ADMIN':
            self.is_staff = True
        super().save(*args, **kwargs)
    
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

class ResearcherSpecialization(models.Model):
    class TaxonomyLevel(models.TextChoices):
        CLASS = 'CLASS', 'Class'
        ORDER = 'ORDER', 'Order'
        FAMILY = 'FAMILY', 'Family'
        GENUS = 'GENUS', 'Genus'
        SPECIES = 'SPECIES', 'Species'

    researcher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='specializations',
        limit_choices_to={'role': 'RESEARCHER'},
    )
    level = models.CharField(max_length=10, choices=TaxonomyLevel.choices)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('researcher', 'level', 'name')

    def __str__(self):
        return f"{self.researcher.username} — {self.level}: {self.name}"


class Follow(models.Model):
    follower = models.ForeignKey(
        User, related_name='following_set', on_delete=models.CASCADE
    )
    following = models.ForeignKey(
        User, related_name='followers_set', on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower.username} → {self.following.username}"

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, related_name='messages', on_delete=models.CASCADE, null=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username} to {self.receiver.username}: {self.content[:20]}"