from django.db import models
from django.conf import settings
from django.utils import timezone

class Badge(models.Model):
    name = models.CharField(max_length=255)
    criteria = models.TextField()
    icon = models.ImageField(upload_to='badges/') 

    def __str__(self):
        return self.name

class Quest(models.Model):
    class QuestStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed/Expired'

    researcher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proposed_quests')
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=QuestStatus.choices, default=QuestStatus.PENDING)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, through='UserQuest', related_name='quests')

    def __str__(self):
        return f"{self.title} ({self.status})"


class UserQuest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    quest = models.ForeignKey(Quest, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    date_completed = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'quest')

class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earned_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    date_received = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'badge')