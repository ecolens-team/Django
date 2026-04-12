import json
import os
from django.core.management.base import BaseCommand
from observations.models import Species

class Command(BaseCommand):
    help = 'Seeds the database with species summaries from JSON'

    def handle(self, *args, **kwargs):
        json_path = os.path.join(os.path.dirname(__file__), '../../species_summaries.json')
        
        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f"File not found: {json_path}"))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.stdout.write("Seeding species...")
        created_count = 0

        for item in data:
            clean_name = item['scientific_name'].replace('_', ' ')

            obj, created = Species.objects.get_or_create(
                scientific_name=clean_name,
                defaults={
                    'description': item.get('summary', ''),
                    # todo update logic here
                    'type': Species.SpeciesType.PLANT 
                }
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully added {created_count} new species."))