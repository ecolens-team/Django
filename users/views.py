from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .permissions import IsApprovedResearcher
from rest_framework import permissions, status
from .models import Follow, ResearcherProfile, User
from .serializers import ResearcherApplicationSerializer, UserProfileSerializer
from django.core.mail import send_mail

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