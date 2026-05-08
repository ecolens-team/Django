from rest_framework import serializers
from .models import Badge, Quest, UserQuest
from observations.models import Observation
from observations.serializers import BasicObservationSerializer
from users.serializers import BasicUserSerializer

class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = '__all__'


class QuestSerializer(serializers.ModelSerializer):
    is_joined = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    user_progress = serializers.SerializerMethodField()
    researcher_username = serializers.CharField(source='researcher.username', read_only=True)
    target_species_ids = serializers.PrimaryKeyRelatedField(
        source='target_species',
        many=True,
        read_only=True,
    )
    recent_submissions = serializers.SerializerMethodField()
    leaderboard = serializers.SerializerMethodField()

    class Meta:
        model = Quest
        fields = '__all__'
        read_only_fields = ['researcher', 'status', 'participants']

    def get_is_joined(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.participants.filter(id=request.user.id).exists()
        return False

    def get_participant_count(self, obj):
        return obj.participants.count()

    def get_user_progress(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        try:
            uq = UserQuest.objects.get(user=request.user, quest=obj)
            if obj.target_count:
                return round((uq.observation_count / obj.target_count) * 100)
            return 0
        except UserQuest.DoesNotExist:
            return 0
    
    def get_recent_submissions(self, obj):
        observations = Observation.objects.filter(quest=obj).order_by('-timestamp')[0:6]
        return BasicObservationSerializer(observations, many=True).data
    
    def get_leaderboard(self, obj):
        top_users = UserQuest.objects.filter(quest=obj).order_by('-observation_count')[0:6]
        return UserQuestSerializer(top_users, many=True).data

class UserQuestSerializer(serializers.ModelSerializer):
    user = BasicUserSerializer(read_only=True)

    class Meta:
        model = UserQuest
        fields = '__all__'
        read_only_fields = ['user', 'quest', 'completed', 'date_completed', 'observation_count']
