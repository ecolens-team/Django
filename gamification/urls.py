from django.urls import path
from .views import (
    ActiveQuestListView, PendingQuestListView, AdminQuestListView,
    QuestDetailView, ProposeQuestView,
    ApproveQuestView, RejectQuestView,
    JoinQuestView, SubmitObservationToQuestView,
    MyQuestsView, GamificationProfileView,
)

urlpatterns = [
    path('profile/', GamificationProfileView.as_view(), name='gamification-profile'),
    path('', ActiveQuestListView.as_view(), name='quests'),
    path('pending/', PendingQuestListView.as_view(), name='quests-pending'),
    path('admin/', AdminQuestListView.as_view(), name='quests-admin'),
    path('mine/', MyQuestsView.as_view(), name='my-quests'),
    path('new/', ProposeQuestView.as_view(), name='new-quest'),
    path('<int:pk>/', QuestDetailView.as_view(), name='quest-detail'),
    path('<int:quest_id>/join/', JoinQuestView.as_view(), name='join-quest'),
    path('<int:quest_id>/submit/', SubmitObservationToQuestView.as_view(), name='submit-observation'),
    path('<int:pk>/approve/', ApproveQuestView.as_view(), name='approve-quest'),
    path('<int:pk>/reject/', RejectQuestView.as_view(), name='reject-quest'),
]
