from django.urls import path
from .views import JoinQuestView, ActiveQuestListView, ProposeQuestView, ApproveQuestView, PendingQuestListView, MyQuestsView, QuestDetailView

urlpatterns = [
    path('', ActiveQuestListView.as_view(), name='quests'),
    path('<int:pk>/', QuestDetailView.as_view(), name='quest-detail'),
    path('mine/', MyQuestsView.as_view(), name='my-quests'),
    path('pending/', PendingQuestListView.as_view(), name='quests-pending'),
    path('<int:quest_id>/join/', JoinQuestView.as_view(), name='join-quest'),
    path('<int:pk>/approve/', ApproveQuestView.as_view(), name='approve-quest'),
    path('new/', ProposeQuestView.as_view(), name='new-quest'),
]