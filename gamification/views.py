from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Quest, UserQuest, Badge, UserBadge
from .serializers import QuestSerializer
from users.permissions import IsApprovedResearcher

LEVEL_NAMES = [
    "Seedling", "Observer", "Explorer",
    "Field Expert", "Specialist", "Ecologist", "Ecosystem Guardian",
]

def compute_level(total_pts):
    level = total_pts // 1000 + 1
    return {
        "total_pts": total_pts,
        "level": level,
        "level_name": LEVEL_NAMES[min(level - 1, len(LEVEL_NAMES) - 1)],
        "xp_in_level": total_pts % 1000,
        "xp_per_level": 1000,
    }


class ActiveQuestListView(generics.ListAPIView):
    serializer_class = QuestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Quest.objects.filter(status='ACTIVE').order_by('-id')


class PendingQuestListView(generics.ListAPIView):
    serializer_class = QuestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Quest.objects.filter(status='PENDING').order_by('-id')


class AdminQuestListView(generics.ListAPIView):
    serializer_class = QuestSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = Quest.objects.all().order_by('-id')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        return qs


class QuestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Quest.objects.all()
    serializer_class = QuestSerializer
    permission_classes = [IsAuthenticated]


class ProposeQuestView(generics.CreateAPIView):
    queryset = Quest.objects.all()
    serializer_class = QuestSerializer
    permission_classes = [IsApprovedResearcher]

    def perform_create(self, serializer):
        serializer.save(researcher=self.request.user, status='PENDING')


class ApproveQuestView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        quest = get_object_or_404(Quest, pk=pk)
        quest.status = 'ACTIVE'
        quest.save()
        return Response(QuestSerializer(quest, context={'request': request}).data)


class RejectQuestView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        quest = get_object_or_404(Quest, pk=pk)
        quest.status = 'REJECTED'
        quest.save()
        return Response(QuestSerializer(quest, context={'request': request}).data)


class JoinQuestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id):
        quest = get_object_or_404(Quest, id=quest_id, status='ACTIVE')
        user_quest, created = UserQuest.objects.get_or_create(
            user=request.user,
            quest=quest
        )
        if created:
            return Response({"message": "Successfully joined the quest!"}, status=status.HTTP_201_CREATED)
        return Response({"message": "You have already joined this quest."}, status=status.HTTP_200_OK)


class SubmitObservationToQuestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id):
        from observations.models import Observation

        quest = get_object_or_404(Quest, id=quest_id, status='ACTIVE')

        user_quest = UserQuest.objects.filter(user=request.user, quest=quest).first()
        if not user_quest:
            return Response({"error": "You must join the quest before submitting."}, status=status.HTTP_400_BAD_REQUEST)

        obs_id = request.data.get('observation_id')
        if not obs_id:
            return Response({"error": "observation_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        observation = get_object_or_404(Observation, id=obs_id, user=request.user)


        if not (quest.start_date <= observation.timestamp <= quest.end_date):
            return Response({"error": "Observation was not made during the quest period."}, status=status.HTTP_400_BAD_REQUEST)


        if quest.target_species.exists():
            if observation.species_id not in quest.target_species.values_list('id', flat=True):
                return Response({"error": "Observation species does not match the quest targets."}, status=status.HTTP_400_BAD_REQUEST)


        if quest.geographic_area:
            if observation.latitude is None or observation.longitude is None:
                return Response({"error": "Observation has no GPS coordinates for area validation."}, status=status.HTTP_400_BAD_REQUEST)
            if not _point_in_polygon(observation.latitude, observation.longitude, quest.geographic_area):
                return Response({"error": "Observation is outside the quest's geographic area."}, status=status.HTTP_400_BAD_REQUEST)


        if observation.quest_id == quest.id:
            return Response({"error": "This observation is already assigned to this quest."}, status=status.HTTP_400_BAD_REQUEST)

        observation.quest = quest
        observation.save(update_fields=['quest'])

        user_quest.observation_count += 1
        just_completed = (
            not user_quest.completed and
            user_quest.observation_count >= quest.target_count
        )
        if just_completed:
            user_quest.completed = True
            user_quest.date_completed = timezone.now()
        user_quest.save()

        if just_completed:
            from .badge_utils import check_badges_on_quest_complete
            check_badges_on_quest_complete(request.user, quest)

        return Response({
            "observation_count": user_quest.observation_count,
            "target_count": quest.target_count,
            "completed": user_quest.completed,
        }, status=status.HTTP_200_OK)


def _point_in_polygon(lat, lng, geojson_polygon):
    """Ray casting algorithm checks if (lat, lng) is inside a GeoJSON Polygon."""
    try:
        coords = geojson_polygon['coordinates'][0] 
    except (KeyError, IndexError, TypeError):
        return True  

    x, y = lng, lat  
    n = len(coords)
    inside = False
    px, py = coords[0]
    for i in range(1, n + 1):
        cx, cy = coords[i % n]
        if min(py, cy) < y <= max(py, cy) and x <= max(px, cx):
            if py != cy:
                x_intersect = (y - py) * (cx - px) / (cy - py) + px
            if px == cx or x <= x_intersect:
                inside = not inside
        px, py = cx, cy
    return inside


class MyQuestsView(generics.ListAPIView):
    serializer_class = QuestSerializer
    permission_classes = [IsApprovedResearcher]

    def get_queryset(self):
        qs = Quest.objects.filter(researcher=self.request.user)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        return qs.order_by('-id')


class GamificationProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        total_pts = sum(
            uq.quest.reward_pts
            for uq in UserQuest.objects.filter(user=user, completed=True).select_related('quest')
        )

        earned_ids = set(
            UserBadge.objects.filter(user=user).values_list('badge_id', flat=True)
        )
        all_badges = Badge.objects.all()

        def badge_data(b):
            return {
                "id": b.id,
                "name": b.name,
                "description": b.description,
                "icon": request.build_absolute_uri(b.icon.url) if b.icon else None,
                "criteria_type": b.criteria_type,
                "criteria_value": b.criteria_value,
                "earned": b.id in earned_ids,
            }

        return Response({
            **compute_level(total_pts),
            "badges": [badge_data(b) for b in all_badges],
        })
