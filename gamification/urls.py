from django.urls import path, include
from .views import JoinQuestView, ActiveQuestListView, ProposeQuestView, ApproveQuestView

urlpatterns = [
    path('', ActiveQuestListView.as_view(), name='quests'),
    path('<int:quest_id>/join/', JoinQuestView.as_view(), name='join-quest'),
    path('<int:pk>/approve/', ApproveQuestView.as_view(), name='approve-quest'),
    path('new/', ProposeQuestView.as_view(), name='new-quest'),
]