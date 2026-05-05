from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .permissions import IsApprovedResearcher
from rest_framework import permissions, status
from .models import Follow, ResearcherProfile, ResearcherSpecialization, User, Conversation, Message
from .serializers import CustomUserDetailsSerializer, ResearcherApplicationSerializer, UserProfileSerializer, ConversationSerializer, MessageSerializer
from django.core.mail import send_mail
from rest_framework.pagination import PageNumberPagination
from observations.models import Observation, Species
from gamification.models import Quest
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import AccessToken
from django.db.models import Count

class WsTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = AccessToken.for_user(request.user)
        return Response({"token": str(token)})

class ResearcherOnlyDemoView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedResearcher]

    def get(self, request):
        return Response({"detail": "Access granted to approved researcher endpoint."})


class ReviewResearcherApplicationView(UpdateAPIView):
    queryset = ResearcherProfile.objects.all().select_related('user')
    serializer_class = ResearcherApplicationSerializer
    permission_classes =[permissions.IsAdminUser]

    def perform_update(self, serializer):
        saved_instance = serializer.save()

        updated_status = saved_instance.application_status
        user_email = saved_instance.user.email

        send_mail(
            subject='Your Researcher Application Update',
            message=f"Hello {saved_instance.user.first_name}\n Your Researcher Application status has been updated to: {updated_status}",
            from_email=None,
            recipient_list=[user_email]
        )


class ResearcherApplicationsListView(ListAPIView):
    serializer_class = ResearcherApplicationSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = ResearcherProfile.objects.all().select_related('user')
        status_query = self.request.query_params.get('status')

        if status_query:
            queryset = queryset.filter(application_status=status_query)
        else:
            queryset = queryset.filter(application_status="PENDING")
        
        return queryset

class UserProfileView(RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = 'username'
    queryset = User.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class FollowToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, username):
        try:
            target_user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if target_user == request.user:
            return Response({'error': 'Cannot follow yourself'}, status=status.HTTP_400_BAD_REQUEST)

        follow, created = Follow.objects.get_or_create(
            follower=request.user,
            following=target_user
        )

        if not created:
            follow.delete()
            return Response({'following': False})

        return Response({'following': True})


class UsersPaginationClass(PageNumberPagination):
    page_size = 10
    max_page_size = 100

class UserFilter(filters.FilterSet):
    role = filters.CharFilter(field_name='role', lookup_expr='iexact')
    username = filters.CharFilter(field_name='username', lookup_expr='icontains')
    email = filters.CharFilter(field_name='email', lookup_expr='icontains')
    id = filters.NumberFilter(field_name='pk', lookup_expr='iexact')

    class Meta:
        model = User
        fields = ['role', 'username', 'email', 'id']

class GetUsersView(ListAPIView):
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all()
    serializer_class = CustomUserDetailsSerializer
    pagination_class = UsersPaginationClass
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserFilter

class AdminStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        total_species = Species.objects.count()
        species_with_obs = Species.objects.filter(observations__isnull=False).distinct().count()

        return Response({
            "researchers": {
                "approved": ResearcherProfile.objects.filter(application_status="APPROVED").count(),
                "pending": ResearcherProfile.objects.filter(application_status="PENDING").count(),
            },
            "quests": {
                "total": Quest.objects.count(),
                "pending": Quest.objects.filter(status="PENDING").count(),
                "active": Quest.objects.filter(status="ACTIVE").count(),
                "completed": Quest.objects.filter(status="COMPLETED").count(),
            },
            "users": {
                "total": User.objects.count(),
            },
            "observations": {
                "total": Observation.objects.count(),
            },
            "species": {
                "total": total_species,
                "with_observations": species_with_obs,
                "without_observations": total_species - species_with_obs,
            },
        })


class ToggleUserActiveView(APIView):
    permission_classes = [permissions.IsAdminUser]
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        user.is_active = not user.is_active
        user.save()

        state = 'active' if user.is_active else 'banned'
        message = f'user with id: {user_id} is now {state}'
        return Response({
            'message': message,
            'is_active': user.is_active
        }, status=status.HTTP_200_OK)


VALID_LEVELS = {c[0] for c in ResearcherSpecialization.TaxonomyLevel.choices}

class ResearcherSpecializationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        specs = ResearcherSpecialization.objects.filter(researcher=request.user)
        data = [{"id": s.pk, "level": s.level, "name": s.name} for s in specs]
        return Response(data)

    def put(self, request):
        """Replace all specializations for the current user with the submitted list."""
        items = request.data if isinstance(request.data, list) else request.data.get('specializations', [])
        errors = []
        for item in items:
            if item.get('level') not in VALID_LEVELS:
                errors.append(f"Invalid level: {item.get('level')}")
            if not item.get('name', '').strip():
                errors.append("Each specialization must have a non-empty name.")
        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        ResearcherSpecialization.objects.filter(researcher=request.user).delete()
        created = [
            ResearcherSpecialization(researcher=request.user, level=item['level'], name=item['name'].strip())
            for item in items
        ]
        ResearcherSpecialization.objects.bulk_create(created, ignore_conflicts=True)
        data = [{"id": s.pk, "level": s.level, "name": s.name}
                for s in ResearcherSpecialization.objects.filter(researcher=request.user)]
        return Response(data, status=status.HTTP_200_OK)

class MyConversationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        my_conversations = Conversation.objects.filter(participants=request.user)
        serializer = ConversationSerializer(my_conversations, many=True, context={'request':request})

        return Response(serializer.data)
    
    def post(self, request):
        other_id = request.data.get('user_id')
        other_user = get_object_or_404(User, id=other_id)

        candidates = Conversation.objects.filter(
            participants=request.user
        ).filter(participants=other_user)

        existing_convo = next(
            (c for c in candidates if c.participants.count() == 2), None
        )

        if existing_convo:
            return Response(ConversationSerializer(existing_convo, context={'request': request}).data)

        new_convo = Conversation.objects.create()
        new_convo.participants.add(request.user, other_user)
        return Response(
            ConversationSerializer(new_convo, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ConversationMessages(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageSerializer

    def get_queryset(self):
        convo_id=self.kwargs.get('id')

        get_object_or_404(
            Conversation,
            id=convo_id, 
            participants=self.request.user
        )
        
        messages = Message.objects.filter(conversation_id=convo_id).order_by('timestamp')
        return messages
