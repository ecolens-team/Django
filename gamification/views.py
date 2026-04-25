from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Quest, UserQuest
from .serializers import QuestSerializer
from users.permissions import IsApprovedResearcher
from rest_framework.permissions import IsAdminUser


class PendingQuestListView(generics.ListAPIView):
    queryset = Quest.objects.filter(status='PENDING')
    serializer_class = QuestSerializer
    permission_classes = [IsAuthenticated]

class ActiveQuestListView(generics.ListAPIView):
    queryset = Quest.objects.filter(status='ACTIVE')
    serializer_class = QuestSerializer
    permission_classes = [IsAuthenticated]

class ProposeQuestView(generics.CreateAPIView):
    queryset = Quest.objects.all()
    serializer_class = QuestSerializer
    permission_classes = [IsApprovedResearcher]

    def perform_create(self, serializer):
        serializer.save(researcher=self.request.user, status='PENDING')

class ApproveQuestView(generics.UpdateAPIView):
    queryset = Quest.objects.all()
    serializer_class = QuestSerializer
    permission_classes = [IsAdminUser]

    def update(self, request, *args, **kwargs):
        quest = self.get_object()
        quest.status = 'ACTIVE'
        quest.save()
        return Response({"message": f"Quest '{quest.title}' is now ACTIVE."})

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