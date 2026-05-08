from django.db import models
from django.conf import settings
from django.utils import timezone

class Badge(models.Model):
    class CriteriaType(models.TextChoices):
        OBSERVATION_COUNT = 'OBSERVATION_COUNT', 'Observation Count'
        QUEST_COUNT       = 'QUEST_COUNT',       'Quests Completed'
        FIRST_SPECIES     = 'FIRST_SPECIES',     'First Species Discovery'

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    icon = models.ImageField(upload_to='badges/', null=True, blank=True)

    criteria_type = models.CharField(
        max_length=30, choices=CriteriaType.choices, null=True, blank=True
    )
    criteria_value = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.name

class Quest(models.Model):
    class QuestStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed/Expired'
        REJECTED = 'REJECTED', 'Rejected'

    class QuestCategory(models.TextChoices):
        PLANT = 'PLANT', 'Plant'
        INSECT = 'INSECT', 'Insect'
        GENERAL = 'GENERAL', 'General'

    researcher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proposed_quests')
    title = models.CharField(max_length=255)
    description = models.TextField()
    rules = models.TextField(blank=True, default='')
    category = models.CharField(max_length=20, choices=QuestCategory.choices, default=QuestCategory.GENERAL)
    reward_pts = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='quests/', null=True, blank=True)
    target_count = models.PositiveIntegerField(default=1)
    geographic_area = models.JSONField(null=True, blank=True)
    target_species = models.ManyToManyField('observations.Species', blank=True, related_name='quests')
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
    observation_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'quest')

class UserBadge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earned_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    date_received = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'badge')