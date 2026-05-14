from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from .models import Observation, Species, Like
from django.contrib.auth import get_user_model

User = get_user_model()

class CoreObservationTests(APITestCase):
    def setUp(self):

        self.user = User.objects.create_user(username='solaf_user', password='password123')
        

        self.researcher = User.objects.create_user(
            username='expert_just', 
            password='password123', 
            role='RESEARCHER'
        )
        self.species = Species.objects.create(scientific_name="Iris haynei", type="PLANT")
        
       
        self.mock_image = SimpleUploadedFile(
            name='test.jpg',
            content=b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x03\x02\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
            content_type='image/jpeg'
        )

    
    def test_successful_observation_upload(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('observations')
        data = {
            'description': 'Beautiful plant near JUST university',
            'governorate': 'Irbid',
            'species_prediction': 'Iris haynei',
            'confidence_level': 0.90,
            'images': self.mock_image
        }
        response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Observation.objects.filter(user=self.user).count(), 1)

    
    def test_regular_user_cannot_verify(self):
        obs = Observation.objects.create(user=self.user, timestamp=timezone.now())
        self.client.force_authenticate(user=self.user)
        url = reverse('observation-verify', kwargs={'pk': obs.pk})
        
        response = self.client.patch(url, {'species_id': self.species.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        obs.refresh_from_db()
        self.assertFalse(obs.verified)

    
    def test_approved_researcher_can_verify(self):
        obs = Observation.objects.create(user=self.user, timestamp=timezone.now())
        self.client.force_authenticate(user=self.researcher)
        url = reverse('observation-verify', kwargs={'pk': obs.pk})
        
        response = self.client.put(url, {'species_id': self.species.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        obs.refresh_from_db()
        self.assertTrue(obs.verified)
        self.assertEqual(obs.species, self.species)

    
    def test_observation_like_functionality(self):
        obs = Observation.objects.create(user=self.user, timestamp=timezone.now())
        self.client.force_authenticate(user=self.user)
        url = reverse('observation-like', kwargs={'pk': obs.pk})
        
        
        res1 = self.client.post(url)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Like.objects.count(), 1)
        
        
        res2 = self.client.post(url)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(Like.objects.count(), 0)

    
    def test_filter_observations_by_governorate(self):
        Observation.objects.create(user=self.user, governorate='Irbid', timestamp=timezone.now())
        Observation.objects.create(user=self.user, governorate='Amman', timestamp=timezone.now())
        
        self.client.force_authenticate(user=self.user)
        url = reverse('observations')
        
        response = self.client.get(url, {'governorate': 'Irbid'})
       
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['governorate'], 'Irbid')