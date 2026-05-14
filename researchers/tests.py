


from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from users.models import ResearcherSpecialization, ResearcherProfile
from observations.models import Observation, ObservationReport, Species
from django.utilfrom django.utils 
import timezones import timezone

User = get_user_model()

class ResearcherAppTests(APITestCase):
    def setUp(self):

        self.researcher = User.objects.create_user(username='botanist_expert', password='password123', role='RESEARCHER')
        ResearcherProfile.objects.create(user=self.researcher, application_status='APPROVED')
        ResearcherSpecialization.objects.create(researcher=self.researcher, level='CLASS', name='PLANTAE')

        
        self.plant_species = Species.objects.create(scientific_name="Iris haynei", type="PLANT")
        self.insect_species = Species.objects.create(scientific_name="Honey Bee", type="INSECT")
        
       
        self.plant_obs = Observation.objects.create(
          user=self.researcher, 
          species=self.plant_species, 
          verified=False,
          timestamp=timezone.now() 
         )      
        self.insect_obs = Observation.objects.create(user=self.researcher, species=self.insect_species, verified=False)

    
    def test_researcher_sees_only_specialized_observations(self):
        self.client.force_authenticate(user=self.researcher)
        url = reverse('researcher-queue')
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
       
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['species_name'], "Iris haynei")

    
    def test_resolve_observation_report(self):
        
        report = ObservationReport.objects.create(observation=self.plant_obs, reporter=self.researcher, note="Wrong ID")
        url = reverse('researcher-resolve-report', kwargs={'pk': report.pk})
        
        self.client.force_authenticate(user=self.researcher)
        response = self.client.patch(url) 
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertTrue(report.resolved)
        self.assertEqual(report.resolved_by, self.researcher)
 

    def test_researcher_stats_logic(self):
        self.client.force_authenticate(user=self.researcher)
        url = reverse('researcher-stats')
        
        response = self.client.get(url)
        
        self.assertEqual(response.data['queue_count'], 1)

   )
    def test_endangered_species_alerts(self):
        
        self.plant_species.is_endangered = True
        self.plant_species.save()
        
        self.client.force_authenticate(user=self.researcher)
        url = reverse('researcher-alerts')
        
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertIn('endangered', response.data[0]['flags'])

   
    def test_export_observations_csv(self):
        self.client.force_authenticate(user=self.researcher)
        url = reverse('researcher-export')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertTrue(response.streaming) 
