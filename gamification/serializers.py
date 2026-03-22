from rest_framework import serializers
from .models import Badge, Quest, UserQuest, UserBadge

class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = '__all__'

class QuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quest
        fields = '__all__'
        read_only_fields = ['researcher', 'status', 'participants']

class UserQuestSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserQuest
        fields = '__all__'
        read_only_fields = ['user', 'quest', 'completed', 'date_completed']