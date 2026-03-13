from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .permissions import IsApprovedResearcher
from rest_framework import permissions
from .models import ResearcherProfile
from .serializers import ResearcherApplicationSerializer
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
