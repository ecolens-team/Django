from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import Follow, ResearcherProfile

User = get_user_model()

class UserManagementTests(APITestCase):
    def setUp(self):
        
        self.admin_user = User.objects.create_superuser(username='admin_solaf', password='password123')
        self.normal_user = User.objects.create_user(username='regular_user', password='password123')
        self.target_user = User.objects.create_user(username='jordan_nature', password='password123')
        
       
        self.follow_url = reverse('follow-toggle', kwargs={'username': self.target_user.username})

    
    def test_follow_toggle_logic(self):
        self.client.force_authenticate(user=self.normal_user)
        
        
        response = self.client.post(self.follow_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Follow.objects.filter(follower=self.normal_user, following=self.target_user).exists())
        
        
        response = self.client.post(self.follow_url)
        self.assertEqual(response.data['following'], False)
        self.assertFalse(Follow.objects.filter(follower=self.normal_user, following=self.target_user).exists())

    
    def test_admin_can_toggle_user_active_status(self):
        url = reverse('toggle-user', kwargs={'user_id': self.target_user.id})
        self.client.force_authenticate(user=self.admin_user)
        
        # تجميد الحساب
        response = self.client.post(url)
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)
        self.assertEqual(response.data['is_active'], False)

    
    def test_regular_user_cannot_freeze_accounts(self):
        url = reverse('toggle-user', kwargs={'user_id': self.admin_user.id})
        self.client.force_authenticate(user=self.normal_user)
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)

    
    def test_admin_role_auto_staff_status(self):
        
        new_admin = User.objects.create_user(username='new_admin', password='password123', role='ADMIN')
        self.assertTrue(new_admin.is_staff)
        self.assertEqual(new_admin.get_role_display(), 'Admin')

    
    def test_researcher_profile_creation_and_status(self):
       
        researcher_user = User.objects.create_user(username='researcher_1', password='password123', role='RESEARCHER')
        profile = ResearcherProfile.objects.create(
            user=researcher_user, 
            institute="JUST University", 
            application_status='PENDING'
        )
        
        
        url = reverse('researcher-only') 
        self.client.force_authenticate(user=researcher_user)
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        profile.application_status = 'APPROVED'
        profile.save()
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
# Create your tests here.
